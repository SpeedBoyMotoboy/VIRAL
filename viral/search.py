"""Busca de vídeos.

Dois motores:
  * YouTube Data API v3 (se a variável YOUTUBE_API_KEY existir) — rápido, filtra
    categoria/país/idioma direto na fonte e traz inscritos do canal.
  * yt-dlp (sem chave nenhuma) — raspa a busca do YouTube e abre cada vídeo
    para pegar curtidas, comentários, tags e legendas.
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .config import CATEGORIES, FORMATS, PERIODS, YOUTUBE_API_KEY
from . import quota
from .filters import SearchFilters, apply_filters
from .models import Video

log = logging.getLogger(__name__)
Progress = Callable[[str], None]


class SearchError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Parâmetro "sp" da busca do YouTube (protobuf codificado em base64)
# ---------------------------------------------------------------------------
def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def youtube_sp(f: SearchFilters) -> str:
    """Monta o filtro da página de resultados: ordenação + data + tipo vídeo + duração."""
    sort = 2 if f.sort == "recent" else 3  # 2 = data de envio, 3 = contagem de views
    inner = bytearray()
    upload = PERIODS[f.period][2]
    if upload:
        inner += b"\x08" + _varint(upload)
    inner += b"\x10" + _varint(1)  # somente vídeos
    dur = FORMATS[f.format][3]
    if dur:
        inner += b"\x18" + _varint(dur)
    if f.only_creative_commons:
        inner += b"\x30" + _varint(1)
    if f.with_subtitles:
        inner += b"\x28" + _varint(1)
    msg = b"\x08" + _varint(sort) + b"\x12" + _varint(len(inner)) + bytes(inner)
    return base64.b64encode(msg).decode()


def youtube_search_url(f: SearchFilters) -> str:
    q = urllib.parse.urlencode({"search_query": f.full_query, "sp": youtube_sp(f)})
    return f"https://www.youtube.com/results?{q}"


def _effective_query(f: SearchFilters) -> SearchFilters:
    if not f.full_query:
        if f.category:
            f.query = CATEGORIES[f.category][0]
        else:
            raise SearchError("Digite um assunto/palavra-chave ou escolha uma categoria/estilo.")
    return f


# ---------------------------------------------------------------------------
# Motor 1: yt-dlp
# ---------------------------------------------------------------------------
def _ydl_opts(f: SearchFilters | None = None, **extra) -> dict:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "ignoreerrors": True, "socket_timeout": 20}
    if f and f.language:
        opts["extractor_args"] = {"youtube": {"lang": [f.language]}}
    opts.update(extra)
    return opts


def fetch_info(url: str, **opts) -> dict:
    """Metadados completos de qualquer link suportado pelo yt-dlp (YouTube, TikTok, Instagram, X, Kwai...)."""
    import yt_dlp

    with yt_dlp.YoutubeDL(_ydl_opts(**opts)) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise SearchError(f"Não consegui ler o link: {url}")
    return info


def search_ytdlp(f: SearchFilters, progress: Progress | None = None) -> list[Video]:
    import yt_dlp

    progress = progress or (lambda m: None)
    url = youtube_search_url(f)
    flat_n = min(f.max_results * 2, 300)
    progress(f"Buscando no YouTube: “{f.full_query}”…")
    with yt_dlp.YoutubeDL(_ydl_opts(f, extract_flat="in_playlist", playlistend=flat_n)) as ydl:
        res = ydl.extract_info(url, download=False)
    entries = [e for e in (res or {}).get("entries") or [] if e and e.get("id")]
    if not entries:
        raise SearchError("A busca não retornou vídeos (sem resultados ou o YouTube bloqueou a conexão).")

    # pré-filtro barato com o que já vem na listagem
    _, dmin, dmax, _ = FORMATS[f.format]
    pre = []
    for e in entries:
        vc, du = e.get("view_count"), e.get("duration")
        if vc is not None and vc < f.min_views:
            continue
        if du is not None and ((dmin and du < dmin) or (dmax and du > dmax)):
            continue
        pre.append(e)
    pre = pre[: f.max_results]
    progress(f"{len(entries)} encontrados, analisando {len(pre)} em detalhe…")

    done = 0

    def detail(e):
        nonlocal done
        u = e.get("url") if str(e.get("url", "")).startswith("http") else f"https://www.youtube.com/watch?v={e['id']}"
        try:
            info = fetch_info(u, extractor_args=_ydl_opts(f).get("extractor_args", {}))
            v = Video.from_ytdlp(info)
        except Exception as exc:  # vídeo removido, restrito por idade etc.
            log.debug("falha em %s: %s", u, exc)
            v = Video.from_ytdlp(e)
        done += 1
        if done % 5 == 0 or done == len(pre):
            progress(f"Analisados {done}/{len(pre)} vídeos…")
        return v

    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(detail, pre))


# ---------------------------------------------------------------------------
# Motor 2: YouTube Data API v3
# ---------------------------------------------------------------------------
API = "https://www.googleapis.com/youtube/v3/"


def _api(endpoint: str, key: str, **params) -> dict:
    params = {k: v for k, v in params.items() if v not in (None, "")}
    params["key"] = key
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.load(r)
            quota.add(endpoint)
            return data
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e)["error"]["message"]
        except Exception:
            msg = str(e)
        if "quota" in msg.lower():
            msg = "a cota diária grátis da API acabou. Renova de madrugada (~5h, horário de Brasília)."
        raise SearchError(f"API do YouTube: {msg}") from e


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _id_pages(f: SearchFilters, key: str, progress: Progress):
    """Gera listas de até 50 ids por página (a API cobra por chamada, não por item)."""
    token = None
    if not f.full_query:
        progress("Buscando vídeos em alta (sem palavra-chave)…")
        while True:
            r = _api("videos", key, part="id", chart="mostPopular", regionCode=f.region or "BR",
                     videoCategoryId=f.category, maxResults=50, pageToken=token)
            yield [i["id"] for i in r.get("items", [])]
            token = r.get("nextPageToken")
            if not token:
                return
    else:
        progress(f"Buscando na API do YouTube: “{f.full_query}”…")
        after = f.published_after
        order = {"recent": "date"}.get(f.sort, "viewCount")
        dur = {"shorts": "short", "curto": "short", "medio": "medium", "longo": "long"}.get(f.format)
        while True:
            r = _api(
                "search", key, part="id", type="video", q=f.full_query, order=order,
                maxResults=50, pageToken=token,
                publishedAfter=after.strftime("%Y-%m-%dT%H:%M:%SZ") if after else None,
                videoCategoryId=f.category, regionCode=f.region, relevanceLanguage=f.language,
                videoDuration=dur, videoLicense="creativeCommon" if f.only_creative_commons else None,
                videoCaption="closedCaption" if f.with_subtitles else None,
            )
            yield [i["id"]["videoId"] for i in r.get("items", []) if i.get("id", {}).get("videoId")]
            token = r.get("nextPageToken")
            if not token:
                return


def _enrich(ids: list[str], key: str) -> list[Video]:
    names = {k: v[0] for k, v in CATEGORIES.items()}
    videos: list[Video] = []
    by_channel: dict[str, list[Video]] = {}
    for chunk in _chunks(ids, 50):
        r = _api("videos", key, part="snippet,statistics,contentDetails,status", id=",".join(chunk), maxResults=50)
        for item in r.get("items", []):
            v = Video.from_youtube_api(item, names)
            videos.append(v)
            cid = item["snippet"].get("channelId")
            if cid:
                by_channel.setdefault(cid, []).append(v)
    for chunk in _chunks(list(by_channel), 50):
        r = _api("channels", key, part="snippet,statistics", id=",".join(chunk), maxResults=50)
        for item in r.get("items", []):
            subs = item.get("statistics", {}).get("subscriberCount")
            country = item.get("snippet", {}).get("country", "")
            for v in by_channel.get(item["id"], []):
                v.channel_followers = int(subs) if subs else None
                v.channel_country = country
    return videos


def search_api(f: SearchFilters, key: str, progress: Progress | None = None, enough=None) -> list[Video]:
    """Lê páginas de 50 até `enough(videos)` ficar verdadeiro (ou até 4 páginas)."""
    progress = progress or (lambda m: None)
    base = -(-f.max_results // 50)
    max_pages = min(4, base * 3)
    seen: set[str] = set()
    videos: list[Video] = []
    for n, page in enumerate(_id_pages(f, key, progress), start=1):
        new = [i for i in dict.fromkeys(page) if i not in seen]
        seen.update(new)
        videos += _enrich(new, key)
        progress(f"Página {n}: {len(videos)} vídeos lidos…")
        if (enough and enough(videos)) or n >= max_pages:
            break
    return videos


# ---------------------------------------------------------------------------
def search(f: SearchFilters, progress: Progress | None = None, api_key: str | None = None) -> dict:
    key = YOUTUBE_API_KEY if api_key is None else api_key
    if key:
        videos = search_api(f, key, progress, lambda vs: len(apply_filters(vs, f)[0]) >= f.max_results)
        engine = "YouTube Data API"
    else:
        videos = search_ytdlp(_effective_query(f), progress)
        engine = "yt-dlp"
    kept, rejected = apply_filters(videos, f)
    kept = kept[: f.max_results]
    return {
        "engine": engine,
        "query": f.full_query,
        "analyzed": len(videos),
        "rejected": rejected,
        "videos": [v.to_dict() for v in kept],
    }


def analyze_links(urls: list[str], progress: Progress | None = None) -> list[dict]:
    """Metadados (fonte, hashtags, palavras-chave, legendas) de links de qualquer plataforma."""
    progress = progress or (lambda m: None)
    out = []
    for i, u in enumerate(urls, 1):
        progress(f"Lendo link {i}/{len(urls)}…")
        try:
            out.append(Video.from_ytdlp(fetch_info(u)).to_dict())
        except Exception as e:
            out.append({"url": u, "error": str(e)})
    return out
