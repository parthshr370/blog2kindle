import os
import sys
import shutil
import glob

EPUBS_DIR = os.path.join(os.path.dirname(__file__), "static", "epubs")

DEFAULT_KINDLE_SUBDIR = os.environ.get("KINDLE_BOOKS_PATH", "books/fiction/blogs")

KINDLE_MOUNT_PATTERNS = {
    "linux": [
        "/run/media/*/Kindle",
        "/media/*/Kindle",
        "/mnt/Kindle",
    ],
    "darwin": [
        "/Volumes/Kindle",
    ],
    "win32": [
        "D:\\Kindle",
        "E:\\Kindle",
        "F:\\Kindle",
        "G:\\Kindle",
    ],
}


def find_kindle():
    platform = sys.platform
    if platform.startswith("linux"):
        patterns = KINDLE_MOUNT_PATTERNS["linux"]
    elif platform == "darwin":
        patterns = KINDLE_MOUNT_PATTERNS["darwin"]
    elif platform == "win32":
        patterns = KINDLE_MOUNT_PATTERNS["win32"]
    else:
        patterns = KINDLE_MOUNT_PATTERNS["linux"]

    for pattern in patterns:
        matches = glob.glob(pattern)
        for m in matches:
            if os.path.isdir(m):
                return m

    if platform == "win32":
        import string
        for letter in string.ascii_uppercase:
            path = f"{letter}:\\documents"
            kindle_marker = f"{letter}:\\system\\version.txt"
            if os.path.isdir(path) and os.path.exists(kindle_marker):
                return f"{letter}:\\"

    return None


def _resolve_books_dir(kindle_path, subdir=None):
    sub = subdir if subdir else DEFAULT_KINDLE_SUBDIR
    books_dir = os.path.join(kindle_path, sub)
    os.makedirs(books_dir, exist_ok=True)
    return books_dir


def get_kindle_status(subdir=None):
    path = find_kindle()
    if not path:
        return {"connected": False, "path": None, "books_dir": None, "kindle_path": DEFAULT_KINDLE_SUBDIR}

    books_dir = _resolve_books_dir(path, subdir)

    return {
        "connected": True,
        "path": path,
        "books_dir": books_dir,
        "kindle_path": subdir or DEFAULT_KINDLE_SUBDIR,
    }


def send_to_kindle(filename, subdir=None):
    path = find_kindle()
    if not path:
        raise RuntimeError("Kindle not connected")

    src = os.path.join(EPUBS_DIR, filename)
    if not os.path.exists(src):
        raise FileNotFoundError(f"File not found: {filename}")

    books_dir = _resolve_books_dir(path, subdir)
    dst = os.path.join(books_dir, filename)
    shutil.copy2(src, dst)
    return dst


def list_kindle_books(subdir=None):
    path = find_kindle()
    if not path:
        return []

    books_dir = _resolve_books_dir(path, subdir)
    books = []
    for entry in os.listdir(books_dir):
        full = os.path.join(books_dir, entry)
        if os.path.isfile(full):
            books.append(entry)
    return sorted(books)
