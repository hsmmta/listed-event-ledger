@echo off
cd /d "%~dp0"
python -m app.local
if errorlevel 1 pause
