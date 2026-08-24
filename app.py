import os
import re
import sys
import glob
import time
import shutil
import logging
import threading
import requests
from urllib.parse import urlparse, parse_qs
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
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
except Exception:
    pass

# Configurações do Servidor
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR, static_url_path="/static")
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CafeDownloader")


def get_node_path() -> str | None:
    """Detecta o executável do Node.js no sistema para resolver desafios JavaScript (EJS)."""
    node_on_path = shutil.which("node")
    if node_on_path:
        return node_on_path

    possible_paths = [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\node\node.exe"),
        os.path.expandvars(r"%APPDATA%\npm\node.cmd"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p

    return None


def get_js_runtimes_config() -> dict:
    """Retorna configuração de runtimes JS para o yt-dlp resolver n-sig e bot challenges."""
    node_path = get_node_path()
    if node_path:
        return {"node": {"path": node_path}}
    
    deno_path = shutil.which("deno")
    if deno_path:
        return {"deno": {"path": deno_path}}
    
    bun_path = shutil.which("bun")
    if bun_path:
        return {"bun": {"path": bun_path}}
    
    return {}


def get_cookie_file() -> str | None:
    """Detecta arquivo de cookies se configurado via arquivo local ou variável de ambiente."""
    env_cookies = os.environ.get("YTDLP_COOKIES")
    if env_cookies:
        cookies_path = os.path.join(TEMP_DOWNLOAD_DIR, "yt_cookies.txt")
        try:
            import base64
            try:
                decoded = base64.b64decode(env_cookies.encode("utf-8")).decode("utf-8")
                content = decoded
            except Exception:
                content = env_cookies
            with open(cookies_path, "w", encoding="utf-8") as f:
                f.write(content)
            return cookies_path
        except Exception as e:
            logger.warning(f"Não foi possível salvar cookies da variável de ambiente: {e}")

    root_cookies = os.path.join(BASE_DIR, "cookies.txt")
    if os.path.exists(root_cookies) and os.path.getsize(root_cookies) > 0:
        return root_cookies

    return None


def schedule_file_removal(filepath: str, delay: int = 15):
    """Remove o arquivo temporário após um atraso para evitar conflitos de lock no Windows (WinError 32)."""
    def _remove():
        time.sleep(delay)
        for _ in range(6):
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"Arquivo temporário removido com sucesso: {filepath}")
                break
            except Exception:
                time.sleep(3)

    t = threading.Thread(target=_remove, daemon=True)
    t.start()


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
                        if now - os.path.getmtime(filepath) > 1800:
                            try:
                                os.remove(filepath)
                                logger.info(f"Arquivo temporário antigo removido: {filename}")
                            except Exception as e:
                                logger.warning(f"Erro ao remover arquivo temporário: {e}")
        except Exception as e:
            logger.error(f"Erro na limpeza de arquivos temporários: {e}")
        time.sleep(600)


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


def normalize_youtube_url(url: str) -> str:
    """Normaliza variantes de URLs do YouTube (shorts, youtu.be, mobile) para URL canônica."""
    if "youtube.com" not in url.lower() and "youtu.be" not in url.lower():
        return url
    
    # Extrai o ID do vídeo de 11 caracteres
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[&?]|$)',
        r'(?:embed\/|v\/|shorts\/|live\/)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
    return url


def check_youtube_oembed(url: str):
    """Consulta o endpoint oEmbed oficial do YouTube para validação instantânea."""
    try:
        norm_url = normalize_youtube_url(url)
        r = requests.get(f"https://www.youtube.com/oembed?url={norm_url}&format=json", timeout=5)
        if r.status_code == 200:
            return True, r.json()
        elif r.status_code == 404:
            return False, "Vídeo não encontrado no YouTube (Erro 404). Verifique se o link foi copiado corretamente."
        elif r.status_code in (401, 403):
            return False, "Este vídeo é privado ou requer autorização do autor no YouTube."
        return False, f"Status HTTP {r.status_code} recebido do YouTube."
    except Exception as e:
        logger.warning(f"Falha na consulta oEmbed do YouTube: {e}")
        return None, None


def build_ydl_opts(
    strategy: str = "default",
    download: bool = False,
    outtmpl: str | None = None,
    media_format: str = "mp3",
    quality: str = "320"
) -> dict:
    """Constrói as opções do yt-dlp com estratégia de clientes, JS runtime e headers adequados."""
    player_clients_map = {
        "default": None,  # Padrão nativo do yt-dlp com Node.js runtime
        "android_vr": ["android_vr", "android"],
        "android_ios": ["android", "ios"],
        "tv_embedded": ["tv_embedded", "android"],
        "web": ["web", "mweb"]
    }

    selected_clients = player_clients_map.get(strategy, None)

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Fetch-Mode": "navigate",
        }
    }

    extractor_args = {
        "tiktok": {
            "app_version": ["current"]
        }
    }
    if selected_clients:
        extractor_args["youtube"] = {
            "player_client": selected_clients
        }
    opts["extractor_args"] = extractor_args

    js_runtimes = get_js_runtimes_config()
    if js_runtimes:
        opts["js_runtimes"] = js_runtimes

    cookie_file = get_cookie_file()
    if cookie_file:
        opts["cookiefile"] = cookie_file

    if os.path.exists(FFMPEG_PATH):
        opts["ffmpeg_location"] = FFMPEG_PATH

    if not download:
        opts["skip_download"] = True
        opts["extract_flat"] = False
        return opts

    # Configurações de Download
    if outtmpl:
        opts["outtmpl"] = outtmpl

    if media_format == "mp3":
        audio_quality = "320" if quality == "320" else ("128" if quality == "128" else "192")
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_quality,
            }],
        })
    else:
        # MP4
        if quality == "1080":
            fmt = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best"
        elif quality == "720":
            fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo+bestaudio/best"
        elif quality == "480":
            fmt = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/bestvideo+bestaudio/best"
        else:
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"

        opts.update({
            "format": fmt,
            "merge_output_format": "mp4",
        })
        if os.path.exists(FFMPEG_PATH):
            opts["postprocessors"] = [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4"
            }]

    return opts


def extract_info_with_fallback(
    url: str,
    download: bool = False,
    outtmpl: str | None = None,
    media_format: str = "mp3",
    quality: str = "320"
):
    """Executa extração ou download tentando estratégias de fallback caso YouTube bloqueie ou desafie a requisição."""
    clean_url = normalize_youtube_url(url)
    is_yt = "youtube.com" in clean_url.lower() or "youtu.be" in clean_url.lower()
    strategies = ["default", "android_vr", "android_ios", "tv_embedded"] if is_yt else ["default"]
    last_error = None

    for idx, strategy in enumerate(strategies):
        try:
            ydl_opts = build_ydl_opts(
                strategy=strategy,
                download=download,
                outtmpl=outtmpl,
                media_format=media_format,
                quality=quality
            )
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=download)
                return info
        except yt_dlp.utils.DownloadError as e:
            last_error = e
            err_str = str(e)
            logger.warning(f"Tentativa {idx + 1}/{len(strategies)} ('{strategy}') falhou: {err_str}")

            err_lower = err_str.lower()
            if any(term in err_lower for term in [
                "this video is unavailable",
                "video unavailable",
                "does not exist",
                "private video",
                "removed by the user",
                "is not a valid url"
            ]):
                raise e
        except Exception as e:
            last_error = e
            logger.warning(f"Erro inesperado na estratégia '{strategy}': {e}")

    if last_error:
        raise last_error
    raise RuntimeError("Não foi possível processar o link com as estratégias disponíveis.")


def parse_friendly_error(error_msg: str) -> str:
    """Converte mensagens técnicas de erro do yt-dlp em orientações claras para o usuário."""
    err_lower = error_msg.lower()

    if "private video" in err_lower or "vídeo privado" in err_lower:
        return "Este vídeo é privado e requer autorização do autor para ser acessado."
    elif any(term in err_lower for term in [
        "this video is unavailable",
        "video unavailable",
        "does not exist",
        "not found",
        "removed by the user",
        "is not a valid url",
        "404"
    ]):
        return "Vídeo indisponível ou excluído. Verifique se o link foi copiado corretamente."
    elif "age" in err_lower and ("restrict" in err_lower or "gate" in err_lower):
        return "Este vídeo possui restrição de idade imposta pela plataforma."
    elif "sign in to confirm you’re not a bot" in err_lower or "confirm you're not a bot" in err_lower:
        return "O YouTube bloqueou temporariamente a requisição por suspeita de bot. Dica: Tente novamente em alguns instantes."
    elif "sign in" in err_lower or "login" in err_lower:
        return "A plataforma está exigindo login para acessar este conteúdo específico."
    elif "requested format is not available" in err_lower:
        return "O formato selecionado não está disponível para esta mídia. Tente outra opção de qualidade."
    elif "http error 429" in err_lower or "too many requests" in err_lower:
        return "Muitas requisições simultâneas. Aguarde alguns segundos antes de tentar novamente."
    elif "copyright" in err_lower or "blocked" in err_lower:
        return "Este conteúdo foi bloqueado por reivindicação de direitos autorais ou restrição geográfica."
    return "Não foi possível carregar as informações do vídeo. Verifique se o link está correto e público."


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health_check():
    node_path = get_node_path()
    cookie_file = get_cookie_file()
    return jsonify({
        "status": "healthy",
        "ffmpeg_available": bool(FFMPEG_PATH and os.path.exists(FFMPEG_PATH)),
        "ffmpeg_path": FFMPEG_PATH,
        "node_available": bool(node_path),
        "node_path": node_path,
        "cookies_active": bool(cookie_file),
        "ytdlp_version": yt_dlp.version.__version__
    })


@app.route("/api/info", methods=["POST"])
def get_video_info():
    """Extrai informações e metadados rápidos do link fornecido ou busca por nome de música."""
    data = request.get_json() or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"success": False, "error": "Por favor, insira um link ou nome de música."}), 400

    # Auto-adiciona https:// caso o usuário tenha colado sem protocolo
    if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("ytsearch"):
        low = url.lower()
        if (
            low.startswith("youtube.com")
            or low.startswith("youtu.be")
            or low.startswith("instagram.com")
            or low.startswith("tiktok.com")
            or low.startswith("facebook.com")
            or low.startswith("fb.watch")
            or low.startswith("fb.com")
            or low.startswith("twitter.com")
            or low.startswith("x.com")
        ):
            url = f"https://{url}"

    parsed = urlparse(url)
    is_search = not bool(parsed.scheme and parsed.netloc)

    if is_search:
        target_query = f"ytsearch1:{url}"
        platform = "youtube"
    else:
        target_query = url
        platform = detect_platform(url)

        # Verificação rápida prévia para o YouTube via oEmbed oficial
        if platform == "youtube":
            ok, oembed_data = check_youtube_oembed(url)
            if ok is False and isinstance(oembed_data, str):
                return jsonify({"success": False, "error": oembed_data}), 404

    try:
        info = extract_info_with_fallback(target_query, download=False)
        if not info:
            return jsonify({"success": False, "error": "Não foi possível obter dados para este vídeo."}), 404

        if "entries" in info and info["entries"]:
            info = info["entries"][0]

        title = info.get("title") or "Vídeo sem título"
        uploader = info.get("uploader") or info.get("channel") or info.get("creator") or "Autor desconhecido"
        duration = info.get("duration")
        thumbnail = info.get("thumbnail") or ""
        video_id = info.get("id") or str(int(time.time()))
        final_url = info.get("webpage_url") or url

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
                "original_url": final_url
            }
        })

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.error(f"Erro de extração yt-dlp: {error_msg}")
        friendly_msg = parse_friendly_error(error_msg)
        return jsonify({"success": False, "error": friendly_msg}), 400
    except Exception as e:
        logger.exception("Erro inesperado em /api/info")
        return jsonify({"success": False, "error": f"Erro interno ao processar link: {str(e)}"}), 500


@app.route("/api/download", methods=["POST"])
def download_media():
    """Baixa e converte a mídia para MP3 ou MP4 com estratégia de resiliência e entrega segura."""
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    media_format = data.get("format", "mp3").lower()  # 'mp3' ou 'mp4'
    quality = data.get("quality", "best")              # '320', '192', '128', '1080', '720', 'best'

    if not url:
        return jsonify({"success": False, "error": "URL obrigatória."}), 400

    platform = detect_platform(url)
    if platform == "youtube":
        ok, oembed_data = check_youtube_oembed(url)
        if ok is False and isinstance(oembed_data, str):
            return jsonify({"success": False, "error": oembed_data}), 404

    unique_id = f"{int(time.time() * 1000)}_{os.getpid()}"
    output_template = os.path.join(TEMP_DOWNLOAD_DIR, f"{unique_id}_%(title).100s.%(ext)s")

    try:
        logger.info(f"Iniciando download ({media_format.upper()} - {quality}): {url}")
        info = extract_info_with_fallback(
            url=url,
            download=True,
            outtmpl=output_template,
            media_format=media_format,
            quality=quality
        )

        if "entries" in info and info["entries"]:
            info = info["entries"][0]

        title = info.get("title") or "download"
        safe_title = sanitize_filename(title)
        final_ext = "mp3" if media_format == "mp3" else "mp4"

        # Localiza o arquivo gerado correspondente ao unique_id
        pattern = os.path.join(TEMP_DOWNLOAD_DIR, f"{unique_id}_*")
        matching_files = glob.glob(pattern)

        if not matching_files:
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

        # Agenda a remoção limpa do arquivo após a entrega para evitar WinError 32
        schedule_file_removal(target_file, delay=15)

        return send_file(
            target_file,
            as_attachment=True,
            download_name=download_filename,
            mimetype=mimetype
        )

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.error(f"Erro durante download do yt-dlp: {error_msg}")
        friendly_msg = parse_friendly_error(error_msg)
        return jsonify({"success": False, "error": friendly_msg}), 400
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
