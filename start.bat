@echo off
title CafeDownloader - Servidor Local
echo ========================================================
echo   ☕ CafeDownloader - MP3 & MP4 Downloader
echo   YouTube, Instagram, TikTok & Facebook
echo ========================================================
echo.
echo Verificando dependencias...
python -m pip install -r requirements.txt
echo.
echo Iniciando servidor local...
echo Acesse no seu navegador: http://localhost:5000
echo.
python app.py
pause
