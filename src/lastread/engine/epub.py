"""The ISBN an EPUB file names for itself. For books put on the Kobo by
hand: the Kobo's database often has no ISBN for them, and an ISBN is the
surest way to the book on Hardcover (rule M10).

The file is the reader's, from anywhere, so it is read with care: only
the package document (the OPF, a few kB), never more than MOST bytes of
it, and anything that is not an EPUB of the usual shape gives "".
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile

CONTAINER = "META-INF/container.xml"
MOST = 1 << 20


def isbn(path: str) -> str:
    """The book's ISBN-13, or "" when the file is not an EPUB, names none,
    or names only numbers that are not ISBNs (a Calibre id, an ASIN, a
    UUID). One marked as an ISBN goes before one that only looks like it."""
    try:
        with zipfile.ZipFile(path) as z:
            opf = _rootfile(z)
            root = ET.fromstring(_read(z, opf)) if opf else None
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError):
        return ""
    if root is None:
        return ""
    marked, unmarked = [], []
    for el in root.iter():
        if _local(el.tag) != "identifier":
            continue
        text = (el.text or "").strip()
        said = "isbn" in text.lower() or any(_local(k) == "scheme" and v.strip().lower() == "isbn" for k, v in el.attrib.items())
        found = isbn13(text.rsplit(":", 1)[-1] if said else text, marked=said)
        if found:
            (marked if said else unmarked).append(found)
    return (marked + unmarked + [""])[0]


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


def _read(z: zipfile.ZipFile, name: str) -> bytes:
    with z.open(name) as fh:
        data = fh.read(MOST + 1)
    if len(data) > MOST:
        raise ValueError(f"{name} is larger than {MOST} bytes")
    return data
