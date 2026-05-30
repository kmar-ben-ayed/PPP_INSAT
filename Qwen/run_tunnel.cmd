@echo off
setlocal

set "CLOUDFLARED=C:\Program Files (x86)\cloudflared\cloudflared.exe"

if not exist "%CLOUDFLARED%" (
    echo cloudflared.exe not found at "%CLOUDFLARED%".
    exit /b 1
)

"%CLOUDFLARED%" tunnel --url http://127.0.0.1:8000
