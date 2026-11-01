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
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime

FOLDER = "Lastread"  # on the Kobo's own storage
PARTIAL = ".lastread-"  # a copy on its way: hidden, so the Kobo does not list it
REMEMBERED = "to-kobo.json"
SPARE = 50 << 20  # room left on the Kobo after a copy
MANY = 20  # more than this at once is asked about first (`to-kobo --yes`)
# Font obfuscation is not DRM: the book opens anywhere (EPUB 3, 4.2; Adobe's older one).
FONTS = {"http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"}


@dataclass
class Result:
    put: list[str] = field(default_factory=list)  # file names, as they are on the Kobo now
    refused: list[tuple[str, str]] = field(default_factory=list)  # (file name, why), said once per file
    left: int = 0  # not put this time: the Kobo is full, or went away
    why_left: str = ""  # "full" or "unplugged"


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


def inside(folder: str, mount: str) -> bool:
    """Whether the folder is on the Kobo itself: then there is nothing to put there."""
    folder, mount = os.path.realpath(folder), os.path.realpath(mount)
    return folder == mount or folder.startswith(mount + os.sep)


def put(folder: str, mount: str, device: str, state_dir: str) -> Result:
    """Put each book of the folder on the Kobo at mount that this Kobo has
    not had from here yet. device names the Kobo (kobo_db.Device.name)."""
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
    for n, (path, sha) in enumerate(todo):
        name, size = os.path.basename(path), os.path.getsize(path)
        if (name.lower(), size) in there and _same(path, sha, there[name.lower(), size]):
            done[sha] = {"name": name, "at": _now(), "found": True}  # already on the Kobo: by hand, or a copy not remembered
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
        try:
            landed = _copy(path, target)
        except OSError:
            r.left, r.why_left = len(todo) - n, "unplugged"
            break
        r.put.append(landed)
        done[sha] = {"name": landed, "at": _now()}
        _keep(state_dir, remembered)
    return r


def _copy(path: str, target: str) -> str:
    """One book into target, completely or not at all (P4, P5): a hidden
    partial copy, flushed, then renamed to a name nothing else has."""
    name = os.path.basename(path)
    partial = os.path.join(target, PARTIAL + name + ".partial")
    with open(path, "rb") as src, open(partial, "wb") as dst:
        shutil.copyfileobj(src, dst, 1 << 20)
        dst.flush()
        os.fsync(dst.fileno())
    landed = _free_name(target, name)
    os.rename(partial, os.path.join(target, landed))
    return landed


def _free_name(target: str, name: str) -> str:
    """name, or name with a number when the Kobo has one by that name (P4)."""
    stem, ext = (name[: -len(".kepub.epub")], ".kepub.epub") if name.lower().endswith(".kepub.epub") else os.path.splitext(name)
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


def _same(path: str, sha: str, candidates: list[str]) -> bool:
    return any(_sha256(c) == sha for c in candidates)


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
    from the folder are forgotten from the hashes; the Kobos keep theirs."""
    remembered["files"] = {p: v for p, v in remembered["files"].items() if os.path.exists(p)}
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, REMEMBERED)
    with open(path + ".tmp", "w") as fh:
        json.dump(remembered, fh, indent=1, sort_keys=True)
    os.replace(path + ".tmp", path)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
