#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
.venv/bin/pip install -q -r requirements.txt
.venv/bin/pip install -q -U yt-dlp
( sleep 2; (xdg-open http://127.0.0.1:5000 || open http://127.0.0.1:5000) >/dev/null 2>&1 ) &
exec .venv/bin/python -m viral web
