from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from fetcher import fetch_blog
from llm import sanitize_markdown
from cover import generate_cover, use_uploaded_cover
from converter import convert_ebook, VALID_FORMATS
from kindle import get_kindle_status, send_to_kindle, list_kindle_books, DEFAULT_KINDLE_SUBDIR

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(
    title="blog2kindle",
    version="0.2.0",
    description="Fetch blog posts, clean them with an LLM, convert to ebook formats, and send to a USB-connected Kindle.",
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
    formats: list[str] = ["epub", "azw3"]


class SanitizeRequest(BaseModel):
    markdown: str


class SendRequest(BaseModel):
    file: str
    kindle_path: str | None = None


class PipelineRequest(BaseModel):
    url: str
    title: str | None = None
    author: str | None = None
    cover: str | None = None
    sanitize: bool = True
    formats: list[str] = ["epub", "azw3"]
    send_to_kindle: bool = False
    kindle_path: str | None = None


class BatchRequest(BaseModel):
    urls: list[str]
    sanitize: bool = True
    formats: list[str] = ["epub", "azw3"]
    send_to_kindle: bool = False
    kindle_path: str | None = None


@app.get("/api/formats", tags=["info"], summary="List supported ebook formats")
def api_formats():
    return {"formats": sorted(VALID_FORMATS)}


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


@app.post("/api/convert", tags=["convert"], summary="Convert markdown to ebook formats")
def api_convert(req: ConvertRequest):
    files = convert_ebook(
        title=req.title,
        markdown_content=req.markdown,
        author=req.author,
        source=req.source,
        cover_filename=req.cover,
        formats=req.formats,
    )
    download_urls = {fmt: f"/static/epubs/{fname}" for fmt, fname in files.items()}
    return {"files": files, "download_urls": download_urls}


@app.post("/api/send-to-kindle", tags=["kindle"], summary="Send an existing file to Kindle")
def api_send_to_kindle(req: SendRequest):
    dst = send_to_kindle(req.file, subdir=req.kindle_path)
    return {"success": True, "kindle_path": dst}


@app.get("/api/kindle/status", tags=["kindle"], summary="Check if Kindle is connected")
def api_kindle_status(kindle_path: str | None = Query(None)):
    return get_kindle_status(subdir=kindle_path)


@app.get("/api/kindle/books", tags=["kindle"], summary="List books on the Kindle")
def api_kindle_books(kindle_path: str | None = Query(None)):
    return {"books": list_kindle_books(subdir=kindle_path)}


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

    files = convert_ebook(
        title=title,
        markdown_content=markdown,
        author=author,
        source=source,
        cover_filename=cover_file,
        formats=req.formats,
    )

    download_urls = {fmt: f"/static/epubs/{fname}" for fmt, fname in files.items()}

    result = {
        "metadata": meta,
        "markdown_preview": blog["markdown"][:500] + "...",
        "cover": cover_file,
        "cover_url": f"/static/covers/{cover_file}",
        "files": files,
        "download_urls": download_urls,
    }

    if req.send_to_kindle:
        kindle_file = files.get("azw3") or files.get("mobi") or files.get("epub")
        if kindle_file:
            dst = send_to_kindle(kindle_file, subdir=req.kindle_path)
            result["kindle_path"] = dst

    return result


def _process_one(url: str, sanitize: bool = True, formats: list[str] | None = None,
                 do_send: bool = False, kindle_path: str | None = None):
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
        files = convert_ebook(
            title=title,
            markdown_content=cleaned,
            author=author,
            source=source,
            cover_filename=cover_file,
            formats=formats,
        )
    except Exception as e:
        return {"url": url, "error": f"convert failed: {e}"}

    result = {
        "url": url,
        "title": title,
        "files": files,
    }

    if do_send:
        kindle_file = files.get("azw3") or files.get("mobi") or files.get("epub")
        if kindle_file:
            try:
                dst = send_to_kindle(kindle_file, subdir=kindle_path)
                result["kindle_path"] = dst
            except Exception as e:
                result["kindle_error"] = str(e)

    return result


@app.post("/api/batch", tags=["pipeline"], summary="Full pipeline for multiple URLs in parallel")
def api_batch(req: BatchRequest):
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_process_one, url, req.sanitize, req.formats, req.send_to_kindle, req.kindle_path): url
            for url in req.urls
        }
        for future in as_completed(futures):
            results.append(future.result())
    return {"results": results}
