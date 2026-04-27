import os
import hashlib
import textwrap
import tempfile

import requests
from PIL import Image, ImageDraw, ImageFont


COVERS_DIR = os.path.join(os.path.dirname(__file__), "static", "covers")
KINDLE_WIDTH = 1072
KINDLE_HEIGHT = 1448


def _get_font(size):
    font_paths = [
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _get_font_regular(size):
    font_paths = [
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _download_cover_image(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".img")
        tmp.write(r.content)
        tmp.close()
        return Image.open(tmp.name).convert("RGB")
    except Exception:
        return None


def generate_cover(title, author=None, source=None, image_url=None):
    os.makedirs(COVERS_DIR, exist_ok=True)

    img = Image.new("RGB", (KINDLE_WIDTH, KINDLE_HEIGHT), "#1a1a2e")
    draw = ImageDraw.Draw(img)

    # accent bar at top
    draw.rectangle([0, 0, KINDLE_WIDTH, 12], fill="#e94560")

    # source label
    y_cursor = 80
    if source:
        font_source = _get_font_regular(36)
        draw.text((80, y_cursor), source.upper(), font=font_source, fill="#e94560")
        y_cursor += 60

    # title
    font_title = _get_font(72)
    wrapped = textwrap.fill(title, width=22)
    y_title = max(y_cursor + 40, 180)
    draw.multiline_text((80, y_title), wrapped, font=font_title, fill="#ffffff", spacing=20)

    bbox = draw.multiline_textbbox((80, y_title), wrapped, font=font_title, spacing=20)
    y_after_title = bbox[3] + 40

    # author
    if author:
        font_author = _get_font_regular(42)
        draw.text((80, y_after_title + 20), author, font=font_author, fill="#aaaaaa")
        y_after_title += 80

    # divider line
    y_after_title += 30
    draw.line([(80, y_after_title), (KINDLE_WIDTH - 80, y_after_title)], fill="#e94560", width=3)
    y_after_title += 40

    # blog image centered below title
    blog_img = _download_cover_image(image_url) if image_url else None
    if blog_img:
        margin = 80
        available_w = KINDLE_WIDTH - margin * 2
        bottom_reserve = 120
        available_h = KINDLE_HEIGHT - y_after_title - bottom_reserve

        if available_h > 100:
            ratio = min(available_w / blog_img.width, available_h / blog_img.height)
            new_w = int(blog_img.width * ratio)
            new_h = int(blog_img.height * ratio)
            blog_img = blog_img.resize((new_w, new_h), Image.LANCZOS)

            x = (KINDLE_WIDTH - new_w) // 2
            y = y_after_title + (available_h - new_h) // 2
            img.paste(blog_img, (x, y))

    # bottom label
    font_bottom = _get_font_regular(28)
    draw.text(
        (80, KINDLE_HEIGHT - 100),
        "blog2kindle",
        font=font_bottom,
        fill="#555555",
    )

    slug = hashlib.md5(title.encode()).hexdigest()[:10]
    filename = f"cover_{slug}.jpg"
    path = os.path.join(COVERS_DIR, filename)
    img.save(path, "JPEG", quality=90)
    return filename


def use_uploaded_cover(upload_file):
    """Accepts a FastAPI UploadFile."""
    os.makedirs(COVERS_DIR, exist_ok=True)
    img = Image.open(upload_file.file)
    img = img.resize((KINDLE_WIDTH, KINDLE_HEIGHT), Image.LANCZOS)
    name = hashlib.md5((upload_file.filename or "upload").encode()).hexdigest()[:10]
    filename = f"cover_{name}.jpg"
    path = os.path.join(COVERS_DIR, filename)
    img.save(path, "JPEG", quality=90)
    return filename
