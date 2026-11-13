@echo off
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\python -m pip install -r requirements.txt
)
.venv\Scripts\python -m pip install -q -r requirements.txt
.venv\Scripts\python -m pip install -q -U yt-dlp
start "" http://127.0.0.1:5000
.venv\Scripts\python -m viral web
pause
