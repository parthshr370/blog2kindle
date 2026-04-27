import os
import shutil
import glob

EPUBS_DIR = os.path.join(os.path.dirname(__file__), "static", "epubs")

KINDLE_MOUNT_PATHS = [
    "/run/media/*/Kindle",
    "/media/*/Kindle",
    "/mnt/Kindle",
]


def find_kindle():
    for pattern in KINDLE_MOUNT_PATHS:
        matches = glob.glob(pattern)
        for m in matches:
            if os.path.isdir(m):
                return m
    return None


def get_kindle_status():
    path = find_kindle()
    if not path:
        return {"connected": False, "path": None, "books_dir": None}

    books_dir = os.path.join(path, "documents")
    os.makedirs(books_dir, exist_ok=True)

    return {
        "connected": True,
        "path": path,
        "books_dir": books_dir,
    }


def send_to_kindle(filename):
    status = get_kindle_status()
    if not status["connected"]:
        raise RuntimeError("Kindle not connected")

    src = os.path.join(EPUBS_DIR, filename)
    if not os.path.exists(src):
        raise FileNotFoundError(f"File not found: {filename}")

    dst = os.path.join(status["books_dir"], filename)
    shutil.copy2(src, dst)
    return dst


def list_kindle_books():
    status = get_kindle_status()
    if not status["connected"]:
        return []

    books = []
    for entry in os.listdir(status["books_dir"]):
        full = os.path.join(status["books_dir"], entry)
        if os.path.isfile(full):
            books.append(entry)
    return sorted(books)
