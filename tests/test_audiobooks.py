"""Audiobooks. The Kobo lists an audiobook from its store among the books
(ContentType 6), with how far the listening is as its percentage. Read as a
book it got an ebook edition on Hardcover and its listening sent as pages.
Now it is known for what it is: off until the reader switches it on, and
then its status and dates on an audiobook edition, without progress."""

import sqlite3

from lastread import booklist
from lastread.engine import hardcover, kobo_db, plan, state
from lastread.engine.plan import action
from tests.test_core import MINE, OLD, make_kobo
from tests.test_hardcover import FakeHC, row, run, sent

LATER = "2099-01-01T09:00:00"  # opened on this Kobo after its first import
HEARD = ("aud", "Mile High", "Liz Tomforde, A Narrator", "978222", 3, 1, "2026-11-01T10:00:00Z", 0)  # the Kobo keeps no reading time for it
HEARD_HIT = {"Mile": [{"book_id": 90, "title": "Mile High", "authors": ["Liz Tomforde"], "pages": 300, "slug": "m"}]}
# The editions of book 90. The first carries the Kobo's ISBN and, as some audiobook editions do, a page count.
A_ISBN = {
    "id": 11,
    "book_id": 90,
    "isbn_13": "978222",
    "pages": 320,
    "reading_format_id": 2,
    "edition_format": "Audiobook",
    "users_count": 1,
}
A_NL = {"id": 12, "book_id": 90, "isbn_13": "x12", "pages": None, "reading_format_id": 2, "users_count": 50, "language": {"code2": "nl"}}
A_EN = {"id": 13, "book_id": 90, "isbn_13": "x13", "pages": None, "reading_format_id": 2, "users_count": 99, "language": {"code2": "en"}}
EBOOK = {"id": 14, "book_id": 90, "isbn_13": "x14", "pages": 300, "reading_format_id": 4, "users_count": 500, "language": {"code2": "nl"}}
PAPER_ISBN = {"id": 15, "book_id": 90, "isbn_13": "978222", "pages": 310, "reading_format_id": 1, "users_count": 9}
BY_ISBN = {"978222": {**A_ISBN, "title": "Mile High"}}


def kobo(tmp_path, books, events=(), name="k.sqlite", audio=("aud",)):
    k = tmp_path / name
    make_kobo(k, books, list(events), audio=audio)
    return kobo_db.read_books(kobo_db.open_db(str(k)))


def imported(tmp_path, books, events=(), name="k.sqlite", audio=("aud",), reader="alice"):
    st = state.connect(str(tmp_path / "state.db"))
    return st, state.import_books(st, reader, "kobo1", kobo(tmp_path, books, events, name, audio))


def switched_on(tmp_path, books=(HEARD,), audio=("aud",)):
    """A shelf whose audiobook the reader switched on, opened on this Kobo after its first import."""
    st, _ = imported(tmp_path, [OLD])
    imported(tmp_path, [OLD, *books], [(b[0], LATER) for b in books], name="2.sqlite", audio=audio)
    state.set_mode(st, "alice", [b[0] for b in books], "on")
    return st


# ---------- which book is one ----------
def test_the_kobo_says_which_book_is_an_audiobook(tmp_path):
    assert {b.content_id: b.audio for b in kobo(tmp_path, [OLD, HEARD])} == {"old": False, "aud": True}
    # It takes both marks: the file's kind and a playing time. One of them alone is still a book.
    con = sqlite3.connect(tmp_path / "k.sqlite")
    con.execute("update content set Duration=0 where ContentID='aud'")
    con.execute("update content set Duration=600 where ContentID='old'")
    con.commit()
    con.close()
    assert not any(b.audio for b in kobo_db.read_books(kobo_db.open_db(str(tmp_path / "k.sqlite"))))
    # A database without the two columns, from a computer on a version that did not upload them: books only.
    assert not any(b.audio for b in kobo(tmp_path, [OLD, HEARD], name="older.sqlite", audio=()))


def test_an_audiobook_is_still_one_after_the_upload(tmp_path):
    kobo(tmp_path, [OLD, HEARD])
    kobo_db.export_for_upload(str(tmp_path / "k.sqlite"), str(tmp_path / "upload.sqlite"))
    assert {b.content_id: b.audio for b in kobo_db.read_books(kobo_db.open_db(str(tmp_path / "upload.sqlite")))} == {
        "old": False,
        "aud": True,
    }


# ---------- which books ----------
def test_an_audiobook_is_off_until_the_reader_switches_it_on(tmp_path):
    st, _ = imported(tmp_path, [OLD])
    # Opened on this Kobo after its first import: a book is new then and syncs by itself. An audiobook is listed, and off.
    _, r = imported(tmp_path, [OLD, HEARD, MINE], [("aud", LATER), ("mine", LATER)], name="2.sqlite")
    aud = row(st, "aud")
    assert r["new_auto"] == 1 and state.syncs(row(st, "mine"))
    assert aud["audio"] == 1 and (aud["mode"], aud["history"]) == ("off", 1) and not state.syncs(aud)
    # Neither does one the Kobo listed before, from the account, become new when it is opened here.
    other = ("aud2", "Another One", "B", "978333", 10, 1, "2026-11-01T10:00:00Z", 0)
    both = ("aud", "aud2")
    imported(tmp_path, [OLD, HEARD, MINE, other], [("aud", LATER), ("mine", LATER)], name="3.sqlite", audio=both)
    _, r = imported(tmp_path, [OLD, HEARD, MINE, other], [("aud", LATER), ("mine", LATER), ("aud2", LATER)], name="4.sqlite", audio=both)
    assert r["new_auto"] == 0 and not state.syncs(row(st, "aud2"))
    # Switched on, it stays on.
    state.set_mode(st, "alice", ["aud"], "on")
    imported(tmp_path, [OLD, HEARD, MINE, other], [("aud", LATER), ("mine", LATER), ("aud2", LATER)], name="5.sqlite", audio=both)
    assert state.syncs(row(st, "aud")) and not state.syncs(row(st, "aud2"))
    # An upload from a computer on an older version does not say what is an audiobook: what is known stays known.
    imported(tmp_path, [OLD, HEARD, MINE, other], [("aud", LATER), ("mine", LATER), ("aud2", LATER)], name="6.sqlite", audio=())
    assert row(st, "aud")["audio"] == 1 and row(st, "aud2")["audio"] == 1


# ---------- what Hardcover gets ----------
def test_an_audiobook_gets_its_status_and_dates_and_no_progress(tmp_path):
    st = switched_on(tmp_path)
    today = state.now()[:10]
    assert plan.desired(row(st, "aud")) == {"status": "reading", "progress": None, "started": today}
    fake = FakeHC(isbn=BY_ISBN)
    assert run(tmp_path, fake, live=False)["planned"] == 1
    assert action(row(st, "aud")) == f"mark Currently reading, started {today}"  # no percentage: none is sent
    assert run(tmp_path, fake)["sent"] == 1
    ub = sent(st, "aud")["user_book_id"]
    assert fake.books[ub]["status_id"] == 2 and fake.books[ub]["edition_id"] == 11
    # The edition has a page count, and still no page is sent: 3% of a listening is not a page.
    assert [c[2] for c in fake.calls if c[0] == "update_read"] == [{"edition_id": 11, "started_at": today}]
    assert sent(st, "aud")["progress"] is None and booklist.shelf_words(sent(st, "aud")) == "Currently reading"
    # Listened on: nothing to send.
    fake.calls.clear()
    imported(tmp_path, [OLD, ("aud", *HEARD[1:4], 40, 1, "2026-11-05T10:00:00Z", 0)], [("aud", LATER)], name="3.sqlite")
    assert row(st, "aud")["percent"] == 40 and action(row(st, "aud")) == ""
    assert run(tmp_path, fake)["sent"] == 0 and fake.calls == []
    # Finished: Read, on the Kobo's date.
    done = ("aud", *HEARD[1:4], 100, 2, "2026-11-10T10:00:00Z", 0, "2026-11-10T10:00:00Z")
    imported(tmp_path, [OLD, done], [("aud", LATER)], name="4.sqlite")
    assert action(row(st, "aud")) == "mark Read, finished 2026-11-10"
    assert run(tmp_path, fake)["sent"] == 1
    assert fake.books[ub]["status_id"] == 3 and fake.books[ub]["user_book_reads"][-1]["finished_at"] == "2026-11-10"
    assert all("progress_pages" not in c[2] for c in fake.calls if c[0] == "update_read")


def test_a_reread_of_an_audiobook_has_no_progress_either(tmp_path):
    done = ("aud", *HEARD[1:4], 100, 2, "2026-11-10T10:00:00Z", 0, "2026-11-10T10:00:00Z")
    st = switched_on(tmp_path, [done])
    state.set_state(st, "alice", "aud", "rereading")
    assert plan.desired(row(st, "aud")) == {"status": "reading", "progress": None, "reread": True}
    st.execute("update book set hc_how='isbn', hc_book_id=90 where content_id='aud'")
    st.commit()
    assert action(row(st, "aud")) == "start a re-read"


# ---------- the edition ----------
def test_an_audiobook_gets_an_audiobook_edition_and_never_an_ebook_one():
    def pick(eds):
        return (hardcover.choose_edition("978222", "nl", eds, audio=True) or {}).get("id")

    assert pick([EBOOK, A_EN, A_NL, PAPER_ISBN, A_ISBN]) == 11  # the Kobo's ISBN, marked Audiobook
    assert pick([EBOOK, A_EN, A_NL, PAPER_ISBN]) == 12  # an audiobook in the book's language
    assert pick([EBOOK, A_EN, PAPER_ISBN]) == 13  # any audiobook
    assert pick([EBOOK, PAPER_ISBN]) == 15  # the Kobo's ISBN, whatever its label
    assert pick([EBOOK]) is None  # no ebook for want of an audiobook: Hardcover's default stays
    # And a book is not given an audiobook edition, also when that one carries its ISBN and is all there is besides.
    assert hardcover.choose_edition("978222", "nl", [A_ISBN, A_NL, EBOOK])["id"] == 14


def test_the_sync_chooses_the_audiobook_edition_and_the_ebook_for_the_book_beside_it(tmp_path):
    st = switched_on(tmp_path, [HEARD, MINE])
    st.execute("update book set language='nl' where content_id='aud'")
    st.commit()
    ebook_81 = {"id": 21, "book_id": 81, "isbn_13": "x21", "pages": 200, "reading_format_id": 4, "users_count": 3}
    audio_81 = {"id": 22, "book_id": 81, "isbn_13": "x22", "pages": None, "reading_format_id": 2, "users_count": 900}
    mine_hit = {"Mine": [{"book_id": 81, "title": "Mine Now", "authors": ["C"], "pages": 100, "slug": "m"}]}
    fake = FakeHC(search={**HEARD_HIT, **mine_hit}, catalog={90: [EBOOK, A_EN, A_NL], 81: [audio_81, ebook_81]})
    assert run(tmp_path, fake)["sent"] == 2 and fake.asked_audio is True  # the audiobook editions were asked for
    aud, mine = row(st, "aud"), row(st, "mine")
    assert (aud["hc_edition_id"], aud["hc_format"], aud["hc_edition_by"]) == (12, "Audiobook", "auto")
    assert (mine["hc_edition_id"], mine["hc_format"]) == (21, "Ebook")
    assert fake.books[sent(st, "aud")["user_book_id"]]["edition_id"] == 12
    # Without an audiobook among the books that sync, the audiobook editions are not asked for.
    state.set_mode(st, "alice", ["aud"], "off")
    st.execute("update book set hc_edition_checked=null")
    st.commit()
    run(tmp_path, fake)
    assert fake.asked_audio is False


def test_a_book_that_turns_out_to_be_an_audiobook_gets_its_edition_chosen_again(tmp_path):
    # Read by a version that did not tell them apart: a book like any other, switched on, with an ebook edition.
    st, _ = imported(tmp_path, [HEARD], audio=())
    state.set_mode(st, "alice", ["aud"], "on")
    fake = FakeHC(search=HEARD_HIT, catalog={90: [EBOOK, A_NL]})
    run(tmp_path, fake)
    ub = sent(st, "aud")["user_book_id"]
    assert row(st, "aud")["hc_edition_id"] == 14 and fake.books[ub]["user_book_reads"][0]["progress_pages"] == 9
    # The next import says what it is. It stays on, as the reader had it, and its edition is chosen again at once.
    imported(tmp_path, [HEARD], name="2.sqlite")
    aud = row(st, "aud")
    assert aud["audio"] == 1 and state.syncs(aud) and aud["hc_edition_checked"] is None
    fake.calls.clear()
    assert run(tmp_path, fake)["editions"] == 1
    assert row(st, "aud")["hc_edition_id"] == 12 and fake.books[ub]["edition_id"] == 12
    assert all("progress_pages" not in c[2] for c in fake.calls if c[0] == "update_read")
    # An edition the reader chose on Hardcover is theirs, audiobook or not.
    st.execute("update book set audio=0, hc_edition_by='hardcover', hc_edition_checked='2026-11-01T00:00:00Z' where content_id='aud'")
    st.commit()
    imported(tmp_path, [HEARD], name="3.sqlite")
    assert row(st, "aud")["hc_edition_checked"] == "2026-11-01T00:00:00Z"


# ---------- the list ----------
def test_audiobooks_are_marked_and_have_a_selection_of_their_own(tmp_path):
    st, _ = imported(tmp_path, [OLD, HEARD])
    assert booklist.ids(st, "alice", "", "audio") == ["aud"]
    rows = {r["content_id"]: r for r in booklist.query_rows(st, "alice", "", "all", "last_read")}
    aud = booklist.entry(rows["aud"], False, {}, booklist.filters_of(st, "alice", "aud"))
    assert aud["audio"] is True and "audio" in aud["filters"] and ["Format", "Audiobook"] in aud["details"]["kobo"]
    old = booklist.entry(rows["old"], False, {}, booklist.filters_of(st, "alice", "old"))
    assert old["audio"] is False and "audio" not in old["filters"] and not any(k == "Format" for k, _ in old["details"]["kobo"])
    # The selection is offered to a reader whose Kobo has an audiobook, and not to one without.
    imported(tmp_path, [OLD], name="bob.sqlite", reader="bob")
    assert "audio" in dict(booklist.groups(st, "alice"))["kobo"] and "audio" not in dict(booklist.groups(st, "bob"))["kobo"]
    assert [k for g, keys in booklist.groups(st, "bob") for k in keys] == [k for k in booklist.FILTERS if k != "audio"]
    # On its audiobook edition it is as it should be; on an ebook edition it is one to put right on Hardcover.
    st.execute("update book set mode='on', hc_book_id=90, last_sent='{}', hc_format_id=2 where content_id='aud'")
    assert booklist.ids(st, "alice", "", "not_ebook") == []
    st.execute("update book set hc_format_id=4 where content_id='aud'")
    assert booklist.ids(st, "alice", "", "not_ebook") == ["aud"]


def test_the_page_marks_an_audiobook_and_offers_its_selection(tmp_path, monkeypatch):
    from tests.test_web import client

    c = client(tmp_path, monkeypatch)
    me = {"Remote-User": "robin"}
    assert "Audiobook" not in c.get("/", headers=me).text  # no audiobook on this Kobo: no tag and no selection
    st = state.connect(str(tmp_path / "state.db"))
    state.import_books(st, "robin", "kobo1", kobo(tmp_path, [OLD, MINE, HEARD], name="2.sqlite"))
    page = c.get("/", headers=me).text
    assert ">Audiobook</span>" in page and "Audiobooks<b>1</b>" in page
    only = c.get("/?f=audio", headers=me).text
    assert "Mile High" in only and "Old Finished" not in only
    details = c.get("/details/aud", headers=me).text
    assert "<dt>Format</dt><dd>Audiobook</dd>" in details and "<dt>Format</dt>" not in c.get("/details/old", headers=me).text
