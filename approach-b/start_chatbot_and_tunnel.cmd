@echo off
setlocal

start "INSAT Chatbot Server" cmd /k "%~dp0run_server.cmd"
timeout /t 4 /nobreak >nul
start "INSAT Chatbot Tunnel" cmd /k "%~dp0run_tunnel.cmd"
