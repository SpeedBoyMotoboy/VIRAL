import base64
from datetime import datetime, timedelta, timezone

from viral.filters import SearchFilters, apply_filters
from viral.models import Video, extract_hashtags, parse_iso_duration
from viral.search import youtube_sp
from viral.translate import Cue, parse_subtitles, to_srt, translate_cues

NOW = datetime.now(timezone.utc)


def vid(i, views, likes=0, comments=0, hours=1, dur=30, **kw):
    return Video(id=str(i), url=f"u{i}", title=f"v{i}", views=views, likes=likes, comments=comments,
                 published_at=NOW - timedelta(hours=hours), duration=dur, **kw).finalize()


def test_hashtags_and_keywords():
    v = Video(id="1", url="u", title="Bolo de cenoura fofinho #receita", description="Faça já! #bolo #Receita #123",
              tags=["bolo caseiro"]).finalize()
    assert v.hashtags == ["#receita", "#bolo", "#Receita"]
    assert "bolo caseiro" in v.keywords and "cenoura" in v.keywords
    assert extract_hashtags("#fyp #viral.") == ["#fyp", "#viral"]


def test_filters_min_and_period_and_sort():
    vs = [vid(1, 500), vid(2, 50_000, 5_000, 100, hours=2), vid(3, 90_000, 100, 1, hours=200),
          vid(4, 20_000, 3_000, 900, hours=1, dur=600)]
    f = SearchFilters.from_dict({"period": "1d", "min_views": "1000", "format": "shorts", "sort": "viral"})
    kept, rej = apply_filters(vs, f)
    assert [v.id for v in kept] == ["2"]
    assert rej == {"poucas views": 1, "fora do período": 1, "duração": 1}
    f = SearchFilters.from_dict({"period": "all", "sort": "engagement"})
    kept, _ = apply_filters(vs, f)
    assert kept[0].id == "4"


def test_filter_parsing_is_safe():
    f = SearchFilters.from_dict({"period": "xx", "min_views": "abc", "max_results": "9999",
                                 "only_downloadable": "on", "exclude_words": "live, ao vivo", "bogus": 1})
    assert f.period == "1w" and f.min_views == 0 and f.max_results == 200
    assert f.only_downloadable is True and f.exclude_words == ["live", "ao vivo"]


def test_youtube_sp():
    f = SearchFilters.from_dict({"period": "1h"})
    assert base64.b64decode(youtube_sp(f)) == b"\x08\x03\x12\x04\x08\x01\x10\x01"
    f = SearchFilters.from_dict({"period": "all", "format": "longo", "sort": "recent"})
    assert base64.b64decode(youtube_sp(f)) == b"\x08\x02\x12\x04\x10\x01\x18\x02"


def test_iso_duration_and_api_item():
    assert parse_iso_duration("PT1H2M3S") == 3723
    v = Video.from_youtube_api({"id": "x", "snippet": {"title": "Oi #teste", "publishedAt": "2026-01-01T00:00:00Z",
                                "channelTitle": "C", "channelId": "UC1", "categoryId": "20"},
                                "statistics": {"viewCount": "100", "likeCount": "10"},
                                "contentDetails": {"duration": "PT45S"}, "status": {"license": "creativeCommon"}},
                               {"20": "Games"})
    assert v.views == 100 and v.likes == 10 and v.comments is None and v.duration == 45
    assert v.category == "Games" and v.license == "Creative Commons" and v.hashtags == ["#teste"]
    assert "youtube.com/watch?v=x" in v.source_credit()


def test_ytdlp_info():
    v = Video.from_ytdlp({"id": "abc", "title": "T", "extractor_key": "TikTok", "webpage_url": "https://tiktok.com/x",
                          "upload_date": "20260101", "view_count": 10, "like_count": 2, "comment_count": 1,
                          "subtitles": {"en": []}, "automatic_captions": {"pt": [], "en-orig": []}})
    assert v.platform == "tiktok" and v.engagement == 30.0 and v.subtitles == ["en"]


VTT = """WEBVTT

00:00:01.000 --> 00:00:02.500 align:start
<c>Hello</c> world

00:00:02.500 --> 00:00:04.000
Hello world
how are you

00:01.000 --> 00:02.000
short
"""


def test_parse_vtt_dedup_and_srt():
    cues = parse_subtitles(VTT)
    assert [c.text for c in cues] == ["Hello world", "how are you", "short"]
    assert cues[0].start == "00:00:01,000" and cues[2].start == "00:00:01,000"
    assert to_srt(cues).startswith("1\n00:00:01,000 --> 00:00:02,500\nHello world\n")


def test_translate_batches_and_fallback():
    cues = [Cue("00:00:01,000", "00:00:02,000", f"line {i}\nx") for i in range(5)]
    calls = []

    def tr(text):
        calls.append(text)
        return text.upper()

    out = translate_cues(cues, tr)
    assert len(calls) == 1 and out[0].text == "LINE 0 X" and out[4].start == "00:00:01,000"

    def bad(text):  # junta linhas -> força fallback por legenda
        return text.replace("\n", " ").upper()

    out = translate_cues(cues, bad)
    assert [c.text for c in out] == [f"LINE {i} X" for i in range(5)]


# ---- idioma / país -----------------------------------------------------------
from viral.lang import matches_language


def lv(title, desc="", lang="", country=""):
    return Video(id=str(abs(hash(title))), url="u", title=title, description=desc, language=lang,
                 channel_country=country, published_at=NOW, duration=30, views=1000).finalize()


def test_idioma_portugues_aceita_e_rejeita():
    pt = lv("Você sabia que o coração do beija-flor bate muito rápido?", "Curiosidades incríveis sobre os animais do Brasil")
    es = lv("¿Sabías que el corazón del colibrí late muy rápido?", "Datos curiosos increíbles sobre los animales")
    en = lv("Did you know the hummingbird heart beats incredibly fast?", "Amazing facts about animals around the world")
    assert matches_language(pt, "pt")[0]
    assert not matches_language(es, "pt")[0]
    assert not matches_language(en, "pt")[0]
    assert matches_language(en, "en")[0]


def test_idioma_declarado_e_sem_evidencia():
    assert matches_language(lv("🔥🔥", lang="pt-BR"), "pt")[0]       # texto curto: vale o declarado
    assert not matches_language(lv("🔥🔥", lang="es"), "pt")[0]
    assert matches_language(lv("🔥🔥"), "pt")[0]                      # sem evidência: não esconde


def test_filtro_aplica_idioma_e_pais():
    vs = [lv("Você sabia que existem planetas feitos de diamante?", "fatos do espaço", country="BR"),
          lv("¿Sabías que existen planetas hechos de diamante?", "datos del espacio", country="MX"),
          lv("Você sabia que o mar é salgado por causa das rochas?", "ciência simples", country="PT"),
          lv("Did you know there are planets made of diamond?", "space facts", country="US")]
    f = SearchFilters.from_dict({"period": "all", "language": "pt", "region": "BR", "sort": "views"})
    kept, rej = apply_filters(vs, f)
    assert [v.channel_country for v in kept] == ["BR"]
    assert rej.get("outro idioma") == 2 and rej.get("canal de outro país") == 1


def test_busca_api_pagina_ate_ter_o_suficiente(monkeypatch):
    """Simula a API: páginas de 50 ids, 1 em cada 3 em português. Deve parar quando juntar 10 em PT."""
    from viral import search as S

    calls = {"search": 0}
    pt = "Você sabia que isso acontece todos os dias no Brasil inteiro?"
    es = "¿Sabías que esto sucede todos los días en todo el país?"

    def fake_api(endpoint, key, **p):
        if endpoint == "search":
            calls["search"] += 1
            n = calls["search"]
            items = [{"id": {"videoId": f"p{n}_{i}"}} for i in range(50)]
            return {"items": items, "nextPageToken": "x"}
        if endpoint == "videos":
            items = []
            for vid in p["id"].split(","):
                i = int(vid.split("_")[1])
                items.append({"id": vid, "snippet": {"title": pt if i % 3 == 0 else es, "description": "", "channelId": "c" + vid,
                                                     "publishedAt": NOW.isoformat(), "categoryId": "24"},
                              "statistics": {"viewCount": "1000"}, "contentDetails": {"duration": "PT30S"}, "status": {"privacyStatus": "public"}})
            return {"items": items}
        if endpoint == "channels":
            return {"items": [{"id": c, "snippet": {"country": "BR"}, "statistics": {"subscriberCount": "100"}} for c in p["id"].split(",")]}

    monkeypatch.setattr(S, "_api", fake_api)
    f = SearchFilters.from_dict({"query": "x", "period": "all", "language": "pt", "region": "BR", "max_results": 10})
    r = S.search(f, api_key="k")
    assert len(r["videos"]) == 10
    assert all(v["detected_language"] == "pt" for v in r["videos"])
    assert calls["search"] == 1  # 50 ids -> ~17 em PT, já bastava

    calls["search"] = 0
    f = SearchFilters.from_dict({"query": "x", "period": "all", "language": "pt", "region": "BR", "max_results": 30})
    r = S.search(f, api_key="k")
    assert len(r["videos"]) == 30 and calls["search"] == 2  # precisou da 2ª página
