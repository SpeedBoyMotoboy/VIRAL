"""Filtros escolhidos pelo usuário e ordenação dos resultados."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone

from .config import CATEGORIES, FORMATS, ORIENTATIONS, PERIODS, STYLES
from .lang import matches_language
from .models import Video


def _int(v, default=0):
    try:
        return int(float(v)) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _float(v, default=0.0):
    try:
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


@dataclass
class SearchFilters:
    query: str = ""
    period: str = "1w"           # 1h, 1d, 1w, 1m, 1y, all
    category: str = ""           # id de CATEGORIES
    style: str = ""              # chave de STYLES
    format: str = ""             # chave de FORMATS
    orientation: str = ""        # vertical | horizontal | "" (qualquer)
    min_views: int = 0
    min_likes: int = 0
    min_comments: int = 0
    min_engagement: float = 0.0  # %
    max_channel_followers: int = 0  # 0 = sem limite (ótimo p/ achar canais pequenos viralizando)
    only_downloadable: bool = False
    only_creative_commons: bool = False
    with_subtitles: bool = False
    exclude_words: list[str] = field(default_factory=list)
    region: str = ""
    language: str = ""
    sort: str = "viral"
    max_results: int = 30        # quantos vídeos analisar

    @classmethod
    def from_dict(cls, data: dict) -> "SearchFilters":
        names = {f.name for f in fields(cls)}
        d = {k: v for k, v in (data or {}).items() if k in names}
        f = cls(**d)
        f.query = str(f.query or "").strip()
        f.period = f.period if f.period in PERIODS else "1w"
        f.category = str(f.category or "") if str(f.category or "") in CATEGORIES else ""
        f.style = f.style if f.style in STYLES else ""
        f.format = f.format if f.format in FORMATS else ""
        f.orientation = f.orientation if f.orientation in ORIENTATIONS else ""
        f.min_views, f.min_likes, f.min_comments = _int(f.min_views), _int(f.min_likes), _int(f.min_comments)
        f.max_channel_followers = _int(f.max_channel_followers)
        f.min_engagement = _float(f.min_engagement)
        f.max_results = max(1, min(_int(f.max_results, 30), 200))
        for b in ("only_downloadable", "only_creative_commons", "with_subtitles"):
            v = getattr(f, b)
            setattr(f, b, v if isinstance(v, bool) else str(v).lower() in ("1", "true", "on", "sim", "yes"))
        if isinstance(f.exclude_words, str):
            f.exclude_words = [w.strip() for w in f.exclude_words.split(",") if w.strip()]
        return f

    # termos finais enviados à plataforma
    @property
    def full_query(self) -> str:
        extra = STYLES.get(self.style, ("", ""))[1]
        return " ".join(x for x in (self.query, extra) if x).strip()

    @property
    def published_after(self) -> datetime | None:
        delta = PERIODS[self.period][1]
        return datetime.now(timezone.utc) - delta if delta else None


def passes(v: Video, f: SearchFilters) -> tuple[bool, str]:
    """Retorna (passou, motivo) — o motivo ajuda a explicar resultados vazios."""
    after = f.published_after
    if after and v.published_at and v.published_at < after:
        return False, "fora do período"
    if f.category:
        pt, en = CATEGORIES[f.category]
        if v.category and v.category not in (pt, en, f.category):
            return False, "outra categoria"
    _, dmin, dmax, _ = FORMATS[f.format]
    if v.duration is not None:
        if dmin is not None and v.duration < dmin:
            return False, "duração"
        if dmax is not None and v.duration > dmax:
            return False, "duração"
    if f.orientation and v.orientation and v.orientation != f.orientation:
        return False, "outra orientação"
    if (v.views or 0) < f.min_views:
        return False, "poucas views"
    if (v.likes or 0) < f.min_likes:
        return False, "poucas curtidas"
    if (v.comments or 0) < f.min_comments:
        return False, "poucos comentários"
    if f.min_engagement and (v.engagement or 0) < f.min_engagement:
        return False, "engajamento baixo"
    if f.max_channel_followers and v.channel_followers and v.channel_followers > f.max_channel_followers:
        return False, "canal grande demais"
    if f.only_downloadable and not v.downloadable:
        return False, "não baixável"
    if f.only_creative_commons and "creative" not in v.license.lower():
        return False, "não é Creative Commons"
    if f.with_subtitles and not (v.subtitles or v.auto_subtitles):
        return False, "sem legenda"
    if f.language:
        ok, _ = matches_language(v, f.language)
        if not ok:
            return False, "outro idioma"
    if f.region and v.channel_country and v.channel_country.upper() != f.region.upper():
        return False, "canal de outro país"
    if f.exclude_words:
        hay = f"{v.title} {v.description}".lower()
        if any(w.lower() in hay for w in f.exclude_words):
            return False, "palavra excluída"
    return True, ""


SORT_KEYS = {
    "viral": lambda v: v.viral_score,
    "views": lambda v: v.views or 0,
    "likes": lambda v: v.likes or 0,
    "comments": lambda v: v.comments or 0,
    "engagement": lambda v: v.engagement or 0,
    "recent": lambda v: v.published_at.timestamp() if v.published_at else 0,
}


def apply_filters(videos: list[Video], f: SearchFilters) -> tuple[list[Video], dict[str, int]]:
    kept, rejected = [], {}
    seen = set()
    for v in videos:
        if v.id in seen:
            continue
        seen.add(v.id)
        ok, reason = passes(v, f)
        if ok:
            kept.append(v)
        else:
            rejected[reason] = rejected.get(reason, 0) + 1
    kept.sort(key=SORT_KEYS.get(f.sort, SORT_KEYS["viral"]), reverse=True)
    return kept, rejected
