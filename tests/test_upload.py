import gzip
import hashlib
import importlib
import sqlite3

import pytest

from tests import client_at
from tests.test_core import MINE, OLD, make_kobo

TOKEN = "test-token-123"


def setup(tmp_path, monkeypatch, max_mb=None):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "readers.yaml").write_text("readers:\n  alice:\n    identities: [alice]\n")
    (cfg / "devices.yaml").write_text(
        f"devices:\n  - token_sha256: {hashlib.sha256(TOKEN.encode()).hexdigest()}\n    reader: alice\n    device: kobo-alice\n"
    )
    monkeypatch.setenv("KHS_DATA", str(tmp_path))
    monkeypatch.setenv("KHS_CONFIG", str(cfg / "readers.yaml"))
    if max_mb is not None:
        monkeypatch.setenv("KHS_MAX_UPLOAD_MB", str(max_mb))
    import lastread.server.upload as up
    import lastread.web.app as web

    importlib.reload(up)
    importlib.reload(web)
    return client_at(web.app)


def body(tmp_path, books, with_user=False, name="k.sqlite"):
    p = tmp_path / name
    make_kobo(p, books, [], with_user=with_user)
    return gzip.compress(p.read_bytes())


def put(c, data, token=TOKEN):
    return c.put("/upload", content=data, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/gzip"})


def test_upload_imports_and_snapshots(tmp_path, monkeypatch):
    c = setup(tmp_path, monkeypatch)
    r = put(c, body(tmp_path, [OLD, MINE]))
    assert r.status_code == 200 and r.json()["ok"] and r.json()["first_import"] and r.json()["reader"] == "alice"
    snaps = list((tmp_path / "snapshots" / "alice" / "kobo-alice").glob("*.sqlite.gz"))
    assert len(snaps) == 1
    moved = ("mine", "Mine Now", "C", "333", 25, 1, "2026-09-30T10:00:00Z", 900)
    r2 = put(c, body(tmp_path, [OLD, moved], name="k2.sqlite"))
    assert r2.json()["changed"] == 1 and not r2.json()["first_import"]
    assert len(list((tmp_path / "snapshots" / "alice" / "kobo-alice").glob("*.sqlite.gz"))) == 2  # also within one second
    assert not list(tmp_path.glob("*.upload")) and not list(tmp_path.glob("tmp*.sqlite"))  # temp files cleaned


def test_upload_rejections(tmp_path, monkeypatch):
    c = setup(tmp_path, monkeypatch)
    assert put(c, body(tmp_path, [OLD]), token="wrong").status_code == 401
    assert c.put("/upload", content=b"x").status_code == 401
    r = put(c, body(tmp_path, [OLD], with_user=True, name="u.sqlite"))
    assert r.status_code == 422 and "user" in r.json()["error"]
    assert put(c, b"not gzip at all").status_code == 400
    junk = tmp_path / "junk.sqlite"
    sqlite3.connect(junk).execute("create table x (a)").connection.commit()
    assert put(c, gzip.compress(junk.read_bytes())).status_code == 422
    assert (
        not (tmp_path / "state.db").exists()
        or not sqlite3.connect(tmp_path / "state.db").execute("select count(*) from book").fetchone()[0]
    )


def test_upload_size_limit(tmp_path, monkeypatch):
    c = setup(tmp_path, monkeypatch, max_mb=0)
    assert put(c, body(tmp_path, [OLD])).status_code == 413


def test_an_upload_too_large_once_unpacked_leaves_nothing_behind(tmp_path, monkeypatch):
    c = setup(tmp_path, monkeypatch, max_mb=1)
    r = put(c, gzip.compress(b"\0" * (2 << 20)))  # small as sent, 2 MB unpacked
    assert r.status_code == 413
    assert not list(tmp_path.glob("tmp*")) and not list(tmp_path.glob("*.upload"))


def test_a_gzip_upload_broken_inside_is_refused_and_leaves_nothing_behind(tmp_path, monkeypatch):
    c = setup(tmp_path, monkeypatch)
    good = body(tmp_path, [OLD, MINE])
    for at in (10, 12, 20, len(good) - 6):  # a good header, then a stream that breaks in its own way at each place
        broken = bytearray(good)
        broken[at : at + 4] = b"\xff" * 4
        r = put(c, bytes(broken))
        assert r.status_code == 400 and "cannot read upload" in r.json()["error"], at
        assert not list(tmp_path.glob("tmp*.sqlite")) and not list(tmp_path.glob("*.upload")), at


def test_the_apps_questions_are_read_only_from_a_known_computer_and_only_so_far(tmp_path, monkeypatch):
    import asyncio

    import lastread.web.app as web
    from lastread.server import upload

    c = setup(tmp_path, monkeypatch)
    known = {"Authorization": f"Bearer {TOKEN}"}
    assert c.post("/api/app/live", json={"live": False}, headers=known).json()["live"] is False
    for path in ("/api/app/live", "/api/app/book", "/api/app/books/sync"):
        r = c.post(path, content=b'{"live": true, "pad": "' + b"x" * web.APP_BODY + b'"}', headers=known)
        assert (r.status_code, r.json()) == (413, {"error": "request too large"}), path

    class Asked:
        """A request whose body says when it is read."""

        def __init__(self, headers):
            self.headers, self.read = headers, False

        async def stream(self):
            self.read = True
            yield b"{}"

    for headers in ({}, {"authorization": "Bearer not-a-token-the-server-knows"}):
        nobody = Asked(headers)
        with pytest.raises(upload.UploadError) as refused:
            asyncio.run(web.app_json(nobody))
        assert refused.value.status == 401 and not nobody.read
    # No length said and more than the most: stopped there, not taken in whole.
    assert c.post("/api/app/live", content=iter([b"x" * web.APP_BODY, b"x" * 10]), headers=known).status_code == 413


def test_collection_endpoint_lists_the_syncing_books(tmp_path, monkeypatch):
    c = setup(tmp_path, monkeypatch)
    from lastread.engine import state

    put(c, body(tmp_path, [OLD, MINE]))
    st = state.connect(str(tmp_path / "state.db"))
    r = c.get("/collection", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 204  # no kobo_collection configured
    from lastread.server import accounts

    accounts.set_collection(st, "alice", "Alice")
    assert c.get("/collection", headers={"Authorization": f"Bearer {TOKEN}"}).text == "Alice\n"  # nothing switched on
    state.set_mode(st, "alice", ["mine"], "on")
    assert c.get("/collection", headers={"Authorization": f"Bearer {TOKEN}"}).text == "Alice\nmine\n"
    assert c.get("/collection", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/collection").status_code == 401


def test_an_upload_with_more_than_the_server_reads_is_refused(tmp_path, monkeypatch):
    """A whole KoboReader.sqlite (minus the login tokens) is what an old
    agent sent: DRM keys, reviews, collections. It is not taken in."""
    from tests.kobo_fixture import make

    c = setup(tmp_path, monkeypatch)
    whole = tmp_path / "whole.sqlite"
    make(str(whole), wal=False)  # content and Event, but also DbVersion, Shelf, ShelfContent
    r = put(c, gzip.compress(whole.read_bytes()))
    assert r.status_code == 422 and "more than the server reads (DbVersion, Shelf, ShelfContent)" in r.json()["error"]
    assert "update lastread" in r.json()["error"]
    one = tmp_path / "one.sqlite"
    make_kobo(one, [OLD], [])
    con = sqlite3.connect(one)
    con.executescript("create table content_keys (k); create table a (x); create table b (x); create table c (x);")
    con.close()
    r = put(c, gzip.compress(one.read_bytes()))
    assert r.status_code == 422 and r.json()["error"].count(",") == 2 and "..." in r.json()["error"]
    # Nothing was kept of either: no snapshot, no book, no temporary file.
    assert not (tmp_path / "snapshots").exists() or not list((tmp_path / "snapshots").rglob("*.gz"))
    assert not list(tmp_path.glob("tmp*.sqlite")) and not list(tmp_path.glob("*.upload"))
    assert put(c, body(tmp_path, [OLD])).status_code == 200  # the two tables alone are welcome


def test_a_database_in_wal_mode_leaves_no_wal_or_shm_behind(tmp_path, monkeypatch):
    """The Kobo keeps its database in WAL mode. Opened read-only, SQLite
    leaves the -wal and -shm next to it on close; the server removes those
    with the upload, whether it takes the upload in or refuses it."""
    c = setup(tmp_path, monkeypatch)

    def wal(books, name, with_user=False):
        p = tmp_path / name
        make_kobo(p, books, [], with_user=with_user)
        con = sqlite3.connect(p)
        assert con.execute("pragma journal_mode=wal").fetchone()[0] == "wal"
        con.close()
        return gzip.compress(p.read_bytes())

    assert put(c, wal([OLD, MINE], "w.sqlite")).status_code == 200
    assert put(c, wal([OLD], "u.sqlite", with_user=True)).status_code == 422
    left = [p.name for p in tmp_path.iterdir() if p.name.startswith("tmp")]
    assert left == []


def test_an_upload_is_imported_off_the_event_loop(tmp_path, monkeypatch):
    import asyncio

    from lastread.server import upload

    c = setup(tmp_path, monkeypatch)
    real, loops = upload.store_and_import, []

    def where(*a, **k):
        try:
            asyncio.get_running_loop()
            loops.append("on the loop")
        except RuntimeError:
            loops.append("in a thread")
        return real(*a, **k)

    monkeypatch.setattr(upload, "store_and_import", where)
    assert put(c, body(tmp_path, [OLD])).status_code == 200
    assert loops == ["in a thread"]  # /healthz and the app's questions are answered meanwhile
