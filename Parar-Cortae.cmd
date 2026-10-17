@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Parar-Cortae.ps1"
if errorlevel 1 pause
