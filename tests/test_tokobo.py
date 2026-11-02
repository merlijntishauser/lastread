"""A folder of the reader's, put on the Kobo at plug-in (rules P1-P6). A
folder plays the Kobo, as in test_local; the books are the smallest EPUBs
there are, made up here."""

import json
import os
import shutil
import sqlite3
import sys
import time
import zipfile
from dataclasses import replace

import pytest

from lastread import cli
from lastread.computer import config, runner
from lastread.engine import epub, kobo_db, tokobo
from tests.test_computer import FakeComputer, register, server  # noqa: F401  (server: a fixture)
from tests.test_epub import CONTAINER, ISBN, an_epub
from tests.test_local import LOCAL, ORIGIN, kobo, local  # noqa: F401  (local: a fixture)

ENCRYPTION = """<?xml version="1.0"?>
<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container" xmlns:enc="http://www.w3.org/2001/04/xmlenc#">
  <enc:EncryptedData><enc:EncryptionMethod Algorithm="{}"/>
    <enc:CipherData><enc:CipherReference URI="OEBPS/{}"/></enc:CipherData></enc:EncryptedData>
</encryption>"""


REAL_KEPUBIFY = tokobo.find_kepubify  # before the fixture below stands in for it
FAKE_KEPUBIFY = f"""#!{sys.executable}
# A stand-in for kepubify 4.0.4: `kepubify -o OUT IN` writes OUT, a kepub; a book it cannot read exits 1.
import shutil, sys, time, zipfile
out, book = sys.argv[sys.argv.index("-o") + 1], sys.argv[-1]
name = book.rsplit("/", 1)[-1]
open(__file__ + ".calls", "a").write(name + "\\n")
if name.startswith("Slow"):
    time.sleep(5)
if name.startswith("Bad"):
    sys.exit(1)
shutil.copyfile(book, out)
with zipfile.ZipFile(out, "a") as z:
    z.writestr("OEBPS/kepubify-titlepage-dummy.xhtml", "<html/>")
"""


@pytest.fixture(autouse=True)
def no_kepubify(monkeypatch):
    """Whatever this computer has installed: no kepubify, unless a test gives one."""
    monkeypatch.setattr(tokobo, "find_kepubify", lambda: "")


def a_kepubify(where, monkeypatch):
    path = where / "kepubify"
    path.write_text(FAKE_KEPUBIFY)
    path.chmod(0o755)
    monkeypatch.setattr(tokobo, "find_kepubify", lambda: str(path))
    return path


def calls(kepubify):
    return open(str(kepubify) + ".calls").read().split() if os.path.exists(str(kepubify) + ".calls") else []


def a_book(path, title="A Book", extra=None):
    """An EPUB at path, its ISBN made from its title so two titles are two files."""
    an_epub(path, f"<dc:identifier>urn:isbn:{ISBN}</dc:identifier>", f"<dc:title>{title}</dc:title>")
    if extra:
        with zipfile.ZipFile(path, "a") as z:
            for name, text in extra.items():
                z.writestr(name, text)
    return str(path)


def on_kobo(home):
    shelf = home / "Volumes" / "KOBOeReader" / tokobo.FOLDER
    return sorted(os.listdir(shelf)) if shelf.is_dir() else []


def tokobo_state(home):
    return str(home / "state")


def mount(home):
    return str(home / "Volumes" / "KOBOeReader")


@pytest.fixture
def plugged(home):
    """A Kobo plugged in and read once (local mode), and a folder of books to put on it."""
    db = kobo(home)
    books = home / "Books"
    books.mkdir()
    mac = FakeComputer(home / "Volumes")
    runner.sync(mac, LOCAL)
    return mac, books, replace(LOCAL, to_kobo=str(books)), db


def test_only_the_books_of_the_folder_you_chose_and_nothing_without_one(plugged, home):
    mac, books, cfg, _ = plugged
    a_book(books / "One.epub", "One")
    a_book(books / "Fantasy" / "Two.kepub.epub", "Two")  # the folders in it count
    a_book(books / ".hidden.epub", "Hidden")
    (books / "Notes.pdf").write_bytes(b"%PDF-1.4")
    (books / ".Trash").mkdir()
    a_book(books / ".Trash" / "Gone.epub", "Gone")
    runner.sync(mac, LOCAL)
    assert on_kobo(home) == []  # no folder chosen: nothing
    out = runner.sync(mac, cfg)
    assert on_kobo(home) == ["One.epub", "Two.kepub.epub"]
    assert out.message == "2 books put on the Kobo. Eject before unplugging."
    # Only into its own folder on the Kobo: the rest of the Kobo is as it was.
    assert sorted(os.listdir(mount(home))) == [".kobo", tokobo.FOLDER]


def test_only_epubs_and_a_book_with_drm_is_refused_and_said_once(plugged, home):
    mac, books, cfg, _ = plugged
    a_book(books / "Adobe.epub", "Adobe", {"META-INF/rights.xml": "<rights/>"})
    a_book(books / "Library.epub", "Library", {"META-INF/license.lcpl": "{}"})
    aes = ENCRYPTION.format("http://www.w3.org/2001/04/xmlenc#aes128-cbc", "chapter1.xhtml")
    a_book(books / "Locked.epub", "Locked", {"META-INF/encryption.xml": aes})
    fonts = ENCRYPTION.format("http://www.idpf.org/2008/embedding", "font.otf")
    a_book(books / "Fonts.epub", "Fonts", {"META-INF/encryption.xml": fonts})  # font obfuscation is not DRM
    (books / "Broken.epub").write_bytes(b"not a zip")
    out = runner.sync(mac, cfg)
    assert on_kobo(home) == ["Fonts.epub"]
    assert out.message == (
        "1 book put on the Kobo. Adobe.epub not put on the Kobo: it has Adobe DRM; open it with Adobe Digital Editions. "
        "Broken.epub not put on the Kobo: it is not an EPUB that can be read. "
        "Library.epub not put on the Kobo: it has Readium LCP DRM; open it with the app of the shop or library. "
        "Locked.epub not put on the Kobo: it is encrypted (DRM). Eject before unplugging."
    )
    assert runner.sync(mac, cfg).message == ""  # said once, not at every plug-in


def test_a_book_goes_on_each_kobo_once_and_a_delete_on_the_kobo_stays(plugged, home):
    mac, books, cfg, _ = plugged
    a_book(books / "One.epub", "One")
    runner.sync(mac, cfg)
    assert on_kobo(home) == ["One.epub"]
    os.unlink(os.path.join(mount(home), tokobo.FOLDER, "One.epub"))  # the reader deletes it on the Kobo
    assert runner.sync(mac, cfg).message == "" and on_kobo(home) == []  # stays deleted
    # Taken out of the folder: it stays on the Kobo.
    a_book(books / "Two.epub", "Two")
    runner.sync(mac, cfg)
    os.unlink(books / "Two.epub")
    runner.sync(mac, cfg)
    assert on_kobo(home) == ["Two.epub"]
    # Moved within the folder, or renamed: still the same book, not put again.
    a_book(books / "Three.epub", "Three")
    runner.sync(mac, cfg)
    (books / "Read").mkdir()
    os.rename(books / "Three.epub", books / "Read" / "Three, renamed.epub")
    assert runner.sync(mac, cfg).message == "" and on_kobo(home) == ["Three.epub", "Two.epub"]
    # One the reader put on the Kobo by hand before is not put there twice.
    a_book(books / "Four.epub", "Four")
    shutil.copyfile(books / "Four.epub", os.path.join(mount(home), "Four.epub"))
    assert runner.sync(mac, cfg).message == "" and on_kobo(home) == ["Three.epub", "Two.epub"]
    # Another Kobo gets every book of the folder, once.
    with open(os.path.join(mount(home), ".kobo", "version"), "w") as fh:
        fh.write("N99OTHERKOBO,4.9.77,6.0.274403,4.9.77,4.9.77,00000000-0000-0000-0000-000000000390\n")
    shutil.rmtree(os.path.join(mount(home), tokobo.FOLDER))
    os.unlink(os.path.join(mount(home), "Four.epub"))
    out = runner.sync(mac, cfg)
    assert out.message == "3 books put on the Kobo. Eject before unplugging."
    assert on_kobo(home) == ["Four.epub", "One.epub", "Three, renamed.epub"]  # what the folder holds now
    remembered = json.load(open(os.path.join(config.state_dir(), tokobo.REMEMBERED)))
    assert len(remembered["kobos"]) == 2


def test_never_over_another_file_a_name_that_is_taken_gets_a_number(plugged, home):
    mac, books, cfg, _ = plugged
    shelf = os.path.join(mount(home), tokobo.FOLDER)
    os.makedirs(shelf)
    a_book(os.path.join(shelf, "Book.epub"), "Another book")
    a_book(os.path.join(shelf, "Story.kepub.epub"), "Another story")
    a_book(books / "Book.epub", "Book")
    a_book(books / "Story.kepub.epub", "Story")
    runner.sync(mac, cfg)
    assert on_kobo(home) == ["Book (2).epub", "Book.epub", "Story (2).kepub.epub", "Story.kepub.epub"]
    with zipfile.ZipFile(os.path.join(shelf, "Book.epub")) as z:
        assert b"Another book" in z.read("OEBPS/content.opf")  # the Kobo's own file is untouched


def test_a_copy_is_whole_or_not_there_also_when_the_kobo_is_pulled_out(plugged, home, monkeypatch):
    mac, books, cfg, _ = plugged
    a_book(books / "One.epub", "One")
    a_book(books / "Two.epub", "Two")
    real = shutil.copyfileobj

    def pulled_out(src, dst, length=0):
        dst.write(src.read(100))
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(shutil, "copyfileobj", pulled_out)
    assert runner.sync(mac, cfg).message == "2 books not put on the Kobo: it was unplugged; the rest go next time."
    [partial] = on_kobo(home)
    assert partial.startswith(".lastread-") and partial.endswith(".partial")  # hidden: the Kobo does not list it
    # Plugged in again: the half copy is cleared away, and both go.
    monkeypatch.setattr(shutil, "copyfileobj", real)
    assert runner.sync(mac, cfg).message == "2 books put on the Kobo. Eject before unplugging."
    assert on_kobo(home) == ["One.epub", "Two.epub"]  # and no partial left
    # A full Kobo: the books wait, nothing is half there.
    a_book(books / "Three.epub", "Three")
    monkeypatch.setattr(shutil, "disk_usage", lambda path: shutil._ntuple_diskusage(10**9, 10**9 - 10, 10))
    assert runner.sync(mac, cfg).message == "1 book not put on the Kobo: it is full."
    assert on_kobo(home) == ["One.epub", "Two.epub"]


def test_a_long_name_goes_and_a_book_the_kobo_will_not_take_is_said_once(plugged, home, monkeypatch):
    mac, books, cfg, _ = plugged
    long = "A" * 240 + ".epub"  # with the hidden copy's prefix and suffix around it, too long for a name on the Kobo
    a_book(books / long, "Long")
    assert runner.sync(mac, cfg).message == "1 book put on the Kobo. Eject before unplugging."
    assert on_kobo(home) == [long]
    # One book the Kobo refuses for itself: said once, and the books sorted after it still go.
    a_book(books / "Bad.epub", "Bad")
    a_book(books / "Zed.epub", "Zed")
    real = tokobo._copy

    def refuses_one(path, target, name, sha):
        if name == "Bad.epub":
            raise OSError(36, "File name too long")
        return real(path, target, name, sha)

    monkeypatch.setattr(tokobo, "_copy", refuses_one)
    out = runner.sync(mac, cfg)
    assert on_kobo(home) == [long, "Zed.epub"]
    assert (
        out.message
        == "1 book put on the Kobo. Bad.epub not put on the Kobo: the Kobo would not take it (File name too long). Eject before unplugging."
    )
    assert runner.sync(mac, cfg).message == ""  # said once


def test_a_name_the_kobo_cannot_hold_goes_with_those_characters_replaced(plugged, home):
    mac, books, cfg, _ = plugged
    a_book(books / 'What? A "Story": Part 1|2.epub', "Story")
    assert runner.sync(mac, cfg).message == "1 book put on the Kobo. Eject before unplugging."
    assert on_kobo(home) == ["What_ A _Story__ Part 1_2.epub"]
    assert tokobo.fat_name("Notes. ") == "Notes" and tokobo.fat_name("...") == "_"


def test_a_kobo_that_refuses_every_copy_keeps_the_books_for_next_time(plugged, home, monkeypatch):
    mac, books, cfg, _ = plugged
    a_book(books / "One.epub", "One")
    a_book(books / "Two.epub", "Two")
    real = tokobo._copy

    def read_only(*a):
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(tokobo, "_copy", read_only)
    out = runner.sync(mac, cfg)
    assert out.message == "2 books not put on the Kobo: it refused to be written to (Read-only file system); the rest go next time."
    monkeypatch.setattr(tokobo, "_copy", real)
    assert runner.sync(mac, cfg).message == "2 books put on the Kobo. Eject before unplugging."


def test_a_list_read_before_a_sync_cannot_take_away_what_the_sync_put(plugged, home):
    mac, books, cfg, _ = plugged
    a_book(books / "One.epub", "One")
    stale = tokobo._remembered(tokobo_state(home))  # the app's list, loaded just before the sync wrote
    assert runner.sync(mac, cfg).message == "1 book put on the Kobo. Eject before unplugging."
    tokobo._keep(tokobo_state(home), stale)  # and written back after it
    kobos = json.load(open(os.path.join(tokobo_state(home), tokobo.REMEMBERED)))["kobos"]
    assert sum(len(v) for v in kobos.values()) == 1
    assert runner.sync(mac, cfg).message == "" and on_kobo(home) == ["One.epub"]


def test_a_book_still_being_written_waits_until_it_has_settled(plugged, home, monkeypatch):
    mac, books, cfg, _ = plugged
    book = a_book(books / "One.epub", "One")
    real, grown = tokobo._sha256, []

    def written_to_while_hashed(path):
        sha = real(path)
        if not grown:
            grown.append(True)
            with open(path, "ab") as fh:  # the rest of the download lands after it was read
                fh.write(b"\0" * 10)
        return sha

    monkeypatch.setattr(tokobo, "_sha256", written_to_while_hashed)
    assert runner.sync(mac, cfg).message == "" and on_kobo(home) == []  # not put with a hash of half the file
    assert runner.sync(mac, cfg).message == "1 book put on the Kobo. Eject before unplugging."
    assert runner.sync(mac, cfg).message == "" and on_kobo(home) == ["One.epub"]  # and once only
    given = json.load(open(os.path.join(tokobo_state(home), tokobo.REMEMBERED)))["kobos"]
    assert list(next(iter(given.values()))) == [real(book)]


def test_only_files_are_written_never_the_database(plugged, home):
    mac, books, cfg, db = plugged
    a_book(books / "One.epub", "One")
    before = open(db, "rb").read()
    assert runner.sync(mac, cfg).message == "1 book put on the Kobo. Eject before unplugging."
    assert open(db, "rb").read() == before


def test_server_mode_puts_the_books_on_the_kobo_from_this_computer(home, server):  # noqa: F811
    kobo(home)
    mac = FakeComputer(home / "Volumes")
    register(server, mac)
    books = home / "Books"
    a_book(books / "One.epub", "One")
    out = runner.sync(mac, config.Config(server=server.url, to_kobo=str(books)))
    assert out.message == "9 books updated. 1 book put on the Kobo. Eject before unplugging."
    assert on_kobo(home) == ["One.epub"]


def test_choosing_the_folder(plugged, home, capsys):
    mac, books, _, _ = plugged
    config.save(LOCAL)
    for n in range(tokobo.MANY + 1):
        a_book(books / f"Book {n:02d}.epub", f"Book {n}")
    with pytest.raises(SystemExit, match=f"{tokobo.MANY + 1} books in .* would go on the Kobo"):
        cli.main(["to-kobo", str(books)], computer=mac)
    assert config.load().to_kobo == ""  # nothing changed
    cli.main(["to-kobo", str(books), "--yes"], computer=mac)
    assert config.load().to_kobo == str(books) and f"{tokobo.MANY + 1} books now" in capsys.readouterr().out
    cli.main(["to-kobo"], computer=mac)
    assert f"{tokobo.MANY + 1} books wait for a Kobo" in capsys.readouterr().out
    # A folder on the Kobo itself is not a folder to put on the Kobo.
    with pytest.raises(SystemExit, match="is on the Kobo itself"):
        cli.main(["to-kobo", mount(home)], computer=mac)
    with pytest.raises(SystemExit, match="is not a folder"):
        cli.main(["to-kobo", str(home / "nowhere")], computer=mac)
    cli.main(["to-kobo", "--off"], computer=mac)
    assert config.load().to_kobo == "" and "The ones on it stay" in capsys.readouterr().out
    # A folder that went away (a disk not plugged in) is said at the sync, and nothing else changes.
    out = runner.sync(mac, replace(LOCAL, to_kobo=str(home / "gone")))
    assert f"No books put on the Kobo: {home / 'gone'} is not there." in out.message


def test_the_books_are_matched_after_the_next_plug_in(plugged, home, capsys):
    """The point of it: put on the Kobo, read, and found on Hardcover by its ISBN (M10)."""
    mac, books, cfg, db = plugged
    a_book(books / "One.epub", "One")
    runner.sync(mac, cfg)
    # The Kobo, after the eject, lists it as a sideloaded book with no ISBN; then it is read.
    con = sqlite3.connect(db)
    con.execute(
        "insert into content values (?, '6', 'application/epub+zip', 'One', 'Someone', '', 20, 1, '2026-11-01T10:00:00Z', 900, '', '', 'en')",
        (f"file:///mnt/onboard/{tokobo.FOLDER}/One.epub",),
    )
    con.commit()
    con.close()
    (home / "copy").mkdir()
    copy = runner.copy_database(db, str(home / "copy"))
    assert kobo_db.fill_isbns(copy, mount(home)) == 1
    isbns = {b.content_id: b.isbn for b in kobo_db.read_books(kobo_db.open_db(copy, allow_user_table=True))}
    assert isbns[f"file:///mnt/onboard/{tokobo.FOLDER}/One.epub"] == ISBN
    # The folder's list knows it by the id the Books list has for it: the app joins the two for its Hardcover status.
    runner.sync(mac, cfg)
    config.save(cfg)
    cli.main(["books", "--json"], computer=mac)
    ids = {b["id"] for b in json.loads(capsys.readouterr().out)["books"]}
    (one,) = tokobo.books(str(books), config.state_dir())
    assert one["ids"] == [f"file:///mnt/onboard/{tokobo.FOLDER}/One.epub"] and set(one["ids"]) <= ids


def test_the_list_says_of_each_book_where_it_is_with_the_kobo(plugged, home):
    mac, books, cfg, _ = plugged
    a_book(books / "One.epub", "One")
    a_book(books / "Locked.epub", "Locked", {"META-INF/rights.xml": "<rights/>"})
    a_book(books / "Mine.epub", "Mine")
    shutil.copyfile(books / "Mine.epub", os.path.join(mount(home), "Mine.epub"))  # put there by hand before
    runner.sync(mac, cfg)
    a_book(books / "Later" / "Two.epub", "Two")
    found = {b["name"]: b for b in tokobo.books(str(books), config.state_dir())}
    assert list(found) == ["Locked.epub", "Mine.epub", "One.epub", os.path.join("Later", "Two.epub")]
    one = found["One.epub"]
    assert (one["title"], one["isbn"], one["kobo"], one["format"], one["why"]) == ("One", ISBN, "on", "epub", "")
    assert one["ids"] == [f"file:///mnt/onboard/{tokobo.FOLDER}/One.epub"] and one["at"].endswith("Z")
    assert found["Mine.epub"]["kobo"] == "on" and found["Mine.epub"]["ids"] == ["file:///mnt/onboard/Mine.epub"]
    locked = found["Locked.epub"]
    assert (locked["kobo"], locked["ids"], locked["why"]) == ("refused", [], "it has Adobe DRM; open it with Adobe Digital Editions")
    assert (found[os.path.join("Later", "Two.epub")]["kobo"], found[os.path.join("Later", "Two.epub")]["at"]) == ("waiting", "")
    # What the book says of itself is kept with its hash: not read again while the file is the same.
    with pytest.MonkeyPatch.context() as m:
        m.setattr(epub, "about", lambda path: pytest.fail(f"read again: {path}"))
        assert [b["title"] for b in tokobo.summary(str(books), config.state_dir())["list"]] == ["Locked", "Mine", "One", "Two"]


def test_asking_for_the_list_writes_nothing_when_nothing_changed(plugged, home, monkeypatch):
    """The Mac app refreshes when its folder is written to, and asks for the
    list on every refresh: a list that rewrote to-kobo.json each time kept
    the app refreshing every second."""
    mac, books, cfg, _ = plugged
    a_book(books / "One.epub", "One")
    runner.sync(mac, cfg)
    tokobo.summary(str(books), config.state_dir())  # the first look may still keep what the book says of itself
    kept = os.path.join(config.state_dir(), tokobo.REMEMBERED)
    before = (os.stat(kept).st_mtime_ns, open(kept).read())
    replaced = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: (replaced.append(b), real(a, b)))
    tokobo.summary(str(books), config.state_dir())
    tokobo.books(str(books), config.state_dir())
    tokobo.waiting(str(books), "", config.state_dir())
    assert replaced == [] and (os.stat(kept).st_mtime_ns, open(kept).read()) == before
    assert not os.path.exists(kept + ".tmp")
    a_book(books / "Two.epub", "Two")  # something new is still kept
    tokobo.books(str(books), config.state_dir())
    assert replaced == [kept] and "Two.epub" in open(kept).read()


def test_a_plain_epub_goes_as_kepub_when_kepubify_is_installed(plugged, home, monkeypatch):
    mac, books, cfg, _ = plugged
    kepubify = a_kepubify(home, monkeypatch)
    a_book(books / "One.epub", "One")
    a_book(books / "Two.kepub.epub", "Two")  # a kepub already: as it is
    mine = (books / "One.epub").read_bytes()
    rows = []
    out = runner.sync(mac, cfg, on_step=rows.append)
    assert on_kobo(home) == ["One.kepub.epub", "Two.kepub.epub"] and calls(kepubify) == ["One.epub"]
    with zipfile.ZipFile(os.path.join(mount(home), tokobo.FOLDER, "One.kepub.epub")) as z:
        assert "OEBPS/kepubify-titlepage-dummy.xhtml" in z.namelist()
    assert (books / "One.epub").read_bytes() == mine  # the reader's own file is not touched
    assert out.message == "2 books put on the Kobo. Eject before unplugging."  # the notification does not say how
    assert [r.text for r in rows if r.what == "To Kobo"] == ["2 books put on the Kobo as kepub"]
    assert os.listdir(home / "scratch") == []  # the converted copies are gone
    # Put on the Kobo once, also as kepub: the reader's file is what is remembered.
    assert runner.sync(mac, cfg).message == "" and calls(kepubify) == ["One.epub"]


def test_a_book_kepubify_cannot_convert_goes_as_it_is(plugged, home, monkeypatch):
    mac, books, cfg, _ = plugged
    a_kepubify(home, monkeypatch)
    monkeypatch.setattr(tokobo, "CONVERT_SECONDS", 0.5)
    a_book(books / "Bad.epub", "Bad")
    a_book(books / "Slow.epub", "Slow")
    a_book(books / "Good.epub", "Good")
    rows = []
    started = time.monotonic()
    runner.sync(mac, cfg, on_step=rows.append)
    assert time.monotonic() - started < 4  # a kepubify that hangs is not waited for
    assert on_kobo(home) == ["Bad.epub", "Good.kepub.epub", "Slow.epub"]
    (row,) = [r for r in rows if r.what == "To Kobo"]
    assert row.state == "warn" and row.text == "3 books put on the Kobo (Bad.epub, Slow.epub as EPUB: kepubify could not convert them)"
    assert os.listdir(home / "scratch") == []


def test_without_kepubify_the_books_go_as_epub_and_it_is_said_how_to_get_kepub(plugged, home, capsys):
    mac, books, cfg, _ = plugged
    a_book(books / "One.epub", "One")
    rows = []
    runner.sync(mac, cfg, on_step=rows.append)
    assert on_kobo(home) == ["One.epub"]
    assert [r.text for r in rows if r.what == "To Kobo"] == ["1 book put on the Kobo as EPUB (kepubify is not installed)"]
    config.save(cfg)
    cli.main(["to-kobo"], computer=mac)
    said = capsys.readouterr().out
    assert "as EPUB;" in said and "kepubify" in said


def test_kepubify_is_found_where_homebrew_puts_it_also_without_it_on_the_path(tmp_path, monkeypatch):
    (tmp_path / "bin").mkdir()
    tool = tmp_path / "bin" / "kepubify"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.setattr(tokobo, "KEPUBIFY_DIRS", ("/nonexistent", str(tmp_path / "bin")))
    assert REAL_KEPUBIFY() == str(tool)
    monkeypatch.setattr(tokobo, "KEPUBIFY_DIRS", ())
    assert REAL_KEPUBIFY() == ""


CHAPTERED = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>In A Book</dc:title>
    <dc:identifier id="id">urn:isbn:{ISBN}</dc:identifier><dc:language>en</dc:language></metadata>
  <manifest><item id="c" href="c.xhtml" media-type="application/xhtml+xml"/></manifest>
  <spine><itemref idref="c"/></spine>
</package>"""


def test_the_mac_apps_own_kepubify_goes_first(tmp_path, monkeypatch):
    own = tmp_path / "Resources" / "bin" / "kepubify"
    own.parent.mkdir(parents=True)
    own.write_text("#!/bin/sh\n")
    own.chmod(0o755)
    elsewhere = tmp_path / "bin" / "kepubify"
    elsewhere.parent.mkdir()
    elsewhere.write_text("#!/bin/sh\n")
    elsewhere.chmod(0o755)
    monkeypatch.setenv("PATH", str(elsewhere.parent))
    monkeypatch.setattr(tokobo, "BUNDLED", str(own))
    assert REAL_KEPUBIFY() == str(own)
    monkeypatch.setattr(tokobo, "BUNDLED", str(tmp_path / "Resources" / "bin" / "none"))  # not the app: what is installed
    assert REAL_KEPUBIFY() == str(elsewhere)


@pytest.mark.skipif(not REAL_KEPUBIFY(), reason="kepubify is not installed here")
def test_the_real_kepubify(tmp_path):
    """With the real program, where it is installed: the kepub keeps its ISBN (M10)."""
    book = str(tmp_path / "In A Book.epub")
    with zipfile.ZipFile(book, "w") as z:  # one chapter, which kepubify marks up
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", CONTAINER)
        z.writestr("OEBPS/content.opf", CHAPTERED)
        z.writestr(
            "OEBPS/c.xhtml", '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><body><p>Two. Sentences.</p></body></html>'
        )
    out = tokobo._kepub(REAL_KEPUBIFY(), book, str(tmp_path))
    assert out == str(tmp_path / "In A Book.kepub.epub") and epub.isbn(out) == ISBN
    with zipfile.ZipFile(out) as z:
        assert any(b"koboSpan" in z.read(n) for n in z.namelist() if n.endswith(".xhtml"))
    (tmp_path / "Bad.epub").write_bytes(b"not a zip")
    assert tokobo._kepub(REAL_KEPUBIFY(), str(tmp_path / "Bad.epub"), str(tmp_path)) == ""


# ---------- choosing the folder on the page (local mode) ----------
def test_the_page_chooses_the_folder_asks_before_many_and_shows_what_was_refused(local, home):  # noqa: F811
    web, mac, inside = local
    books = home / "Books"
    a_book(books / "One.epub", "One")
    a_book(books / "Adobe.epub", "Adobe", {"META-INF/rights.xml": "<rights/>"})
    page = inside.get("/settings").text
    assert 'id="tokobo"' in page and "No folder: nothing is put on the Kobo" in page

    # A folder that is not one, and one on the Kobo, are refused next to the form.
    r = inside.post("/settings/to-kobo", data={"folder": str(home / "nowhere")}, headers=ORIGIN)
    assert r.status_code == 400 and "That is not a folder on this computer." in r.text and config.load().to_kobo == ""
    kobo(home)
    r = inside.post("/settings/to-kobo", data={"folder": mount(home)}, headers=ORIGIN)
    assert r.status_code == 400 and "That folder is on the Kobo itself." in r.text

    r = inside.post("/settings/to-kobo", data={"folder": str(books)}, headers=ORIGIN, follow_redirects=False)
    assert r.headers["location"] == "/settings?ok=tokobo_on#tokobo" and config.load().to_kobo == str(books)
    page = inside.get("/settings?ok=tokobo_on").text
    assert f"Books in {books} go on the Kobo at plug-in, as EPUB; 2 of 2 wait for a Kobo" in page
    assert "With kepubify installed" in page

    # After a plug-in: what went is no longer waiting, and the one with DRM is listed with why.
    runner.sync(mac, replace(LOCAL, to_kobo=str(books)))
    page = inside.get("/settings").text
    assert "0 of 2 wait for a Kobo" in page and "<b>Adobe.epub</b>: it has Adobe DRM; open it with Adobe Digital Editions" in page

    # A folder with many books not on a Kobo yet: asked first, with the number; nothing kept until yes.
    many = home / "Many"
    for n in range(tokobo.MANY + 1):
        a_book(many / f"Book {n:02d}.epub", f"Many {n}")
    r = inside.post("/settings/to-kobo", data={"folder": str(many)}, headers=ORIGIN)
    assert r.status_code == 200 and f"{tokobo.MANY + 1} books in {many} would go on the Kobo" in r.text
    assert f"Put all {tokobo.MANY + 1} on the Kobo" in r.text and config.load().to_kobo == str(books)
    inside.post("/settings/to-kobo", data={"folder": str(many), "yes": "1"}, headers=ORIGIN)
    assert config.load().to_kobo == str(many)

    r = inside.post("/settings/to-kobo/off", headers=ORIGIN, follow_redirects=False)
    assert r.headers["location"] == "/settings?ok=tokobo_off#tokobo" and config.load().to_kobo == ""


def test_the_server_page_has_no_folder(home, server):  # noqa: F811
    """The folder is the computer's: on a server's page there is nothing to choose."""
    assert 'id="tokobo"' not in server.page.get("/settings").text
    assert server.page.post("/settings/to-kobo", data={"folder": "/tmp"}).status_code == 404
