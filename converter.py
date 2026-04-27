import os
import re
import subprocess
import tempfile
import shutil
import mistune

EPUBS_DIR = os.path.join(os.path.dirname(__file__), "static", "epubs")
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "static", "images")
COVERS_DIR = os.path.join(os.path.dirname(__file__), "static", "covers")


def _build_html(title, markdown_content, author=None, source=None):
    html_body = _markdown_to_html(markdown_content)

    header = f"<h1>{title}</h1>\n"
    if source:
        header += f'<p style="color: #888; font-size: 0.9em;">Source: {source}</p>\n'
    if author:
        header += f'<p style="color: #888; font-size: 0.9em;">By {author}</p>\n'
    header += "<hr/>\n"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
body {{ font-family: Georgia, serif; line-height: 1.6; margin: 2em; }}
h1, h2, h3 {{ font-family: Helvetica, Arial, sans-serif; }}
pre {{ background: #f4f4f4; padding: 1em; overflow-x: auto; font-size: 0.85em; }}
code {{ background: #f4f4f4; padding: 2px 4px; font-size: 0.9em; }}
pre code {{ background: none; padding: 0; }}
img {{ max-width: 100%; height: auto; }}
blockquote {{ border-left: 3px solid #ccc; margin-left: 0; padding-left: 1em; color: #555; }}
</style>
</head>
<body>
{header}
{html_body}
</body>
</html>"""


def _markdown_to_html(text):
    return mistune.html(text)


def _slugify(title):
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')[:60]
    return slug


def _run_ebook_convert(cmd):
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env["PATH"] = "/usr/bin:/usr/local/bin:" + env.get("PATH", "")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"ebook-convert failed: {result.stderr}")


def convert_to_epub(title, markdown_content, author=None, source=None, cover_filename=None):
    os.makedirs(EPUBS_DIR, exist_ok=True)

    slug = _slugify(title)
    epub_filename = f"{slug}.epub"
    azw3_filename = f"{slug}.azw3"
    epub_path = os.path.join(EPUBS_DIR, epub_filename)
    azw3_path = os.path.join(EPUBS_DIR, azw3_filename)

    with tempfile.TemporaryDirectory() as tmpdir:
        html_content = _build_html(title, markdown_content, author, source)

        tmp_images = os.path.join(tmpdir, "images")
        if os.path.exists(IMAGES_DIR):
            shutil.copytree(IMAGES_DIR, tmp_images)

        html_path = os.path.join(tmpdir, "article.html")
        with open(html_path, "w") as f:
            f.write(html_content)

        base_args = [
            "--title", title,
            "--language", "en",
            "--tags", "blog",
            "--publisher", source or "blog2kindle",
        ]

        if author:
            base_args.extend(["--authors", author])

        if cover_filename:
            cover_path = os.path.join(COVERS_DIR, cover_filename)
            if os.path.exists(cover_path):
                base_args.extend(["--cover", cover_path])

        # generate EPUB
        cmd_epub = [
            "ebook-convert", html_path, epub_path,
            "--no-default-epub-cover", "--epub-inline-toc",
        ] + base_args
        _run_ebook_convert(cmd_epub)

        # generate AZW3 (native Kindle format)
        cmd_azw3 = [
            "ebook-convert", html_path, azw3_path,
        ] + base_args
        _run_ebook_convert(cmd_azw3)

    return {"epub": epub_filename, "azw3": azw3_filename}
