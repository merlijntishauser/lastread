"""Read books and device-local activity from a Kobo's KoboReader.sqlite.

Findings on a real database (2026-09-30, firmware 6.0) that shape this:
- `content` rows with ContentType 6 are books. `TimeSpentReading`,
  `___PercentRead`, `ReadStatus` and `DateLastRead` are synced through
  Kobo's cloud across every device on the account, so on a shared family
  account they mix everyone's reading.
- `Event` is device-local (it starts on the day the device was set up), so
  a book with an Event row was opened on *this* device.
- The `user` table holds the account's AuthToken/RefreshToken. Uploads must
  not contain it; `open_db` refuses a database that still has it unless the
  caller explicitly allows it (a local import of a raw copy).
"""

from __future__ import annotations

import errno
import hashlib
import os
import sqlite3
from dataclasses import dataclass

from . import epub


class NotAKoboDatabase(ValueError):
    pass


class ContainsKoboTokens(ValueError):
    pass


@dataclass(frozen=True)
class Book:
    content_id: str
    title: str
    author: str
    isbn: str
    percent: int  # 0-100, account-wide
    status: int  # 0 unread, 1 reading, 2 finished (account-wide)
    last_read: str  # ISO timestamp or ""
    seconds_read: int  # TimeSpentReading, account-wide
    first_event: str  # first device-local Event, "" if never opened here
    finished_at: str = ""  # LastTimeFinishedReading: survives reopening a finished book
    image_id: str = ""  # cover id on Kobo's CDN
    language: str = ""  # "nl", "en", ... as the Kobo records it


def open_db(path: str, allow_user_table: bool = False) -> sqlite3.Connection:
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    except sqlite3.DatabaseError as e:
        raise NotAKoboDatabase(f"not a readable SQLite database: {e}") from e
    if "content" not in tables:
        con.close()
        raise NotAKoboDatabase("no `content` table: not a KoboReader.sqlite")
    if "user" in tables and not allow_user_table:
        con.close()
        raise ContainsKoboTokens("the `user` table (Kobo login tokens) must be removed before upload")
    return con


def read_books(con: sqlite3.Connection) -> list[Book]:
    has_event = con.execute("select count(*) from sqlite_master where type='table' and name='Event'").fetchone()[0]
    first_event = {}
    if has_event:
        for cid, first in con.execute("select ContentID, min(coalesce(FirstOccurrence, LastOccurrence)) from Event group by ContentID"):
            first_event[cid] = first or ""
    cols = {r[1] for r in con.execute("pragma table_info(content)")}
    image_col = "ImageId" if "ImageId" in cols else "''"
    lang_col = "Language" if "Language" in cols else "''"
    books = []
    for row in con.execute(
        f"""select ContentID, Title, Attribution, ISBN, ___PercentRead, ReadStatus,
                       DateLastRead, TimeSpentReading, LastTimeFinishedReading, {image_col}, {lang_col}
                from content where ContentType = 6"""
    ):
        cid, title, author, isbn, pct, status, last_read, secs, finished, image_id, language = row
        books.append(
            Book(
                content_id=cid,
                title=(title or "").strip(),
                author=(author or "").strip(),
                isbn=_isbn(isbn),
                percent=int(pct or 0),
                status=int(status or 0),
                last_read=last_read or "",
                seconds_read=int(secs or 0),
                first_event=first_event.get(cid, ""),
                finished_at=finished or "",
                image_id=image_id or "",
                language=(language or "").lower()[:2],
            )
        )
    return books


def _isbn(text: str | None) -> str:
    """The Kobo's own ISBN column as Hardcover keeps an ISBN: thirteen digits,
    also when the Kobo has it with hyphens or spaces, or as an ISBN-10. What
    is no ISBN stays as the Kobo has it."""
    text = (text or "").strip()
    return epub.isbn13(text, marked=True) or text


# ---------- books put on the Kobo by hand ----------
# A sideloaded book's ContentID is its file on the Kobo. The Kobo often
# keeps no ISBN for it; the EPUB itself usually names one (rule M10).
ONBOARD = "file:///mnt/onboard/"
# What reading or writing a file says when the device under it went away.
GONE = (errno.ENOENT, errno.ENODEV, errno.ENXIO, errno.EIO, errno.ENOTDIR, errno.ESTALE)


def _own_file(root: str, cid: str) -> str:
    """The EPUB of a book put on the Kobo by hand, on the Kobo at root; "" for
    a PDF, or a path that leads off the Kobo."""
    path = os.path.realpath(os.path.join(root, cid[len(ONBOARD) :]))
    return path if path.lower().endswith(".epub") and path.startswith(root + os.sep) else ""


def own_files(db_path: str, mount: str) -> list[tuple[str, str]]:
    """Each book put on the Kobo by hand: its id and its EPUB there. db_path
    is the private copy; the Kobo is only read."""
    root = os.path.realpath(mount)
    try:
        con = sqlite3.connect(db_path)
    except sqlite3.DatabaseError:
        return []
    try:
        rows = con.execute(
            "select ContentID from content where ContentType = 6 and substr(ContentID, 1, ?) = ?", (len(ONBOARD), ONBOARD)
        ).fetchall()
    except sqlite3.DatabaseError:
        return []  # read_books says what is wrong with the database
    finally:
        con.close()
    return [(cid, path) for (cid,) in rows if (path := _own_file(root, cid))]


def fill_isbns(db_path: str, mount: str) -> int:
    """Give each book put on the Kobo by hand the ISBN its own EPUB names,
    where the database has none. db_path is the private copy, never the
    Kobo's own file; the Kobo is only read. Returns how many got one."""
    root = os.path.realpath(mount)
    try:
        con = sqlite3.connect(db_path)
    except sqlite3.DatabaseError:
        return 0
    try:
        ids = [
            r[0]
            for r in con.execute(
                "select ContentID from content where ContentType = 6 and substr(ContentID, 1, ?) = ? and coalesce(trim(ISBN), '') = ''",
                (len(ONBOARD), ONBOARD),
            )
        ]
        filled = 0
        for cid in ids:
            path = _own_file(root, cid)
            found = epub.isbn(path) if path else ""
            if found:
                con.execute("update content set ISBN = ? where ContentID = ?", (found, cid))
                filled += 1
        con.commit()
        return filled
    except sqlite3.DatabaseError:
        return 0  # read_books says what is wrong with the database
    finally:
        con.close()


# ---------- the device ----------
# .kobo/version on the device is one line of comma-separated fields. Seen on
# Kobo software 6.0.274403: serial, 4.9.77, 6.0.274403, 4.9.77, 4.9.77,
# 00000000-0000-0000-0000-000000000393 (the last one is the model).
MODELS = {"390": "Kobo Libra Colour", "391": "Kobo Clara BW", "393": "Kobo Clara Colour"}


@dataclass(frozen=True)
class Device:
    serial: str = ""
    software: str = ""  # the Kobo software version, e.g. 6.0.274403
    model: str = ""  # a name when the model id is one of MODELS, else the id

    @property
    def name(self) -> str:
        """A name for this device in the state database: stable for one
        Kobo, different for another, and it does not show the serial."""
        return "kobo-" + hashlib.sha256(self.serial.encode()).hexdigest()[:8] if self.serial else "kobo"


def device(mount: str) -> Device:
    """What the Kobo mounted at `mount` says about itself; empty fields
    when the file is missing or has another shape."""
    try:
        with open(os.path.join(mount, ".kobo", "version"), encoding="utf-8", errors="replace") as fh:
            parts = [p.strip() for p in fh.readline().split(",")]
    except OSError:
        return Device()
    if len(parts) < 6:
        return Device(serial=parts[0] if parts else "")
    model = parts[5].rsplit("-", 1)[-1].lstrip("0")
    return Device(serial=parts[0], software=parts[2], model=MODELS.get(model, f"model {model}" if model else ""))


# ---------- what leaves the computer in server mode ----------
# Exactly what read_books() reads, and nothing else the Kobo keeps in its
# database: no login tokens (user), no DRM keys (content_keys), no reviews,
# wishlist, shelves, activity or reading settings.
UPLOAD_CONTENT = (
    ("ContentID", "TEXT"),
    ("ContentType", "TEXT"),
    ("Title", "TEXT"),
    ("Attribution", "TEXT"),
    ("ISBN", "TEXT"),
    ("___PercentRead", "INT"),
    ("ReadStatus", "INT"),
    ("DateLastRead", "TEXT"),
    ("TimeSpentReading", "INT"),
    ("LastTimeFinishedReading", "TEXT"),
    ("ImageId", "TEXT"),
    ("Language", "TEXT"),
)
UPLOAD_EVENT = ("ContentID", "FirstOccurrence", "LastOccurrence")
UPLOAD_TABLES = {"content", "Event"}


def export_for_upload(src_path: str, dst_path: str) -> int:
    """Write a new database at dst_path with only the book rows and the
    device's reading events, in the columns the server reads. src_path is a
    private copy of the Kobo's database. Returns the number of books."""
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        tables = {r[0] for r in src.execute("select name from sqlite_master where type='table'")}
        if "content" not in tables:
            raise NotAKoboDatabase("no `content` table: not a KoboReader.sqlite")
        have = {r[1] for r in src.execute("pragma table_info(content)")}
        cols = [(c, t) for c, t in UPLOAD_CONTENT if c in have]
        names = ", ".join(c for c, _ in cols)
        dst.execute(f"create table content ({', '.join(f'{c} {t}' for c, t in cols)})")
        dst.execute("create table Event (ContentID TEXT, FirstOccurrence TEXT, LastOccurrence TEXT)")
        books = src.execute(f"select {names} from content where ContentType = 6").fetchall()
        dst.executemany(f"insert into content values ({', '.join('?' * len(cols))})", books)
        if "Event" in tables and set(UPLOAD_EVENT) <= {r[1] for r in src.execute("pragma table_info(Event)")}:
            ids = {b[0] for b in books}
            events = [e for e in src.execute(f"select {', '.join(UPLOAD_EVENT)} from Event") if e[0] in ids]
            dst.executemany("insert into Event values (?, ?, ?)", events)
        dst.commit()
        return len(books)
    except sqlite3.DatabaseError as e:
        raise NotAKoboDatabase(f"not a readable SQLite database: {e}") from e
    finally:
        src.close()
        dst.close()
