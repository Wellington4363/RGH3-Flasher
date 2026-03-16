Desenvolvido por: Wellington4363 (W.Tech SP) (wde4363)

Data de Lançamento: 12/03/2026

🛠 Sobre o Projeto
O RGH3 Flasher é uma ferramenta completa para técnicos em eletrônica, projetada para automatizar e simplificar o processo de conversão de consoles Xbox 360 para o método RGH 3.0. O software gerencia desde a leitura da NAND original até a injeção de patches avançados e gravação final, eliminando processos manuais e reduzindo riscos na bancada.

✨ Principais Recursos
Integração com uma versão customizada do PicoFlasher: Adicionada a leitura de CPUKEY atrvés da porta UART e com controle total do hardware Raspberry Pi Pico para leitura e gravação em alta velocidade.

Decriptação Nativa de KV: Extração e verificação automática de CPU Key, DVD Key e informações da placa diretamente do dump.

Monitor UART em Tempo Real: Escuta automática do XeLL para captura instantânea da CPU Key.

Tuning Térmico: Injeção automática de alvos de temperatura (65/63/59) para preservação do hardware.

Patches Avançados: Suporte a XL Storage (>2TB), NoIntMU (Reparo de 4GB), NoFCRT, e muito mais.

Interface Moderna: Desenvolvida em CustomTkinter com feedback visual e sonoro de processos.

📁 Estrutura de Pastas
Para o funcionamento correto, o executável deve estar acompanhado da pasta tools/, contendo os binários do xeBuild, PicoFlasher_uart e recursos de mídia.

⚠️ Importante:
Dentro da pasta Essencial, disponibilizamos o arquivo picoflasher_uart.uf2 com integração para leitura UART. Este firmware deve ser instalado no seu Raspberry Pi Pico para que todas as funções do software funcionem corretamente.

Link para Download RGH3 Flasher v.1.0
https://drive.google.com/file/d/1NuqiP4pfGEhTMKB6dTUuEWZyy_vRVuKb/view?usp=sharing
