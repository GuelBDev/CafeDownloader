# ☕ CaféDownloader - MP3 & MP4 Downloader

Uma aplicação web completa, moderna e elegante com tema **Café (Latte, Mocha, Bege Pastel e Tons de Marrom Aconchegante)** para baixar músicas em **MP3** (áudio isolado de alta fidelidade) e vídeos em **MP4** (vídeo com áudio integrado) a partir de links de compartilhamento do **YouTube, Instagram, TikTok, Facebook e Twitter / X**.

---

## ✨ Recursos & Destaques

- ☕ **Design Acolhedor & Sofisticado (Tema Café)**: Paleta rica em bege pastel, marrom mocha, café expresso, vapor de café sutil e micro-interações fluidas.
- 🎵 **Download em MP3**: Extração pura de áudio em 320 kbps (Alta Qualidade), 192 kbps (Padrão) e 128 kbps (Econômico).
- 🎬 **Download em MP4**: Vídeo multiplexado com áudio em 1080p (Full HD), 720p (HD) ou 480p.
- 🌐 **Multiplataforma**: Suporte a **YouTube, Instagram (Reels e Vídeos), TikTok, Facebook e Twitter / X**.
- 📋 **Colar Inteligente**: Botão de colar instantâneo a partir da área de transferência com detecção automática da plataforma.
- 📜 **Histórico de Downloads**: Salva os downloads recentes no navegador para acesso rápido.
- ⚡ **Sem Instalação Complexa de FFmpeg**: Utiliza `imageio-ffmpeg` para fornecer os binários de conversão automaticamente no Windows.
- 🚀 **Bypass Inteligente Anti-Bot & JS Runtime**: Detecta automaticamente Node.js no sistema para resolver desafios JavaScript e mitigar bloqueios do YouTube.
- 🍪 **Suporte Opcional a Cookies**: Permite uso de `cookies.txt` ou variável `YTDLP_COOKIES` para servidores em nuvem ou conexões restritas.
- 🧹 **Limpeza Automática Segura**: Arquivos temporários gerados são limpos automaticamente com tratamento especial para Windows.

---

## 🚀 Como Executar o Projeto

### Opção 1: Via Arquivo `.bat` (Mais Fácil)
Dê um duplo clique no arquivo [`start.bat`](file:///c:/Users/migue/Downloads/Projetos/MP3eMP4Downloader/start.bat). O script instalará as dependências e iniciará o servidor.

### Opção 2: Via Terminal (PowerShell / CMD)
1. Instale as dependências:
   ```bash
   python -m pip install -r requirements.txt
   ```
2. Inicie a aplicação:
   ```bash
   python app.py
   ```
3. Abra seu navegador em:
   👉 **`http://localhost:5000`**

---

## 📁 Estrutura do Projeto

```
MP3eMP4Downloader/
├── app.py                     # Servidor Flask com endpoints /api/info e /api/download
├── requirements.txt           # Dependências (Flask, yt-dlp, imageio-ffmpeg, flask-cors)
├── start.bat                  # Inicializador rápido para Windows
├── README.md                  # Documentação do projeto
├── templates/
│   └── index.html             # Interface principal moderna com tema Café
└── static/
    ├── css/
    │   └── styles.css         # Design System Café completo, variáveis CSS e responsividade
    └── js/
        └── app.js             # Lógica de integração com a API, manipulação do DOM e histórico
```
