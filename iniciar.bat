@echo off
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\python -m pip install -r requirements.txt
)
.venv\Scripts\python -m pip install -U yt-dlp >nul
start "" http://127.0.0.1:5000
.venv\Scripts\python -m viral web
pause
