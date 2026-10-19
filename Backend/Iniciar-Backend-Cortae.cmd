@echo off
title Cortaê - Backend
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Execute Configurar-Cortae.cmd na pasta principal primeiro.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" runtime_check.py
if errorlevel 1 exit /b 1
"%~dp0.venv\Scripts\python.exe" main.py
exit /b %errorlevel%
