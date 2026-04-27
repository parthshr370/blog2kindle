# blog2kindle

Fetch blog posts, clean them up (with or without an LLM), convert to ebook formats (EPUB, AZW3, PDF, MOBI), and push to a USB-connected Kindle.

LLM is optional. Flip the "skip llm cleanup" toggle or pass `"sanitize": false` in the API.

**Two ways to use it:**
- **Frontend** at `localhost:8000` -- paste a URL, pick formats, convert, download or send to Kindle
- **API** at `localhost:8000/docs` -- hit endpoints directly with curl, scripts, or any HTTP client

Both are available the moment the server starts.

## Quick start

### Docker

```bash
git clone https://github.com/parthshr370/blog2kindle && cd blog2kindle
cp .env.example .env        # add a Gemini or OpenRouter key if you want LLM cleanup
docker compose up --build
```

### Local

Needs [uv](https://docs.astral.sh/uv/) and [Calibre](https://calibre-ebook.com/).

```bash
git clone https://github.com/parthshr370/blog2kindle && cd blog2kindle
cp .env.example .env
uv sync
uv run uvicorn app:app --port 8000
```

Open [localhost:8000](http://localhost:8000).

## What it does

1. **Fetch** -- extracts article content, metadata (title, author, OG image), images, converts to markdown
2. **Clean** (optional) -- LLM strips nav junk, fixes formatting, preserves all content. Or skip it entirely.
3. **Convert** -- Calibre generates EPUB, AZW3, PDF, MOBI (pick any combination)
4. **Send** -- detects USB Kindle on Linux/macOS/Windows, copies the file to your configured folder

## API

Full Swagger docs at `/docs`.

| Method | Path | What it does |
|--------|------|--------------|
| `POST` | `/api/fetch` | Fetch and extract a blog URL |
| `POST` | `/api/sanitize` | Clean markdown with LLM |
| `POST` | `/api/convert` | Convert markdown to ebook formats |
| `POST` | `/api/pipeline` | Full pipeline: fetch, clean, convert |
| `POST` | `/api/batch` | Process multiple URLs in parallel |
| `POST` | `/api/send-to-kindle` | Send a file to USB Kindle |
| `POST` | `/api/cover/generate` | Generate a cover image |
| `POST` | `/api/cover/upload` | Upload a custom cover |
| `GET`  | `/api/kindle/status` | Check Kindle connection |
| `GET`  | `/api/kindle/books` | List books on Kindle |
| `GET`  | `/api/formats` | List supported output formats |

**Key parameters:**
- `sanitize` (bool, default `true`) -- set `false` to skip LLM
- `formats` (list, default `["epub", "azw3"]`) -- pick from `epub`, `azw3`, `pdf`, `mobi`
- `kindle_path` (string, optional) -- subdirectory on Kindle to send files to
- `send_to_kindle` (bool, default `false`) -- auto-send after conversion

<details>
<summary>API examples (curl)</summary>

**Single URL, no LLM:**
```bash
curl -X POST http://localhost:8000/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/post", "sanitize": false}'
```

**With LLM + PDF:**
```bash
curl -X POST http://localhost:8000/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/post", "formats": ["epub", "azw3", "pdf"]}'
```

**Batch (parallel):**
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

**Step by step:**
```bash
# 1. fetch
curl -X POST http://localhost:8000/api/fetch \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/post"}'

# 2. (optional) clean with LLM
curl -X POST http://localhost:8000/api/sanitize \
  -H "Content-Type: application/json" \
  -d '{"markdown": "<paste markdown from step 1>"}'

# 3. convert
curl -X POST http://localhost:8000/api/convert \
  -H "Content-Type: application/json" \
  -d '{"title": "Post Title", "markdown": "<markdown>", "formats": ["epub", "pdf"]}'

# 4. download
curl -O http://localhost:8000/static/epubs/post-title.epub

# 5. (optional) send to kindle
curl -X POST http://localhost:8000/api/send-to-kindle \
  -H "Content-Type: application/json" \
  -d '{"file": "post-title.azw3"}'
```
</details>

## Kindle

Plug in via USB. The app auto-detects on Linux, macOS, and Windows. The status dot in the frontend turns green when connected.

Target folder is configurable three ways (priority order):
1. Per-request `kindle_path` param in the API
2. Frontend input field (persisted in localStorage)
3. `KINDLE_BOOKS_PATH` env variable (default: `books/fiction/blogs`)

For Docker, uncomment the volume mount in `docker-compose.yml` and set your Kindle's mount path.

## Config

| Variable | Required | What |
|----------|----------|------|
| `GEMINI_API_KEY` | No | Google Gemini key for LLM cleanup |
| `OPENROUTER_API_KEY` | No | OpenRouter key (fallback) |
| `KINDLE_BOOKS_PATH` | No | Kindle subdirectory (default: `books/fiction/blogs`) |

No keys needed if you skip LLM cleanup.

## Known limitations

- **JS-rendered sites** (Reddit, some Medium pages): fetcher uses `requests`, not a browser. Works with static blogs, Substack, Ghost, Hugo, Jekyll, etc.
- **Long posts**: no chunking for LLM cleanup. Very long articles may fail. Use `sanitize: false` as a workaround.
- **Kindle in Docker**: needs manual volume mount since Kindle mounts on the host.
- **EPUB on Kindle**: AZW3 indexes reliably. EPUB support varies by model/firmware.

## Stack

- Python 3.12 + FastAPI, managed with [uv](https://docs.astral.sh/uv/)
- [Calibre](https://calibre-ebook.com/) for ebook conversion
- Gemini 3.1 Flash Lite via [pydantic-ai](https://ai.pydantic.dev/) for optional LLM cleanup
- Pillow for cover generation
- Vanilla HTML/CSS/JS frontend, [Catppuccin Mocha](https://catppuccin.com/) theme
