@echo off
title BlackSquare Stock CRM V2
cd /d "%~dp0"
echo Installing requirements...
python -m pip install -r requirements.txt
echo.
echo Starting BlackSquare...
python app.py
pause
