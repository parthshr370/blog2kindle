# blog2kindle

Fetch blog posts, optionally clean them with an LLM, convert to ebook formats (EPUB, AZW3, PDF, MOBI), and send to a USB-connected Kindle.

Works entirely without an LLM — flip the "skip llm cleanup" toggle or pass `"sanitize": false` in the API.

## Quick start

### With Docker (recommended)

```bash
git clone <repo-url> && cd blog2kindle
cp .env.example .env        # optionally add a Gemini or OpenRouter key
docker compose up --build
```

Open [localhost:8000](http://localhost:8000). That's it.

### Without Docker

Requires [uv](https://docs.astral.sh/uv/) and [Calibre](https://calibre-ebook.com/) (for `ebook-convert`).

```bash
git clone <repo-url> && cd blog2kindle
cp .env.example .env
uv sync
uv run uvicorn app:app --port 8000
```

Open [localhost:8000](http://localhost:8000).

## How it works — full walkthrough

### Frontend flow

1. **Paste a URL** and click **fetch**. The app extracts the article, metadata (title, author, OG image), and converts to markdown.
2. **Preview** the extracted content. Optionally click **clean with llm** to sanitize (removes nav junk, fixes formatting). Or toggle **skip llm cleanup** to skip this entirely.
3. **Pick output formats** — checkboxes for EPUB, AZW3, PDF, MOBI. EPUB + AZW3 are checked by default.
4. Click **convert**. Calibre generates each selected format. Download links appear below.
5. If a **Kindle is plugged in** (USB), the status dot turns green and the **send** button activates. Click it to copy the AZW3 to your Kindle's documents folder.

### API-only flow (no frontend needed)

**Single URL, no LLM:**
```bash
curl -X POST http://localhost:8000/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/post", "sanitize": false}'
```

**Single URL, with LLM + PDF:**
```bash
curl -X POST http://localhost:8000/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/post", "formats": ["epub", "azw3", "pdf"]}'
```

**Batch — multiple URLs in parallel:**
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

**Step-by-step (manual control):**
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

## API reference

All endpoints have Swagger docs at `/docs`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/fetch` | Fetch and extract a blog URL |
| `POST` | `/api/sanitize` | Clean markdown with LLM |
| `POST` | `/api/convert` | Convert markdown to ebook formats |
| `POST` | `/api/pipeline` | Full pipeline: fetch → clean → convert |
| `POST` | `/api/batch` | Process multiple URLs in parallel |
| `POST` | `/api/send-to-kindle` | Send a file to USB-connected Kindle |
| `POST` | `/api/cover/generate` | Generate a cover image from metadata |
| `POST` | `/api/cover/upload` | Upload a custom cover image |
| `GET`  | `/api/kindle/status` | Check Kindle connection |
| `GET`  | `/api/kindle/books` | List books on connected Kindle |
| `GET`  | `/api/formats` | List supported output formats |

### Key request parameters

- **`sanitize`** (bool, default `true`) — set `false` to skip LLM cleanup. Works on `/api/pipeline` and `/api/batch`.
- **`formats`** (list, default `["epub", "azw3"]`) — pick from `epub`, `azw3`, `pdf`, `mobi`. Works on `/api/convert`, `/api/pipeline`, `/api/batch`.
- **`send_to_kindle`** (bool, default `false`) — auto-send best Kindle format after conversion. Works on `/api/pipeline` and `/api/batch`.

## Kindle support

Plug in your Kindle via USB. The app auto-detects it on:

- **Linux:** `/run/media/*/Kindle`, `/media/*/Kindle`, `/mnt/Kindle`
- **macOS:** `/Volumes/Kindle`
- **Windows:** scans drive letters for Kindle's `system/version.txt` marker

The frontend status indicator polls every 10 seconds. AZW3 is preferred for Kindle (indexes properly); EPUB files may not show up on older Kindles.

**Docker + Kindle:** uncomment the volume mount in `docker-compose.yml` and set your Kindle's mount path:
```yaml
volumes:
  - /run/media/youruser/Kindle:/mnt/Kindle:rw
```

## Configuration

### Environment variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | No | Google Gemini API key for LLM cleanup |
| `OPENROUTER_API_KEY` | No | OpenRouter key (fallback if no Gemini key) |

Neither key is needed if you skip LLM cleanup.

### LLM model

Default: `gemini-3.1-flash-lite-preview` via Google or OpenRouter. Change in `llm.py`.

## Project structure

```
blog2kindle/
  app.py              # FastAPI app, all endpoints
  fetcher.py          # blog URL → markdown extraction
  llm.py              # LLM sanitization (optional)
  converter.py        # markdown → epub/azw3/pdf/mobi via Calibre
  cover.py            # cover image generation (PIL)
  kindle.py           # Kindle USB detection + file transfer
  static/
    index.html        # frontend (Catppuccin Mocha theme)
    *.ttf             # ZedMono Nerd Font
    epubs/            # generated ebooks (gitignored)
    covers/           # generated covers (gitignored)
    images/           # downloaded blog images (gitignored)
  Dockerfile
  docker-compose.yml
  pyproject.toml      # dependencies (managed by uv)
  uv.lock
```

## Known limitations

- **Long blogs:** no chunking or token limit handling for LLM cleanup. Very long posts may fail sanitization — use `sanitize: false` as a workaround.
- **JS-rendered sites:** fetcher uses `requests` (no browser), so SPAs or JS-heavy sites may return empty content. Works well with static blogs, Substack, Medium, Ghost, Hugo, Jekyll, etc.
- **Kindle detection in Docker:** needs manual volume mount since the Kindle mounts on the host, not inside the container.
- **AZW3 vs EPUB on Kindle:** AZW3 files index reliably. EPUB support varies by Kindle model/firmware.

## Roadmap / ideas

- [ ] Batch processing UI in frontend (currently API-only)
- [ ] Email-to-Kindle support (Send to Kindle via Amazon email)
- [ ] Reading list / queue with history of converted articles
- [ ] Custom LLM model selection from frontend
- [ ] Webhook/notification when batch processing completes
- [ ] Playwright/browser-based fetcher for JS-rendered sites
- [ ] OPDS feed for converted ebooks
- [ ] Mobile-friendly PWA wrapper

## Stack

- **Backend:** Python 3.12 + FastAPI, managed with [uv](https://docs.astral.sh/uv/)
- **Ebook conversion:** [Calibre](https://calibre-ebook.com/) (`ebook-convert`)
- **LLM cleanup:** Gemini 3.1 Flash Lite via [pydantic-ai](https://ai.pydantic.dev/) (optional)
- **Cover generation:** Pillow
- **Frontend:** vanilla HTML/CSS/JS, [Catppuccin Mocha](https://catppuccin.com/) palette, ZedMono Nerd Font
