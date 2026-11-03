"""Where the tool keeps its things on this computer, and what `setup` chose.

State folder: ~/Library/Application Support/kobo-hardcover-sync on macOS,
$XDG_DATA_HOME/kobo-hardcover-sync (~/.local/share/...) elsewhere;
KHS_HOME overrides both (tests, and anyone who wants it elsewhere).

Settings are a few lines of `key = "value"` in config.toml there:

    server = "https://kobo.example.org"   # server mode; absent = local mode
    eject_after_sync = false
    allow_untested_kobo = false
    verbose_log = false                   # true: book titles in agent.log
    export_to = "/Users/sam/reading.json" # written after every sync; absent = not
    webhook_url = "https://example.org/hook" # POSTed to after a sync that read the Kobo
    to_kobo = "/Users/sam/Books/To Kobo"  # its EPUBs are put on the Kobo at plug-in; absent = not
    to_kobo_collection = "own"            # the books of the Kobo's Lastread folder: in no collection
                                          # (absent), "synced" (the collection of the books that sync),
                                          # or "own" (a collection of their own)
    to_kobo_collection_name = "Lastread"  # the name of that one; absent = Lastread
    check_for_updates = false             # the Mac app: do not ask GitHub for a newer version
"""

from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass

APP = "kobo-hardcover-sync"


def state_dir() -> str:
    if os.environ.get("KHS_HOME"):
        return os.environ["KHS_HOME"]
    if sys.platform == "darwin":
        return os.path.expanduser(f"~/Library/Application Support/{APP}")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), APP)


# What happens to the books in the Kobo's Lastread folder (the EPUB folder's,
# engine/tokobo.py): nothing, they join the collection of the books that sync,
# or they have a collection of their own (rule P8).
FOLDER_COLLECTIONS = ("none", "synced", "own")
FOLDER_COLLECTION_NAME = "Lastread"


@dataclass
class Config:
    server: str = ""  # "" = local mode
    eject_after_sync: bool = False
    allow_untested_kobo: bool = False
    verbose_log: bool = False
    export_to: str = ""  # `export --every-sync`: the file kept up to date
    webhook_url: str = ""  # `webhook URL`: where a sync that read the Kobo is POSTed (its token is a secret)
    to_kobo: str = ""  # `to-kobo FOLDER`: the folder whose books are put on the Kobo
    to_kobo_collection: str = "none"  # `to-kobo --collection`: none, synced or own (FOLDER_COLLECTIONS)
    to_kobo_collection_name: str = FOLDER_COLLECTION_NAME  # `to-kobo --name`: the name of the own one
    check_for_updates: bool = True  # the Mac app only (update.py); written down only when off

    set_up: bool = False  # has `setup` been run here?

    @property
    def path(self) -> str:
        return os.path.join(state_dir(), "config.toml")

    @property
    def mode(self) -> str:
        """ "server", "local", or "" when setup has not been run."""
        return ("server" if self.server else "local") if self.set_up else ""


class Broken(Exception):
    """config.toml is there but cannot be read; str() says where and what to do."""


def load() -> Config:
    c = Config()
    try:
        with open(c.path, "rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError:
        return c
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as ex:
        said = str(ex)
        if m := re.search(r"\s*\(at line (\d+), column \d+\)$", said):
            said = f"line {m.group(1)}: {said[: m.start()]}"
        raise Broken(f"{c.path} cannot be read, {said}. Correct it, or delete it and set up again.") from ex
    c.set_up = True
    c.server = str(data.get("server") or "").rstrip("/")
    c.eject_after_sync = bool(data.get("eject_after_sync", False))
    c.allow_untested_kobo = bool(data.get("allow_untested_kobo", False))
    c.verbose_log = bool(data.get("verbose_log", False))
    c.export_to = str(data.get("export_to") or "")
    c.webhook_url = str(data.get("webhook_url") or "")
    c.to_kobo = str(data.get("to_kobo") or "")
    how = str(data.get("to_kobo_collection") or "none")
    c.to_kobo_collection = how if how in FOLDER_COLLECTIONS else "none"
    c.to_kobo_collection_name = str(data.get("to_kobo_collection_name") or "").strip() or FOLDER_COLLECTION_NAME
    c.check_for_updates = bool(data.get("check_for_updates", True))
    return c


def save(c: Config) -> None:
    os.makedirs(state_dir(), mode=0o700, exist_ok=True)
    lines = []
    if c.server:
        lines.append("server = " + _quote(c.server.rstrip("/")))
    lines.append(f"eject_after_sync = {str(c.eject_after_sync).lower()}")
    lines.append(f"allow_untested_kobo = {str(c.allow_untested_kobo).lower()}")
    lines.append(f"verbose_log = {str(c.verbose_log).lower()}")
    if c.export_to:
        lines.append("export_to = " + _quote(c.export_to))
    if c.webhook_url:
        lines.append("webhook_url = " + _quote(c.webhook_url))
    if c.to_kobo:
        lines.append("to_kobo = " + _quote(c.to_kobo))
    if c.to_kobo_collection != "none":
        lines.append("to_kobo_collection = " + _quote(c.to_kobo_collection))
    if c.to_kobo_collection_name != FOLDER_COLLECTION_NAME:
        lines.append("to_kobo_collection_name = " + _quote(c.to_kobo_collection_name))
    if not c.check_for_updates:
        lines.append("check_for_updates = false")
    tmp = c.path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, c.path)
    c.set_up = True


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
