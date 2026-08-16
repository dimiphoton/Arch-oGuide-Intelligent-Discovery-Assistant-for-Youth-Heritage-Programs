@echo off
cd /d "%~dp0"
echo Demarrage ArchéoGuide...
echo Ouvre http://localhost:8501 dans ton navigateur
"archoguide-env\Scripts\python.exe" scripts\run_app.py
pause
