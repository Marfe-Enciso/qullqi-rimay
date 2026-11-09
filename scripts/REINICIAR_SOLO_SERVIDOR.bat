@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Qullqi Rimay - Servidor (NO CERRAR)
echo  Reiniciando SOLO el servidor (el tunel y la URL de Twilio se mantienen)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /PID %%p /F >nul 2>&1
cd backend
set WHATSAPP_DEMO_AUTOLINK=true
echo  Listo. No necesitas cambiar nada en Twilio. Deja esta ventana abierta.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >> ..\server_log.txt 2>&1
