"""Linha de comando.

Exemplos:
  python -m viral buscar "receita de bolo" --periodo 1d --min-views 10000 --formato shorts
  python -m viral buscar "" --categoria 20 --periodo 1w --ordenar engagement --csv games.csv
  python -m viral info https://www.tiktok.com/@x/video/123
  python -m viral baixar https://youtu.be/abc --qualidade 720 --traduzir pt
  python -m viral traduzir downloads/.../legenda.en.srt --para pt
  python -m viral web
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import config
from .filters import SearchFilters


def _print_video(i: int, v: dict) -> None:
    def n(x):
        return "—" if x is None else f"{x:,}".replace(",", ".")

    print(f"\n#{i} {v['title']}")
    print(f"   {v['url']}")
    print(f"   canal: {v['channel']}  |  publicado: {(v['published_at'] or '?')[:16]}  |  duração: {v['duration']}s")
    print(f"   views {n(v['views'])}  curtidas {n(v['likes'])}  comentários {n(v['comments'])}  "
          f"engaj. {v['engagement']}%  views/h {v['views_per_hour']}  score {v['viral_score']}")
    if v["hashtags"]:
        print(f"   hashtags: {' '.join(v['hashtags'][:15])}")
    if v["keywords"]:
        print(f"   palavras-chave: {', '.join(v['keywords'][:15])}")


def cmd_buscar(a) -> int:
    from .search import SearchError, search

    f = SearchFilters.from_dict({
        "query": a.query, "period": a.periodo, "category": a.categoria, "style": a.estilo, "format": a.formato,
        "min_views": a.min_views, "min_likes": a.min_likes, "min_comments": a.min_comments,
        "min_engagement": a.min_engajamento, "max_channel_followers": a.max_inscritos,
        "only_downloadable": a.so_baixaveis, "only_creative_commons": a.creative_commons,
        "with_subtitles": a.com_legenda, "exclude_words": a.excluir or "", "region": a.pais,
        "language": a.idioma, "sort": a.ordenar, "max_results": a.limite,
    })
    try:
        r = search(f, progress=lambda m: print("·", m, file=sys.stderr))
    except SearchError as e:
        print("Erro:", e, file=sys.stderr)
        return 1
    print(f"\n{len(r['videos'])} de {r['analyzed']} vídeos passaram nos filtros (motor: {r['engine']})")
    if r["rejected"]:
        print("descartados:", ", ".join(f"{v} {k}" for k, v in r["rejected"].items()))
    for i, v in enumerate(r["videos"], 1):
        _print_video(i, v)
    if a.json:
        Path(a.json).write_text(json.dumps(r["videos"], ensure_ascii=False, indent=2), encoding="utf-8")
        print("\nJSON salvo em", a.json)
    if a.csv:
        cols = ["title", "url", "channel", "published_at", "duration", "views", "likes", "comments", "engagement",
                "views_per_hour", "viral_score", "category", "license", "hashtags", "keywords", "source"]
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(cols)
            for v in r["videos"]:
                w.writerow([" ".join(v[c]) if isinstance(v[c], list) else v[c] for c in cols])
        print("CSV salvo em", a.csv)
    if a.baixar and r["videos"]:
        from .media import download

        for v in r["videos"][: a.baixar]:
            print(f"\nBaixando: {v['title']}")
            res = download(v["url"], quality=a.qualidade, translate_to=a.traduzir,
                           progress=lambda m, p=None: print("  ·", m, file=sys.stderr))
            print("  pasta:", res.folder)
    return 0


def cmd_info(a) -> int:
    from .search import analyze_links

    for i, v in enumerate(analyze_links(a.urls), 1):
        if "error" in v:
            print(f"\n#{i} ERRO {v['url']}: {v['error']}")
            continue
        _print_video(i, v)
        print(f"   fonte: {v['source']}")
        print(f"   legendas: {', '.join(v['subtitles']) or '—'}  | automáticas: {len(v['auto_subtitles'])} idiomas")
    return 0


def cmd_baixar(a) -> int:
    from .media import download

    for url in a.urls:
        res = download(url, quality=a.qualidade, subtitles=not a.sem_legenda, sub_lang=a.legenda,
                       translate_to=a.traduzir, progress=lambda m, p=None: print("·", m, file=sys.stderr))
        print("\nPasta:", res.folder)
        for f in res.files:
            print("  ", f.name)
        for w in res.warnings:
            print("  ⚠", w)
    return 0


def cmd_traduzir(a) -> int:
    from .translate import translate_file

    out = translate_file(Path(a.arquivo), a.para, a.de, progress=lambda m: print("·", m, file=sys.stderr))
    print("Legenda traduzida:", out)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="viral", description="Caçador de vídeos virais")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("buscar", help="buscar e filtrar vídeos")
    b.add_argument("query", help='assunto/palavras-chave ("" = em alta, precisa de API key ou categoria)')
    b.add_argument("--periodo", default="1w", choices=list(config.PERIODS))
    b.add_argument("--categoria", default="", help="id: " + ", ".join(f"{k}={v[0]}" for k, v in config.CATEGORIES.items()))
    b.add_argument("--estilo", default="", choices=list(config.STYLES))
    b.add_argument("--formato", default="", choices=list(config.FORMATS))
    b.add_argument("--min-views", type=int, default=0)
    b.add_argument("--min-likes", type=int, default=0)
    b.add_argument("--min-comments", type=int, default=0)
    b.add_argument("--min-engajamento", type=float, default=0)
    b.add_argument("--max-inscritos", type=int, default=0, help="só canais com até N inscritos")
    b.add_argument("--so-baixaveis", action="store_true")
    b.add_argument("--creative-commons", action="store_true")
    b.add_argument("--com-legenda", action="store_true")
    b.add_argument("--excluir", help="palavras separadas por vírgula")
    b.add_argument("--pais", default="")
    b.add_argument("--idioma", default="")
    b.add_argument("--ordenar", default="viral", choices=list(config.SORTS))
    b.add_argument("--limite", type=int, default=30, help="quantos vídeos analisar")
    b.add_argument("--json")
    b.add_argument("--csv")
    b.add_argument("--baixar", type=int, default=0, help="baixar os N primeiros resultados")
    b.add_argument("--qualidade", default="best")
    b.add_argument("--traduzir", default="", help="traduzir legendas para (ex.: pt)")
    b.set_defaults(fn=cmd_buscar)

    i = sub.add_parser("info", help="fonte, hashtags, palavras-chave e métricas de links")
    i.add_argument("urls", nargs="+")
    i.set_defaults(fn=cmd_info)

    d = sub.add_parser("baixar", help="baixar vídeo/áudio + legendas + ficha")
    d.add_argument("urls", nargs="+")
    d.add_argument("--qualidade", default="best", choices=["best", "1080", "720", "480", "audio", "none"])
    d.add_argument("--legenda", default="", help="idioma da legenda (padrão: original)")
    d.add_argument("--sem-legenda", action="store_true")
    d.add_argument("--traduzir", default="", help="traduzir legenda para (ex.: pt)")
    d.set_defaults(fn=cmd_baixar)

    t = sub.add_parser("traduzir", help="traduzir um arquivo .srt/.vtt")
    t.add_argument("arquivo")
    t.add_argument("--para", default="pt")
    t.add_argument("--de", default="auto")
    t.set_defaults(fn=cmd_traduzir)

    w = sub.add_parser("web", help="abrir a interface web")
    w.set_defaults(fn=lambda a: __import__("viral.web", fromlist=["main"]).main() or 0)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
