"""Leitura/escrita de legendas SRT/VTT e tradução mantendo os tempos."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

TIME = r"\d{1,2}:\d{2}:\d{2}[,.]\d{3}|\d{2}:\d{2}[,.]\d{3}"
CUE_RE = re.compile(rf"({TIME})\s*-->\s*({TIME})[^\n]*\n(.*?)(?:\n\s*\n|\Z)", re.S)
TAG_RE = re.compile(r"<[^>]+>|\{\\[^}]+\}")


@dataclass
class Cue:
    start: str
    end: str
    text: str


def _norm_time(t: str) -> str:
    t = t.replace(".", ",")
    return t if t.count(":") == 2 else "00:" + t


def parse_subtitles(content: str) -> list[Cue]:
    """Aceita SRT ou WebVTT. Remove tags e linhas duplicadas das legendas automáticas."""
    content = content.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    cues: list[Cue] = []
    for m in CUE_RE.finditer(content + "\n\n"):
        lines = [TAG_RE.sub("", l).strip() for l in m.group(3).split("\n")]
        lines = [l for l in lines if l and not l.isdigit()]
        text = "\n".join(lines).strip()
        if not text:
            continue
        # legendas automáticas do YouTube repetem a linha anterior
        if cues and text.split("\n")[0] == cues[-1].text.split("\n")[-1]:
            rest = "\n".join(text.split("\n")[1:]).strip()
            if not rest:
                cues[-1].end = _norm_time(m.group(2))
                continue
            text = rest
        cues.append(Cue(_norm_time(m.group(1)), _norm_time(m.group(2)), text))
    return cues


def to_srt(cues: list[Cue]) -> str:
    return "\n".join(f"{i}\n{c.start} --> {c.end}\n{c.text}\n" for i, c in enumerate(cues, 1))


def to_text(cues: list[Cue]) -> str:
    """Transcrição corrida (útil para roteiro / copiar texto)."""
    return " ".join(c.text.replace("\n", " ") for c in cues).strip()


Translator = Callable[[str], str]


def google_translator(target: str, source: str = "auto") -> Translator:
    from deep_translator import GoogleTranslator

    gt = GoogleTranslator(source=source, target=target)
    return lambda text: gt.translate(text) or ""


SEP = "\n"
MAX_CHARS = 4500


def translate_cues(cues: list[Cue], translate: Translator, progress: Callable[[str], None] | None = None) -> list[Cue]:
    """Traduz em lotes (uma linha por legenda) para fazer poucas chamadas.

    Se o tradutor juntar/separar linhas e a contagem não bater, cai para
    tradução legenda por legenda naquele lote.
    """
    progress = progress or (lambda m: None)
    texts = [c.text.replace("\n", " ") for c in cues]
    out: list[str] = []
    batch: list[str] = []

    def flush():
        if not batch:
            return
        result = translate(SEP.join(batch))
        parts = [p.strip() for p in result.split(SEP)]
        if len(parts) != len(batch):
            parts = [translate(t).strip() for t in batch]
        out.extend(parts)
        progress(f"Traduzidas {len(out)}/{len(texts)} legendas…")
        batch.clear()

    size = 0
    for t in texts:
        if size + len(t) + 1 > MAX_CHARS:
            flush()
            size = 0
        batch.append(t)
        size += len(t) + 1
    flush()
    return [Cue(c.start, c.end, t or c.text) for c, t in zip(cues, out)]


def translate_file(path: Path, target: str, source: str = "auto", translate: Translator | None = None,
                   progress: Callable[[str], None] | None = None) -> Path:
    path = Path(path)
    cues = parse_subtitles(path.read_text(encoding="utf-8", errors="replace"))
    if not cues:
        raise ValueError(f"Legenda vazia ou formato não reconhecido: {path.name}")
    translated = translate_cues(cues, translate or google_translator(target, source), progress)
    stem = re.sub(r"\.[A-Za-z-]{2,8}$", "", path.stem)  # tira o idioma original (video.en -> video)
    out = path.with_name(f"{stem}.{target}.srt")
    out.write_text(to_srt(translated), encoding="utf-8")
    out.with_suffix(".txt").write_text(to_text(translated), encoding="utf-8")
    return out
