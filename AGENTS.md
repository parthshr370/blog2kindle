# AGENTS.md

Guide for AI agents, scripts, and programmatic consumers of the blog2kindle API.

## What this repo does

blog2kindle is a FastAPI server that converts blog URLs into ebook files. It exposes a REST API that handles the full pipeline: fetching web content, extracting article text, optionally cleaning it with an LLM, generating a cover image, and converting to multiple ebook formats via Calibre.

Everything runs locally. No external services required (LLM cleanup is optional).

## Starting the server

```bash
# with uv (local)
uv sync && uv run uvicorn app:app --host 0.0.0.0 --port 8000

# with docker
docker compose up --build
```

Server runs at `http://localhost:8000`. Swagger docs at `/docs`.

## Core endpoints

### `/api/pipeline` (POST) -- do everything in one call

The simplest way to use blog2kindle. Pass a URL, get back ebook files.

```bash
curl -X POST http://localhost:8000/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/post", "sanitize": false}'
```

With LLM cleanup and extra formats:

```bash
curl -X POST http://localhost:8000/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/post", "formats": ["epub", "azw3", "pdf"]}'
```

Response includes `files` (filename per format), `download_urls` (paths to fetch the files), `metadata`, and `cover_url`.

### `/api/batch` (POST) -- multiple URLs in parallel

Same as pipeline but for a list. Runs up to 4 URLs concurrently. Each URL succeeds or fails independently.

```bash
curl -X POST http://localhost:8000/api/batch \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://example.com/post-1",
      "https://example.com/post-2",
      "https://example.com/post-3"
    ],
    "sanitize": false,
    "formats": ["epub", "azw3"]
  }'
```

### `/api/fetch` (POST) -- extract only

Returns raw markdown, metadata (title, author, source, OG image URL), and downloaded image paths. No conversion.

```bash
curl -X POST http://localhost:8000/api/fetch \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/post"}'
```

### `/api/sanitize` (POST) -- LLM cleanup only

Takes raw markdown, returns cleaned markdown. Requires `GEMINI_API_KEY` or `OPENROUTER_API_KEY` in the environment.

```bash
curl -X POST http://localhost:8000/api/sanitize \
  -H "Content-Type: application/json" \
  -d '{"markdown": "raw markdown text here"}'
```

### `/api/convert` (POST) -- convert only

Takes markdown + metadata, returns ebook files.

```bash
curl -X POST http://localhost:8000/api/convert \
  -H "Content-Type: application/json" \
  -d '{"title": "My Post", "markdown": "# Hello\n\nContent here.", "author": "Author Name", "formats": ["epub", "azw3", "pdf", "mobi"]}'
```

### `/api/send-to-kindle` (POST) -- transfer a file

Copies a generated file to the Kindle. Kindle must be USB-connected.

```bash
curl -X POST http://localhost:8000/api/send-to-kindle \
  -H "Content-Type: application/json" \
  -d '{"file": "my-post.azw3", "kindle_path": "books/fiction/blogs"}'
```

### `/api/kindle/status` (GET) -- check connection

Returns `connected` (bool), `path` (mount point), `books_dir` (target folder).

```bash
curl http://localhost:8000/api/kindle/status
```

### `/api/kindle/books` (GET) -- list books on Kindle

```bash
curl http://localhost:8000/api/kindle/books
```

### `/api/formats` (GET) -- list supported formats

```bash
curl http://localhost:8000/api/formats
```

Returns `["azw3", "epub", "mobi", "pdf"]`.

### Download a generated file

```bash
curl -O http://localhost:8000/static/epubs/my-post.epub
```

## Parameters reference

| Parameter | Type | Default | Used in | What it does |
|-----------|------|---------|---------|-------------|
| `sanitize` | bool | `true` | pipeline, batch | Skip LLM cleanup when `false` |
| `formats` | list[str] | `["epub", "azw3"]` | convert, pipeline, batch | Output formats to generate |
| `send_to_kindle` | bool | `false` | pipeline, batch | Auto-send to Kindle after conversion |
| `kindle_path` | string | env `KINDLE_BOOKS_PATH` | send, pipeline, batch, kindle/status, kindle/books | Subdirectory on Kindle |
| `title` | string | from metadata | pipeline, convert | Override extracted title |
| `author` | string | from metadata | pipeline, convert | Override extracted author |
| `cover` | string | auto-generated | pipeline, convert | Use a specific cover filename |

## Building on top of this

### Custom pipeline

Call endpoints individually for full control:

1. `POST /api/fetch` with the URL
2. Process/modify the markdown yourself
3. `POST /api/convert` with your processed markdown
4. `GET /static/epubs/{filename}` to download the result

### Batch processing script

```python
import requests

urls = [
    "https://blog.example.com/post-1",
    "https://blog.example.com/post-2",
]

resp = requests.post("http://localhost:8000/api/batch", json={
    "urls": urls,
    "sanitize": False,
    "formats": ["epub"],
})

for result in resp.json()["results"]:
    if "error" in result:
        print(f"FAILED: {result['url']} -- {result['error']}")
    else:
        print(f"OK: {result['title']} -- {result['files']}")
```

### Custom cover then convert

```python
import requests

# generate cover with custom params
cover = requests.post("http://localhost:8000/api/cover/generate", json={
    "title": "My Post",
    "author": "Author",
    "image_url": "https://example.com/og-image.jpg",
}).json()

# convert with that cover
result = requests.post("http://localhost:8000/api/convert", json={
    "title": "My Post",
    "markdown": "# Content\n\nHere.",
    "cover": cover["cover"],
    "formats": ["epub", "azw3"],
}).json()
```

## File structure

```
app.py              -- FastAPI app, all endpoints
fetcher.py          -- URL to markdown extraction
llm.py              -- LLM sanitization (Gemini via pydantic-ai)
converter.py        -- markdown to ebook via Calibre (epub/azw3/pdf/mobi)
cover.py            -- cover image generation (Pillow)
kindle.py           -- USB Kindle detection and file transfer (Linux/macOS/Windows)
static/index.html   -- frontend UI
```

## Environment

| Variable | What |
|----------|------|
| `GEMINI_API_KEY` | Gemini key for LLM cleanup (optional) |
| `OPENROUTER_API_KEY` | OpenRouter fallback (optional) |
| `KINDLE_BOOKS_PATH` | Kindle target subdirectory (default: `books/fiction/blogs`) |

## Limitations agents should know about

- Fetcher uses `requests` (no JS rendering). Reddit, some Medium pages, and SPAs will fail or return garbage. Static blogs, Substack, Ghost, Hugo, Jekyll work well.
- LLM cleanup has no token chunking. Very long articles may fail. Pass `sanitize: false` to skip.
- Calibre (`ebook-convert`) must be available in PATH. Docker image includes it. Local installs need Calibre installed separately.
- Generated files are stored in `static/epubs/`, `static/covers/`, `static/images/`. These are not cleaned up automatically.
