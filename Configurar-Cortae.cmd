@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Configurar-Cortae.ps1"
if errorlevel 1 pause
