"""Books put on a Kobo by hand (rules G1, G2): the files you name, on the
Kobo that is plugged in, whoever's it is. A Kobo that is not the reader's
is left alone by every sync (W3), and this is the one thing that can still
be done with it from here."""

import errno
import os
import types

import pytest

from lastread import cli
from lastread.computer import kobos, runner
from lastread.engine import tokobo
from tests import said
from tests.test_app_answers import answer, same_shape, sample
from tests.test_computer import FakeComputer
from tests.test_tokobo import ENCRYPTION, a_book, a_kepubify, mount, no_kepubify, on_kobo, plugged  # noqa: F401 (fixtures)
from tests.test_whose_kobo import THEIRS, says


def a_pdf(path, text=b"a school book"):
    path.write_bytes(b"%PDF-1.7\n" + text + b"\n%%EOF\n")
    return str(path)


@pytest.fixture
def guest(plugged, home):  # noqa: F811
    """Someone else's Kobo plugged into the reader's computer, and said to be so."""
    mac, _, cfg, db = plugged
    theirs = says(home, THEIRS, "390")
    kobos.say(str(home / "state"), theirs.name, False, theirs.model)
    return mac, cfg, db, theirs


def test_a_book_is_put_on_a_kobo_that_is_not_the_readers_and_nothing_else_is_done_with_it(guest, home, capsys, monkeypatch):
    mac, cfg, db, theirs = guest
    a_kepubify(home, monkeypatch)
    book, pdf = a_book(home / "School.epub", "School"), a_pdf(home / "Reader for class.pdf")
    before = open(db, "rb").read()
    found = answer(capsys, "put", book, pdf, "--json", computer=mac)
    assert found["put"] == ["School.kepub.epub", "Reader for class.pdf"] and found["refused"] == [] and found["left"] == 0
    assert found["kobo"] == {"id": theirs.name, "model": "Kobo Libra Colour", "whose": "other"}
    assert [(b["name"], b["format"]) for b in found["books"]] == [("Reader for class.pdf", "pdf"), ("School.kepub.epub", "kepub")]
    assert open(home / "Volumes" / "KOBOeReader" / tokobo.FOLDER / "Reader for class.pdf", "rb").read() == open(pdf, "rb").read()
    assert open(db, "rb").read() == before and mac.ejected == []  # only files, and it stays plugged in
    # The sync still leaves it alone, and the reader's own folder of books does not go on it.
    a_book(home / "Books" / "Mine.epub", "Mine")
    assert runner.sync(mac, cfg, trigger="mount").message == "" and "Mine.epub" not in on_kobo(home)
    assert not os.path.exists(home / "state" / tokobo.REMEMBERED) or theirs.name not in open(home / "state" / tokobo.REMEMBERED).read()
    # Asked, it ejects when it is done.
    assert answer(capsys, "put", "--eject", "--json", computer=mac)["ejected"] is True and mac.ejected == [mount(home)]


def test_a_book_put_by_hand_never_goes_over_another_and_a_pdf_goes_as_it_is(plugged, home, capsys):  # noqa: F811
    mac, _, _, _ = plugged  # the reader's own Kobo: by hand works there too
    pdf = a_pdf(home / "Notes.pdf")
    cli.main(["put", pdf], computer=mac)
    cli.main(["put", pdf, a_book(home / "One.epub", "One")], computer=mac)
    told = said(capsys)
    assert on_kobo(home) == ["Notes (2).pdf", "Notes.pdf", "One.epub"]
    assert "Kobo Clara Colour, yours" in told and "One.epub as EPUB (kepubify is not installed)" in told
    assert "Eject before unplugging." in told
    assert not [f for f in os.listdir(home / "Volumes" / "KOBOeReader" / tokobo.FOLDER) if f.startswith(".")]  # nothing left half


def test_what_cannot_go_by_hand_is_said_and_the_rest_still_goes(guest, home, capsys):
    mac, _, _, _ = guest
    good = a_book(home / "Good.epub", "Good")
    locked = a_book(
        home / "Locked.epub",
        "Locked",
        {"META-INF/encryption.xml": ENCRYPTION.format("http://www.w3.org/2001/04/xmlenc#aes256-cbc", "c.xhtml")},
    )
    (home / "Scan.pdf").write_bytes(b"<html>not a pdf</html>")
    (home / "Letter.docx").write_bytes(b"PK")
    same = lambda found: same_shape(found, sample("put.json"))  # noqa: E731 (what the Mac app reads)
    found = answer(
        capsys,
        "put",
        locked,
        str(home / "Scan.pdf"),
        str(home / "Letter.docx"),
        str(home / "Gone.epub"),
        good,
        "--json",
        computer=mac,
        exits=1,
    )
    assert found["put"] == ["Good.epub"]
    same(found)
    assert {r["name"]: r["why"] for r in found["refused"]} == {
        "Locked.epub": "it is encrypted (DRM)",
        "Scan.pdf": "it is not a PDF that can be read",
        "Letter.docx": "it is not an EPUB or a PDF",
        "Gone.epub": "it is not there",
    }
    # A book that is on the Kobo is not put on it from there, and without a Kobo there is nothing to put a book on.
    there = str(home / "Volumes" / "KOBOeReader" / tokobo.FOLDER / "Good.epub")
    assert tokobo.put_files([there], mount(home)).refused == [("Good.epub", "it is on the Kobo already")]
    (home / "Empty").mkdir()
    with pytest.raises(SystemExit) as ended:
        cli.main(["put", good], computer=FakeComputer(home / "Empty"))
    assert "no Kobo is plugged in" in str(ended.value)


def test_a_kobo_without_room_gets_nothing_half_by_hand(guest, home, monkeypatch):
    monkeypatch.setattr(tokobo.shutil, "disk_usage", lambda path: types.SimpleNamespace(free=1 << 20))
    r = tokobo.put_files([a_pdf(home / "One.pdf"), a_pdf(home / "Two.pdf")], mount(home))
    assert (r.put, r.left, r.why_left) == ([], 2, "full") and on_kobo(home) == []


def test_only_a_book_in_the_kobos_lastread_folder_can_be_taken_off(guest, home, capsys):
    mac, _, db, _ = guest
    cli.main(["put", a_pdf(home / "Notes.pdf"), a_book(home / "One.epub", "One")], computer=mac)
    kobo = home / "Volumes" / "KOBOeReader"
    a_book(kobo / "Bought elsewhere.epub", "Theirs")  # the Kobo's own business
    (kobo / tokobo.FOLDER / ".hidden.pdf").write_bytes(b"%PDF-")
    assert [b["name"] for b in tokobo.in_folder(mount(home))] == ["Notes.pdf", "One.epub"]
    for elsewhere in ("../Bought elsewhere.epub", "../.kobo/KoboReader.sqlite", ".hidden.pdf", "Bought elsewhere.epub", ""):
        with pytest.raises(tokobo.Refused):
            tokobo.take_off(mount(home), elsewhere)
    assert os.path.exists(db) and os.path.exists(kobo / "Bought elsewhere.epub")
    capsys.readouterr()
    found = answer(capsys, "put", "--remove", "Notes.pdf", "--json", computer=mac)
    assert found["removed"] == ["Notes.pdf"] and [b["name"] for b in found["books"]] == ["One.epub"]
    with pytest.raises(SystemExit) as ended:
        cli.main(["put", "--remove", "Notes.pdf"], computer=mac)
    assert "Notes.pdf is not in the Kobo's Lastread folder" in str(ended.value)


def test_a_file_this_computer_cannot_open_is_not_taken_for_a_broken_book(plugged, home, monkeypatch):  # noqa: F811
    mac, books, cfg, _ = plugged
    a_book(books / "One.epub", "One")
    runner.sync(mac, cfg)  # read once: its hash is kept, so the next plug-in does not open it to know it
    os.unlink(home / "Volumes" / "KOBOeReader" / tokobo.FOLDER / "One.epub")
    a_book(books / "Two.epub", "Two")
    real = tokobo._drm

    def in_icloud(path):  # as macOS answers a sync the Kobo started, for a file it keeps in iCloud
        if path.endswith("Two.epub"):
            raise OSError(errno.EDEADLK, "Resource deadlock avoided")
        return real(path)

    monkeypatch.setattr(tokobo, "_drm", in_icloud)
    out = runner.sync(mac, cfg)
    assert out.message == "Two.epub not put on the Kobo yet: this computer could not read it (Resource deadlock avoided)."
    assert [b["kobo"] for b in tokobo.books(str(books), str(home / "state")) if b["name"] == "Two.epub"] == ["waiting"]  # not refused
    monkeypatch.setattr(tokobo, "_drm", real)
    assert runner.sync(mac, cfg).message == "1 book put on the Kobo. Eject before unplugging."  # tried again, and it went
    # What macOS says of such a file is put in words that say what to do.
    monkeypatch.setattr(tokobo.os, "stat", lambda path: types.SimpleNamespace(st_flags=tokobo.SF_DATALESS))
    assert tokobo._why_unread("x.epub", OSError(errno.EDEADLK, "Resource deadlock avoided")).startswith("macOS keeps it in iCloud")
