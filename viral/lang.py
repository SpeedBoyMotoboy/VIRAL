"""Detecção de idioma do vídeo: idioma declarado pelo YouTube + análise do texto."""
from __future__ import annotations

import re

from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException

DetectorFactory.seed = 0  # resultado estável

_URL = re.compile(r"https?://\S+")
_NOISE = re.compile(r"[#@_]|\d+")
CONFIDENT = 0.85  # prob. mínima para o texto "vencer" o idioma declarado


def norm(code: str) -> str:
    """'pt-BR' -> 'pt', 'zh-cn' -> 'zh'."""
    return (code or "").lower().replace("_", "-").split("-")[0]


def detect_text_language(text: str) -> tuple[str, float]:
    """Retorna (código, probabilidade) ou ('', 0) se o texto for curto/ambíguo demais."""
    text = _NOISE.sub(" ", _URL.sub(" ", text or ""))
    letters = sum(ch.isalpha() for ch in text)
    if letters < 12:
        return "", 0.0
    try:
        best = detect_langs(text)[0]
    except LangDetectException:
        return "", 0.0
    return norm(best.lang), float(best.prob)


def video_text(v) -> str:
    return " ".join([v.title or "", (v.description or "")[:400], " ".join((v.tags or [])[:10])])


def matches_language(v, wanted: str) -> tuple[bool, str]:
    """True se o vídeo parece estar no idioma pedido.

    Regras: texto com alta confiança vence; senão vale o idioma declarado;
    sem nenhuma evidência, aceita (melhor mostrar do que esconder um bom vídeo)."""
    want = norm(wanted)
    if not want:
        return True, ""
    declared = norm(getattr(v, "language", ""))
    code, prob = detect_text_language(video_text(v))
    if not getattr(v, "detected_language", ""):
        v.detected_language = code
    if code and prob >= CONFIDENT:
        return (code == want), "texto"
    if declared:
        return (declared == want), "declarado"
    if code and prob >= 0.6:
        return (code == want), "texto fraco"
    return True, "sem evidência"
