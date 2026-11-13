import copy
import json
import sqlite3

import pytest

from lastread.engine import hardcover, job, kobo_db, state
from lastread.engine.plan import action, desired
from tests.test_core import OLD, make_kobo


class FakeHC:
    """A small in-memory Hardcover: a shelf that behaves like the real one
    (a new shelf book gets a read entry by itself), plus a catalogue."""

    def __init__(self, isbn=None, search=None, catalog=None):
        self.isbn, self.search_res, self.catalog = isbn or {}, search or {}, catalog or {}
        self.calls, self.next_id, self.books = [], 100, {}
        self.me = {"id": 1, "username": "alice"}  # the account the token is for

    def _id(self):
        self.next_id += 1
        return self.next_id

    def _edition(self, eid):
        for eds in self.catalog.values():
            for e in eds:
                if e["id"] == eid:
                    return {
                        "id": eid,
                        "pages": e.get("pages"),
                        "reading_format_id": e.get("reading_format_id"),
                        "edition_format": e.get("edition_format"),
                        "isbn_13": e.get("isbn_13"),
                    }
        return {"id": eid, "pages": None, "reading_format_id": None, "edition_format": None, "isbn_13": None} if eid else None

    # lookups
    def whoami(self):
        return self.me

    def editions_by_isbn(self, isbns):
        return {i: self.isbn[i] for i in isbns if i in self.isbn}

    def search(self, text, n=3):
        return self.search_res.get(text.split(" ")[0], [])

    def shelf(self):
        out = copy.deepcopy(list(self.books.values()))
        for u in out:
            u["edition"] = self._edition(u["edition_id"])
        return out

    def editions_for_books(self, book_ids, isbns, audio=False):
        self.asked_audio = audio
        formats = (4, 2) if audio else (4,)  # as the real one: by ISBN, or of a form the rule can choose
        return {
            b: [e for e in self.catalog[b] if e.get("isbn_13") in isbns or e.get("reading_format_id") in formats]
            for b in book_ids
            if b in self.catalog
        }

    def reads(self, ub_id):
        return copy.deepcopy(self.books[ub_id]["user_book_reads"])

    # writes
    def insert_user_book(self, obj):
        self.calls.append(("insert_ub", obj))
        ub = self._id()
        self.books[ub] = {
            "id": ub,
            "book_id": obj["book_id"],
            "status_id": obj["status_id"],
            "edition_id": obj.get("edition_id"),
            "user_book_reads": [
                {
                    "id": self._id(),
                    "started_at": None,
                    "progress_pages": None,
                    "edition_id": None,
                    "finished_at": "2026-09-30" if obj["status_id"] == 3 else None,
                }
            ],
        }
        return ub

    def update_user_book(self, i, obj):
        self.calls.append(("update_ub", i, obj))
        self.books[i].update(obj)

    def insert_read(self, ub, r):
        self.calls.append(("insert_read", ub, r))
        rid = self._id()
        self.books[ub]["user_book_reads"].append({"id": rid, "started_at": None, "finished_at": None, "progress_pages": None, **r})
        return rid

    def update_read(self, i, r):
        self.calls.append(("update_read", i, r))
        for u in self.books.values():
            for x in u["user_book_reads"]:
                if x["id"] == i:
                    x.update(r)

    def delete_user_book(self, i):
        self.calls.append(("delete_ub", i))
        self.books.pop(i, None)

    # what the reader does on hardcover.app
    def reader_sets(self, ub, **kw):
        read = kw.pop("read", None)
        self.books[ub].update(kw)
        if read:
            self.books[ub]["user_book_reads"][-1].update(read)


class Bookkeeping(FakeHC):
    """Hardcover as its guide "Updating a Book's Progress and Dates Read"
    (2026-10-23) has it, and as a real shelf showed: it keeps the
    read-throughs in step itself. Currently Reading starts one when none is
    going on, Read finishes the one going on, and progress at the edition's
    last page finishes it and marks the book Read."""

    TODAY = "2026-11-12"

    def _going(self, ub):
        return hardcover.read_in_progress(self.books[ub]["user_book_reads"])

    def _status(self, ub, was):
        now = self.books[ub]["status_id"]
        if now == 2 and was != 2 and not self._going(ub):
            self.books[ub]["user_book_reads"].append(
                {"id": self._id(), "started_at": self.TODAY, "finished_at": None, "progress_pages": None, "edition_id": None}
            )
        if now == 3 and was != 3 and self._going(ub):
            self._going(ub)["finished_at"] = self.TODAY

    def update_user_book(self, i, obj):
        was = self.books[i]["status_id"]
        super().update_user_book(i, obj)
        self._status(i, was)

    def update_read(self, i, r):
        super().update_read(i, r)
        for u in self.books.values():
            pages = next((e["pages"] for e in self.isbn.values() if e["id"] == u["edition_id"]), None)
            for x in u["user_book_reads"]:
                if x["id"] == i and pages and not x.get("finished_at") and (x.get("progress_pages") or 0) >= pages:
                    x["finished_at"] = self.TODAY
                    u["status_id"] = 3

    def reader_sets(self, ub, **kw):
        was = self.books[ub]["status_id"]
        super().reader_sets(ub, **kw)
        self._status(ub, was)


def test_pages_from_a_percentage():
    assert hardcover.pages_for(46, 300) == 138 and hardcover.pages_for(10, None) is None


def setup(tmp_path, books):
    tmp_path.mkdir(exist_ok=True)
    k = tmp_path / "k.sqlite"
    make_kobo(k, books, [])
    st = state.connect(str(tmp_path / "state.db"))
    state.import_books(st, "alice", "kobo1", kobo_db.read_books(kobo_db.open_db(str(k))))
    state.set_mode(st, "alice", [b[0] for b in books], "on")
    return st


def run(tmp_path, fake, live=True):
    return job.run(str(tmp_path / "state.db"), "alice", live=live, client=fake)


def row(st, cid):
    return st.execute("select * from book where content_id=?", (cid,)).fetchone()


def sent(st, cid):
    return json.loads(row(st, cid)["last_sent"])


READING = ("rd", "Blindness", "José Saramago", "978000", 46, 1, "2026-09-29T10:00:00Z", 900)
TRANSL = ("tr", "De strijd der koningen", "George R.R. Martin", "978111", 10, 1, "2026-09-29T10:00:00Z", 900)
OLD_ED = {"111": {"id": 7, "book_id": 70, "isbn_13": "111", "pages": 400, "title": "Old Finished"}}
BLIND = {"Blindness": [{"book_id": 80, "title": "Blindness", "authors": ["Jose Saramago"], "pages": 300, "slug": "b"}]}


def test_dry_run_matches_but_writes_nothing(tmp_path):
    st = setup(tmp_path, [OLD, READING, TRANSL])
    fake = FakeHC(
        isbn=OLD_ED,
        search={
            **BLIND,
            "De": [{"book_id": 90, "title": "A Clash of Kings", "authors": ["George R.R. Martin"], "pages": 700, "slug": "c"}],
        },
    )
    r = run(tmp_path, fake, live=False)
    assert r["status"] == "ok" and r["matched"] == 2 and r["uncertain"] == 1 and r["planned"] == 2
    assert fake.calls == []
    tr = row(st, "tr")
    assert tr["hc_how"] == "uncertain" and json.loads(tr["hc_candidates"])[0]["book_id"] == 90


def test_live_sends_one_read_entry_per_book_and_is_idempotent(tmp_path):
    st = setup(tmp_path, [OLD, READING])
    fake = FakeHC(isbn=OLD_ED, search=BLIND)
    r = run(tmp_path, fake)
    assert r["sent"] == 2 and r["errors"] == 0
    kinds = [c[0] for c in fake.calls]
    # The read entry Hardcover made itself is updated; none is added.
    assert kinds.count("insert_ub") == 2 and kinds.count("update_read") == 2 and "insert_read" not in kinds
    assert all(len(u["user_book_reads"]) == 1 for u in fake.books.values())
    old_read = [c for c in fake.calls if c[0] == "update_read" and c[2].get("finished_at")][0]
    assert old_read[2] == {"edition_id": 7, "finished_at": "2021-05-01"}
    rd_read = [c for c in fake.calls if c[0] == "update_read" and "progress_pages" in c[2]][0]
    assert rd_read[2]["progress_pages"] == 138  # 46% of 300 pages
    fake.calls.clear()
    r2 = run(tmp_path, fake)
    assert r2["sent"] == 0 and r2["adopted"] == 0 and fake.calls == []
    st.execute("update book set percent=60 where content_id='rd'")
    st.commit()
    run(tmp_path, fake)
    assert [c[0] for c in fake.calls] == ["update_read"] and fake.calls[0][2]["progress_pages"] == 180


def test_remove_deletes_and_switches_off(tmp_path):
    st = setup(tmp_path, [OLD])
    fake = FakeHC(isbn=OLD_ED)
    run(tmp_path, fake)
    ub = sent(st, "old")["user_book_id"]
    job.remove(st, "alice", "old", fake)
    assert fake.calls[-1] == ("delete_ub", ub)
    r = row(st, "old")
    assert r["mode"] == "off" and r["last_sent"] is None


def test_reread_of_a_shelf_book_adds_a_read_but_a_new_book_never_gets_two(tmp_path):
    st = setup(tmp_path, [OLD])
    fake = FakeHC(isbn=OLD_ED)
    run(tmp_path, fake)
    fake.calls.clear()
    state.set_state(st, "alice", "old", "rereading", "2026-10-01")
    run(tmp_path, fake)
    assert [c[0] for c in fake.calls] == ["update_ub", "insert_read"]  # a second read-through, on purpose
    st2 = setup(tmp_path / "b", [READING])
    fake2 = FakeHC(search=BLIND)
    state.set_state(st2, "alice", "rd", "rereading", "2026-10-01")
    run(tmp_path / "b", fake2)
    assert [c[0] for c in fake2.calls] == ["insert_ub", "update_read"]


def test_a_reread_whose_answer_was_lost_is_not_added_twice(tmp_path, monkeypatch):
    st = setup(tmp_path, [OLD])
    fake = FakeHC(isbn=OLD_ED)
    run(tmp_path, fake)
    ub = sent(st, "old")["user_book_id"]
    first = json.dumps({**sent(st, "old"), "at": "2026-09-30T10:00:00Z"})  # the first sync, a day before the re-read began
    st.execute("update book set last_sent=? where content_id='old'", (first,))
    st.commit()
    state.set_state(st, "alice", "old", "rereading", "2026-10-01")
    real = fake.insert_read

    def added_then_lost(ub_id, r):
        real(ub_id, r)  # on the shelf at Hardcover...
        raise hardcover.HardcoverError("Hardcover did not answer in time", "refused")  # ...but not heard back here

    monkeypatch.setattr(fake, "insert_read", added_then_lost)
    run(tmp_path, fake)
    monkeypatch.setattr(fake, "insert_read", real)
    fake.calls.clear()
    run(tmp_path, fake)
    reads = fake.books[ub]["user_book_reads"]
    # The re-read's one read-through, used; the status is said once more, as nothing recorded it.
    assert len(reads) == 2 and [c[0] for c in fake.calls] == ["update_ub", "update_read"] and fake.calls[1][1] == reads[-1]["id"]
    assert sent(st, "old")["reread"] and sent(st, "old")["read_id"] == reads[-1]["id"]
    fake.calls.clear()
    run(tmp_path, fake)
    assert fake.calls == []


# ---------- Hardcover -> lastread ----------
def test_read_on_hardcover_becomes_a_pinned_finished_state(tmp_path):
    st = setup(tmp_path, [READING])
    fake = FakeHC(search=BLIND)
    run(tmp_path, fake)
    ub = sent(st, "rd")["user_book_id"]
    fake.reader_sets(ub, status_id=3, read={"finished_at": "2026-10-02"})
    fake.calls.clear()
    r = run(tmp_path, fake)
    got = row(st, "rd")
    assert r["adopted"] == 1 and got["state"] == "finished" and got["state_date"] == "2026-10-02"
    assert fake.calls == [] and action(got) == ""  # nothing is sent back
    # Later Kobo progress does not undo it.
    st.execute("update book set percent=80 where content_id='rd'")
    st.commit()
    assert run(tmp_path, fake)["sent"] == 0 and fake.books[ub]["status_id"] == 3


def test_want_to_read_and_dnf_are_left_alone_until_follow_kobo(tmp_path):
    st = setup(tmp_path, [READING])
    fake = FakeHC(search=BLIND)
    run(tmp_path, fake)
    ub = sent(st, "rd")["user_book_id"]
    fake.reader_sets(ub, status_id=5)
    run(tmp_path, fake)
    assert row(st, "rd")["state"] == "dnf"
    st.execute("update book set percent=70 where content_id='rd'")
    st.commit()
    fake.calls.clear()
    assert run(tmp_path, fake)["sent"] == 0 and fake.calls == [] and fake.books[ub]["status_id"] == 5
    fake.reader_sets(ub, status_id=1)
    run(tmp_path, fake)
    assert row(st, "rd")["state"] == "want"
    # Back to Follow Kobo on the page: the Kobo's state goes out again.
    state.set_state(st, "alice", "rd", "kobo")
    run(tmp_path, fake)
    assert fake.books[ub]["status_id"] == 2 and fake.books[ub]["user_book_reads"][-1]["progress_pages"] == 210


def test_finished_book_set_to_reading_on_hardcover_is_a_reread(tmp_path):
    st = setup(tmp_path, [OLD])
    fake = FakeHC(isbn=OLD_ED)
    run(tmp_path, fake)
    ub = sent(st, "old")["user_book_id"]
    fake.reader_sets(ub, status_id=2, read={"started_at": "2026-10-03"})
    run(tmp_path, fake)
    got = row(st, "old")
    assert got["state"] == "rereading" and got["state_date"] == "2026-10-03" and fake.books[ub]["status_id"] == 2


def opened_again(st, cid, percent):
    """The Kobo after a finished book was opened again: reading, at a new percentage, its old finish date kept."""
    st.execute("update book set status=1, percent=? where content_id=?", (percent, cid))
    st.commit()


def test_a_reread_declared_here_is_the_read_through_hardcover_starts(tmp_path):
    """On a real shelf one declared re-read left two new read-throughs, their
    ids one apart: the one Hardcover starts when the book goes back to
    Currently Reading, and the one this tool added beside it."""
    st = setup(tmp_path, [OLD])
    fake = Bookkeeping(isbn=OLD_ED)
    run(tmp_path, fake)
    ub = sent(st, "old")["user_book_id"]
    first = dict(fake.books[ub]["user_book_reads"][0])
    assert first["finished_at"] == "2021-05-01"
    fake.calls.clear()
    state.set_state(st, "alice", "old", "rereading", "2026-10-01")
    run(tmp_path, fake)
    reads = fake.books[ub]["user_book_reads"]
    assert [c[0] for c in fake.calls] == ["update_ub", "update_read"] and len(reads) == 2  # one new read-through, Hardcover's
    assert reads[0] == first and sent(st, "old")["read_id"] == reads[1]["id"]
    # The Kobo still says 100%: that is the read-through before, not the last page of this one.
    assert (reads[1]["started_at"], reads[1]["finished_at"], reads[1]["progress_pages"]) == ("2026-10-01", None, 0)
    fake.calls.clear()
    run(tmp_path, fake)
    assert fake.calls == [] and fake.books[ub]["status_id"] == 2 and row(st, "old")["state"] == "rereading"  # not ended the moment it began
    # Opened again on the Kobo: its percentage is the re-read's, and goes to the re-read's read.
    opened_again(st, "old", 30)
    run(tmp_path, fake)
    assert reads[1]["progress_pages"] == 120 and reads[0] == first and len(reads) == 2
    assert desired(row(st, "old"))["progress"] == 30


def test_a_reread_begun_on_hardcover_goes_on_in_its_own_read(tmp_path):
    st = setup(tmp_path, [OLD])
    fake = Bookkeeping(isbn=OLD_ED)
    run(tmp_path, fake)
    ub = sent(st, "old")["user_book_id"]
    first = dict(fake.books[ub]["user_book_reads"][0])
    fake.reader_sets(ub, status_id=2)  # Currently Reading on Hardcover: it starts a read-through of its own
    reads = fake.books[ub]["user_book_reads"]
    assert len(reads) == 2
    run(tmp_path, fake)
    got = row(st, "old")
    assert (got["state"], got["state_date"]) == ("rereading", Bookkeeping.TODAY)  # the new read's start, not the old one's
    assert sent(st, "old")["read_id"] == reads[1]["id"] and reads[0] == first
    opened_again(st, "old", 30)
    run(tmp_path, fake)
    assert reads[1]["progress_pages"] == 120 and reads[0] == first and len(reads) == 2  # the finished read keeps what it had
    assert fake.books[ub]["status_id"] == 2 and row(st, "old")["state"] == "rereading"


def test_progress_is_never_written_into_a_read_that_has_its_finish_date(tmp_path):
    """Where Hardcover starts no read-through of its own, the tool adds one:
    the finished read is the reader's record of that time."""
    st = setup(tmp_path, [OLD])
    fake = FakeHC(isbn=OLD_ED)
    run(tmp_path, fake)
    ub = sent(st, "old")["user_book_id"]
    first = dict(fake.books[ub]["user_book_reads"][0])
    fake.reader_sets(ub, status_id=2)  # set back to Currently Reading, and no new read beside the finished one
    run(tmp_path, fake)
    opened_again(st, "old", 30)
    run(tmp_path, fake)
    reads = fake.books[ub]["user_book_reads"]
    assert len(reads) == 2 and reads[0] == first
    assert (reads[1]["finished_at"], reads[1]["progress_pages"]) == (None, 120) and sent(st, "old")["read_id"] == reads[1]["id"]


def test_a_reread_finished_on_the_kobo_after_it_was_declared_is_its_own_100_percent(tmp_path):
    st = setup(tmp_path, [OLD])
    state.set_state(st, "alice", "old", "rereading", "2026-10-01")
    assert desired(row(st, "old"))["progress"] == 0  # finished in 2021, declared now: not begun yet
    st.execute("update book set finished_at='2999-01-01T10:00:00Z' where content_id='old'")  # finished again, after the declaration
    assert desired(row(st, "old"))["progress"] == 100


def test_removed_on_hardcover_switches_sync_off_and_is_not_added_again(tmp_path):
    st = setup(tmp_path, [OLD])
    fake = FakeHC(isbn=OLD_ED)
    run(tmp_path, fake)
    fake.books.clear()
    fake.calls.clear()
    r = run(tmp_path, fake)
    got = row(st, "old")
    assert r["removed"] == 1 and got["mode"] == "off" and got["last_sent"] is None and got["hc_book_id"] == 70
    assert run(tmp_path, fake)["sent"] == 0 and fake.calls == [] and fake.books == {}


def test_state_set_on_the_page_wins_over_an_edit_on_hardcover(tmp_path):
    st = setup(tmp_path, [READING])
    fake = FakeHC(search=BLIND)
    run(tmp_path, fake)
    ub = sent(st, "rd")["user_book_id"]
    fake.reader_sets(ub, status_id=5)  # Did not finish, on Hardcover
    state.set_state(st, "alice", "rd", "finished", "2026-10-05")  # ... and Finished on the page, later
    st.execute("update book set state_changed='2099-01-01T00:00:00Z' where content_id='rd'")
    st.commit()
    run(tmp_path, fake)
    assert row(st, "rd")["state"] == "finished" and fake.books[ub]["status_id"] == 3
    assert fake.books[ub]["user_book_reads"][-1]["finished_at"] == "2026-10-05"


def test_changed_finish_date_on_the_page_is_sent(tmp_path):
    st = setup(tmp_path, [OLD])
    fake = FakeHC(isbn=OLD_ED)
    run(tmp_path, fake)
    state.set_state(st, "alice", "old", "finished", "2022-02-02")
    assert action(row(st, "old")) == "set the finish date to 2022-02-02"
    run(tmp_path, fake)
    assert list(fake.books.values())[0]["user_book_reads"][0]["finished_at"] == "2022-02-02"


# ---------- editions ----------
E_ISBN_EBOOK = {
    "id": 1,
    "isbn_13": "978000",
    "reading_format_id": 4,
    "edition_format": "ebook",
    "pages": 310,
    "users_count": 1,
    "language": {"code2": "nl"},
}
E_ISBN_PAPER = {
    "id": 2,
    "isbn_13": "978000",
    "reading_format_id": 1,
    "edition_format": "Paperback",
    "pages": 320,
    "users_count": 9,
    "language": {"code2": "nl"},
}
E_NL_EBOOK = {
    "id": 3,
    "isbn_13": "999",
    "reading_format_id": 4,
    "edition_format": "",
    "pages": 300,
    "users_count": 2,
    "language": {"code2": "nl"},
}
E_NL_EBOOK_POPULAR = {
    "id": 4,
    "isbn_13": "998",
    "reading_format_id": 4,
    "edition_format": "",
    "pages": 301,
    "users_count": 50,
    "language": {"code2": "nl"},
}
E_EN_EBOOK = {
    "id": 5,
    "isbn_13": "997",
    "reading_format_id": 4,
    "edition_format": "Kindle Edition",
    "pages": 290,
    "users_count": 900,
    "language": {"code2": "en"},
}


def test_edition_choice_order():
    def pick(eds):
        return (hardcover.choose_edition("978000", "nl", eds) or {}).get("id")

    assert pick([E_ISBN_PAPER, E_NL_EBOOK, E_ISBN_EBOOK, E_EN_EBOOK]) == 1  # Kobo's ISBN, marked Ebook
    assert pick([E_ISBN_PAPER, E_NL_EBOOK, E_NL_EBOOK_POPULAR, E_EN_EBOOK]) == 4  # ebook in the book's language, most readers
    assert pick([E_ISBN_PAPER, E_EN_EBOOK]) == 5  # any ebook beats a physical edition
    assert pick([E_EN_EBOOK]) == 5
    assert pick([E_ISBN_PAPER]) == 2  # Kobo's ISBN, whatever its label
    assert pick([]) is None
    assert hardcover.format_name(4, "ebook") == "Ebook" and hardcover.format_name(1, "Paperback") == "Physical (Paperback)"
    assert hardcover.format_name(4, "Kindle Edition") == "Ebook (Kindle Edition)" and hardcover.format_name(None, "") == ""


def test_ebook_edition_is_chosen_and_set_on_the_shelf(tmp_path):
    st = setup(tmp_path, [READING])
    st.execute("update book set language='nl' where content_id='rd'")
    st.commit()
    fake = FakeHC(search=BLIND, catalog={80: [E_ISBN_PAPER, E_NL_EBOOK]})
    r = run(tmp_path, fake)
    got = row(st, "rd")
    assert r["editions"] == 1 and got["hc_edition_id"] == 3 and got["hc_edition_by"] == "auto" and got["hc_format"] == "Ebook"
    ub = sent(st, "rd")["user_book_id"]
    assert fake.books[ub]["edition_id"] == 3 and fake.books[ub]["user_book_reads"][0]["progress_pages"] == 138
    fake.calls.clear()
    assert run(tmp_path, fake)["sent"] == 0 and fake.calls == []  # chosen once, not re-sent


def test_existing_shelf_edition_is_a_baseline_then_replaced_by_the_rule(tmp_path):
    """The first two-way sync: the edition on the shelf is lastread's or
    Hardcover's default, not the reader's choice, so the rule may replace it."""
    st = setup(tmp_path, [READING])
    st.execute("update book set language='nl' where content_id='rd'")
    st.commit()
    fake = FakeHC(search=BLIND, catalog={80: [E_ISBN_PAPER]})
    run(tmp_path, fake)  # sent with the paperback ISBN edition
    ub = sent(st, "rd")["user_book_id"]
    s = sent(st, "rd")
    s.pop("hc")
    s.pop("edition_id")
    s.pop("at")  # as written before two-way sync existed
    st.execute("update book set last_sent=?, hc_edition_by=null, hc_edition_checked=null where content_id='rd'", (json.dumps(s),))
    st.commit()
    fake.catalog[80].append(E_NL_EBOOK)
    run(tmp_path, fake)
    assert row(st, "rd")["hc_edition_by"] == "auto" and fake.books[ub]["edition_id"] == 3


def test_edition_chosen_on_hardcover_is_adopted_and_never_overwritten(tmp_path):
    st = setup(tmp_path, [READING])
    st.execute("update book set language='nl' where content_id='rd'")
    st.commit()
    fake = FakeHC(search=BLIND, catalog={80: [E_NL_EBOOK, E_NL_EBOOK_POPULAR, E_EN_EBOOK]})
    run(tmp_path, fake)
    ub = sent(st, "rd")["user_book_id"]
    assert fake.books[ub]["edition_id"] == 4
    fake.reader_sets(ub, edition_id=5)  # the reader prefers the English ebook
    r = run(tmp_path, fake)
    got = row(st, "rd")
    assert r["adopted"] == 1 and got["hc_edition_id"] == 5 and got["hc_edition_by"] == "hardcover" and got["hc_pages"] == 290
    st.execute("update book set percent=50, hc_edition_checked=null where content_id='rd'")
    st.commit()
    run(tmp_path, fake)
    assert fake.books[ub]["edition_id"] == 5 and fake.books[ub]["user_book_reads"][0]["progress_pages"] == 145  # 50% of 290


def test_a_run_that_breaks_on_something_unexpected_still_ends(tmp_path, monkeypatch):
    setup(tmp_path, [OLD]).close()

    def broken(*a, **k):
        raise KeyError("status_id")

    monkeypatch.setattr(job.syncback, "pull", broken)
    with pytest.raises(KeyError):
        run(tmp_path, FakeHC(), live=True)
    con = sqlite3.connect(tmp_path / "state.db")
    status, detail = con.execute("select status, detail from job order by started desc limit 1").fetchone()
    assert "alice" not in job.progress and "alice" not in job._running  # the page stops showing it, the next run may start
    assert status == "failed" and json.loads(detail)["fatal"] == "Stopped by something this tool did not expect (KeyError: 'status_id')"
    monkeypatch.undo()
    assert run(tmp_path, FakeHC(), live=True)["status"] == "ok"
