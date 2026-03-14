# código produzido por Wellington de Araújo Pereira (wde4363) (welltech) em 13/03/2026
# www.wtechsp.com.br
# destinado a conversão de nand de xbox 360 (RETAIL ou RGH2) para o atual RGH3 
# RGH3 Flasher v.1.0 

import customtkinter as ctk
import os
import subprocess
import threading
import filecmp
import shutil
import re
import pygame
import serial
import serial.tools.list_ports
import time
import hashlib
import hmac
from Crypto.Cipher import ARC4
from tkinter import filedialog, messagebox
from PIL import Image
import webbrowser
import sys
from PIL import Image, ImageTk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class RGH3Studio(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RGH3 Flasher v.1.0 - wde4363")
        self.geometry("950x750")
        self.pico_conectado_anteriormente = False
        
        pygame.mixer.init()

        self.caminho_nand_atual = ""
        self.mapa_ecc = {
            "Trinity": "RGH3_Trinity.bin",
            "Corona 16MB": "RGH3_Corona.bin",
            "Corona 16MB WB": "RGH3_Corona_WB2K.ecc",
            "Corona 4GB": "RGH3_Corona_4G.bin",
            "Corona 4GB WB": "RGH3_Corona_4G_WB2K.ecc",
            "Jasper": "RGH3_Jasper_27mhz.bin",
            "Jasper BB": "RGH3_Jasper_27mhz.bin",
            "Falcon": "RGH3_Falcon_27mhz.bin"
        }

        self.cfg_temp_cpu = "65"
        self.cfg_temp_gpu = "63"
        self.cfg_temp_edram = "59"
        self.cfg_nofcrt = False
        self.cfg_usbdsec = True
        self.cfg_nointmu = False
        self.cfg_nohdmiwait = False
        self.cfg_nowifi = False
        self.cfg_nolan = False
        self.cfg_nohdd = False
        self.cfg_xl_both = False
        self.cfg_dvdkey = ""
        self.dvd_original = ""
        self.kv_region = ""
        self.kv_osig = ""
        self.kv_serial = ""
        self.ultima_chave_kv = ""
        self.janela_opcoes = None
        self.uart_thread = None
        self.uart_stop_event = threading.Event()
        self.vcmd_hex = (self.register(self._validar_entrada_hex), '%P')
        self._carregar_recursos()
        self._criar_pastas_base()
        self._construir_interface()
        self._iniciar_monitores()
        self.after(500, self._auditoria_de_arquivos)
        self.atualizar_tela_patches()


    def _obter_caminho_base(self):
        """Descobre o caminho base real para o .exe ou .py"""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def abrir_diagrama_instalacao(self):
        placa = self.combo_placa.get()
        if not placa:
            messagebox.showwarning("Atenção", "Selecione o modelo da placa primeiro!")
            return

        mapa_fotos = {
            "Trinity": "TRINITY.jpg",
            "Corona 16MB": "CORONA 16MB.jpg",
            "Corona 16MB WB": "CORONA 16MB.jpg",
            "Corona 4GB": "CORONA_4G.jpg",
            "Corona 4GB WB": "CORONA_4G.jpg",
            "Jasper": "JASPER.jpg",
            "Jasper BB": "JASPER.jpg",
            "Falcon": "JASPER.jpg"
        }

        nome_foto = mapa_fotos.get(placa)
        caminho_base = self._obter_caminho_base()
        caminho_img = os.path.join(caminho_base, "Essencial", "Diagrama_PicoFlasher_UART", nome_foto)

        if not os.path.exists(caminho_img):
            messagebox.showerror("Erro", f"Diagrama não encontrado:\n{nome_foto}")
            return

        try:
            janela_diag = ctk.CTkToplevel(self)
            janela_diag.title(f"Esquema de Ligação - {placa}")
            janela_diag.attributes("-topmost", True)
            
            img_pil = Image.open(caminho_img)
            img_tk = ImageTk.PhotoImage(img_pil)

            lbl_img = ctk.CTkLabel(janela_diag, image=img_tk, text="")
            lbl_img.image = img_tk 
            lbl_img.pack(padx=20, pady=20)
        except Exception as e:
            self.log_mensagem(f"[ERRO] Falha ao abrir diagrama: {e}")


    def _validar_entrada_hex(self, P):
        if len(P) > 32: return False
        if P == "" or re.fullmatch(r'[0-9a-fA-F]*', P): return True
        return False

    def _verificar_checksum_cpukey(self, key):
        if len(key) != 32: return False
        try:
            if not all(c in "0123456789ABCDEF" for c in key.upper()): return False
            if len(set(key)) <= 1: return False
            return True
        except: return False

    def _validar_cpukey_evento(self, event=None):
        val = self.entry_cpukey.get().upper()
        if len(val) == 32:
            if self._verificar_checksum_cpukey(val):
                if getattr(self, 'ultima_chave_kv', '') != val:
                    if self.caminho_nand_atual:
                        self.entry_cpukey.configure(border_color="#F39C12")
                        self.btn3.configure(state="disabled")
                        self.ultima_chave_kv = val
                        threading.Thread(target=self._extrair_kv_nativa, daemon=True).start()
                    else:
                        self.entry_cpukey.configure(border_color="#228b22")
                        self.btn3.configure(state="normal")
                        self.ultima_chave_kv = val
            else:
                self.entry_cpukey.configure(border_color="#8b0000")
                self.btn3.configure(state="disabled")
                self.ultima_chave_kv = ""
        else:
            self.entry_cpukey.configure(border_color=["#979DA2", "#565B5E"])
            self.btn3.configure(state="disabled")
            self.ultima_chave_kv = ""

    def get_region_name(self, region_hex):
        regions = {
            "02FE": "PAL/EU", "00FF": "NTSC/US", "01FE": "NTSC/JAP",
            "01FF": "NTSC/JAP", "01FC": "NTSC/KOR", "0101": "NTSC/HK",
            "0201": "PAL/AUS", "7FFF": "DEVKIT"
        }
        return regions.get(region_hex, f"0x{region_hex}")

    def _extrair_kv_nativa(self):
        try:
            path = self.caminho_nand_atual
            key_str = self.entry_cpukey.get().strip().upper()
            
            if not path or len(key_str) != 32: return
            
            self.after(0, lambda: self.lbl_kv_info.configure(text="Lendo KV...", text_color="#F39C12"))

            cpukey = bytes.fromhex(key_str)
            file_size = os.path.getsize(path)
            
            with open(path, 'rb') as f:
                if file_size in [17301504, 69206016, 276824064, 553648128] or (file_size % 528 == 0):
                    f.seek(0x4200) 
                    raw_data = f.read(0x4400)
                    kv_encrypted = bytearray()
                    for i in range(0, 0x4000, 0x200):
                        chunk_offset = (i // 512) * 528
                        kv_encrypted += raw_data[chunk_offset : chunk_offset + 512]
                else:
                    f.seek(0x4000) 
                    kv_encrypted = f.read(0x4000)

            nonce = kv_encrypted[0:16]
            rc4_key = hmac.new(cpukey, nonce, hashlib.sha1).digest()[:16]
            cipher = ARC4.new(rc4_key)
            kv_decrypted = nonce + cipher.decrypt(kv_encrypted[16:])
            
            if kv_decrypted[0x40:0x50] != b'\x00'*16:
                raise ValueError("A CPU Key não corresponde a esta NAND (Check 0x40 falhou).")

            region_hex = kv_decrypted[0xC8:0xCA].hex().upper()
            dvd_hex = kv_decrypted[0x100:0x110].hex().upper()
            osig_str = kv_decrypted[0xC92:0xCAE].decode('ascii', errors='ignore').strip('\x00')
            serial_str = kv_decrypted[0xB0:0xBC].decode('ascii', errors='ignore').strip('\x00')

            self.dvd_original = dvd_hex
            self.kv_region = f"Região: {self.get_region_name(region_hex)}"
            self.kv_osig = f"Leitor Original: {osig_str}"
            self.kv_serial = serial_str

            self.atualizar_tela_dvdkey()
            texto_kv = f"{self.kv_region} | {self.kv_osig}"
            self.after(0, lambda: self.lbl_kv_info.configure(text=texto_kv, text_color="#3498DB"))
            
            if serial_str:
                self.after(0, lambda: [self.entry_id.delete(0, "end"), self.entry_id.insert(0, serial_str)])

            self.after(0, lambda: self.entry_cpukey.configure(border_color="#228b22"))
            self.after(0, lambda: self.btn3.configure(state="normal"))
            self.log_mensagem("[KV] Dados extraídos e verificados com sucesso!")

        except ValueError as ve:
            self.log_mensagem(f"[KV ALERTA] {str(ve)}")
            self.after(0, lambda: self.entry_cpukey.configure(border_color="#E74C3C"))
            self.after(0, lambda: self.btn3.configure(state="disabled"))
            self.after(0, lambda: self.lbl_kv_info.configure(text="[ERRO] CPU Key Incompatível com a Placa", text_color="#E74C3C"))
            self.after(0, lambda: self.lbl_dvdkey.configure(text="DVD Key: Inválida", text_color="#E74C3C"))
            
        except Exception as e:
            self.log_mensagem(f"[KV ERRO] Falha estrutural ao ler KV: {str(e)}")
            self.after(0, lambda: self.entry_cpukey.configure(border_color="#E74C3C"))
            self.after(0, lambda: self.btn3.configure(state="disabled"))
            self.after(0, lambda: self.lbl_kv_info.configure(text="Erro ao decriptar Keyvault", text_color="#E74C3C"))

    def _limpar_kv_info(self):
        self.kv_region = ""
        self.kv_osig = ""
        self.kv_serial = ""
        self.ultima_chave_kv = ""
        self.after(0, lambda: self.lbl_kv_info.configure(text=""))

    def _carregar_recursos(self):
        path_icon = os.path.join("tools", "picoflasher_uart", "picoflasher_uart.png")
        if os.path.exists(path_icon):
            img_pil = Image.open(path_icon)
            self.pico_icon_on = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(200, 90))
        else: self.pico_icon_on = None

        path_logo = os.path.abspath(os.path.join("tools", "img", "RGH3_Flasher.png"))
        if os.path.exists(path_logo):
            img_logo_pil = Image.open(path_logo)
            self.img_logo_app = ctk.CTkImage(light_image=img_logo_pil, dark_image=img_logo_pil, size=(120, 90))
        else: 
            self.img_logo_app = None

    def _tocar_som(self, tipo):
        try:
            arquivo = "sucesso.mp3" if tipo == "sucesso" else "erro.mp3"
            caminho = os.path.join("tools", "sound", arquivo) 
            if os.path.exists(caminho):
                pygame.mixer.music.load(caminho)
                pygame.mixer.music.play()
        except: pass

    def _iniciar_monitores(self):
        threading.Thread(target=self._thread_monitor_pico, daemon=True).start()

    def _thread_monitor_pico(self):
        while True:
            try:
                cmd = 'wmic path Win32_PnPEntity get DeviceID'
                output = subprocess.check_output(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW).decode()
                conectado_agora = "VID_600D" in output
                
                if conectado_agora and self.pico_icon_on:
                    self.after(0, lambda: self.lbl_pico_status.configure(image=self.pico_icon_on, text=""))
                    if not self.pico_conectado_anteriormente:
                        self.log_mensagem("[SISTEMA] Gravador conectado!")
                        self.after(0, self._resetar_cores_botoes)
                        self.after(0, lambda: self.combo_placa.set("")) 
                else:
                    self.after(0, lambda: self.lbl_pico_status.configure(image="", text="Leitor Desconectado"))
                
                self.pico_conectado_anteriormente = conectado_agora
            except: pass
            time.sleep(3)

    def _criar_pastas_base(self):
        pastas = [
            "nand", "output", "common/rgh3/Freeboot_2to3/ecc", 
            "tools/picoflasher_uart", "tools/xebuild", "tools/sound", 
            "tools/img", "common/clean_smc", 
            "Essencial/Diagrama_PicoFlasher_UART" 
        ]
        for pasta in pastas:
            os.makedirs(os.path.abspath(pasta), exist_ok=True)

    def _construir_interface(self):
        self.lbl_titulo = ctk.CTkLabel(
            self, 
            text=" RGH3 Flasher", 
            font=("Roboto", 24, "bold"), 
            image=self.img_logo_app, 
            compound="left",
            cursor="hand2"  
        )
        self.lbl_titulo.pack(padx=20, pady=(15, 5), anchor="w")
        self.lbl_titulo.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/Wellington4363/RGH3-Flasher/"))
        
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.pack(fill="x", padx=20, pady=10)
        
        frame_pipe = ctk.CTkFrame(frame_top, width=220)
        frame_pipe.pack(side="left", fill="y", padx=(0, 10))

        ctk.CTkLabel(frame_pipe, text="", font=("Roboto", 18, "bold")).pack(pady=(15, 5))
        self.lbl_pico_status = ctk.CTkLabel(frame_pipe, text="Buscando Leitor...", text_color="#5a5a5a")
        self.lbl_pico_status.pack(pady=5)
        
        ctk.CTkLabel(frame_pipe, text="Setup", font=("Roboto", 18, "bold")).pack(pady=(15, 5))
        self.btn1 = ctk.CTkButton(frame_pipe, text="1 Ler NAND", command=lambda: self._iniciar_thread(self.ler_nand_segura, self.btn1))
        self.btn1.pack(pady=5, padx=20, fill="x")
        self.btn2 = ctk.CTkButton(frame_pipe, text="2 Gravar XELL", command=lambda: self._iniciar_thread(self.gravar_xell, self.btn2))
        self.btn2.pack(pady=5, padx=20, fill="x")
        self.btn3 = ctk.CTkButton(frame_pipe, text="3 Converter RGH3", command=lambda: self._iniciar_thread(self.pipeline_conversao, self.btn3), fg_color="#b85c00", hover_color="#8f4700", state="disabled")
        self.btn3.pack(pady=5, padx=20, fill="x")
        self.btn4 = ctk.CTkButton(frame_pipe, text="4 Gravar RGH3", command=lambda: self._iniciar_thread(self.gravar_rgh3_final, self.btn4))
        self.btn4.pack(pady=5, padx=20, fill="x")

        self.progressbar = ctk.CTkProgressBar(
            frame_pipe, 
            mode="determinate", 
            height=12, 
            progress_color="#1e1e1e",
            fg_color="#1e1e1e"
        )
        self.animando_barra = False 
        self.progressbar.pack(pady=(20, 20), padx=20, fill="x")
        self.progressbar.set(0)

        frame_dados = ctk.CTkFrame(frame_top)
        frame_dados.pack(side="right", fill="both", expand=True)
        ctk.CTkLabel(frame_dados, text="Dados do Console", font=("Roboto", 18, "bold")).pack(pady=(15, 20))
        
        row1 = ctk.CTkFrame(frame_dados, fg_color="transparent")
        row1.pack(pady=5)
        self.entry_id = ctk.CTkEntry(row1, width=200, placeholder_text="ID / Serial")
        self.entry_id.pack(side="left", padx=5)
        self.combo_placa = ctk.CTkComboBox(row1, values=list(self.mapa_ecc.keys()), width=180)
        self.combo_placa.set("") 
        self.combo_placa.pack(side="left", padx=5)
        self.btn_diag = ctk.CTkButton(
            row1, 
            text="Diagrama 📸", 
            width=100, 
            command=self.abrir_diagrama_instalacao,
            fg_color="#e67e22", 
            hover_color="#b85c00"
        )
        self.btn_diag.pack(side="left", padx=5)

        self.btn_query = ctk.CTkButton(row1, text="?", width=30, command=lambda: self._iniciar_thread(self.identificar_hardware), fg_color="#5a5a5a", hover_color="#3d3d3d")
        self.btn_query.pack(side="left", padx=5)

        row_cpu = ctk.CTkFrame(frame_dados, fg_color="transparent")
        row_cpu.pack(pady=10)
        self.entry_cpukey = ctk.CTkEntry(row_cpu, width=320, placeholder_text="CPU KEY (32 dígitos)", validate='key', validatecommand=self.vcmd_hex)
        self.entry_cpukey.pack(side="left", padx=5)
        self.entry_cpukey.bind("<KeyRelease>", self._validar_cpukey_evento)
        
        self.btn_uart = ctk.CTkButton(row_cpu, text="📡 Ler CPU Key", width=100, command=self.alternar_uart, fg_color="#5a5a5a", hover_color="#3d3d3d")
        self.btn_uart.pack(side="left", padx=5)
        
        self.lbl_tipo_nand = ctk.CTkLabel(frame_dados, text="", font=("Roboto", 14, "bold"), text_color="#F39C12")
        self.lbl_tipo_nand.pack(pady=5)
        
        self.lbl_dvdkey = ctk.CTkLabel(frame_dados, text="DVD Key: ---", font=("Consolas", 13), text_color="#3498DB")
        self.lbl_dvdkey.pack(pady=(5, 0))

        self.lbl_kv_info = ctk.CTkLabel(frame_dados, text="", font=("Consolas", 12), text_color="#3498DB")
        self.lbl_kv_info.pack(pady=(0, 5))

        self.lbl_temp = ctk.CTkLabel(frame_dados, text=f"Temp Alvo: CPU {self.cfg_temp_cpu} / GPU {self.cfg_temp_gpu} / MEM {self.cfg_temp_edram}", font=("Consolas", 13), text_color="#3498DB")
        self.lbl_temp.pack(pady=(0, 5)) 

        self.lbl_patches = ctk.CTkLabel(frame_dados, text="Patches: Padrão", font=("Consolas", 13), text_color="#95A5A6")
        self.lbl_patches.pack(pady=(0, 5))

        self.lbl_nand_path = ctk.CTkLabel(frame_dados, text="Nenhuma NAND carregada", text_color="gray")
        self.lbl_nand_path.pack(pady=(15, 5))
        
        row_btns = ctk.CTkFrame(frame_dados, fg_color="transparent")
        row_btns.pack(pady=(5, 15))
        ctk.CTkButton(row_btns, text="Carregar NAND", command=self.carregar_nand_bd).pack(side="left", padx=5)

        self.btn_gravar_avulsa = ctk.CTkButton(row_btns, text="Gravar NAND Selec", command=lambda: self._iniciar_thread(self.gravar_nand_bd_direta), width=100, fg_color="#5a5a5a")
        self.btn_gravar_avulsa.pack(side="left", padx=5)
        
        ctk.CTkButton(row_btns, text="⚙️ Avançado", command=self.abrir_opcoes_avancadas, width=100, fg_color="transparent", border_width=1).pack(side="left", padx=5)
        
        frame_log = ctk.CTkFrame(self)
        frame_log.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        ctk.CTkLabel(frame_log, text="Console Log", font=("Roboto", 14, "bold")).pack(anchor="w", padx=15, pady=(10, 0))
        self.caixa_log = ctk.CTkTextbox(frame_log, font=("Consolas", 12), fg_color="#1e1e1e")
        self.caixa_log.pack(fill="both", expand=True, padx=15, pady=(5, 15))

    

    def _encontrar_porta_pico(self):
        portas = list(serial.tools.list_ports.comports())
        candidatas = []
        for p in portas:
            if "600D" in p.hwid or "2E8A" in p.hwid or "Pico" in p.description:
                candidatas.append(p.device)
        if candidatas:
            candidatas.sort(key=lambda x: int(re.sub(r'\D', '', x)))
            return candidatas[-1] 
        return None

    def alternar_uart(self):
        if self.uart_thread and self.uart_thread.is_alive():
            self.uart_stop_event.set()
            self.log_mensagem("[UART] Interrompendo leitura...")
            self.btn_uart.configure(fg_color="#5a5a5a", text="📡 Ler CPU Key")
        else:
            self.uart_stop_event.clear()
            self.uart_thread = threading.Thread(target=self._tarefa_uart, daemon=True)
            self.uart_thread.start()

    def _tarefa_uart(self):
        porta = self._encontrar_porta_pico()
        if not porta:
            self.log_mensagem("[ERRO UART] Porta COM do Pico não encontrada.")
            self.after(0, lambda: self.btn_uart.configure(fg_color="#5a5a5a", text="📡 Ler CPU Key"))
            return

        self.log_mensagem(f"[UART] Lendo a {porta} (115200 bps)... Ligue o Console!")
        self.after(0, lambda: self.btn_uart.configure(fg_color="#228b22", text="Lendo ..."))

        try:
            with serial.Serial(porta, 115200, timeout=1) as ser:
                while not self.uart_stop_event.is_set():
                    linha = ser.readline().decode('ascii', errors='ignore').strip()
                    if linha:
                        self.log_mensagem(f"[XeLL] {linha}")
                        match = re.search(r'([0-9a-fA-F]{32})', linha)
                        if match:
                            possivel_chave = match.group(1).upper()
                            if self._verificar_checksum_cpukey(possivel_chave):
                                self.log_mensagem(f"[SUCESSO UART] CPU Key Capturada!")
                                self.after(0, lambda k=possivel_chave: self._preencher_cpukey_uart(k))
                                self._tocar_som("sucesso")
                                
                                messagebox.showinfo(
                                    "CPU Key Capturada!", 
                                    "PRÓXIMOS PASSOS NA BANCADA:\n\n"
                                    "1. Desligue o console e remova a fonte.\n"
                                    "2. Reconecte o conector SPI/SD na placa.\n"
                                    "3. (Opcional) Insira novos parâmetros se necessário em avançado.\n"
                                    "4. Clique em '3 Converter RGH3'.\n"
                                    "5. Clique em '4 Gravar RGH3' para finalizar."
                                )
                                
                                self.after(0, lambda: self.btn3.focus_set())
                                self.uart_stop_event.set()
                                break
        except Exception as e:
            self.log_mensagem(f"[ERRO UART] Conexão perdida: {str(e)}")
        finally:
            self.after(0, lambda: self.btn_uart.configure(fg_color="#5a5a5a", text="📡 Ler CPU Key"))
            self.log_mensagem("[UART] Leitura finalizada.")

    def _preencher_cpukey_uart(self, key):
        self.entry_cpukey.delete(0, "end")
        self.entry_cpukey.insert(0, key)
        self._validar_cpukey_evento() 

    def _resetar_cores_botoes(self):
        self.btn1.configure(fg_color=["#3B8ED0", "#1F6AA5"])
        self.btn2.configure(fg_color=["#3B8ED0", "#1F6AA5"])
        self.btn3.configure(fg_color="#b85c00")
        self.btn4.configure(fg_color=["#3B8ED0", "#1F6AA5"])

    def log_mensagem(self, texto):
        self.after(0, lambda: [self.caixa_log.configure(state="normal"), self.caixa_log.insert("end", f"{texto}\n"), self.caixa_log.see("end"), self.caixa_log.configure(state="disabled")])

    def animar_cor_progresso(self):
        if not self.animando_barra:
            return
        cor_atual = self.progressbar.cget("progress_color")
        nova_cor = "#65CEFF" if cor_atual == "#3498DB" else "#3498DB"
        self.progressbar.configure(progress_color=nova_cor)
        self.after(500, self.animar_cor_progresso)

    def start_loading(self):
        self.animando_barra = True
        self.after(0, lambda: [
            self.progressbar.configure(progress_color="#3498DB"),
            self.progressbar.set(0),
            self.animar_cor_progresso()
        ])

    def stop_loading(self):
        self.animando_barra = False
        self.after(1000, lambda: [
            self.progressbar.configure(progress_color="#1e1e1e"),
            self.progressbar.set(1.0)
        ])

    def _executar_comando(self, comando, pasta_trabalho=None, com_progresso=False):
        try:
            processo = subprocess.Popen(
                comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, cwd=pasta_trabalho,
                creationflags=subprocess.CREATE_NO_WINDOW, bufsize=1, universal_newlines=True
            )

            output_completo = []
            buffer_linha = ""

            while True:
                char = processo.stdout.read(1)
                if not char and processo.poll() is not None:
                    break
                
                if char:
                    buffer_linha += char
                    if char == '\n' or char == '\r':
                        output_completo.append(buffer_linha)
                        if com_progresso:
                            self._interpretar_progresso_pico(buffer_linha)
                        buffer_linha = "" 

            output_final = "".join(output_completo)
            sucesso_real = processo.returncode == 0
            
            erros_criticos = ["ERRO", "Error", "Not Found", "failed", "failed: 0"]
            if any(erro in output_final for erro in erros_criticos):
                sucesso_real = False

            return sucesso_real, output_final
        except Exception as e:
            return False, str(e)

    def _interpretar_progresso_pico(self, linha):
        match_hex = re.findall(r'0x([0-9a-fA-F]+)', linha)
        if len(match_hex) >= 2:
            try:
                atual = int(match_hex[0], 16)
                total = int(match_hex[1], 16)
                if total > 0:
                    progresso = atual / total
                    self.after(0, lambda p=min(progresso, 1.0): self.progressbar.set(p))
            except: pass

    def _auditoria_de_arquivos(self):
        self.log_mensagem("[SISTEMA] Verificando integridade...")
        p_ecc = os.path.abspath("common/rgh3/Freeboot_2to3/ecc")
        for ecc in self.mapa_ecc.values():
            if not os.path.exists(os.path.join(p_ecc, ecc)):
                self.log_mensagem(f"[AVISO] ECC ausente: {ecc}")
        self.log_mensagem("[OK] Verificação concluída.")

    def _criar_item_patch(self, parent, texto, var, info_texto):
        frame_linha = ctk.CTkFrame(parent, fg_color="transparent")
        frame_linha.pack(fill="x", padx=40, pady=2)
        chk = ctk.CTkCheckBox(frame_linha, text=texto, variable=var, font=("Roboto", 13))
        chk.pack(side="left")
        btn_info = ctk.CTkButton(
            frame_linha, text="ℹ️", width=24, height=24, fg_color="transparent", hover_color="#3d3d3d",
            command=lambda: messagebox.showinfo(texto.split(" ")[0], info_texto)
        )
        btn_info.pack(side="right")

    def abrir_opcoes_avancadas(self):
        if self.janela_opcoes is None or not self.janela_opcoes.winfo_exists():
            self.janela_opcoes = ctk.CTkToplevel(self)
            self.janela_opcoes.title("Avançado - Tuning do Console")
            self.janela_opcoes.geometry("450x650") 
            self.janela_opcoes.attributes("-topmost", True)
            
            ctk.CTkLabel(self.janela_opcoes, text="Temperaturas Alvo (°C):", font=("Roboto", 14, "bold")).pack(pady=(10, 5))
            
            frame_temps = ctk.CTkFrame(self.janela_opcoes, fg_color="transparent")
            frame_temps.pack(pady=5)
            val_temps = ["80", "75", "70", "65", "64", "63", "62", "61", "60", "59", "58", "57", "56", "55", "54", "53", "52", "51", "50"]
            
            ctk.CTkLabel(frame_temps, text="CPU:").grid(row=0, column=0, padx=5)
            self.combo_cpu = ctk.CTkComboBox(frame_temps, values=val_temps, width=70)
            self.combo_cpu.set(self.cfg_temp_cpu); self.combo_cpu.grid(row=0, column=1, padx=5)
            
            ctk.CTkLabel(frame_temps, text="GPU:").grid(row=0, column=2, padx=5)
            self.combo_gpu = ctk.CTkComboBox(frame_temps, values=val_temps, width=70)
            self.combo_gpu.set(self.cfg_temp_gpu); self.combo_gpu.grid(row=0, column=3, padx=5)

            ctk.CTkLabel(frame_temps, text="eDRAM:").grid(row=0, column=4, padx=5)
            self.combo_edram = ctk.CTkComboBox(frame_temps, values=val_temps, width=70)
            self.combo_edram.set(self.cfg_temp_edram); self.combo_edram.grid(row=0, column=5, padx=5)

            ctk.CTkLabel(self.janela_opcoes, text="DVD Key Spoof:", font=("Roboto", 14, "bold")).pack(pady=(15, 5))
            self.entry_dvd = ctk.CTkEntry(self.janela_opcoes, width=320, validate='key', validatecommand=self.vcmd_hex)
            self.entry_dvd.insert(0, self.cfg_dvdkey); self.entry_dvd.pack()

            ctk.CTkLabel(self.janela_opcoes, text="Patches Essenciais:", font=("Roboto", 14, "bold"), text_color="#F39C12").pack(pady=(15, 5))
            
            self.chk_nofcrt_var = ctk.BooleanVar(value=self.cfg_nofcrt)
            self._criar_item_patch(self.janela_opcoes, "NoFCRT (Desativar checagem)", self.chk_nofcrt_var, 
                "Desativa a checagem de integridade do leitor de DVD na NAND. Essencial para salvar Slims rodando com leitor trocado (Spoof).")
            
            self.chk_usbdsec_var = ctk.BooleanVar(value=self.cfg_usbdsec)
            self._criar_item_patch(self.janela_opcoes, "USBDsec (Liberar USB)", self.chk_usbdsec_var, 
                "Injeta um patch no xam.xex para remover restrições de segurança das portas USB. Permite uso de HDs e controles não originais.")

            ctk.CTkLabel(self.janela_opcoes, text="Patches Adicionais (Reparo):", font=("Roboto", 14, "bold"), text_color="#3498DB").pack(pady=(15, 5))

            self.chk_nointmu_var = ctk.BooleanVar(value=self.cfg_nointmu)
            self._criar_item_patch(self.janela_opcoes, "NoIntMU (Ignorar eMMC 4GB)", self.chk_nointmu_var, 
                "Desativa a montagem da memória interna. Salva placas Corona 4GB que estão travando devido ao chip eMMC corrompido ou morto.")

            self.chk_nohdmiwait_var = ctk.BooleanVar(value=self.cfg_nohdmiwait)
            self._criar_item_patch(self.janela_opcoes, "NoHDMIWait (Boot Instante)", self.chk_nohdmiwait_var, 
                "Força o console a não esperar a resposta do cabo HDMI para iniciar o boot. Acelera a inicialização.")
            
            self.chk_xl_both_var = ctk.BooleanVar(value=self.cfg_xl_both)
            self._criar_item_patch(self.janela_opcoes, "XL Storage (HDs > 2TB)", self.chk_xl_both_var, 
                "Reescreve os drivers de armazenamento para permitir o uso de HDs internos e externos maiores que 2TB (suporta até 16TB).")

            self.chk_nowifi_var = ctk.BooleanVar(value=self.cfg_nowifi)
            self._criar_item_patch(self.janela_opcoes, "NoWiFi (Desativar Sem Fio)", self.chk_nowifi_var, 
                "Desativa o módulo Wi-Fi a nível de sistema operacional. Útil se o componente físico estiver em curto e travando o videogame.")

            self.chk_nolan_var = ctk.BooleanVar(value=self.cfg_nolan)
            self._criar_item_patch(self.janela_opcoes, "NoLAN (Desativar Cabo Rede)", self.chk_nolan_var, 
                "Desativa a interface de rede cabeada. Útil se o CI de rede onboard queimou após uma descarga elétrica.")

            self.chk_nohdd_var = ctk.BooleanVar(value=self.cfg_nohdd)
            self._criar_item_patch(self.janela_opcoes, "NoHDD (Desativar SATA)", self.chk_nohdd_var, 
                "Desativa a porta SATA do HD interno. Ajuda no diagnóstico se a Ponte Sul estiver com problemas no barramento.")

            ctk.CTkButton(self.janela_opcoes, text="Salvar", command=self.salvar_opcoes_avancadas, fg_color="#27AE60", hover_color="#2ECC71").pack(pady=20)

    def salvar_opcoes_avancadas(self):
        chave_digitada = self.entry_dvd.get().strip().upper()

        if chave_digitada != "" and len(chave_digitada) != 32:
            messagebox.showerror("Erro de Validação", "A DVD Key (Spoof) precisa ter exatos 32 caracteres hexadecimais!\n\nDeixe em branco se não quiser usar Spoof.")
            return

        self.cfg_temp_cpu = self.combo_cpu.get()
        self.cfg_temp_gpu = self.combo_gpu.get()
        self.cfg_temp_edram = self.combo_edram.get()
        self.cfg_dvdkey = chave_digitada
        self.cfg_nofcrt = self.chk_nofcrt_var.get()
        self.cfg_usbdsec = self.chk_usbdsec_var.get()
        self.cfg_nointmu = self.chk_nointmu_var.get()
        self.cfg_nohdmiwait = self.chk_nohdmiwait_var.get()
        self.cfg_nowifi = self.chk_nowifi_var.get()
        self.cfg_nolan = self.chk_nolan_var.get()
        self.cfg_nohdd = self.chk_nohdd_var.get()
        self.cfg_xl_both = self.chk_xl_both_var.get()

        self.log_mensagem("[SISTEMA] Configurações Avançadas salvas.")
        self.janela_opcoes.destroy()

        self.atualizar_tela_temp()
        self.atualizar_tela_dvdkey()
        self.atualizar_tela_patches()
        self.atualizar_estado_gravar_avulsa()

    def atualizar_tela_temp(self):
        is_custom = self.cfg_temp_cpu != "65" or self.cfg_temp_gpu != "63" or self.cfg_temp_edram != "59"
        cor = "#E74C3C" if is_custom else "#3498DB"
        texto = f"Temp Alvo: CPU {self.cfg_temp_cpu} / GPU {self.cfg_temp_gpu} / MEM {self.cfg_temp_edram}"
        self.after(0, lambda: self.lbl_temp.configure(text=texto, text_color=cor))

    def atualizar_tela_dvdkey(self):
        if self.cfg_dvdkey:
            self.after(0, lambda: self.lbl_dvdkey.configure(text=f"DVD Key: {self.cfg_dvdkey} (Spoof)", text_color="#E74C3C"))
        elif self.dvd_original:
            self.after(0, lambda: self.lbl_dvdkey.configure(text=f"DVD Key: {self.dvd_original}", text_color="#3498DB"))
        else:
            self.after(0, lambda: self.lbl_dvdkey.configure(text="DVD Key: ---", text_color="#3498DB"))

    def atualizar_tela_patches(self):
        patches = []
        if self.cfg_nofcrt: patches.append("NoFCRT")
        if self.cfg_usbdsec: patches.append("USBD")
        if self.cfg_nointmu: patches.append("NoMU")
        if self.cfg_nohdmiwait: patches.append("NoHDMI")
        if self.cfg_nowifi: patches.append("NoWiFi")
        if self.cfg_nolan: patches.append("NoLAN")
        if self.cfg_nohdd: patches.append("NoHDD")
        if self.cfg_xl_both: patches.append("XL_HDD")
        
        outros_patches = self.cfg_nofcrt or self.cfg_nointmu or self.cfg_nohdmiwait or \
                         self.cfg_nowifi or self.cfg_nolan or self.cfg_nohdd or self.cfg_xl_both
        
        cor = "#E74C3C" if outros_patches else "#3498DB" 
        texto = "Patches: " + ", ".join(patches) if patches else "Patches: Padrão"
        self.after(0, lambda: self.lbl_patches.configure(text=texto, text_color=cor))

    def atualizar_estado_gravar_avulsa(self):
        is_custom = self.cfg_temp_cpu != "65" or self.cfg_temp_gpu != "63" or self.cfg_temp_edram != "59"
        tem_mods = (self.cfg_dvdkey != "") or self.cfg_nofcrt or self.cfg_nointmu or \
                   self.cfg_nohdmiwait or self.cfg_nowifi or self.cfg_nolan or self.cfg_nohdd or self.cfg_xl_both
        
        if is_custom or tem_mods:
            self.after(0, lambda: self.btn_gravar_avulsa.configure(state="disabled"))
        else:
            self.after(0, lambda: self.btn_gravar_avulsa.configure(state="normal"))

    def _obter_nome_ecc(self, placa):
        return self.mapa_ecc.get(placa)

    def _iniciar_thread(self, target_func, botao=None):
        if botao: self._resetar_cores_botoes()
        self.start_loading()
        threading.Thread(target=lambda: self._envolver_thread(target_func, botao), daemon=True).start()

    def _envolver_thread(self, target_func, botao=None):
        sucesso = False
        try:
            res = target_func()
            if res is True: sucesso = True
        except: sucesso = False
        finally:
            self.stop_loading()
            if botao:
                cor = "#228b22" if sucesso else "#8b0000"
                self.after(0, lambda b=botao, c=cor: b.configure(fg_color=c))
            
            if sucesso:
                self._tocar_som("sucesso")
                
                if botao == self.btn2:
                    messagebox.showinfo(
                        "Xell Gravado com Sucesso!", 
                        "1. Desconecte o conector SPI/SD da placa.\n"
                        "2. Mantenha o conector UART ligado na placa.\n"
                        "3. Conecte a fonte e o cabo de vídeo.\n"
                        "4. Ligue o console.\n\n"
                        "A Leitura da CPU Key iniciará ao clicar em OK."
                    )
                    self.log_mensagem("[AUTO] Iniciando escuta da CPU Key...")
                    self.after(500, self.alternar_uart)
                    
                elif botao == self.btn4:
                    messagebox.showinfo(
                        "RGH3 Gravado com Sucesso!", 
                        "A imagem final foi escrita na placa com êxito!\n\n"
                        "PASSOS FINAIS:\n"
                        "1. Desconecte o gravador (SPI/SD) da placa-mãe.\n"
                        "2. Verifique se os fios do RGH3 (PLL e POST) estão bem soldados.\n"
                        "3. Conecte o cabo HDMI/AV e a Fonte.\n"
                        "4. Ligue o console!\n\n"
                    )
            else:
                self._tocar_som("erro")

    def _detectar_tipo_nand(self, caminho):
        try:
            with open(caminho, 'rb') as f:
                cabecalho = f.read(2 * 1024 * 1024) 
                if b'XeLL' in cabecalho or b'xeBuild' in cabecalho or b'GLITCH' in cabecalho: return "RGH"
                else: return "Retail (Original)"
        except Exception: return "Desconhecida"

    def identificar_hardware(self):
        self.after(0, lambda: self.combo_placa.set(""))
        p_exe = os.path.abspath("tools/picoflasher_uart/PicoFlasher_uart.exe")
        tmp = os.path.abspath("nand/_temp/check.bin")
        self.log_mensagem("[HARDWARE] Identificando placa..."); os.makedirs(os.path.dirname(tmp), exist_ok=True)
        try:
            proc = subprocess.Popen([p_exe, "-r", tmp], stdout=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            det = None
            for linha in iter(proc.stdout.readline, ""):
                l = linha.lower()
                if "não encontrado" in l or "not found" in l: break 
                if "00023010" in l: det = "Trinity"
                elif "00043000" in l: det = "Corona 16MB"
                elif "008a3020" in l: det = "Jasper" 
                elif "00aa3020" in l or "008a0020" in l: det = "Jasper BB" 
                elif "004a3020" in l: det = "Falcon"
                if det: 
                    proc.terminate()
                    try: proc.wait(timeout=1)
                    except: pass
                    break
            
            if det:
                self.after(0, lambda: self.combo_placa.set(det))
                self.log_mensagem(f"[SUCESSO] Placa: {det}")
                return True
            else:
                self.log_mensagem("[ERRO] Placa não conectada ou sem energia.")
                self.log_mensagem(">> 1. Verifique se o cabo SPI/SD está bem encaixado na placa.")
                self.log_mensagem(">> 2. Certifique-se de que a fonte de energia está plugada (Standby).")
                self.log_mensagem(">> 3. Desconecte e reconecte o USB do Gravador e tente novamente.")
                return False
        except Exception as e:
            self.log_mensagem(f"[ERRO] Erro ao identificar: {e}")
        return False

    def carregar_nand_bd(self):
        cam = filedialog.askopenfilename(initialdir=os.path.abspath("nand"), filetypes=[("BIN", "*.bin")])
        if cam:
            self.entry_id.delete(0, "end")
            self.entry_cpukey.delete(0, "end")

            self.dvd_original = "" 
            self.cfg_dvdkey = ""
            self.cfg_temp_cpu = "65"
            self.cfg_temp_gpu = "63"
            self.cfg_temp_edram = "59"
            self.cfg_nofcrt = False
            self.cfg_usbdsec = True 
            self.cfg_nointmu = False
            self.cfg_nohdmiwait = False
            self.cfg_nowifi = False
            self.cfg_nolan = False
            self.cfg_nohdd = False
            self.cfg_xl_both = False
            self._limpar_kv_info()
            
            self.atualizar_tela_dvdkey()
            self.atualizar_tela_temp()
            self.atualizar_tela_patches()
            self.atualizar_estado_gravar_avulsa() 
            self.lbl_dvdkey.configure(text="DVD Key: ---")
            self.lbl_tipo_nand.configure(text="Tipo de NAND: Aguardando...", text_color="#F39C12")
            
            self.caminho_nand_atual = os.path.abspath(cam)
            self.lbl_nand_path.configure(text=os.path.basename(cam), text_color="white")
            p_con = os.path.dirname(cam)
            c_info = os.path.join(p_con, "info.txt")
            
            if os.path.exists(c_info):
                with open(c_info, "r") as f: cont = f.read()
                m_placa = re.search(r"Console Type:\s*(.*)", cont)
                m_cpu = re.search(r"Cpu Key:\s*(.*)", cont)
                m_serial = re.search(r"Serial:\s*(\d+)", cont)
                m_dvd = re.search(r"DVD Key:\s*(.*)", cont)

                if m_dvd and m_dvd.group(1).strip() != 'N/A':
                    self.dvd_original = m_dvd.group(1).strip()
                self.atualizar_tela_dvdkey()

                if m_placa: self.combo_placa.set(m_placa.group(1).strip())
                if m_cpu: self.entry_cpukey.insert(0, m_cpu.group(1).strip())
                if m_serial: self.entry_id.insert(0, m_serial.group(1).strip())

                self.log_mensagem("[SISTEMA] Dados importados.")
                self._validar_cpukey_evento()
            else: 
                self.entry_id.insert(0, os.path.basename(p_con))
            
            if self.combo_placa.get() == "":
                placa_detectada = self._descobrir_placa_pelo_cb(self.caminho_nand_atual)
                if placa_detectada:
                    self.after(0, lambda: self.combo_placa.set(placa_detectada))
                    self.log_mensagem(f"[SISTEMA] Placa identificada pelo CB: {placa_detectada}")

            tipo = self._detectar_tipo_nand(self.caminho_nand_atual)
            self.lbl_tipo_nand.configure(text=f"Tipo de NAND: {tipo}")

    def ler_nand_segura(self):
        if not self.identificar_hardware(): 
            self.log_mensagem("[ERRO] Falha na identificação da placa. Verifique a conexão.")
            self.log_mensagem(">> 1. Verifique se o cabo SPI/SD está bem encaixado na placa.")
            self.log_mensagem(">> 2. Certifique-se de que a fonte de energia está plugada (Standby).")
            self.log_mensagem(">> 3. Desconecte e reconecte o USB do Gravador e tente novamente.")
            return False

        placa_detectada = self.combo_placa.get()
        id_c = self.entry_id.get().strip()

        if not id_c:
            data_hora = time.strftime("%Y%m%d_%H%M")
            id_c = f"{placa_detectada}_{data_hora}"
            self.after(0, lambda: [self.entry_id.delete(0, "end"), self.entry_id.insert(0, id_c)])
            self.log_mensagem(f"[SISTEMA] ID não informado. Gerado automaticamente: {id_c}")
        
        self.dvd_original = "" 
        self.cfg_dvdkey = ""
        self.cfg_temp_cpu = "65"
        self.cfg_temp_gpu = "63"
        self.cfg_temp_edram = "59"
        self.cfg_nofcrt = False
        self.cfg_usbdsec = True
        self.cfg_nointmu = False
        self.cfg_nohdmiwait = False
        self.cfg_nowifi = False
        self.cfg_nolan = False
        self.cfg_nohdd = False
        self.cfg_xl_both = False 
        self._limpar_kv_info()       
        self.atualizar_tela_dvdkey() 
        self.atualizar_tela_temp()
        self.atualizar_tela_patches()
        self.atualizar_estado_gravar_avulsa()   
        
        self.after(0, lambda: [
            self.entry_cpukey.delete(0, "end"),
            self.lbl_tipo_nand.configure(text="Tipo de NAND: Lendo hardware...", text_color="#3498DB"),
            self.lbl_nand_path.configure(text="Aguardando finalização...", text_color="gray"),
            self._validar_cpukey_evento()
        ])

        placa = self.combo_placa.get()
        p_exe = os.path.abspath("tools/picoflasher_uart/PicoFlasher_uart.exe")
        tmp_dir = os.path.abspath("nand/_temp"); os.makedirs(tmp_dir, exist_ok=True)
        d1, d2 = os.path.join(tmp_dir, "dump1.bin"), os.path.join(tmp_dir, "dump2.bin")
        for f in [d1, d2]: 
            if os.path.exists(f): os.remove(f)
            
        cmd_r1 = [p_exe, "-r", d1]
        cmd_r2 = [p_exe, "-r", d2]
        
        if placa == "Corona 4GB":
            cmd_r1.extend(["0", "0x18000"])
            cmd_r2.extend(["0", "0x18000"])
            self.log_mensagem("[SISTEMA] Modo 4GB: Limitando leitura a 48MB (0x18000 blocos)...")
        elif placa == "Jasper BB":
            cmd_r1.extend(["0", "0x200"]) 
            cmd_r2.extend(["0", "0x200"])
            self.log_mensagem("[SISTEMA] Modo Jasper BB: Limitando leitura a 64MB (0x200 blocos)...")
            
        self.log_mensagem("[HARDWARE] Lendo Dump 1...")
        s1, _ = self._executar_comando(cmd_r1, com_progresso=True)
        if not s1: return False
        
        self.log_mensagem("[HARDWARE] Lendo Dump 2...")
        s2, _ = self._executar_comando(cmd_r2, com_progresso=True)
        if not s2: return False
        
        if os.path.exists(d1) and os.path.exists(d2):
            self.log_mensagem("[SISTEMA] Comparando arquivos...")
            if filecmp.cmp(d1, d2, shallow=False):
                self.log_mensagem("[SUCESSO] NANDs idênticas!")
                p_db = os.path.abspath(f"nand/{id_c}"); os.makedirs(p_db, exist_ok=True)
                shutil.move(d1, os.path.join(p_db, "nanddump.bin")); os.remove(d2)
                self.caminho_nand_atual = os.path.join(p_db, "nanddump.bin")
                tipo = self._detectar_tipo_nand(self.caminho_nand_atual)
                self.after(0, lambda t=tipo: self.lbl_tipo_nand.configure(text=f"Tipo de NAND: {t}"))
                self.after(0, lambda: self.lbl_nand_path.configure(text=f"Carregada: {id_c}/nanddump.bin", text_color="white"))
                return True
            else: self.log_mensagem("[ERRO CRÍTICO] Dumps são DIFERENTES!"); return False
        else: return False

    def gravar_xell(self):
        placa = self.combo_placa.get()
        if not placa or placa == "":
            self.log_mensagem("[ERRO] Identifique ou selecione a placa primeiro!"); return False            
            
        if "Corona" in placa and "WB" not in placa:
            resposta = messagebox.askyesno(
                "Atenção: Verificação de Memória",
                f"Você selecionou a placa: {placa}\n\nATENÇÃO: Verifique fisicamente se o chip de memória na placa é da marca Winbond?\n\nSe o chip for Winbond, clique em 'Não', e altere para a versão 'WB' e tente novamente.\n\nDeseja prosseguir com a gravação do XeLL padrão agora?"
            )
            if not resposta: self.log_mensagem("[AVISO] Gravação cancelada."); return False

        nome_ecc = self._obter_nome_ecc(placa)
        c_ecc = os.path.abspath(f"common/rgh3/Freeboot_2to3/ecc/{nome_ecc}")       
        if not os.path.exists(c_ecc): 
            self.log_mensagem(f"[ERRO] Arquivo ECC não encontrado: {nome_ecc}"); return False          
            
        if not self.identificar_hardware(): 
            self.log_mensagem("[ERRO CRÍTICO] Gravação abortada por segurança: Console não detectado!")
            self.log_mensagem(">> 1. Verifique se o cabo SPI/SD está bem encaixado na placa.")
            self.log_mensagem(">> 2. Certifique-se de que a fonte de energia está plugada (Standby).")
            self.log_mensagem(">> 3. Desconecte e reconecte o USB do Gravador e tente novamente.")
            return False

        time.sleep(0.5) 

        p_exe = os.path.abspath("tools/picoflasher_uart/PicoFlasher_uart.exe")
        self.log_mensagem(f"[HARDWARE] Gravando Xell ({nome_ecc})...")
        suc, log_cmd = self._executar_comando([p_exe, "-w", c_ecc], com_progresso=True)       
        
        if not suc: self.log_mensagem(f"[ERRO] A gravação falhou! Log: {log_cmd}")
        return suc

    def pipeline_conversao(self):
        placa = self.combo_placa.get()
        if not placa or placa == "": self.log_mensagem("[ERRO] Placa não selecionada."); return False
            
        key, id_tela = self.entry_cpukey.get().strip().upper(), self.entry_id.get().strip()
        if len(key) != 32 or not self._verificar_checksum_cpukey(key): self.log_mensagem("[ERRO] CPU KEY inválida."); return False
        if not self.caminho_nand_atual or not id_tela: self.log_mensagem("[ERRO] Dados incompletos."); return False

        self.after(0, lambda: self.progressbar.set(0.1))
        p_xe, p_mo = os.path.abspath("tools/xebuild"), os.path.abspath("common/rgh3/Freeboot_2to3")
        s_fi_output = os.path.abspath("output/updflash_RGH3.bin")
        r2_temp = os.path.abspath("output/xe_temp.bin")
        id_soberano = id_tela if id_tela else "console"

        self.log_mensagem("[CONVERTENDO 1/2] xeBuild: Reconstruindo imagem...")
        d_xe = os.path.join(p_xe, "data"); os.makedirs(d_xe, exist_ok=True)
        shutil.copy2(self.caminho_nand_atual, os.path.join(d_xe, "nanddump.bin"))
        
        mapa_smc = {
            "Trinity": "SMC_Trinity.bin", "Corona 16MB": "SMC_Corona.bin", "Corona 16MB WB": "SMC_Corona.bin",
            "Corona 4GB": "SMC_Corona.bin", "Corona 4GB WB": "SMC_Corona.bin", "Jasper": "SMC_Jasper.bin", 
            "Jasper BB": "SMC_Jasper.bin", "Falcon": "SMC_Falcon.bin"
        }
        
        nome_smc_limpo = mapa_smc.get(placa)
        caminho_smc_limpo = os.path.abspath(os.path.join("common", "clean_smc", nome_smc_limpo))
        usou_smc_limpo = False
        
        if os.path.exists(caminho_smc_limpo):
            shutil.copy2(caminho_smc_limpo, os.path.join(d_xe, "smc.bin"))
            usou_smc_limpo = True
        else: self.log_mensagem(f"[AVISO] SMC Limpo não encontrado! Usando o da NAND...")

        options_str = (
            "[Options]\n"
            "1blkey = DD88AD0C9ED669E7B56794FB68563EFA\n"
            f"cpukey = {key}\n"
            "patchsmc = true\n" 
            f"cputemp = {self.cfg_temp_cpu}\n"
            f"gputemp = {self.cfg_temp_gpu}\n"
            f"edramtemp = {self.cfg_temp_edram}\n"
        )
        
        if self.cfg_dvdkey and len(self.cfg_dvdkey) == 32: options_str += f"dvdkey = {self.cfg_dvdkey}\n"
        if self.cfg_nofcrt: options_str += "fcrt = false\n"

        with open(os.path.join(d_xe, "options.ini"), "w", encoding="ascii") as f: f.write(options_str)
        with open(os.path.join(d_xe, "cpukey.txt"), "w", encoding="ascii") as f: f.write(key)
            
        m_xe = {
            "Trinity": "trinity", "Corona 16MB": "corona", "Corona 16MB WB": "corona",
            "Corona 4GB": "corona4g", "Corona 4GB WB": "corona4g", "Jasper": "jasper", 
            "Jasper BB": "jasper", "Falcon": "falcon"
        }
        
        cmd_xe = [os.path.join(p_xe, "xeBuild.exe"), "-t", "glitch2", "-c", m_xe[placa], "-f", "17559", "-d", "data", "updflash.bin"]
        
        if self.cfg_usbdsec: cmd_xe.extend(["-a", "usbdsec"])
        if self.cfg_nointmu: cmd_xe.extend(["-a", "nointmu"])
        if self.cfg_nohdmiwait: cmd_xe.extend(["-a", "nohdmiwait"])
        if self.cfg_nowifi: cmd_xe.extend(["-a", "nowifi"])
        if self.cfg_nolan: cmd_xe.extend(["-a", "nolan"])
        if self.cfg_nohdd: cmd_xe.extend(["-a", "nohdd"])
        if self.cfg_xl_both: cmd_xe.extend(["-a", "xl_both"])

        sucesso_xe, log_xe = self._executar_comando(cmd_xe, p_xe)
        
        if "updflash.bin image built" in log_xe:
            self.after(0, lambda: self.progressbar.set(0.7))
            dvd = re.search(r"DVD Key\s*:\s*([A-F0-9]+)", log_xe, re.I)
            ldv = re.search(r"CF LDV\s*:\s*(\d+)", log_xe, re.I)
            dvd_str = dvd.group(1) if dvd else 'N/A'
            
            p_con_bd = os.path.abspath(os.path.join("nand", id_soberano)); os.makedirs(p_con_bd, exist_ok=True)
            with open(os.path.join(p_con_bd, "info.txt"), "w") as f:
                f.write(f"Console Type: {placa}\nCpu Key: {key}\nDVD Key: {dvd_str}\nSerial: {id_soberano}\nCF LDV: {ldv.group(1) if ldv else 'N/A'}\n")
            
            dest_nand_orig = os.path.join(p_con_bd, "nanddump.bin")
            pasta_origem = os.path.abspath(os.path.dirname(self.caminho_nand_atual))
            pasta_raiz_nand = os.path.abspath("nand")

            # Copia a nand para a nova pasta do serial se ela ainda não existir lá
            if not os.path.exists(dest_nand_orig) and self.caminho_nand_atual != dest_nand_orig:
                shutil.copy2(self.caminho_nand_atual, dest_nand_orig)

            # --- FAXINA INTELIGENTE: LIMPEZA DE PASTA DUPLICADA ---
            # Se a pasta antiga estiver dentro do nosso BD (nand/) e for diferente da pasta do serial novo, nós a deletamos.
            if pasta_origem.startswith(pasta_raiz_nand) and pasta_origem != p_con_bd and "_temp" not in pasta_origem.lower():
                try:
                    shutil.rmtree(pasta_origem)
                    self.log_mensagem(f"[SISTEMA] Arquivos gravados na pasta: {id_soberano}")
                except:
                    pass
            # ------------------------------------------------------

            self.caminho_nand_atual = dest_nand_orig
            self.after(0, lambda: self.lbl_nand_path.configure(text=f"Carregada: {id_soberano}/nanddump.bin", text_color="white"))
            
            upd_gen = os.path.join(p_xe, "updflash.bin")
            if os.path.exists(upd_gen): shutil.move(upd_gen, r2_temp)
        else: 
            self.log_mensagem("[ERRO] xeBuild falhou na reconstrução. Log do erro:\n" + log_xe)
            return False

        self.log_mensagem("[CONVERTENDO 2/2] Aplicando Patch RGH 3.0...")
        cmd_23 = [os.path.join(p_mo, "python.exe"), os.path.join(p_mo, "2to3.py"), os.path.abspath(f"common/rgh3/Freeboot_2to3/ecc/{self._obter_nome_ecc(placa)}"), r2_temp, key, s_fi_output]
        sucesso_23, log_23 = self._executar_comando(cmd_23, p_mo)
        
        if sucesso_23 and os.path.exists(s_fi_output):
            self.after(0, lambda: self.progressbar.set(1.0))
            shutil.copy2(s_fi_output, os.path.join(p_con_bd, "updflash_RGH3.bin"))
            self.log_mensagem(f"[SUCESSO] RGH3 Gerado e arquivado na pasta: nand/{id_soberano}/")
            resultado_final = True
        else:
            self.log_mensagem("[ERRO] Falha no Patch RGH3.")
            resultado_final = False

        try: 
            if os.path.exists(r2_temp): os.remove(r2_temp)
            os.remove(os.path.join(p_xe, "data", "nanddump.bin"))
            os.remove(os.path.join(p_xe, "data", "cpukey.txt"))
            os.remove(os.path.join(p_xe, "data", "options.ini"))
            if usou_smc_limpo: os.remove(os.path.join(p_xe, "data", "smc.bin"))
        except: pass
        
        return resultado_final

    def gravar_rgh3_final(self):
        s_fi = os.path.abspath("output/updflash_RGH3.bin")
        
        if not os.path.exists(s_fi): 
            self.log_mensagem("[ERRO] O arquivo RGH3 não existe! Você esqueceu de clicar em '3 Converter RGH3'?")
            return False
        
        if not self.identificar_hardware(): 
            self.log_mensagem("[ERRO CRÍTICO] Gravação abortada por segurança: Console não detectado!")
            self.log_mensagem(">> 1. Verifique se o cabo SPI/SD está bem encaixado na placa.")
            self.log_mensagem(">> 2. Certifique-se de que a fonte de energia está plugada (Standby).")
            self.log_mensagem(">> 3. Desconecte e reconecte o USB do Gravador e tente novamente.")
            return False

        time.sleep(0.5)

        self.log_mensagem(f"[HARDWARE] Gravando: {os.path.basename(s_fi)}...")
        suc, log_cmd = self._executar_comando([os.path.abspath("tools/picoflasher_uart/PicoFlasher_uart.exe"), "-w", s_fi], com_progresso=True)
        
        if not suc: self.log_mensagem(f"[ERRO] A gravação falhou! Log: {log_cmd}")
        return suc

    def gravar_nand_bd_direta(self):
        if not self.caminho_nand_atual: 
            self.log_mensagem("[ERRO] Nenhuma NAND foi carregada para gravação!")
            return False
        
        if not self.identificar_hardware(): 
            self.log_mensagem("[ERRO CRÍTICO] Gravação abortada por segurança: Console não detectado!")
            self.log_mensagem(">> 1. Verifique se o cabo SPI/SD está bem encaixado na placa.")
            self.log_mensagem(">> 2. Certifique-se de que a fonte de energia está plugada (Standby).")
            self.log_mensagem(">> 3. Desconecte e reconecte o USB do Gravador e tente novamente.")
            return False

        time.sleep(0.5)

        self.log_mensagem(f"[HARDWARE] Gravando {os.path.basename(self.caminho_nand_atual)}...")
        suc, log_cmd = self._executar_comando([os.path.abspath("tools/picoflasher_uart/PicoFlasher_uart.exe"), "-w", self.caminho_nand_atual], com_progresso=True)
        
        if not suc: self.log_mensagem(f"[ERRO] A gravação falhou! Log: {log_cmd}")
        return suc
    def _descobrir_placa_pelo_cb(self, caminho):
        try:
            file_size = os.path.getsize(caminho)
            
            if file_size in [49152000, 50331648]:
                return "Corona 4GB"
                
            with open(caminho, "rb") as f:
                raw_data = f.read(0x20000)
                
            if file_size in [17301504, 69206016, 276824064, 553648128] or (file_size % 528 == 0):
                clean_data = b""
                for i in range(0, len(raw_data), 528):
                    clean_data += raw_data[i : i+512]
                dados_header = clean_data
            else:
                dados_header = raw_data

            for i in range(0, len(dados_header) - 4, 2):
                if dados_header[i:i+2] == b"CB":
                    import struct
                    cb_version = struct.unpack(">H", dados_header[i+2:i+4])[0]
                    
                    if 9188 <= cb_version <= 9250: return "Trinity"
                    elif 13121 <= cb_version <= 13200: return "Corona 16MB"
                    elif 4558 <= cb_version <= 4590: return "Falcon"
                    elif 6712 <= cb_version <= 6754: 
                        if file_size > 18000000: return "Jasper BB"
                        return "Jasper"
            
            return None
        except Exception as e:
            return None
        
    def abrir_github(self, event=None):
        webbrowser.open_new("https://github.com/Wellington4363/RGH3-Flasher/")

if __name__ == "__main__":
    RGH3Studio().mainloop()