"""Books from a folder of the reader's, put on the Kobo when it is plugged
in (docs/plans/2026-11-01-to-kobo-folder-design.md; rules P1-P6).

Only files are written, into one folder on the Kobo (FOLDER). The Kobo's
database is never opened for this: the Kobo finds the new files itself
after the eject. What was put on which Kobo is remembered in the state
folder (REMEMBERED), by each file's SHA-256, so a book is put on each Kobo
once, and one deleted on the Kobo stays deleted. The hashes of the
folder's files are kept there too, by path, size and time, so a folder of
hundreds of books is not read whole at every plug-in.

A book with DRM is not copied: it would not open on the Kobo. Nothing is
ever decrypted; the file is only looked at for the marks DRM leaves.

A plain EPUB goes on the Kobo as kepub when kepubify is there (P7): the
Kobo's own renderer, with its reading statistics. kepubify (MIT, by
Patrick Gaskin) comes with the Mac app, and elsewhere is the reader's own
install; it is run on a copy in a
temporary folder of this computer, never on the Kobo and never on the
reader's file. Seen with kepubify 4.0.4: `kepubify -o OUT IN` with one
input and an OUT that does not exist writes OUT, keeps the OPF (and so
the ISBN, M10), and exits non-zero on a book it cannot read.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime

from . import epub
from .kobo_db import GONE, ONBOARD

log = logging.getLogger(__name__)

FOLDER = "Lastread"  # on the Kobo's own storage
PARTIAL = ".lastread-"  # a copy on its way: hidden, so the Kobo does not list it
REMEMBERED = "to-kobo.json"
SPARE = 50 << 20  # room left on the Kobo after a copy
MANY = 20  # more than this at once is asked about first (`to-kobo --yes`)
KEPUB = ".kepub.epub"
CONVERT_SECONDS = 300  # one book; kepubify takes a second or two
# Where kepubify is when the plug-in trigger's PATH does not have it: Homebrew's, and `go install`'s.
KEPUBIFY_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "~/go/bin")
# The Mac app's own, next to the Python it runs on (Contents/Resources/bin, build.sh): looked at first.
BUNDLED = os.path.join(os.path.dirname(sys.prefix), "bin", "kepubify")
# Font obfuscation is not DRM: the book opens anywhere (EPUB 3, 4.2; Adobe's older one).
FONTS = {"http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"}
# A copy refused for the whole Kobo, not for one book: the rest would hear the same.
WHOLE_KOBO = (errno.EROFS, errno.EACCES, errno.EPERM, errno.ENOSPC, errno.EDQUOT)
# Not allowed in a name on the Kobo's FAT storage; put as "_" instead.
NOT_ON_FAT = str.maketrans({c: "_" for c in '<>:"/\\|?*'} | {chr(c): "_" for c in range(32)})


@dataclass
class Result:
    put: list[str] = field(default_factory=list)  # file names, as they are on the Kobo now
    refused: list[tuple[str, str]] = field(default_factory=list)  # (file name, why), said once per file
    left: int = 0  # not put this time: the Kobo is full, or went away
    kepubify: str = ""  # the kepubify that converted, "" when there is none
    as_epub: list[str] = field(default_factory=list)  # plain EPUBs put on the Kobo as they are
    unconverted: list[str] = field(default_factory=list)  # of those, the ones kepubify could not convert
    why_left: str = ""  # "full", "unplugged", or what the Kobo said when it refused every copy


def books_in(folder: str) -> list[str]:
    """The EPUBs in the folder and the folders in it, sorted; hidden ones
    left out (P1, P2)."""
    found = []
    for here, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        found += [os.path.join(here, f) for f in sorted(files) if f.lower().endswith(".epub") and not f.startswith(".")]
    return found


def drm(path: str) -> str:
    """Why this EPUB would not open on the Kobo, "" when it would (P2)."""
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "META-INF/rights.xml" in names:
                return "it has Adobe DRM; open it with Adobe Digital Editions"
            if "META-INF/license.lcpl" in names:
                return "it has Readium LCP DRM; open it with the app of the shop or library"
            if "META-INF/encryption.xml" in names:
                with z.open("META-INF/encryption.xml") as fh:
                    root = ET.fromstring(fh.read(1 << 20))
                methods = {el.get("Algorithm", "") for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "EncryptionMethod"}
                if methods - FONTS:
                    return "it is encrypted (DRM)"
    except (OSError, zipfile.BadZipFile, ET.ParseError):
        return "it is not an EPUB that can be read"
    return ""


def waiting(folder: str, device: str, state_dir: str) -> list[str]:
    """The books in the folder this Kobo has not been given yet; with
    device "", the ones no Kobo has been given yet."""
    remembered = _remembered(state_dir)
    kobos = remembered["kobos"]
    done = kobos.get(device, {}) if device else {sha for books in kobos.values() for sha in books}
    out = [p for p in books_in(folder) if _hash(remembered, p) not in done]
    _keep(state_dir, remembered)
    return out


class Refused(ValueError):
    """A folder that is not taken: key names the reason (strings for the page), n the books waiting."""

    def __init__(self, key: str, text: str, n: int = 0):
        super().__init__(text)
        self.key, self.n = key, n


def choose(folder: str, mount: str | None, state_dir: str, yes: bool = False) -> tuple[str, int]:
    """The folder as it is kept (absolute), and how many of its books no
    Kobo has yet; Refused when it cannot be taken: not a folder, on the
    Kobo itself, or more than MANY books at once without yes (P1). The
    command, the page and the Mac app all choose through this."""
    folder = os.path.abspath(os.path.expanduser(folder.strip()))
    if not os.path.isdir(folder):
        raise Refused("not_a_folder", f"{folder} is not a folder.")
    if mount and inside(folder, mount):
        raise Refused("on_the_kobo", f"{folder} is on the Kobo itself; choose a folder on this computer.")
    n = len(waiting(folder, "", state_dir))
    if n > MANY and not yes:
        raise Refused("too_many", f"{n} books in {folder} would go on the Kobo at the next plug-in.", n)
    return folder, n


def summary(folder: str, state_dir: str) -> dict:
    """What the page and the app show about the folder: whether it is
    there, how many books it holds and how many wait for a Kobo, the ones
    that were refused (still in the folder) and why, the kepubify that
    converts them ("" for none), and each book (books())."""
    out = {"folder": folder, "there": bool(folder) and os.path.isdir(folder), "books": 0, "waiting": 0, "refused": [], "list": []}
    out["kepubify"] = find_kepubify()
    if not out["there"]:
        return out
    out["list"] = books(folder, state_dir)
    out["books"] = len(out["list"])
    out["waiting"] = sum(1 for b in out["list"] if b["kobo"] == "waiting")
    out["refused"] = [{"name": os.path.basename(b["name"]), "why": b["why"]} for b in out["list"] if b["kobo"] == "refused"]
    return out


def books(folder: str, state_dir: str) -> list[dict]:
    """Each book of the folder: its name there (with the folder it is in),
    what it says of itself (epub.about), and where it is with the Kobos:
    "on" one, "refused" (why says why), or "waiting" for the next plug-in.
    For one on a Kobo, when it went (at), its format (kepub or EPUB), and the
    ids the Kobo knows it by (its ContentID: the id of `books --json`)."""
    remembered = _remembered(state_dir)
    out = []
    for path in books_in(folder):
        sha = _hash(remembered, path)
        on = [kobo[sha] for kobo in remembered["kobos"].values() if sha in kobo]
        put = sorted((v for v in on if not v.get("refused")), key=lambda v: v.get("at", ""))
        refused = next((v["refused"] for v in on if v.get("refused")), "")
        name = put[0]["name"] if put else os.path.basename(path)
        out.append(
            {
                "name": os.path.relpath(path, folder),
                **_about(remembered, path),
                "kobo": "on" if put else "refused" if refused else "waiting",
                "why": "" if put else refused,
                "at": put[0].get("at", "") if put else "",
                "format": ("kepub" if name.lower().endswith(KEPUB) else "epub") if put else "",
                "ids": sorted({ONBOARD + _where(v) for v in put if _where(v)}),
            }
        )
    _keep(state_dir, remembered)
    return out


def inside(folder: str, mount: str) -> bool:
    """Whether the folder is on the Kobo itself: then there is nothing to put there."""
    folder, mount = os.path.realpath(folder), os.path.realpath(mount)
    return folder == mount or folder.startswith(mount + os.sep)


def find_kepubify() -> str:
    """kepubify: the Mac app's own, else one installed on the PATH, or
    where Homebrew and Go put it; "" when there is none."""
    if os.path.isfile(BUNDLED) and os.access(BUNDLED, os.X_OK):
        return BUNDLED
    for d in ("", *KEPUBIFY_DIRS):
        found = shutil.which("kepubify", path=os.path.expanduser(d) if d else None)
        if found:
            return found
    return ""


def put(folder: str, mount: str, device: str, state_dir: str, kepubify: str | None = None) -> Result:
    """Put each book of the folder on the Kobo at mount that this Kobo has
    not had from here yet. device names the Kobo (kobo_db.Device.name).
    kepubify: the program to convert with; None looks for it, "" is none."""
    r = Result()
    if inside(folder, mount):
        return r
    remembered = _remembered(state_dir)
    done = remembered["kobos"].setdefault(device, {})
    target = os.path.join(mount, FOLDER)
    todo = [(p, sha) for p in books_in(folder) if (sha := _hash(remembered, p)) not in done]
    _keep(state_dir, remembered)
    if not todo:
        return r
    os.makedirs(target, exist_ok=True)
    for stale in os.listdir(target):  # left by a copy the Kobo was pulled out of (P5)
        if stale.startswith(PARTIAL):
            os.unlink(os.path.join(target, stale))
    there = _on_the_kobo(mount)
    r.kepubify = find_kepubify() if kepubify is None else kepubify
    with tempfile.TemporaryDirectory(prefix="khs-kepub-") as tmp:
        _put_each(r, todo, there, mount, target, tmp, done, remembered, state_dir)
    return r


def _put_each(r: Result, todo, there, mount: str, target: str, tmp: str, done: dict, remembered: dict, state_dir: str) -> None:
    for n, (path, sha) in enumerate(todo):
        name, size = os.path.basename(path), os.path.getsize(path)
        if (name.lower(), size) in there and (same := _same(path, sha, there[name.lower(), size])):
            # Already on the Kobo: by hand, or a copy not remembered.
            done[sha] = {"name": name, "at": _now(), "found": True, "path": os.path.relpath(same, mount).replace(os.sep, "/")}
            _keep(state_dir, remembered)
            continue
        if why := drm(path):
            r.refused.append((name, why))
            done[sha] = {"name": name, "at": _now(), "refused": why}
            _keep(state_dir, remembered)
            continue
        if shutil.disk_usage(mount).free < size + SPARE:
            r.left, r.why_left = len(todo) - n, "full"
            break
        if _changed(remembered, path):  # still being written: it waits for a plug-in when it has settled
            log.info("a book changed since it was read, left for the next sync")
            continue
        source, as_name = path, fat_name(name)
        if not name.lower().endswith(KEPUB):
            converted = _kepub(r.kepubify, path, tmp) if r.kepubify else ""
            if converted:
                source, as_name = converted, fat_name(os.path.basename(converted))
            else:
                r.as_epub.append(name)
                if r.kepubify:
                    r.unconverted.append(name)
        try:
            landed = _copy(source, target, as_name, sha)
        except OSError as ex:
            if not os.path.isdir(mount) or ex.errno in GONE:
                r.left, r.why_left = len(todo) - n, "unplugged"
                break
            why = ex.strerror or str(ex)
            if ex.errno in WHOLE_KOBO:
                r.left, r.why_left = len(todo) - n, why
                break
            # This book's own trouble, such as a name too long for the Kobo: said once, the rest still go.
            log.warning("a book was not put on the Kobo: %s", why)
            r.refused.append((name, f"the Kobo would not take it ({why})"))
            done[sha] = {"name": name, "at": _now(), "refused": why}
            _keep(state_dir, remembered)
            continue
        finally:
            if source != path:
                os.unlink(source)
        if _changed(remembered, path):  # written to during the copy: what landed may be neither version
            log.info("a book changed while it was copied, taken off and left for the next sync")
            with contextlib.suppress(OSError):
                os.unlink(os.path.join(target, landed))
            continue
        r.put.append(landed)
        done[sha] = {"name": landed, "at": _now()}
        _keep(state_dir, remembered)


def _kepub(kepubify: str, path: str, tmp: str) -> str:
    """The book converted to kepub in tmp, or "" when kepubify did not
    manage (P7): then it goes as it is."""
    name = os.path.basename(path)
    out = os.path.join(tmp, name[: -len(".epub")] + KEPUB)
    try:
        done = subprocess.run(
            [kepubify, "-o", out, path], stdin=subprocess.DEVNULL, capture_output=True, timeout=CONVERT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError) as ex:
        log.warning("kepubify did not run: %s", ex)
        done = None
    if done is not None and done.returncode == 0 and zipfile.is_zipfile(out):
        return out
    if done is not None:
        log.warning("kepubify could not convert a book (exit %s)", done.returncode)
    if os.path.exists(out):
        os.unlink(out)
    return ""


def fat_name(name: str) -> str:
    """name as the Kobo's FAT storage can hold it."""
    return name.translate(NOT_ON_FAT).rstrip(" .") or "_"


def _copy(path: str, target: str, name: str, sha: str) -> str:
    """One book into target as name, completely or not at all (P4, P5): a
    hidden partial copy, flushed, then renamed to a name nothing else has.
    The partial copy is named by the book's hash, short whatever the name."""
    partial = os.path.join(target, PARTIAL + sha[:16] + ".partial")
    try:
        with open(path, "rb") as src, open(partial, "wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
            dst.flush()
            os.fsync(dst.fileno())
        landed = _free_name(target, name)
        os.rename(partial, os.path.join(target, landed))
    except OSError as ex:
        if ex.errno not in GONE:  # a Kobo pulled out takes it along; the next plug-in clears what is left
            with contextlib.suppress(OSError):
                os.unlink(partial)
        raise
    return landed


def _free_name(target: str, name: str) -> str:
    """name, or name with a number when the Kobo has one by that name (P4)."""
    stem, ext = (name[: -len(KEPUB)], KEPUB) if name.lower().endswith(KEPUB) else os.path.splitext(name)
    taken = {f.lower() for f in os.listdir(target)}
    candidate, n = name, 1
    while candidate.lower() in taken:
        n += 1
        candidate = f"{stem} ({n}){ext}"
    return candidate


def _on_the_kobo(mount: str) -> dict[tuple[str, int], list[str]]:
    """The books already on the Kobo, by (name, size): where to look for one
    put there by hand. Hidden folders (.kobo and the like) are not books."""
    found: dict[tuple[str, int], list[str]] = {}
    for here, dirs, files in os.walk(mount):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.lower().endswith(".epub") and not f.startswith("."):
                p = os.path.join(here, f)
                try:
                    found.setdefault((f.lower(), os.path.getsize(p)), []).append(p)
                except OSError:
                    pass
    return found


def _same(path: str, sha: str, candidates: list[str]) -> str:
    """The one of candidates that is this book, "" for none."""
    return next((c for c in candidates if _sha256(c) == sha), "")


def _hash(remembered: dict, path: str) -> str:
    """The file's SHA-256, from what is kept when the file has not changed since."""
    st = os.stat(path)
    key = [st.st_size, st.st_mtime_ns]
    kept = remembered["files"].get(path)
    if kept and kept[:2] == key:
        return kept[2]
    sha = _sha256(path)
    remembered["files"][path] = [*key, sha]
    return sha


def _changed(remembered: dict, path: str) -> bool:
    """Whether the file is no longer as it was when it was hashed (_hash)."""
    try:
        st = os.stat(path)
    except OSError:
        return True
    return remembered["files"].get(path, [])[:2] != [st.st_size, st.st_mtime_ns]


def _where(given: dict) -> str:
    """Where on the Kobo a book went, from its root; "" for one that was
    found there before this was remembered."""
    return given.get("path") or ("" if given.get("found") else f"{FOLDER}/{given['name']}")


def _about(remembered: dict, path: str) -> dict:
    """epub.about, kept with the file's hash (after _hash) until it changes."""
    kept = remembered["files"][path]
    if len(kept) < 4:
        kept[3:] = [epub.about(path)]
    return kept[3]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _remembered(state_dir: str) -> dict:
    try:
        with open(os.path.join(state_dir, REMEMBERED)) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    return {"kobos": data.get("kobos") or {}, "files": data.get("files") or {}}


def _keep(state_dir: str, remembered: dict) -> None:
    """After every book, so a sync that dies keeps what it did. Files gone
    from the folder are forgotten from the hashes; the Kobos keep theirs.
    Written only when it changed: the Mac app refreshes when the state
    folder is written to, and asks for the list on every refresh.

    Readers (the list, the app) keep the hashes too, so a sync and a
    reader can write at the same time. Under a lock, the file is read
    again and merged: what was put on a Kobo is only ever added, so a
    reader that loaded before a sync's write cannot take it away.
    `remembered` is brought up to the merge in place."""
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, REMEMBERED)
    with open(path + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        there = _remembered(state_dir)
        for device, theirs in there["kobos"].items():
            mine = remembered["kobos"].setdefault(device, {})
            for sha, given in theirs.items():
                mine.setdefault(sha, given)
        for p, kept in there["files"].items():
            remembered["files"].setdefault(p, kept)
        remembered["files"] = {p: v for p, v in remembered["files"].items() if os.path.exists(p)}
        text = json.dumps(remembered, indent=1, sort_keys=True)
        try:
            with open(path) as fh:
                if fh.read() == text:
                    return
        except OSError:
            pass
        with open(path + ".tmp", "w") as fh:
            fh.write(text)
        os.replace(path + ".tmp", path)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
