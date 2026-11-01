"""Books put on the Kobo by hand: the ISBN their own EPUB names, where the
Kobo's database has none (rule M10). The EPUBs here are made up, the
smallest files of the shape a store or Calibre writes."""

import os
import sqlite3
import zipfile

from lastread.computer import runner
from lastread.engine import epub, kobo_db, state
from tests.kobo_fixture import BOOKS, SIDELOADED, make
from tests.test_core import make_kobo
from tests.test_hardcover import FakeHC, row, run, setup

ISBN = "9780306406157"  # a valid ISBN-13; its ISBN-10 is 0306406152
OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" xmlns:opf="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>A Sideloaded Book</dc:title>
    {}
  </metadata>
</package>"""
CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""


def an_epub(path, *identifiers, container=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        if container:
            z.writestr("META-INF/container.xml", CONTAINER)
        z.writestr("OEBPS/content.opf", OPF.format("\n    ".join(identifiers)))
    return str(path)


def test_an_epub_names_its_isbn_and_other_numbers_are_not_taken_for_one(tmp_path):
    def found(*identifiers, **kw):
        return epub.isbn(an_epub(tmp_path / "b.epub", *identifiers, **kw))

    # The shapes stores and Calibre write.
    assert found(f"<dc:identifier>urn:isbn:{ISBN}</dc:identifier>") == ISBN
    assert found('<dc:identifier opf:scheme="ISBN">978-0-306-40615-7</dc:identifier>') == ISBN
    assert found(f"<dc:identifier>{ISBN}</dc:identifier>") == ISBN  # EPUB 3: no scheme, the number alone
    assert found('<dc:identifier opf:scheme="ISBN">0-306-40615-2</dc:identifier>') == ISBN  # ISBN-10, as 13
    assert found("<dc:identifier>ISBN 0306406152</dc:identifier>") == ISBN
    # The package document found without container.xml, when there is one.
    assert found(f"<dc:identifier>urn:isbn:{ISBN}</dc:identifier>", container=False) == ISBN
    # One marked as an ISBN goes before one that only looks like it.
    other = "9781861972712"
    assert found(f"<dc:identifier>{other}</dc:identifier>", f"<dc:identifier>urn:isbn:{ISBN}</dc:identifier>") == ISBN
    # Not ISBNs: a wrong check digit, an unmarked ten digits, Calibre's ids, an ASIN.
    assert found("<dc:identifier>urn:isbn:9780306406158</dc:identifier>") == ""
    assert found("<dc:identifier>0306406152</dc:identifier>") == ""
    assert (
        found(
            '<dc:identifier opf:scheme="calibre">1234</dc:identifier>',
            '<dc:identifier opf:scheme="uuid">urn:uuid:0e2d5b1c-4b6e-4f0f-9a43-9780306406157</dc:identifier>',
            '<dc:identifier opf:scheme="MOBI-ASIN">B00EXAMPLE</dc:identifier>',
        )
        == ""
    )
    # Not EPUBs of the usual shape: nothing, and no error.
    (tmp_path / "not.epub").write_bytes(b"%PDF-1.4")
    assert epub.isbn(str(tmp_path / "not.epub")) == "" and epub.isbn(str(tmp_path / "missing.epub")) == ""
    with zipfile.ZipFile(tmp_path / "big.epub", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("META-INF/container.xml", CONTAINER)
        z.writestr("OEBPS/content.opf", OPF.format(f"<dc:identifier>urn:isbn:{ISBN}</dc:identifier>" + " " * epub.MOST))
    assert epub.isbn(str(tmp_path / "big.epub")) == ""  # more than an OPF can be: not read


def test_a_book_put_on_the_kobo_by_hand_gets_the_isbn_its_own_file_names(tmp_path):
    mount = tmp_path / "KOBOeReader"
    db = mount / ".kobo" / "KoboReader.sqlite"
    db.parent.mkdir(parents=True)
    make(str(db))
    an_epub(mount / "A Sideloaded Book.epub", f"<dc:identifier>urn:isbn:{ISBN}</dc:identifier>")
    # Ones that are not read: a PDF, a path that leads off the Kobo, the SD card.
    an_epub(tmp_path / "outside.epub", "<dc:identifier>urn:isbn:9781861972712</dc:identifier>")
    not_read = ["file:///mnt/onboard/A Paper.pdf", "file:///mnt/onboard/../outside.epub", "file:///mnt/sd/On The Card.epub"]
    con = sqlite3.connect(db)
    for cid in not_read:
        con.execute("insert into content values (?, '6', 'application/epub+zip', 'x', 'y', '', 5, 1, '', 60, '', '', 'en')", (cid,))
    con.commit()
    con.close()
    (mount / "A Paper.pdf").write_bytes(b"%PDF-1.4")
    copy = runner.copy_database(str(db), str(tmp_path))
    on_kobo = db.read_bytes()

    assert kobo_db.fill_isbns(copy, str(mount)) == 1
    isbns = {b.content_id: b.isbn for b in kobo_db.read_books(kobo_db.open_db(copy))}
    assert isbns[SIDELOADED] == ISBN
    assert [isbns[c] for c in BOOKS] == [f"97800000000{n:02d}" for n in range(8)]  # the Kobo's own ISBNs stay
    assert [isbns[c] for c in not_read] == ["", "", ""]
    assert db.read_bytes() == on_kobo  # the Kobo is only read
    assert kobo_db.fill_isbns(copy, str(mount)) == 0  # one that has an ISBN is not opened again

    # In server mode the upload carries it.
    small = str(tmp_path / "upload.sqlite")
    kobo_db.export_for_upload(copy, small)
    assert sqlite3.connect(small).execute("select ISBN from content where ContentID = ?", (SIDELOADED,)).fetchone()[0] == ISBN


def test_a_waiting_book_is_looked_up_again_when_its_isbn_arrives(tmp_path):
    side = ("file:///mnt/onboard/Side.epub", "Een Boek Dat Niemand Kent", "Iemand", "", 30, 1, "2026-09-29T10:00:00Z", 900)
    st = setup(tmp_path, [side])
    fake = FakeHC(isbn={ISBN: {"id": 7, "book_id": 70, "isbn_13": ISBN, "pages": 250, "title": "A Book Nobody Knows"}})
    assert run(tmp_path, fake, live=False)["uncertain"] == 1 and row(st, side[0])["hc_how"] == "none"
    assert run(tmp_path, fake, live=False)["uncertain"] == 0  # waits for the reader (M2)

    # The next sync reads the ISBN from the file: one more look, and it is found by it.
    make_kobo(tmp_path / "k2.sqlite", [side[:3] + (ISBN,) + side[4:]], [])
    state.import_books(st, "alice", "kobo1", kobo_db.read_books(kobo_db.open_db(str(tmp_path / "k2.sqlite"))))
    run(tmp_path, fake, live=False)
    assert (row(st, side[0])["hc_how"], row(st, side[0])["hc_book_id"]) == ("isbn", 70)

    # A match the reader chose stays, whatever ISBN turns up later (M3).
    st.execute("update book set hc_how = 'manual', hc_book_id = 99, isbn = '' where content_id = ?", (side[0],))
    st.commit()
    state.import_books(st, "alice", "kobo1", kobo_db.read_books(kobo_db.open_db(str(tmp_path / "k2.sqlite"))))
    run(tmp_path, fake, live=False)
    assert (row(st, side[0])["hc_how"], row(st, side[0])["hc_book_id"]) == ("manual", 99)
