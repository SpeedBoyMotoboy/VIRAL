"""Interface web (Flask). Rode:  python -m viral.web  e abra http://127.0.0.1:5000"""
from __future__ import annotations

import hmac
import os
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request, send_from_directory

from . import config
from .filters import SearchFilters
from .media import QUALITIES, download
from .search import SearchError, analyze_links, search

app = Flask(__name__)
pool = ThreadPoolExecutor(max_workers=3)

# Login opcional (HTTP Basic). Ativo só se VIRAL_USER e VIRAL_PASS estiverem definidos,
# ex.: na VPS, onde o app fica exposto na internet.
_AUTH_USER = os.environ.get("VIRAL_USER", "").strip()
_AUTH_PASS = os.environ.get("VIRAL_PASS", "").strip()


@app.before_request
def _exigir_login():
    if not (_AUTH_USER and _AUTH_PASS):
        return None
    auth = request.authorization
    if auth and hmac.compare_digest(auth.username or "", _AUTH_USER) \
            and hmac.compare_digest(auth.password or "", _AUTH_PASS):
        return None
    return Response("Login necessário.", 401, {"WWW-Authenticate": 'Basic realm="VIRAL"'})
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def _new_job(kind: str, label: str) -> dict:
    job = {"id": uuid.uuid4().hex[:12], "kind": kind, "label": label, "status": "running",
           "message": "Na fila…", "percent": None, "result": None, "error": None, "created": time.time()}
    with LOCK:
        JOBS[job["id"]] = job
        # guarda só os 200 mais recentes
        for old in sorted(JOBS.values(), key=lambda j: j["created"])[:-200]:
            JOBS.pop(old["id"], None)
    return job


def _run(job: dict, fn, *args, **kwargs):
    def task():
        try:
            job["result"] = fn(*args, **kwargs)
            job["status"] = "done"
        except SearchError as e:
            job["status"], job["error"] = "error", str(e)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            job["status"], job["error"] = "error", str(e).replace("ERROR: ", "")

    pool.submit(task)
    return jsonify({"job": job["id"]})


@app.get("/")
def index():
    return render_template(
        "index.html",
        periods={k: v[0] for k, v in config.PERIODS.items()},
        categories={k: v[0] for k, v in config.CATEGORIES.items()},
        styles={k: v[0] for k, v in config.STYLES.items()},
        formats={k: v[0] for k, v in config.FORMATS.items()},
        sorts=config.SORTS,
        languages=config.LANGUAGES,
        regions=config.REGIONS,
        qualities=QUALITIES,
        engine="YouTube Data API" if config.YOUTUBE_API_KEY else "yt-dlp (sem chave de API)",
    )


@app.post("/api/search")
def api_search():
    f = SearchFilters.from_dict(request.get_json(force=True) or {})
    job = _new_job("search", f.full_query or "em alta")

    def progress(msg):
        job["message"] = msg

    return _run(job, search, f, progress)


@app.post("/api/links")
def api_links():
    raw = (request.get_json(force=True) or {}).get("urls", "")
    urls = [u.strip() for u in (raw if isinstance(raw, list) else str(raw).split()) if u.strip().startswith("http")]
    if not urls:
        return jsonify({"error": "Cole pelo menos um link (http…)."}), 400
    job = _new_job("links", f"{len(urls)} link(s)")
    return _run(job, analyze_links, urls[:50], lambda m: job.__setitem__("message", m))


@app.post("/api/download")
def api_download():
    d = request.get_json(force=True) or {}
    url = str(d.get("url", "")).strip()
    if not url.startswith("http"):
        return jsonify({"error": "Link inválido."}), 400
    job = _new_job("download", d.get("title") or url)

    def progress(msg, pct=None):
        job["message"] = msg
        if pct is not None:
            job["percent"] = round(pct, 1)

    def run():
        return download(
            url,
            quality=d.get("quality", "best") if d.get("quality") in QUALITIES else "best",
            subtitles=bool(d.get("subtitles", True)),
            sub_lang=str(d.get("sub_lang", "")),
            translate_to=str(d.get("translate_to", "")),
            progress=progress,
        ).to_dict()

    return _run(job, run)


@app.get("/api/jobs/<job_id>")
def api_job(job_id):
    job = JOBS.get(job_id)
    if not job:
        abort(404)
    return jsonify(job)


@app.get("/api/jobs")
def api_jobs():
    jobs = sorted(JOBS.values(), key=lambda j: j["created"], reverse=True)
    return jsonify([{k: j[k] for k in ("id", "kind", "label", "status", "message", "percent", "error")}
                    | {"result": j["result"] if j["kind"] == "download" else None} for j in jobs if j["kind"] == "download"])


@app.get("/files/<path:path>")
def files(path):
    base = config.DOWNLOAD_DIR
    target = (base / path).resolve()
    if not target.is_relative_to(base) or not target.is_file():
        abort(404)
    return send_from_directory(base, path, as_attachment=request.args.get("dl") == "1")


def main():
    config.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    host = os.environ.get("VIRAL_HOST", "127.0.0.1")
    port = int(os.environ.get("VIRAL_PORT", "5000"))
    print(f"\n  VIRAL rodando em http://{host}:{port}\n  Downloads em: {config.DOWNLOAD_DIR}\n")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
