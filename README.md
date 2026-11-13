# VIRAL 🔥 — caçador de vídeos virais

Acha os vídeos que estão bombando, filtra pelos seus critérios, mostra **fonte, título,
#hashtags e palavras-chave**, **baixa** (vídeo ou áudio, quando disponível) e **baixa e traduz a legenda**.

## O que faz

| Função | Detalhe |
|---|---|
| **Buscar virais** | Por assunto/palavra-chave, categoria, estilo (curiosidades, humor, cortes, receitas…) e formato (Shorts, curto, médio, longo) |
| **Período de postagem** | Última hora · último dia · última semana · último mês · último ano · qualquer data |
| **Filtros mínimos** | Visualizações, curtidas, comentários, % de engajamento |
| **Mais filtros** | País, idioma, tamanho máximo do canal (achar canal pequeno viralizando), excluir palavras, só baixáveis, só com legenda, só Creative Commons (livre para reuso) |
| **Ranking** | Score viral (views por hora × engajamento × views/inscritos), views, curtidas, comentários, engajamento, mais recentes |
| **Dados de cada vídeo** | Título, fonte/crédito pronto para copiar, canal, data, duração, #hashtags, palavras-chave (tags + termos mais usados), licença, legendas disponíveis |
| **Analisar links** | Cole links de YouTube, TikTok, Instagram, Kwai, X, Facebook, Vimeo… e receba tudo acima |
| **Baixar** | Melhor qualidade, 1080p, 720p, 480p, só áudio MP3 ou só legenda+ficha · vários de uma vez |
| **Legendas** | Baixa a legenda original (ou automática) em `.srt`, **traduz** para o idioma escolhido mantendo os tempos, e gera também a transcrição em `.txt` |
| **Exportar** | Resultados em CSV (abre no Excel) ou JSON; botão para copiar as hashtags mais usadas no topo |

Cada download vira uma pasta em `downloads/` com:

```
Título do vídeo [id]/
  video.mp4            (ou video.mp3)
  video.jpg            capa
  legenda.en.srt       legenda original
  legenda.pt.srt       legenda traduzida
  legenda.pt.txt       transcrição traduzida
  ficha.txt / .json    fonte, título (e traduzido), hashtags, palavras-chave, métricas, descrição
```

## Instalar e abrir

Precisa de **Python 3.10+** e **FFmpeg** (para juntar áudio/vídeo e converter legendas).

- Windows: instale Python (marque “Add to PATH”) e FFmpeg (`winget install ffmpeg`), depois dê dois cliques em **`iniciar.bat`**.
- Linux/Mac: `./iniciar.sh`

Abre em http://127.0.0.1:5000.

Manual:

```bash
pip install -r requirements.txt
```

```bash
python -m viral web
```

## Motor de busca: com ou sem chave

- **Sem chave (padrão):** usa o `yt-dlp` para ler a busca do YouTube e abrir cada vídeo. Funciona na hora, mas é mais lento (analisa ~30 vídeos em alguns segundos).
- **Com chave da YouTube Data API (recomendado):** muito mais rápido, filtra categoria/país/idioma direto no YouTube, traz o número de inscritos do canal e, **sem palavra-chave, mostra os vídeos em alta** do país/categoria.
  Crie a chave grátis em https://console.cloud.google.com → “YouTube Data API v3” → Credenciais, e rode:

  Windows (PowerShell):
  ```powershell
  $env:YOUTUBE_API_KEY="SUA_CHAVE"; python -m viral web
  ```
  Linux/Mac:
  ```bash
  YOUTUBE_API_KEY=SUA_CHAVE python -m viral web
  ```

Outras variáveis: `VIRAL_DOWNLOAD_DIR` (pasta dos downloads), `VIRAL_PORT` (porta, padrão 5000).

## Linha de comando

```bash
python -m viral buscar "receita de bolo" --periodo 1d --min-views 10000 --formato shorts --csv bolos.csv
```

```bash
python -m viral buscar "curiosidades" --periodo 1w --min-likes 5000 --max-inscritos 50000 --baixar 3 --traduzir pt
```

```bash
python -m viral info https://www.tiktok.com/@perfil/video/123
```

```bash
python -m viral baixar https://youtu.be/ID --qualidade 720 --traduzir pt
```

```bash
python -m viral traduzir "downloads/Video [id]/legenda.en.srt" --para pt
```

`python -m viral buscar -h` lista todas as opções.

## Observações

- Busca por palavra-chave é no **YouTube** (inclui Shorts). TikTok/Instagram/Kwai etc. funcionam pela aba **Analisar links** (metadados + download), pois essas plataformas não têm busca pública estável.
- Se algo parar de funcionar, atualize o yt-dlp: `pip install -U yt-dlp` (os scripts `iniciar` já fazem isso).
- Respeite direitos autorais: use a **fonte/crédito** gerado, prefira o filtro **Creative Commons** para reutilizar, e não reposte conteúdo de terceiros sem permissão.

## Testes

```bash
python -m pytest -q
```
