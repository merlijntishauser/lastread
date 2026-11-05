"""The ISBN an EPUB file names for itself, inside it or else in its file
name, as some shops name theirs. For books put on the Kobo by hand: the Kobo's database often has no ISBN for them, and an ISBN is the
surest way to the book on Hardcover (rule M10). Its title and author
too, for the books of the folder that goes on the Kobo (tokobo), and its
cover, which Kobo's cover server does not have for such a book.

The file is the reader's, from anywhere, so it is read with care: only
the package document (the OPF, a few kB), never more than MOST bytes of
it, and anything that is not an EPUB of the usual shape gives "".
"""

from __future__ import annotations

import os
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from urllib.parse import unquote

CONTAINER = "META-INF/container.xml"
MOST = 1 << 20
COVER_MOST = 4 << 20  # as much as a cover from Kobo's cover server may be (web/covers.py)
PICTURES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")  # JPEG and PNG: what every place a cover is shown can show
IN_NAME = re.compile(r"(?<!\d)97[89](?:[ -]?\d){10}(?!\d)")


def isbn(path: str) -> str:
    """The book's ISBN-13, or "" when the file is not an EPUB, names none,
    or names only numbers that are not ISBNs (a Calibre id, an ASIN, a
    UUID). One marked as an ISBN goes before one that only looks like it,
    and either goes before the one in the file's name (in_name)."""
    return about(path)["isbn"]


def about(path: str) -> dict:
    """What the book says of itself: its title, its first author and its
    ISBN (as isbn() finds it); "" for each the file does not say."""
    found = {"title": "", "author": "", "isbn": ""}
    try:
        with zipfile.ZipFile(path) as z:
            opf = _rootfile(z)
            root = ET.fromstring(_read(z, opf)) if opf else None
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError):
        return found
    if root is None:
        return found
    marked, unmarked = [], []
    for el in root.iter():
        tag, text = _local(el.tag), " ".join((el.text or "").split())
        if tag in ("title", "creator") and text and not found["title" if tag == "title" else "author"]:
            found["title" if tag == "title" else "author"] = text
        if tag != "identifier":
            continue
        said = "isbn" in text.lower() or any(_local(k) == "scheme" and v.strip().lower() == "isbn" for k, v in el.attrib.items())
        isbn = isbn13(text.rsplit(":", 1)[-1] if said else text, marked=said)
        if isbn:
            (marked if said else unmarked).append(isbn)
    found["isbn"] = (marked + unmarked + [in_name(path)])[0]
    return found


def in_name(path: str) -> str:
    """The ISBN-13 in the file's own name, its check digit right, or "" when
    there is none. Two different ones say nothing: which is the book's is
    not known. Ten digits are not taken, as in the book itself unmarked."""
    found = {isbn13(number) for number in IN_NAME.findall(os.path.basename(path))} - {""}
    return found.pop() if len(found) == 1 else ""


def cover(path: str) -> bytes | None:
    """The picture the book names as its cover, or None when it names none,
    or one that is not a JPEG or PNG, or larger than COVER_MOST. Read from the
    archive, never unpacked, so a path in the file leads nowhere outside it."""
    try:
        with zipfile.ZipFile(path) as z:
            opf = _rootfile(z)
            href = _cover_href(ET.fromstring(_read(z, opf))) if opf else ""
            if not href:
                return None
            data = _read(z, posixpath.normpath(posixpath.join(posixpath.dirname(opf), unquote(href))), COVER_MOST)
    except (OSError, ValueError, KeyError, EOFError, RuntimeError, NotImplementedError, zipfile.BadZipFile, zlib.error, ET.ParseError):
        return None
    return data if data.startswith(PICTURES) else None


def _cover_href(root: ET.Element) -> str:
    """Where the package document says the cover is: the item marked as the
    cover image (EPUB 3), else the item its cover meta names (EPUB 2). Never
    guessed from a file's name: a wrong picture is worse than none."""
    items = [el for el in root.iter() if _local(el.tag) == "item"]
    for el in items:
        if "cover-image" in (el.get("properties") or "").split():
            return el.get("href", "")
    named = next((el.get("content") for el in root.iter() if _local(el.tag) == "meta" and (el.get("name") or "").lower() == "cover"), None)
    return next((el.get("href", "") for el in items if named and el.get("id") == named), "")


def isbn13(text: str, marked: bool = False) -> str:
    """text as an ISBN-13 when it is a valid ISBN: 13 digits starting 978
    or 979, or (only when it is marked as an ISBN) 10 with their check
    digit, turned into 13. Hyphens, spaces and an "ISBN" in front do not
    count."""
    s = re.sub(r"[\s-]", "", re.sub(r"(?i)^\s*isbn(-1[03])?\s*:?", "", text)).upper()
    if re.fullmatch(r"97[89]\d{10}", s) and _check13(s[:12]) == s[12]:
        return s
    if marked and re.fullmatch(r"\d{9}[\dX]", s) and sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(s)) % 11 == 0:
        return "978" + s[:9] + _check13("978" + s[:9])
    return ""


def _check13(twelve: str) -> str:
    return str(-sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(twelve)) % 10)


def _local(name: str) -> str:
    """A tag or attribute name without its namespace."""
    return name.rsplit("}", 1)[-1]


def _rootfile(z: zipfile.ZipFile) -> str:
    """Where the package document is: as META-INF/container.xml says, or
    else the one .opf file there is."""
    try:
        container = ET.fromstring(_read(z, CONTAINER))
    except KeyError:
        container = None
    for el in container.iter() if container is not None else ():
        if (
            _local(el.tag) == "rootfile"
            and el.get("full-path")
            and el.get("media-type", "application/oebps-package+xml") == "application/oebps-package+xml"
        ):
            return el.get("full-path", "")
    opfs = [n for n in z.namelist() if n.lower().endswith(".opf")]
    return opfs[0] if len(opfs) == 1 else ""


def _read(z: zipfile.ZipFile, name: str, most: int = MOST) -> bytes:
    with z.open(name) as fh:
        data = fh.read(most + 1)
    if len(data) > most:
        raise ValueError(f"{name} is larger than {most} bytes")
    return data
