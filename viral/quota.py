"""Contador local da cota diária da YouTube Data API (10.000 unidades; renova à meia-noite do Pacífico)."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

LIMIT = 10_000
COST = {"search": 100}  # os demais endpoints custam 1
PATH = Path.home() / ".viral_quota.json"
_LOCK = threading.Lock()


def _day() -> str:
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:  # noqa: BLE001 - sem tzdata (Windows): aproxima com UTC-8
        now = datetime.now(timezone(timedelta(hours=-8)))
    return now.strftime("%Y-%m-%d")


def _load() -> dict:
    try:
        d = json.loads(PATH.read_text(encoding="utf-8"))
        if d.get("day") == _day():
            return d
    except Exception:  # noqa: BLE001
        pass
    return {"day": _day(), "used": 0}


def add(endpoint: str) -> None:
    with _LOCK:
        d = _load()
        d["used"] += COST.get(endpoint, 1)
        try:
            PATH.write_text(json.dumps(d), encoding="utf-8")
        except OSError:
            pass


def status() -> dict:
    with _LOCK:
        d = _load()
    return {"used": d["used"], "limit": LIMIT, "left": max(LIMIT - d["used"], 0), "searches_left": max(LIMIT - d["used"], 0) // 100}
