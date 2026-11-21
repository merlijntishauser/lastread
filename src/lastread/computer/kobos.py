"""Whose Kobo is plugged in (rules W1-W5).

One login on a computer syncs for one reader, and any Kobo can be plugged
into it: a partner's, a child's, a friend's. Read as the reader's own, its
books and progress land among theirs and go to their Hardcover shelf. So
the computer keeps which Kobos are the reader's, in kobos.json in the state
folder, and a Kobo it has not met is not read until the reader has said
whose it is.

A Kobo is known by the name kobo_db.Device makes from its serial number
(kobo-1a2b3c4d): the serial itself is kept nowhere.

    {"mine":  {"kobo-1a2b3c4d": {"model": "Kobo Clara Colour", "since": "2026-11-21T19:02:11Z"}},
     "other": {"kobo-5e6f7a8b": {"model": "model 378", "since": "..."}}}
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import UTC, datetime

from ..engine.kobo_db import Device

FILE = "kobos.json"
MINE, OTHER, UNKNOWN = "mine", "other", ""
ID = re.compile(r"^kobo-[0-9a-f]{8}$")


def _path(state_dir: str) -> str:
    return os.path.join(state_dir, FILE)


def _read(state_dir: str) -> dict | None:
    """The record, or None when this computer has never kept one. A file
    that cannot be read as one is an empty record: every Kobo is asked
    about again, which is the safe way to be wrong."""
    try:
        with open(_path(state_dir), encoding="utf-8") as fh:
            found = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {MINE: {}, OTHER: {}}
    if not isinstance(found, dict):
        return {MINE: {}, OTHER: {}}
    return {k: v if isinstance(v := found.get(k), dict) else {} for k in (MINE, OTHER)}


def _write(state_dir: str, record: dict) -> None:
    os.makedirs(state_dir, mode=0o700, exist_ok=True)
    tmp = _path(state_dir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, _path(state_dir))


def _from_before(state_dir: str) -> dict:
    """The Kobos a version without this record synced here, as far as this
    computer can still tell. Local mode kept each Kobo by its name in the
    state database. Server mode kept no name, but the books put on a Kobo
    from a folder are remembered per Kobo: the one that got them first is
    the reader's. Whatever came later is asked about."""
    mine: dict = {}
    try:
        con = sqlite3.connect(f"file:{os.path.join(state_dir, 'state.db')}?mode=ro", uri=True)
        try:
            for (name,) in con.execute("select device from device order by first_import"):
                if ID.match(name or ""):
                    mine[name] = {"model": "", "since": ""}
        finally:
            con.close()
    except sqlite3.Error:
        pass
    if mine:
        return {MINE: mine, OTHER: {}}
    try:
        with open(os.path.join(state_dir, "to-kobo.json"), encoding="utf-8") as fh:
            per_kobo = json.load(fh).get("kobos") or {}
        first = {
            name: min((b.get("at") or "") for b in books.values())
            for name, books in per_kobo.items()
            if ID.match(name) and isinstance(books, dict) and books
        }
    except (OSError, ValueError, AttributeError, TypeError):
        first = {}
    if first:
        mine[min(first, key=lambda name: (first[name], name))] = {"model": "", "since": ""}
    return {MINE: mine, OTHER: {}}


def _known(state_dir: str) -> tuple[dict, bool]:
    """(the record, whether it is on disk)."""
    record = _read(state_dir)
    return (record, True) if record is not None else (_from_before(state_dir), False)


def whose(state_dir: str, dev: Device) -> str:
    """MINE, OTHER, or UNKNOWN for a Kobo the reader has to be asked about.
    Changes nothing. A Kobo that does not say its serial cannot be told
    from another: it is read, as every Kobo was before (W5)."""
    if not dev.serial:
        return MINE
    record, kept = _known(state_dir)
    if dev.name in record[MINE]:
        return MINE
    if dev.name in record[OTHER]:
        return OTHER
    # The first Kobo this computer reads is the reader's: whoever sets a computer up plugs in their own (W1).
    return UNKNOWN if kept or record[MINE] else MINE


def meet(state_dir: str, dev: Device) -> str:
    """whose(), and the record kept: at the first Kobo ever, that it is the
    reader's. Called by a sync, which is what reads a Kobo."""
    found = whose(state_dir, dev)
    if not dev.serial:
        return found
    record, kept = _known(state_dir)
    if found == MINE and not record[MINE].get(dev.name, {}).get("since"):
        record[MINE][dev.name] = {"model": dev.model, "since": _now()}
        kept = False
    if not kept:
        _write(state_dir, record)
    return found


def say(state_dir: str, name: str, mine: bool, model: str = "") -> None:
    """The reader's answer for one Kobo; it replaces an earlier one."""
    if not ID.match(name):
        raise ValueError(f"{name} is not the name of a Kobo")
    record, _ = _known(state_dir)
    was = record[MINE].pop(name, None) or record[OTHER].pop(name, None) or {}
    record[MINE if mine else OTHER][name] = {"model": model or was.get("model", ""), "since": _now()}
    _write(state_dir, record)


def forget(state_dir: str, name: str) -> bool:
    """Take a Kobo out of the record: it is asked about at its next plug-in. True when it was there."""
    record, _ = _known(state_dir)
    there = bool(record[MINE].pop(name, None)) | bool(record[OTHER].pop(name, None))
    _write(state_dir, record)
    return there


def listed(state_dir: str) -> list[dict]:
    """Every Kobo this computer knows: {"id", "whose", "model", "since"}, the reader's own first."""
    record, _ = _known(state_dir)
    return [
        {"id": name, "whose": kind, **{k: about.get(k, "") for k in ("model", "since")}}
        for kind in (MINE, OTHER)
        for name, about in sorted(record[kind].items())
    ]


def question(dev: Device, in_app: bool) -> str:
    """What a sync says in place of reading a Kobo it has not met."""
    what = f" ({dev.model})" if dev.model else ""
    how = "Open Lastread to say whose it is." if in_app else "Say whose it is: `lastread kobo mine` or `lastread kobo not-mine`."
    return f"This computer has not synced this Kobo{what} before. Nothing was read from it, and nothing was sent. {how}"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
