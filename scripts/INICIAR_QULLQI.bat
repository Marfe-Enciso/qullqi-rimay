@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Qullqi Rimay + WhatsApp (NO CERRAR)
echo.
echo  ==============================================================
echo    QULLQI RIMAY - Servidor + URL para Twilio Sandbox
echo  ==============================================================
echo.
if not exist cloudflared.exe (
  echo  Descargando cloudflared ^(una sola vez, ~60 MB^)...
  curl -L -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
)
echo  [1/4] Cerrando servidor y tunel anteriores...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /PID %%p /F >nul 2>&1
taskkill /IM cloudflared.exe /F >nul 2>&1
if exist tunnel_log.txt del tunnel_log.txt
if exist webhook_url.txt del webhook_url.txt
echo  [2/4] Abriendo tunel publico (espera 10-30 segundos)...
start "Tunel Qullqi (NO CERRAR)" /min cloudflared.exe tunnel --protocol http2 --url http://localhost:8000 --logfile tunnel_log.txt
python poner_webhook.py
if errorlevel 1 (
  echo  Hubo un problema con el tunel. Avisale a Claude.
  pause
  exit /b 1
)
echo  [3/4] URL copiada al portapapeles. Abriendo Twilio Sandbox settings...
type webhook_url.txt | clip
start "" "https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox"
echo.
echo  EN TWILIO: pega (Ctrl+V) en "When a message comes in", metodo POST, y Save.
echo.
echo  [4/4] Encendiendo la aplicacion en http://localhost:8000 ...
start "" cmd /c "timeout /t 6 >nul && start http://localhost:8000"
cd backend
set WHATSAPP_DEMO_AUTOLINK=true
echo  Listo. Deja ESTA ventana y la del tunel abiertas durante la demo.
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > ..\server_log.txt 2>&1
