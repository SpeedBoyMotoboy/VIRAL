"""Opções fixas: períodos, categorias, estilos, formatos e idiomas."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

def _default_download_dir() -> Path:
    """Pasta 'Downloads\\VIRAL' do usuário (se existir Downloads); senão ./downloads."""
    dl = Path.home() / "Downloads"
    return dl / "VIRAL" if dl.is_dir() else Path.cwd() / "downloads"


DOWNLOAD_DIR = Path(os.environ.get("VIRAL_DOWNLOAD_DIR") or _default_download_dir()).resolve()
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()

# Período de postagem -> (rótulo, timedelta, código do filtro "upload date" da busca do YouTube)
PERIODS: dict[str, tuple[str, timedelta | None, int | None]] = {
    "1h": ("Última hora", timedelta(hours=1), 1),
    "1d": ("Último dia", timedelta(days=1), 2),
    "1w": ("Última semana", timedelta(weeks=1), 3),
    "1m": ("Último mês", timedelta(days=30), 4),
    "1y": ("Último ano", timedelta(days=365), 5),
    "all": ("Qualquer data", None, None),
}

# Categorias do YouTube: id -> (nome PT, nome EN usado pelo yt-dlp)
CATEGORIES: dict[str, tuple[str, str]] = {
    "1": ("Filmes e animação", "Film & Animation"),
    "2": ("Carros e veículos", "Autos & Vehicles"),
    "10": ("Música", "Music"),
    "15": ("Animais", "Pets & Animals"),
    "17": ("Esportes", "Sports"),
    "19": ("Viagens e eventos", "Travel & Events"),
    "20": ("Games", "Gaming"),
    "22": ("Pessoas e blogs", "People & Blogs"),
    "23": ("Comédia", "Comedy"),
    "24": ("Entretenimento", "Entertainment"),
    "25": ("Notícias e política", "News & Politics"),
    "26": ("Guias e estilo", "Howto & Style"),
    "27": ("Educação", "Education"),
    "28": ("Ciência e tecnologia", "Science & Technology"),
    "29": ("ONGs e ativismo", "Nonprofits & Activism"),
}

# Estilos de conteúdo: termos adicionados à busca
STYLES: dict[str, tuple[str, str]] = {
    "": ("Qualquer estilo", ""),
    "curiosidades": ("Curiosidades / fatos", "curiosidades fatos incríveis"),
    "humor": ("Humor / memes", "engraçado memes"),
    "motivacional": ("Motivacional", "motivação motivacional"),
    "tutorial": ("Tutorial / como fazer", "tutorial como fazer"),
    "cortes": ("Cortes de podcast", "cortes podcast"),
    "react": ("React / reação", "react reação"),
    "historia": ("Histórias / storytelling", "história real"),
    "receitas": ("Receitas", "receita fácil"),
    "noticias": ("Notícias", "notícias hoje"),
    "fitness": ("Fitness / treino", "treino academia"),
    "financas": ("Finanças / dinheiro", "dinheiro finanças investimento"),
    "tecnologia": ("Tecnologia / IA", "tecnologia inteligência artificial"),
    "animais": ("Animais fofos", "animais fofos"),
    "satisfatorio": ("Satisfatório / ASMR", "satisfatório asmr"),
    "games": ("Games / gameplay", "gameplay"),
}

# Formato / duração (segundos): id -> (rótulo, mín, máx, código do filtro "duration" do YouTube)
FORMATS: dict[str, tuple[str, int | None, int | None, int | None]] = {
    "": ("Qualquer duração", None, None, None),
    "shorts": ("Shorts / Reels (até 3 min)", None, 180, 1),
    "curto": ("Curto (até 4 min)", None, 240, 1),
    "medio": ("Médio (4–20 min)", 240, 1200, 3),
    "longo": ("Longo (mais de 20 min)", 1200, None, 2),
}

# Orientação do vídeo
ORIENTATIONS: dict[str, str] = {
    "": "Qualquer orientação",
    "vertical": "Vertical (Shorts / Reels / TikTok)",
    "horizontal": "Horizontal (tela deitada)",
}

# Ordenação dos resultados
SORTS: dict[str, str] = {
    "viral": "Score viral (views por hora)",
    "views": "Mais visualizações",
    "likes": "Mais curtidas",
    "comments": "Mais comentários",
    "engagement": "Maior engajamento (%)",
    "recent": "Mais recentes",
}

LANGUAGES: dict[str, str] = {
    "pt": "Português",
    "en": "Inglês",
    "es": "Espanhol",
    "fr": "Francês",
    "de": "Alemão",
    "it": "Italiano",
    "ja": "Japonês",
    "ko": "Coreano",
    "zh-CN": "Chinês (simplificado)",
    "ru": "Russo",
    "ar": "Árabe",
    "hi": "Hindi",
}

REGIONS: dict[str, str] = {
    "": "Qualquer país",
    "BR": "Brasil",
    "US": "Estados Unidos",
    "PT": "Portugal",
    "MX": "México",
    "ES": "Espanha",
    "AR": "Argentina",
    "GB": "Reino Unido",
    "IN": "Índia",
    "JP": "Japão",
}
