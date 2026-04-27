import os
import hashlib
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md


IMAGES_DIR = os.path.join(os.path.dirname(__file__), "static", "images")


def _download_image(url, session):
    os.makedirs(IMAGES_DIR, exist_ok=True)
    ext = os.path.splitext(urlparse(url).path)[1] or ".png"
    name = hashlib.md5(url.encode()).hexdigest() + ext
    path = os.path.join(IMAGES_DIR, name)
    if not os.path.exists(path):
        try:
            r = session.get(url, timeout=15)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
        except Exception:
            return None
    return name


def _extract_article(soup, url):
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    article = soup.find("article")
    if article and len(article.get_text()) > 200:
        return article

    candidates = soup.find_all(
        "div", class_=re.compile(r"post|article|entry|content|blog|body|rich-text", re.I)
    )
    if candidates:
        article = max(candidates, key=lambda el: len(el.get_text()))
        if len(article.get_text()) > 200:
            return article

    main = soup.find("main")
    if main and len(main.get_text()) > 200:
        return main

    return soup.find("body") or soup


def _extract_metadata(soup, url):
    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title.get("content")
    if not title:
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else "Untitled"

    author = None
    author_meta = soup.find("meta", attrs={"name": "author"})
    if author_meta:
        author = author_meta.get("content")

    description = None
    desc_meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", property="og:description"
    )
    if desc_meta:
        description = desc_meta.get("content")

    og_image = soup.find("meta", property="og:image")
    cover_url = og_image.get("content") if og_image else None

    source = urlparse(url).netloc.replace("www.", "")

    return {
        "title": title,
        "author": author,
        "description": description,
        "cover_url": cover_url,
        "source": source,
        "url": url,
    }


def fetch_blog(url):
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )

    resp = session.get(url, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    metadata = _extract_metadata(soup, url)
    article = _extract_article(soup, url)

    for img in article.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        abs_url = urljoin(url, src)
        local_name = _download_image(abs_url, session)
        if local_name:
            img["src"] = f"images/{local_name}"

    markdown = md(
        str(article),
        heading_style="ATX",
        code_language_callback=lambda el: el.get("class", [""])[0].replace("language-", "")
        if el.get("class")
        else "",
    )

    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()

    images = [
        f for f in os.listdir(IMAGES_DIR) if os.path.isfile(os.path.join(IMAGES_DIR, f))
    ]

    return {
        "metadata": metadata,
        "markdown": markdown,
        "images": images,
    }
