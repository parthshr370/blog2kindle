from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from fetcher import fetch_blog
from llm import sanitize_markdown
from cover import generate_cover, use_uploaded_cover
from converter import convert_to_epub
from kindle import get_kindle_status, send_to_kindle, list_kindle_books

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(
    title="blog2kindle",
    version="0.1.0",
    description="Fetch blog posts, clean them with an LLM, convert to EPUB/AZW3, and send to a USB-connected Kindle.",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


class FetchRequest(BaseModel):
    url: str


class CoverRequest(BaseModel):
    title: str
    author: str | None = None
    source: str | None = None
    image_url: str | None = None


class ConvertRequest(BaseModel):
    title: str
    markdown: str
    author: str | None = None
    source: str | None = None
    cover: str | None = None


class SanitizeRequest(BaseModel):
    markdown: str


class SendRequest(BaseModel):
    file: str


class PipelineRequest(BaseModel):
    url: str
    title: str | None = None
    author: str | None = None
    cover: str | None = None
    sanitize: bool = True
    send_to_kindle: bool = False


class BatchRequest(BaseModel):
    urls: list[str]
    sanitize: bool = True
    send_to_kindle: bool = False


@app.post("/api/fetch", tags=["fetch"], summary="Fetch a single blog URL")
def api_fetch(req: FetchRequest):
    result = fetch_blog(req.url)
    return result


@app.post("/api/sanitize", tags=["cleanup"], summary="Clean raw markdown with LLM")
def api_sanitize(req: SanitizeRequest):
    from llm import _build_agent
    if not _build_agent():
        return {"error": "no API key set — add GEMINI_API_KEY or OPENROUTER_API_KEY to .env"}
    cleaned = sanitize_markdown(req.markdown)
    return {"markdown": cleaned}


@app.post("/api/cover/generate", tags=["cover"], summary="Generate a cover image")
def api_generate_cover(req: CoverRequest):
    filename = generate_cover(req.title, author=req.author, source=req.source, image_url=req.image_url)
    return {"cover": filename, "preview_url": f"/static/covers/{filename}"}


@app.post("/api/cover/upload", tags=["cover"], summary="Upload a custom cover image")
def api_upload_cover(file: UploadFile = File(...)):
    filename = use_uploaded_cover(file)
    return {"cover": filename, "preview_url": f"/static/covers/{filename}"}


@app.post("/api/convert", tags=["convert"], summary="Convert markdown to EPUB + AZW3")
def api_convert(req: ConvertRequest):
    files = convert_to_epub(
        title=req.title,
        markdown_content=req.markdown,
        author=req.author,
        source=req.source,
        cover_filename=req.cover,
    )
    return {
        "epub": files["epub"],
        "azw3": files["azw3"],
        "download_url": f"/static/epubs/{files['epub']}",
    }


@app.post("/api/send-to-kindle", tags=["kindle"], summary="Send an existing file to Kindle")
def api_send_to_kindle(req: SendRequest):
    kindle_path = send_to_kindle(req.file)
    return {"success": True, "kindle_path": kindle_path}


@app.get("/api/kindle/status", tags=["kindle"], summary="Check if Kindle is connected")
def api_kindle_status():
    return get_kindle_status()


@app.get("/api/kindle/books", tags=["kindle"], summary="List books on the Kindle")
def api_kindle_books():
    return {"books": list_kindle_books()}


@app.post("/api/pipeline", tags=["pipeline"], summary="Full pipeline for a single URL")
def api_pipeline(req: PipelineRequest):
    blog = fetch_blog(req.url)
    meta = blog["metadata"]

    title = req.title or meta["title"]
    author = req.author or meta.get("author")
    source = meta.get("source")

    markdown = sanitize_markdown(blog["markdown"]) if req.sanitize else blog["markdown"]

    cover_file = req.cover
    if not cover_file:
        cover_file = generate_cover(title, author=author, source=source, image_url=meta.get("cover_url"))

    files = convert_to_epub(
        title=title,
        markdown_content=markdown,
        author=author,
        source=source,
        cover_filename=cover_file,
    )

    result = {
        "metadata": meta,
        "markdown_preview": blog["markdown"][:500] + "...",
        "cover": cover_file,
        "cover_url": f"/static/covers/{cover_file}",
        "epub": files["epub"],
        "azw3": files["azw3"],
        "download_url": f"/static/epubs/{files['epub']}",
    }

    if req.send_to_kindle:
        kindle_path = send_to_kindle(files["azw3"])
        result["kindle_path"] = kindle_path

    return result


def _process_one(url: str, sanitize: bool = True, send_to_kindle: bool = False):
    """Fetch one blog, optionally sanitize, convert, optionally send to Kindle."""
    try:
        blog = fetch_blog(url)
    except Exception as e:
        return {"url": url, "error": f"fetch failed: {e}"}

    meta = blog["metadata"]
    title = meta["title"]
    author = meta.get("author")
    source = meta.get("source")

    try:
        cleaned = sanitize_markdown(blog["markdown"]) if sanitize else blog["markdown"]
    except Exception as e:
        return {"url": url, "error": f"sanitize failed: {e}"}

    try:
        cover_file = generate_cover(title, author=author, source=source, image_url=meta.get("cover_url"))
    except Exception:
        cover_file = None

    try:
        files = convert_to_epub(
            title=title,
            markdown_content=cleaned,
            author=author,
            source=source,
            cover_filename=cover_file,
        )
    except Exception as e:
        return {"url": url, "error": f"convert failed: {e}"}

    result = {
        "url": url,
        "title": title,
        "epub": files["epub"],
        "azw3": files["azw3"],
    }

    if send_to_kindle:
        try:
            kindle_path = send_to_kindle(files["azw3"])
            result["kindle_path"] = kindle_path
        except Exception as e:
            result["kindle_error"] = str(e)

    return result


@app.post("/api/batch", tags=["pipeline"], summary="Full pipeline for multiple URLs in parallel")
def api_batch(req: BatchRequest):
    """Process multiple URLs in parallel. Returns per-URL results."""
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_process_one, url, req.sanitize, req.send_to_kindle): url for url in req.urls}
        for future in as_completed(futures):
            results.append(future.result())
    return {"results": results}
