"""Kit de postagem: títulos, descrição, hashtags e comentário fixado para copiar e colar.

Três níveis: (1) sugestões locais por modelos (grátis, na hora); (2) prompt pronto para colar no
Claude (qualidade alta, grátis); (3) IA direta no app, se houver ANTHROPIC_API_KEY (paga, centavos)."""
from __future__ import annotations

import json
import os
import re
import urllib.request

from .lang import detect_text_language

_URL = re.compile(r"https?://\S+")
_TAG = re.compile(r"#\w+")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]+")
HOOKS = ["Você sabia?", "Isso é real:", "Pare tudo e veja:", "Ninguém te conta isso:", "Olha só:"]
SUFFIXES = ["(você não vai acreditar)", "(até o final)", "😱", "🤯", "(curiosidade que poucos sabem)"]
CTA = "👉 Segue o canal e deixa o like pra não perder as próximas curiosidades!"
PIN = "Qual parte te surpreendeu mais? Comenta aqui 👇"


def clean_title(t: str) -> str:
    t = _URL.sub(" ", t or "")
    t = _TAG.sub(" ", t)
    t = _EMOJI.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip(" -|–—:·")
    letters = [c for c in t if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.7:  # GRITARIA -> frase normal
        t = t.capitalize()
    return t[:1].upper() + t[1:] if t else t


def to_portuguese(text: str) -> str:
    """Traduz para PT-BR se o texto estiver em outro idioma (precisa de internet); falha em silêncio."""
    code, prob = detect_text_language(text)
    if not text or code in ("", "pt") or prob < 0.6:
        return text
    try:
        from deep_translator import GoogleTranslator

        return GoogleTranslator(source="auto", target="pt").translate(text) or text
    except Exception:  # noqa: BLE001
        return text


def _hashtags(v: dict, limit: int = 12) -> list[str]:
    out: list[str] = []
    short = (v.get("duration") or 999) <= 180

    def add(tag: str):
        tag = "#" + re.sub(r"[^\w]", "", tag.lstrip("#"))
        if len(tag) > 2 and tag.lower() not in {x.lower() for x in out}:
            out.append(tag)

    for h in v.get("hashtags") or []:
        add(h)
    for k in (v.get("keywords") or [])[:10]:
        if " " not in k.strip():  # só palavras soltas viram hashtag
            add(k)
    if short:
        add("shorts")
    for h in ("curiosidades", "viral"):
        add(h)
    return out[:limit]


def build_kit(v: dict, translate: bool = True) -> dict:
    topic = clean_title(v.get("title", ""))
    if translate:
        topic = clean_title(to_portuguese(topic))
    base = topic.rstrip(" .!?")
    titles = [topic]
    titles += [f"{h} {base}" for h in HOOKS[:2]]
    titles += [f"{base} {s}" for s in SUFFIXES[:3]]
    seen, final = set(), []
    for t in titles:
        t = t.strip()
        if 0 < len(t) <= 100 and t.lower() not in seen:
            seen.add(t.lower())
            final.append(t)
    tags = _hashtags(v)
    credit = v.get("source") or (f"Vídeo original: {v.get('url','')}" if v.get("url") else "")
    desc = "\n\n".join(x for x in (f"{final[1] if len(final) > 1 else topic}", CTA,
                                    f"🎬 Crédito: {credit}" if credit else "", " ".join(tags)) if x)
    words = [k for k in (v.get("keywords") or []) if k][:15]
    return {"titles": final, "description": desc, "hashtags": tags, "keywords": ", ".join(words)[:480],
            "pinned_comment": PIN, "credit": credit, "prompt": build_prompt(v, topic)}


def build_prompt(v: dict, topic: str = "") -> str:
    """Prompt pronto para colar no Claude e receber títulos/descrição de alta qualidade."""
    return (
        "Você é especialista em vídeos curtos virais no Brasil. Com base no vídeo abaixo, crie para eu postar "
        "no meu canal (PT-BR, ORIGINAL, sem copiar o título):\n"
        "1) 8 títulos diferentes (até 60 caracteres, com gancho de curiosidade);\n"
        "2) 2 descrições curtas (com chamada para seguir e 5 a 8 hashtags);\n"
        "3) 12 hashtags;\n4) palavras-chave separadas por vírgula (até 400 caracteres);\n"
        "5) 3 frases de gancho para os primeiros 3 segundos;\n6) 1 comentário fixado que gere respostas.\n\n"
        f"Título original: {v.get('title','')}\nCanal: {v.get('channel','')}\n"
        f"Descrição original: {(v.get('description') or '')[:500]}\n"
        f"Palavras-chave: {', '.join((v.get('keywords') or [])[:15])}\n"
        f"Views: {v.get('views')} | Curtidas: {v.get('likes')} | Comentários: {v.get('comments')} | "
        f"Duração: {v.get('duration')}s\n"
    )


def ai_kit(v: dict, api_key: str, model: str = "claude-haiku-5-5") -> str:
    """Gera o kit com a API da Anthropic (opcional; cobra poucos centavos por vídeo)."""
    body = json.dumps({"model": model, "max_tokens": 1500,
                       "messages": [{"role": "user", "content": build_prompt(v)}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return "".join(b.get("text", "") for b in data.get("content", []))


def ai_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
