import os
import re
import sys
import glob
import time
import shutil
import logging
import threading
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, after_this_request
from flask_cors import CORS

try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = "ffmpeg"

import yt_dlp

# Configuração de encoding para terminal Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Identificação de ambiente (Local vs Vercel Serverless)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CURRENT_DIR) == "api":
    BASE_DIR = os.path.dirname(CURRENT_DIR)
else:
    BASE_DIR = CURRENT_DIR

TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# No Vercel/Lambda apenas a pasta /tmp é gravável
if IS_VERCEL:
    TEMP_DOWNLOAD_DIR = "/tmp/temp_downloads"
else:
    TEMP_DOWNLOAD_DIR = os.path.join(BASE_DIR, "temp_downloads")

try:
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
except Exception as e:
    pass

# Configurações do Servidor
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR, static_url_path="/static")
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CafeDownloader")


@app.route("/static/<path:filename>")
def serve_static(filename):
    """Garante entrega confiável de arquivos CSS/JS na Vercel e localmente."""
    return send_from_directory(STATIC_DIR, filename)


@app.route("/favicon.ico")
def favicon():
    """Entrega o favicon de café diretamente na raiz."""
    return send_from_directory(STATIC_DIR, "favicon.svg", mimetype="image/svg+xml")


def cleanup_old_files():
    """Limpa arquivos temporários com mais de 30 minutos."""
    while True:
        try:
            now = time.time()
            if os.path.exists(TEMP_DOWNLOAD_DIR):
                for filename in os.listdir(TEMP_DOWNLOAD_DIR):
                    filepath = os.path.join(TEMP_DOWNLOAD_DIR, filename)
                    if os.path.isfile(filepath):
                        # Se o arquivo foi criado há mais de 30 minutos (1800 segundos)
                        if now - os.path.getmtime(filepath) > 1800:
                            try:
                                os.remove(filepath)
                                logger.info(f"Arquivo temporário antigo removido: {filename}")
                            except Exception as e:
                                logger.warning(f"Erro ao remover arquivo temporário: {e}")
        except Exception as e:
            logger.error(f"Erro na limpeza de arquivos temporários: {e}")
        time.sleep(600)  # roda a cada 10 minutos


# Inicia thread de limpeza periódica apenas em ambiente persistente (não-serverless)
if not IS_VERCEL:
    cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
    cleanup_thread.start()


def sanitize_filename(name: str) -> str:
    """Sanitiza o nome do arquivo para evitar caracteres inválidos no SO."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.strip()
    return clean if clean else "download"


def format_duration(seconds) -> str:
    """Formata segundos em MM:SS ou HH:MM:SS."""
    if not seconds or not isinstance(seconds, (int, float)):
        return "--:--"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def detect_platform(url: str) -> str:
    """Identifica a plataforma com base no domínio."""
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "instagram.com" in url_lower:
        return "instagram"
    elif "tiktok.com" in url_lower:
        return "tiktok"
    elif "facebook.com" in url_lower or "fb.watch" in url_lower or "fb.com" in url_lower:
        return "facebook"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "twitter"
    return "other"


def get_base_ydl_opts():
    """Retorna opções base com suporte a JS Runtime (Node.js) e clientes móveis para evitar 403."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android", "mweb"]
            },
            "tiktok": {
                "app_version": ["current"]
            }
        },
        "js_runtimes": {"node": {}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
        }
    }
    if os.path.exists(FFMPEG_PATH):
        opts["ffmpeg_location"] = FFMPEG_PATH
    return opts


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "ffmpeg_available": bool(FFMPEG_PATH and os.path.exists(FFMPEG_PATH)),
        "ffmpeg_path": FFMPEG_PATH,
        "ytdlp_version": yt_dlp.version.__version__
    })


@app.route("/api/info", methods=["POST"])
def get_video_info():
    """Extrai informações e metadados rápidos do link fornecido."""
    data = request.get_json() or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"success": False, "error": "Por favor, insira um link válido."}), 400

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return jsonify({"success": False, "error": "Link inválido. Certifique-se de incluir http:// ou https://"}), 400

    ydl_opts = get_base_ydl_opts()
    ydl_opts.update({
        "skip_download": True,
        "extract_flat": False,
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return jsonify({"success": False, "error": "Não foi possível obter dados para este vídeo."}), 404

            # Trata caso de playlist retornada como primeiro item
            if "entries" in info and info["entries"]:
                info = info["entries"][0]

            title = info.get("title") or "Vídeo sem título"
            uploader = info.get("uploader") or info.get("channel") or info.get("creator") or "Autor desconhecido"
            duration = info.get("duration")
            thumbnail = info.get("thumbnail") or ""
            video_id = info.get("id") or str(int(time.time()))
            platform = detect_platform(url)

            return jsonify({
                "success": True,
                "data": {
                    "id": video_id,
                    "title": title,
                    "author": uploader,
                    "duration": duration,
                    "duration_formatted": format_duration(duration),
                    "thumbnail": thumbnail,
                    "platform": platform,
                    "original_url": url
                }
            })

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.error(f"Erro de extração yt-dlp: {error_msg}")
        if "Private video" in error_msg:
            msg = "Este vídeo é privado ou requer autenticação."
        elif "Video unavailable" in error_msg:
            msg = "Vídeo indisponível ou excluído."
        elif "Sign in" in error_msg:
            msg = "A plataforma está exigindo login para acessar este conteúdo."
        else:
            msg = "Não foi possível carregar as informações do vídeo. Verifique se o link está correto."
        return jsonify({"success": False, "error": msg}), 400
    except Exception as e:
        logger.exception("Erro inesperado em /api/info")
        return jsonify({"success": False, "error": f"Erro interno ao processar link: {str(e)}"}), 500


@app.route("/api/download", methods=["POST"])
def download_media():
    """Baixa e converte a mídia para MP3 ou MP4."""
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    media_format = data.get("format", "mp3").lower()  # 'mp3' ou 'mp4'
    quality = data.get("quality", "best")              # '320', '192', '128', '1080', '720', 'best'

    if not url:
        return jsonify({"success": False, "error": "URL obrigatória."}), 400

    unique_id = f"{int(time.time() * 1000)}_{os.getpid()}"
    output_template = os.path.join(TEMP_DOWNLOAD_DIR, f"{unique_id}_%(title).100s.%(ext)s")

    ydl_opts = get_base_ydl_opts()
    ydl_opts["outtmpl"] = output_template

    if media_format == "mp3":
        # Configuração de extração para MP3 puro
        audio_quality = "320" if quality == "320" else ("128" if quality == "128" else "192")
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_quality,
            }],
        })
    else:
        # Configuração para MP4 com áudio integrado
        if quality == "1080":
            fmt = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best"
        elif quality == "720":
            fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo+bestaudio/best"
        elif quality == "480":
            fmt = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/bestvideo+bestaudio/best"
        else:
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"

        ydl_opts.update({
            "format": fmt,
            "merge_output_format": "mp4",
        })
        if os.path.exists(FFMPEG_PATH):
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4"
            }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Iniciando download ({media_format.upper()} - {quality}): {url}")
            info = ydl.extract_info(url, download=True)
            if "entries" in info and info["entries"]:
                info = info["entries"][0]

            title = info.get("title") or "download"
            safe_title = sanitize_filename(title)
            final_ext = "mp3" if media_format == "mp3" else "mp4"

            # Localiza o arquivo gerado correspondente ao unique_id
            pattern = os.path.join(TEMP_DOWNLOAD_DIR, f"{unique_id}_*")
            matching_files = glob.glob(pattern)

            if not matching_files:
                # Tenta buscar por qualquer arquivo com o prefixo
                matching_files = [
                    os.path.join(TEMP_DOWNLOAD_DIR, f)
                    for f in os.listdir(TEMP_DOWNLOAD_DIR)
                    if f.startswith(unique_id)
                ]

            if not matching_files:
                raise FileNotFoundError("Arquivo baixado não foi encontrado no servidor.")

            target_file = matching_files[0]
            download_filename = f"{safe_title}.{final_ext}"
            mimetype = "audio/mpeg" if media_format == "mp3" else "video/mp4"

            @after_this_request
            def remove_file(response):
                try:
                    if os.path.exists(target_file):
                        os.remove(target_file)
                        logger.info(f"Arquivo temporário entregue e removido com sucesso: {target_file}")
                except Exception as ex:
                    logger.warning(f"Erro ao remover arquivo temporário após envio: {ex}")
                return response

            return send_file(
                target_file,
                as_attachment=True,
                download_name=download_filename,
                mimetype=mimetype
            )

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Erro durante download do yt-dlp: {e}")
        return jsonify({"success": False, "error": f"Erro ao baixar mídia: {str(e)}"}), 400
    except Exception as e:
        logger.exception("Erro interno durante o download")
        return jsonify({"success": False, "error": f"Falha no processamento do arquivo: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    try:
        print(f"\n☕ CafeDownloader inicializado com sucesso!")
        print(f"☕ Acesse no seu navegador: http://localhost:{port}\n")
    except Exception:
        print(f"\nCafeDownloader inicializado com sucesso!")
        print(f"Acesse no seu navegador: http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
