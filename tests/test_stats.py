from lastread.engine import kobo_db, state
from lastread.server.stats import stats
from tests.test_core import make_kobo


def book(cid, secs, pct=10, status=1, finished=""):
    return (cid, f"Title {cid}", "Author", "999", pct, status, "2026-09-30T08:00:00Z", secs, finished)


def test_minutes_only_count_books_opened_on_this_device(tmp_path):
    st = state.connect(str(tmp_path / "state.db"))
    k1 = tmp_path / "a.sqlite"
    make_kobo(k1, [book("mine", 600), book("family", 600)], [("mine", "2026-09-05T09:00:00")])
    state.import_books(st, "alice", "kobo1", kobo_db.read_books(kobo_db.open_db(str(k1))))
    k2 = tmp_path / "b.sqlite"
    # 30 min more on my book, 45 min more on a family book read on another Kobo
    make_kobo(k2, [book("mine", 600 + 1800, 20), book("family", 600 + 2700, 50)], [("mine", "2026-09-05T09:00:00")])
    r = state.import_books(st, "alice", "kobo1", kobo_db.read_books(kobo_db.open_db(str(k2))))
    assert r["minutes_read"] == 30
    s = stats(st, "alice", today=state.local_day())
    assert s["minutes_today"] == 30 and s["minutes_week"] == 30
    assert s["current_title"] == "Title mine" and s["current_percent"] == 20


def test_a_new_books_minutes_before_its_first_sync_count_once(tmp_path):
    st = state.connect(str(tmp_path / "state.db"))

    def read(name, books, events):
        make_kobo(tmp_path / name, books, events)
        return state.import_books(st, "alice", "kobo1", kobo_db.read_books(kobo_db.open_db(str(tmp_path / name))))

    later = ("new", "2099-01-01T09:00:00")
    read("a.sqlite", [book("mine", 600)], [("mine", "2026-09-05T09:00:00")])  # the first import: history, no minutes
    # A book begun after it, twenty minutes in when the Kobo is plugged in next; and one someone else on the account began.
    r = read("b.sqlite", [book("mine", 600), book("new", 1200, 8), book("family", 3000, 30)], [("mine", "2026-09-05T09:00:00"), later])
    assert (r["new_auto"], r["minutes_read"]) == (1, 20)
    again = read("c.sqlite", [book("mine", 600), book("new", 1200, 8), book("family", 3000, 30)], [("mine", "2026-09-05T09:00:00"), later])
    assert again["minutes_read"] == 0
    more = read("d.sqlite", [book("mine", 600), book("new", 1800, 12), book("family", 3000, 30)], [("mine", "2026-09-05T09:00:00"), later])
    assert more["minutes_read"] == 10 and stats(st, "alice", today=state.local_day())["minutes_today"] == 30


def test_finished_this_year_counts_synced_books_only(tmp_path):
    st = state.connect(str(tmp_path / "state.db"))
    k = tmp_path / "a.sqlite"
    make_kobo(
        k,
        [
            book("a", 100, 100, 2, "2026-03-01T10:00:00Z"),
            book("b", 100, 100, 2, "2025-03-01T10:00:00Z"),
            book("c", 100, 100, 2, "2026-04-01T10:00:00Z"),
        ],
        [],
    )
    state.import_books(st, "alice", "kobo1", kobo_db.read_books(kobo_db.open_db(str(k))))
    state.set_mode(st, "alice", ["a", "b"], "on")
    assert stats(st, "alice", today="2026-09-30")["finished_this_year"] == 1  # c is off, b is 2025
