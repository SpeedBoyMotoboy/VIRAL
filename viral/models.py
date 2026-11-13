"""Modelo de vídeo normalizado + extração de hashtags e palavras-chave."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

HASHTAG_RE = re.compile(r"#([^\s#.,;:!?()\[\]{}\"'<>]+)", re.UNICODE)
WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)

STOPWORDS = set(
    """
    the and for you your with this that are was from have not but all can how what when why who
    out get got one our its his her they them their just like more about into over than then
    video videos official new part full episode shorts short
    que para com uma por não mais como mas foi ele ela eles elas seu sua seus suas isso esse essa
    este esta aqui quando muito já também só pelo pela pelos pelas são ser tem ter vai vou meu minha
    nos nas dos das num numa até sem sobre depois antes você vocês ele dele dela fazer feito
    los las del con una por para que más como pero sus este esta esto muy sin sobre
    """.split()
)


def extract_hashtags(*texts: str | None) -> list[str]:
    seen: dict[str, None] = {}
    for text in texts:
        for tag in HASHTAG_RE.findall(text or ""):
            tag = tag.strip("_-")
            if tag and not tag.isdigit():
                seen.setdefault("#" + tag, None)
    return list(seen)


def extract_keywords(title: str, description: str = "", tags: list[str] | None = None, limit: int = 15) -> list[str]:
    """Palavras-chave = tags do vídeo + palavras mais frequentes de título/descrição."""
    result: dict[str, None] = {}
    for t in tags or []:
        t = t.strip()
        if t:
            result.setdefault(t.lower(), None)
    counter: Counter[str] = Counter()
    for w in WORD_RE.findall(title or ""):
        w = w.lower()
        if w not in STOPWORDS:
            counter[w] += 3  # título pesa mais
    for w in WORD_RE.findall(HASHTAG_RE.sub(" ", description or "")[:3000]):
        w = w.lower()
        if w not in STOPWORDS and not w.startswith("http"):
            counter[w] += 1
    for w, _ in counter.most_common(limit):
        result.setdefault(w, None)
    return list(result)[: max(limit, len(tags or []))]


def parse_date(value) -> datetime | None:
    """Aceita timestamp unix, 'YYYYMMDD' (yt-dlp) ou ISO 8601 (API)."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        s = str(value)
        if re.fullmatch(r"\d{8}", s):
            return datetime.strptime(s, "%Y%m%d").replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


ISO_DURATION_RE = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_iso_duration(value: str | None) -> int | None:
    if not value:
        return None
    m = ISO_DURATION_RE.fullmatch(value)
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


@dataclass
class Video:
    id: str
    url: str
    title: str
    platform: str = "youtube"
    description: str = ""
    channel: str = ""
    channel_url: str = ""
    channel_followers: int | None = None
    thumbnail: str = ""
    published_at: datetime | None = None
    duration: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    category: str = ""
    tags: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    language: str = ""
    detected_language: str = ""
    channel_country: str = ""
    license: str = ""
    downloadable: bool = True
    availability: str = ""
    subtitles: list[str] = field(default_factory=list)
    auto_subtitles: list[str] = field(default_factory=list)

    # ---- métricas derivadas -------------------------------------------------
    @property
    def age_hours(self) -> float | None:
        if not self.published_at:
            return None
        delta = datetime.now(timezone.utc) - self.published_at
        return max(delta.total_seconds() / 3600, 1.0)

    @property
    def engagement(self) -> float | None:
        """(curtidas + comentários) / views, em %."""
        if not self.views:
            return None
        return round(((self.likes or 0) + (self.comments or 0)) / self.views * 100, 2)

    @property
    def views_per_hour(self) -> float | None:
        if self.views is None or self.age_hours is None:
            return None
        return round(self.views / self.age_hours, 1)

    @property
    def viral_score(self) -> float:
        """Velocidade de views ponderada pelo engajamento e pelo tamanho do canal.

        Um vídeo de canal pequeno com muitas views por hora tem score maior que
        o mesmo número vindo de um canal gigante (isso é o "fora da curva").
        """
        vph = self.views_per_hour or 0
        eng = self.engagement or 0
        score = vph * (1 + eng / 10)
        if self.channel_followers and self.views:
            ratio = self.views / max(self.channel_followers, 1)
            score *= 1 + min(ratio, 10) / 5
        return round(score, 1)

    def finalize(self) -> "Video":
        if not self.hashtags:
            self.hashtags = extract_hashtags(self.title, self.description)
        if not self.keywords:
            self.keywords = extract_keywords(self.title, self.description, self.tags)
        return self

    def source_credit(self) -> str:
        """Texto de crédito / fonte pronto para colar."""
        parts = [f'"{self.title}"']
        if self.channel:
            parts.append(f"por {self.channel}")
        parts.append(f"({self.platform})")
        line = " ".join(parts) + f" — {self.url}"
        if self.license:
            line += f" | Licença: {self.license}"
        return line

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published_at"] = self.published_at.isoformat() if self.published_at else None
        d["engagement"] = self.engagement
        d["views_per_hour"] = self.views_per_hour
        d["viral_score"] = self.viral_score
        d["source"] = self.source_credit()
        return d

    # ---- construtores -----------------------------------------------------
    @classmethod
    def from_ytdlp(cls, info: dict) -> "Video":
        vid = info.get("id") or ""
        url = info.get("webpage_url") or info.get("original_url") or info.get("url") or ""
        platform = (info.get("extractor_key") or info.get("ie_key") or "youtube").lower()
        if platform.startswith("youtube"):
            platform = "youtube"
            if vid and not url.startswith("http"):
                url = f"https://www.youtube.com/watch?v={vid}"
        thumb = info.get("thumbnail") or ""
        if not thumb and info.get("thumbnails"):
            thumb = info["thumbnails"][-1].get("url", "")
        cats = info.get("categories") or []
        published = parse_date(info.get("timestamp")) or parse_date(info.get("release_timestamp")) or parse_date(info.get("upload_date"))
        availability = info.get("availability") or ""
        live = info.get("live_status") or ""
        downloadable = availability not in ("private", "premium_only", "subscriber_only", "needs_auth") and live not in ("is_upcoming",)
        return cls(
            id=vid,
            url=url,
            title=info.get("title") or "",
            platform=platform,
            description=info.get("description") or "",
            channel=info.get("channel") or info.get("uploader") or "",
            channel_url=info.get("channel_url") or info.get("uploader_url") or "",
            channel_followers=info.get("channel_follower_count"),
            thumbnail=thumb,
            published_at=published,
            duration=int(info["duration"]) if info.get("duration") else None,
            views=info.get("view_count"),
            likes=info.get("like_count"),
            comments=info.get("comment_count"),
            category=cats[0] if cats else "",
            tags=list(info.get("tags") or []),
            language=info.get("language") or "",
            license=info.get("license") or "",
            downloadable=downloadable,
            availability=availability or live,
            subtitles=sorted((info.get("subtitles") or {}).keys()),
            auto_subtitles=sorted((info.get("automatic_captions") or {}).keys()),
        ).finalize()

    @classmethod
    def from_youtube_api(cls, item: dict, category_names: dict[str, str] | None = None) -> "Video":
        sn = item.get("snippet", {})
        st = item.get("statistics", {})
        cd = item.get("contentDetails", {})
        status = item.get("status", {})
        vid = item["id"]
        thumbs = sn.get("thumbnails", {})
        thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")

        def num(key):
            return int(st[key]) if key in st else None

        lic = status.get("license", "")
        return cls(
            id=vid,
            url=f"https://www.youtube.com/watch?v={vid}",
            title=sn.get("title", ""),
            description=sn.get("description", ""),
            channel=sn.get("channelTitle", ""),
            channel_url=f"https://www.youtube.com/channel/{sn['channelId']}" if sn.get("channelId") else "",
            thumbnail=thumb,
            published_at=parse_date(sn.get("publishedAt")),
            duration=parse_iso_duration(cd.get("duration")),
            views=num("viewCount"),
            likes=num("likeCount"),
            comments=num("commentCount"),
            category=(category_names or {}).get(sn.get("categoryId", ""), sn.get("categoryId", "")),
            tags=list(sn.get("tags") or []),
            language=sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "",
            license={"creativeCommon": "Creative Commons", "youtube": "Licença padrão do YouTube"}.get(lic, lic),
            downloadable=status.get("privacyStatus", "public") == "public" and sn.get("liveBroadcastContent", "none") != "upcoming",
            availability=sn.get("liveBroadcastContent", ""),
            subtitles=["(tem legendas)"] if cd.get("caption") == "true" else [],
        ).finalize()
