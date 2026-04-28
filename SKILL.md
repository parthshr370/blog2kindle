---
name: blog2kindle
description: Convert blog posts and articles to ebooks (EPUB/AZW3/PDF/MOBI) and push to Kindle. Handles URLs, raw pasted content, batch processing, and Kindle file transfer. Triggers on blog URLs shared in chat, pasted article text, or mentions of kindle/ebook/epub/read-later/convert-this.
---

# blog2kindle

A local API that turns blog posts into ebooks. It can fetch a URL, extract the article, optionally clean it with an LLM, generate a cover, convert to any ebook format, and push to a USB-connected Kindle.

The server runs at `http://localhost:8000`. Swagger docs at `/docs`.

## Before you do anything

Make sure the server is up. If it's not, start it from the blog2kindle repo.

```bash
curl -s http://localhost:8000/api/formats > /dev/null 2>&1 && echo "up" || echo "down"
```

If down:
```bash
uv run uvicorn app:app --port 8000 &
sleep 2 && curl -s http://localhost:8000/api/formats > /dev/null 2>&1 && echo "ready" || echo "failed"
```

It may already be running from a previous session. Check before starting a second instance.

Calibre (`ebook-convert`) needs to be in PATH. The Docker setup includes it. Local installs need Calibre installed separately.

## How to think about this

There are really only three scenarios:

**1. User gives you a URL (or several).** Use `/api/pipeline` for one, `/api/batch` for many. These handle everything: fetch, cover, convert, optionally send to Kindle.

**2. User pastes content directly.** Skip fetching entirely. Go straight to `/api/convert` with the text they gave you. You construct the title and author from context.

**3. User wants granular control.** They want to fetch first, preview, maybe clean with LLM, then decide on formats. Use the individual endpoints: `/api/fetch`, `/api/sanitize`, `/api/convert`, `/api/send-to-kindle`.

Most of the time it's scenario 1.

## The endpoints

### Full pipeline (the default choice)

```bash
curl -s -X POST http://localhost:8000/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{"url": "THE_URL", "sanitize": false, "formats": ["epub"]}'
```

If the user wants it on their Kindle too:

```bash
curl -s -X POST http://localhost:8000/api/pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "url": "THE_URL",
    "sanitize": false,
    "formats": ["epub", "azw3"],
    "send_to_kindle": true,
    "kindle_path": "books/fiction/blogs"
  }'
```

You can also override `title`, `author`, and `cover` here if the user wants something specific.

Response gives you `files`, `download_urls`, `metadata`, and `cover_url` (show the cover preview to the user if they'd find it interesting).

### Batch (multiple URLs)

```bash
curl -s -X POST http://localhost:8000/api/batch \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["URL1", "URL2", "URL3"],
    "sanitize": false,
    "formats": ["epub"],
    "send_to_kindle": true,
    "kindle_path": "books/fiction/blogs"
  }'
```

Runs 4 at a time. Results come back unordered (as they finish, not input order). Each URL succeeds or fails on its own -- one bad URL won't break the rest. Report per-URL results.

### Pasted content

User drops article text into chat. Write it to a temp file and use jq to build safe JSON:

```bash
cat > /tmp/b2k_content.md << 'B2K_EOF'
... the pasted content ...
B2K_EOF

jq -n --rawfile md /tmp/b2k_content.md \
  '{title: "Title From Context", markdown: $md, author: "Author If Known", source: "source.com", formats: ["epub"]}' | \
  curl -s -X POST http://localhost:8000/api/convert -H "Content-Type: application/json" -d @-
```

The `source` field is optional but nice -- it adds a "Source: ..." line in the ebook header. Construct `title` and `author` from whatever context you have.

For short snippets, inline JSON works fine:

```bash
curl -s -X POST http://localhost:8000/api/convert \
  -H "Content-Type: application/json" \
  -d '{"title": "Quick Note", "markdown": "# Hello\n\nShort content.", "formats": ["epub"]}'
```

### Fetch only (preview)

```bash
curl -s -X POST http://localhost:8000/api/fetch \
  -H "Content-Type: application/json" \
  -d '{"url": "THE_URL"}'
```

Returns `metadata` (title, author, source, cover_url, description), `markdown` (full text), and `images` (downloaded filenames). Images get saved locally and markdown refs are rewritten to local paths -- if you show the markdown to the user, image links won't render outside the API.

### LLM cleanup

```bash
curl -s -X POST http://localhost:8000/api/sanitize \
  -H "Content-Type: application/json" \
  -d '{"markdown": "RAW_TEXT"}'
```

Needs `GEMINI_API_KEY` or `OPENROUTER_API_KEY` configured. If neither is set, the API returns the raw text unchanged and logs the failure.

### Kindle

```bash
# check connection
curl -s http://localhost:8000/api/kindle/status

# send a file
curl -s -X POST http://localhost:8000/api/send-to-kindle \
  -H "Content-Type: application/json" \
  -d '{"file": "filename.azw3", "kindle_path": "books/fiction/blogs"}'

# list what's on it
curl -s http://localhost:8000/api/kindle/books
```

AZW3 is the best format for Kindle (indexes properly). When `send_to_kindle: true` is used in pipeline/batch, the API auto-picks: azw3 > mobi > epub.

If Kindle's not connected, just give the user the download URLs and let them know to plug in.

### Covers

```bash
# generate from metadata
curl -s -X POST http://localhost:8000/api/cover/generate \
  -H "Content-Type: application/json" \
  -d '{"title": "Post Title", "author": "Author", "image_url": "https://example.com/og.jpg"}'

# upload custom image
curl -s -X POST http://localhost:8000/api/cover/upload \
  -F "file=@/path/to/image.jpg"
```

Both return `cover` (filename) and `preview_url`. Pass the filename as the `cover` param in pipeline or convert.

### Download files

```bash
curl -O http://localhost:8000/static/epubs/filename.epub
```

### List formats

```bash
curl -s http://localhost:8000/api/formats
```

Returns `["azw3", "epub", "mobi", "pdf"]`.

## Parameters worth knowing

- `sanitize` (bool, default `true`) -- the API defaults to LLM cleanup on. Unless the user asks for it, pass `false`.
- `formats` (list, default `["epub", "azw3"]`) -- any combo of `epub`, `azw3`, `pdf`, `mobi`.
- `kindle_path` (string) -- subdirectory on the Kindle. User's default is `books/fiction/blogs`.
- `send_to_kindle` (bool) -- set `true` in pipeline/batch to auto-send. Preferred over calling send-to-kindle separately.
- `title`, `author`, `source`, `cover` -- all overridable in pipeline and convert.

## Things to know

- **JS-rendered sites** (Reddit, some Medium pages, SPAs) will fail or return garbage. The fetcher uses `requests`, not a browser. If a fetch comes back empty or weird, suggest the user paste the content directly instead.
- **Very long articles** may fail LLM cleanup (no chunking). Just use `sanitize: false`.
- **Generated files** accumulate in `static/epubs/`, `static/covers/`, `static/images/`. Not auto-cleaned.
- **LLM without a key** -- the API silently falls back to raw markdown. It won't error, but the cleanup just doesn't happen.
