"""Download de vídeo/áudio/legendas + ficha do vídeo (fonte, hashtags, palavras-chave)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import DOWNLOAD_DIR
from .models import Video
from .translate import translate_file

Progress = Callable[[str, float | None], None]

QUALITIES = {
    "best": "Melhor disponível",
    "1080": "1080p",
    "720": "720p",
    "480": "480p",
    "audio": "Somente áudio (MP3)",
    "none": "Não baixar vídeo (só legendas/ficha)",
}


def _format_for(quality: str) -> str:
    if quality == "audio":
        return "bestaudio/best"
    if quality in ("1080", "720", "480"):
        return f"bv*[height<={quality}][ext=mp4]+ba[ext=m4a]/bv*[height<={quality}]+ba/b[height<={quality}]/b"
    return "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b"


def safe_name(text: str, limit: int = 80) -> str:
    text = re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", text).strip()
    return re.sub(r"\s+", " ", text)[:limit].strip() or "video"


@dataclass
class DownloadResult:
    folder: Path
    files: list[Path] = field(default_factory=list)
    video: Video | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self, base: Path = DOWNLOAD_DIR) -> dict:
        def rel(p: Path) -> str:
            try:
                return str(p.relative_to(base))
            except ValueError:
                return str(p)

        return {
            "folder": rel(self.folder),
            "files": [rel(p) for p in self.files],
            "video": self.video.to_dict() if self.video else None,
            "warnings": self.warnings,
        }


def _n(x) -> str:
    return "?" if x is None else str(x)


def write_sheet(v: Video, folder: Path, translated_title: str = "") -> Path:
    """Ficha .txt com tudo que é útil para repostar/creditar."""
    lines = [
        f"TÍTULO: {v.title}",
        *( [f"TÍTULO TRADUZIDO: {translated_title}"] if translated_title else [] ),
        f"FONTE / CRÉDITO: {v.source_credit()}",
        f"LINK: {v.url}",
        f"CANAL: {v.channel} {v.channel_url}".rstrip(),
        f"PLATAFORMA: {v.platform}",
        f"PUBLICADO EM: {v.published_at:%d/%m/%Y %H:%M} UTC" if v.published_at else "PUBLICADO EM: ?",
        f"DURAÇÃO: {v.duration or '?'} s",
        f"VIEWS: {_n(v.views)}  CURTIDAS: {_n(v.likes)}  COMENTÁRIOS: {_n(v.comments)}",
        f"ENGAJAMENTO: {_n(v.engagement)}%  VIEWS/HORA: {_n(v.views_per_hour)}  SCORE VIRAL: {v.viral_score}",
        f"CATEGORIA: {v.category}",
        f"LICENÇA: {v.license or 'não informada'}",
        "",
        "HASHTAGS:",
        " ".join(v.hashtags) or "(nenhuma)",
        "",
        "PALAVRAS-CHAVE / TAGS:",
        ", ".join(v.keywords) or "(nenhuma)",
        "",
        "DESCRIÇÃO:",
        v.description,
    ]
    path = folder / "ficha.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    (folder / "ficha.json").write_text(json.dumps(v.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def pick_sub_lang(info: dict, wanted: str) -> tuple[str | None, bool]:
    """Escolhe o idioma de legenda: o pedido, senão o original do vídeo, senão inglês.

    Retorna (código, é_automática).
    """
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    original = (info.get("language") or "").split("-")[0]
    candidates = [c for c in (wanted, original, "en", "pt", "es") if c]

    def find(pool: dict, code: str) -> str | None:
        if code in pool:
            return code
        for k in pool:
            if k.split("-")[0] == code and "orig" not in k:
                return k
        for k in pool:
            if k.split("-")[0] == code:
                return k
        return None

    for code in candidates:
        if hit := find(manual, code):
            return hit, False
    for code in candidates:
        # legenda automática "-orig" é a transcrição real; as outras são traduções automáticas
        if hit := find(auto, f"{code}-orig") or find(auto, code):
            return hit, True
    if manual:
        return next(iter(manual)), False
    return None, False


def download(
    url: str,
    quality: str = "best",
    subtitles: bool = True,
    sub_lang: str = "",
    translate_to: str = "",
    translate_title: bool = True,
    out_dir: Path = DOWNLOAD_DIR,
    progress: Progress | None = None,
) -> DownloadResult:
    import yt_dlp

    progress = progress or (lambda m, p=None: None)
    progress("Lendo informações do vídeo…", 0)
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("Vídeo indisponível ou link inválido.")
    if info.get("_type") == "playlist":
        entries = [e for e in info.get("entries") or [] if e]
        if not entries:
            raise RuntimeError("Playlist vazia.")
        info = entries[0]

    v = Video.from_ytdlp(info)
    folder = Path(out_dir) / f"{safe_name(v.title, 60)} [{v.id}]"
    folder.mkdir(parents=True, exist_ok=True)
    result = DownloadResult(folder=folder, video=v)

    if not v.downloadable and quality != "none":
        result.warnings.append(f"Vídeo marcado como não baixável ({v.availability}). Tentando mesmo assim…")

    sub_code, is_auto = (None, False)
    if subtitles:
        sub_code, is_auto = pick_sub_lang(info, sub_lang)
        if not sub_code:
            result.warnings.append("Este vídeo não tem legendas disponíveis.")

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            pct = (d.get("downloaded_bytes", 0) / total * 100) if total else None
            progress(f"Baixando… {d.get('_percent_str', '').strip()} {d.get('_speed_str', '').strip()}", pct)
        elif d.get("status") == "finished":
            progress("Processando arquivo…", 100)

    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": str(folder / "video.%(ext)s"),
        "noprogress": True,
        "progress_hooks": [hook],
        "writethumbnail": True,
        "restrictfilenames": False,
        "postprocessors": [{"key": "FFmpegThumbnailsConvertor", "format": "jpg"}],
    }
    if quality == "none":
        opts["skip_download"] = True
    else:
        opts["format"] = _format_for(quality)
        if quality == "audio":
            opts["postprocessors"].append({"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"})
        else:
            opts["merge_output_format"] = "mp4"
    if sub_code:
        opts.update({
            "writesubtitles": not is_auto,
            "writeautomaticsub": is_auto,
            "subtitleslangs": [sub_code],
            "subtitlesformat": "srt/vtt/best",
        })
        opts["postprocessors"].append({"key": "FFmpegSubtitlesConvertor", "format": "srt"})

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.process_ie_result(info, download=True)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).replace("ERROR: ", "")
        if quality != "none":
            result.warnings.append(f"Download do vídeo não disponível: {msg}")
            # ainda tenta salvar legenda e ficha
            if sub_code:
                with yt_dlp.YoutubeDL({**opts, "skip_download": True}) as ydl:
                    ydl.process_ie_result(info, download=True)
        else:
            raise

    # legendas: renomeia "video.en-orig.srt" -> "legenda.en.srt"
    for sub in folder.glob("video.*.srt"):
        lang = sub.suffixes[-2].lstrip(".").replace("-orig", "")
        target = folder / f"legenda.{lang}.srt"
        sub.replace(target)
    for sub in folder.glob("video.*.vtt"):
        lang = sub.suffixes[-2].lstrip(".").replace("-orig", "")
        sub.replace(folder / f"legenda.{lang}.vtt")

    translated_title = ""
    if translate_to:
        subs = sorted(folder.glob("legenda.*.srt")) or sorted(folder.glob("legenda.*.vtt"))
        src = next((s for s in subs if not s.name.endswith(f".{translate_to}.srt")), None)
        if src:
            progress(f"Traduzindo legenda para {translate_to}…", None)
            try:
                translate_file(src, translate_to, progress=lambda m: progress(m, None))
            except Exception as e:
                result.warnings.append(f"Falha ao traduzir a legenda: {e}")
        elif subtitles and not subs:
            result.warnings.append("Sem legenda para traduzir.")
        if translate_title:
            try:
                from .translate import google_translator

                translated_title = google_translator(translate_to)(v.title)
            except Exception:
                pass

    from .translate import parse_subtitles, to_text

    for s in folder.glob("legenda.*.srt"):
        txt = s.with_suffix(".txt")
        if not txt.exists():
            txt.write_text(to_text(parse_subtitles(s.read_text(encoding="utf-8", errors="replace"))), encoding="utf-8")

    write_sheet(v, folder, translated_title)
    result.files = sorted(p for p in folder.iterdir() if p.is_file())
    progress("Concluído!", 100)
    return result
