"""Book covers: fetched once from Kobo's public cover CDN by the book's
ImageId, kept in DATA/covers, served by the app itself. The browser never
talks to Kobo; the page loads nothing from outside.

A book without a usable cover gets a marker file, so a missing cover is
asked for once a week, not on every page view. Only an answer from the
CDN says a cover is missing: when it cannot be reached (offline, a
timeout, its own trouble) nothing is marked, and it is asked again after
a minute.

A book put on the Kobo by hand has no cover there: the Kobo makes its ImageId
from the file's path, and that is never sent to the CDN. A sync keeps the
picture the EPUB names instead (own_path), on the computer the Kobo is plugged
into; it does not go to a server.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
import urllib.error
import urllib.request

CDN = os.environ.get("KHS_COVER_URL") or "https://cdn.kobo.com/book-images/{id}/{size}/False/image.jpg"
# width/height/quality as Kobo's CDN takes them. "large" is for the lightbox:
# sharp on a laptop or retina screen at about 420 KB (2400 wide is over 1 MB).
SIZES = {"thumb": "240/360/85", "large": "1200/1800/90"}
# The id goes into a URL and a filename. file____mnt_onboard_...: a file's path, the reader's own, and no cover of Kobo's.
ID_OK = re.compile(r"^(?!file_)[A-Za-z0-9_-]{1,80}$")
OWN = "own-covers"
RETRY_MISSING_AFTER = 7 * 86400
MAX_BYTES = 4 * 1024 * 1024
RETRY_UNREACHABLE_AFTER = 60  # seconds, for every cover at once: offline, each would wait for its own timeout
_unreachable_since = 0.0


class Unreachable(Exception):
    """The CDN could not be asked; this says nothing about the cover."""


def download(image_id: str, size: str = "thumb") -> bytes | None:
    """The cover as JPEG bytes, or None when the CDN says there is none;
    Unreachable when it could not say. Separate so tests can replace it."""
    req = urllib.request.Request(CDN.format(id=image_id, size=SIZES[size]), headers={"User-Agent": "lastread"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status != 200 or "image" not in r.headers.get("Content-Type", ""):
                return None
            data = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as ex:
        if ex.code == 429 or ex.code >= 500:  # the CDN's own trouble, not an answer about the cover
            raise Unreachable(str(ex)) from ex
        return None
    except Exception as ex:  # no network, DNS, a timeout, a connection cut halfway
        raise Unreachable(str(ex)) from ex
    return data if 0 < len(data) <= MAX_BYTES else None


def _own(data_dir: str, content_id: str) -> str:
    return os.path.join(data_dir, OWN, hashlib.sha256(content_id.encode()).hexdigest()[:40])


def own_path(data_dir: str, content_id: str) -> str | None:
    """The picture a sync kept from the book's own EPUB, or None."""
    stem = _own(data_dir, content_id)
    return next((stem + ext for ext in (".jpg", ".png") if os.path.exists(stem + ext)), None)


def keep_own(data_dir: str, content_id: str, data: bytes) -> None:
    """Keep the picture of the book's own EPUB: a JPEG, or a PNG (epub.cover)."""
    os.makedirs(os.path.join(data_dir, OWN), exist_ok=True)
    _write(_own(data_dir, content_id) + (".png" if data.startswith(b"\x89PNG") else ".jpg"), data)


def _write(path: str, data: bytes) -> None:
    """Whole or not at all: one temporary file per call, as the page's threads fetch at once."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=f".{os.path.basename(path)}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def cover_path(data_dir: str, image_id: str, size: str = "thumb") -> str | None:
    """Path of the cached cover, fetching it on first use. None = no cover."""
    if not image_id or not ID_OK.match(image_id) or size not in SIZES:
        return None
    d = os.path.join(data_dir, "covers")
    os.makedirs(d, exist_ok=True)
    stem = image_id if size == "thumb" else f"{image_id}.{size}"
    path, missing = os.path.join(d, stem + ".jpg"), os.path.join(d, stem + ".none")
    if os.path.exists(path):
        return path
    if os.path.exists(missing) and time.time() - os.path.getmtime(missing) < RETRY_MISSING_AFTER:
        return None
    global _unreachable_since
    if time.time() - _unreachable_since < RETRY_UNREACHABLE_AFTER:
        return None
    try:
        data = download(image_id, size)
    except Unreachable:
        _unreachable_since = time.time()
        return None
    if data is None:
        open(missing, "w").close()
        return None
    _write(path, data)
    if os.path.exists(missing):
        os.unlink(missing)
    return path
