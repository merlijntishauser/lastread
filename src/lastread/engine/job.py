"""One sync run for a reader:
  1. take over what the reader changed on Hardcover (syncback, live only);
  2. match unmatched books;
  3. choose an edition where the reader has not chosen one (ebook first);
  4. send what changed.
Dry run unless the reader went live under Settings: in a dry run
only the plan is recorded and nothing is written to Hardcover.

The caller hands over the reader's Hardcover token: where it is kept
(the server's database, or the computer's own secret store) is not the
engine's business."""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime, timedelta

from . import hardcover, state, syncback
from .plan import action, desired, quiet

log = logging.getLogger(__name__)  # titles only at debug level (see logs.py)
_running: set[str] = set()
_lock = threading.Lock()
# Where a reader's sync is, for the page to show while it runs: {"phase": "start" | "shelf" | "match" | "send",
# "done": books sent so far, "total": books to send}. Set before the work begins, gone when it ends.
progress: dict[str, dict] = {}
# Hardcover grows: a book it did not have, or a title it did not list for one, may be there a week later.
LOOK_AGAIN_DAYS = 7
LOOK_AGAIN_AT_ONCE = 25  # so a long list of waiting books is not searched for in one run


def begin(reader: str) -> None:
    """Say a sync for this reader is on its way, before its thread is started: the page drawn
    right after a click then already shows it running."""
    progress[reader] = {"phase": "start", "done": 0, "total": 0}


def syncing_rows(con, reader):
    return [r for r in con.execute("select * from book where reader=?", (reader,)) if state.syncs(r)]


def run(db_path: str, reader: str, live: bool, client: hardcover.Client | None = None, token: str = "") -> dict:
    with _lock:
        if reader in _running:
            return {"status": "already running"}
        _running.add(reader)
    con, started, status = None, "", "failed"
    counts = {"matched": 0, "uncertain": 0, "sent": 0, "planned": 0, "errors": 0, "adopted": 0, "removed": 0, "editions": 0}
    # The books this run was about, for a reader watching it (the command, by hand). They are handed back
    # and nowhere else: not kept with the run, not logged.
    books = []

    def about(r, what, went, error=""):
        books.append(
            {
                "id": r["content_id"],
                "image_id": r["image_id"],
                "title": r["hc_title"] or r["title"],
                "percent": r["percent"],
                "finished": desired(r)["status"] == "read",
                "what": what,
                "went": went,
                "error": error,
            }
        )

    # Whatever goes wrong, the run ends: the reader is free for the next one, the page stops showing
    # it as running, and the job row says it failed and why.
    try:
        progress[reader] = {"phase": "shelf" if live else "match", "done": 0, "total": 0}
        con = state.connect(db_path)
        started = state.now()
        con.execute("insert into job (reader, started, live, status) values (?,?,?,?)", (reader, started, int(live), "running"))
        con.commit()
        try:
            client = client or hardcover.Client(token)
            shelf = []
            if live:
                check_account(con, reader, client.whoami())
                shelf = client.shelf()
                counts.update(syncback.pull(con, reader, shelf))
            progress[reader] = {"phase": "match", "done": 0, "total": 0}
            # Not looked up yet, or waiting for the reader since rules that have changed since: those get one more look.
            # So do the ones that have waited a while, since Hardcover grows: a few per run, the longest-waiting first.
            waiting = [r for r in syncing_rows(con, reader) if not r["hc_book_id"]]
            todo = [r for r in waiting if r["hc_how"] not in ("uncertain", "none") or (r["hc_looked"] or 1) < hardcover.MATCH_RULES]
            first_look = {r["content_id"] for r in todo}
            long_ago = (datetime.now(UTC) - timedelta(days=LOOK_AGAIN_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
            again = [r for r in waiting if r["content_id"] not in first_look and (r["hc_looked_at"] or "") <= long_ago]
            todo += sorted(again, key=lambda r: r["hc_looked_at"] or "")[:LOOK_AGAIN_AT_ONCE]
            for cid, m in hardcover.match_books(client, todo).items():
                con.execute(
                    """update book set hc_how=?, hc_book_id=?, hc_edition_id=?, hc_pages=?, hc_title=?, hc_candidates=?, hc_looked=?,
                               hc_looked_at=?
                               where reader=? and content_id=?""",
                    (
                        m["how"],
                        m["book_id"],
                        m["edition_id"],
                        m["pages"],
                        m["title"],
                        json.dumps(m["candidates"]),
                        hardcover.MATCH_RULES,
                        started,
                        reader,
                        cid,
                    ),
                )
                if m["book_id"] or cid in first_look:  # a book that waits as it did is no news to the reader
                    counts["matched" if m["book_id"] else "uncertain"] += 1
                if m["book_id"]:
                    log.debug("matched %r: Hardcover book %s (%s)", m["title"], m["book_id"], m["how"])
                else:
                    log.debug("no sure match for Kobo book %s: left for the reader to choose", cid)
            con.commit()
            counts["editions"] = choose_editions(con, reader, client)
            existing = {u["book_id"]: u for u in shelf}
            rows = syncing_rows(con, reader)
            silent = quiet(rows)
            rows = [r for r in rows if r["hc_book_id"] and (r["device"], r["content_id"]) not in silent and action(r)]
            progress[reader] = {"phase": "send", "done": 0, "total": len(rows)}
            for i, planned in enumerate(rows):
                progress[reader] = {"phase": "send", "done": i, "total": len(rows)}
                # The book as it is now, not as it was when the run began: a first sync of hundreds of
                # books takes minutes, and what the reader switches off or sets on the page meanwhile holds.
                r = con.execute(
                    "select * from book where reader=? and device=? and content_id=?", (reader, planned["device"], planned["content_id"])
                ).fetchone()
                what = action(r) if r is not None and state.syncs(r) and r["hc_book_id"] else ""
                if not what:
                    continue
                if not live:
                    counts["planned"] += 1
                    log.debug("would send %r: %s", r["title"], what)
                    about(r, what, "planned")
                    continue
                try:
                    sent = json.loads(r["last_sent"]) if r["last_sent"] else {}
                    new = hardcover.apply(client, r, desired(r), sent, existing.get(r["hc_book_id"]))
                    new["at"] = state.now()
                    state.record_sent(con, reader, r, json.dumps(new))
                    con.execute("update book set hc_error=null where reader=? and content_id=?", (reader, r["content_id"]))
                    counts["sent"] += 1
                    log.debug("sent %r: %s", r["title"], what)
                    about(r, what, "sent")
                except hardcover.HardcoverError as e:
                    if e.stops_the_run:  # no token, no connection, too many requests: the next book would hear the same
                        con.commit()
                        raise
                    con.execute("update book set hc_error=? where reader=? and content_id=?", (str(e)[:300], reader, r["content_id"]))
                    counts["errors"] += 1
                    log.warning("a book could not be sent (%s); its row on the page says why", e.kind)
                    log.debug("not sent %r: %s", r["title"], e)
                    about(r, what, "failed", str(e))
                con.commit()
            status = "ok" if not counts["errors"] else "errors"
            if live and state.has_records(con, reader):
                state.bind_account(con, reader, client.whoami())  # the shelf the records are on, from now on
        except hardcover.HardcoverError as e:
            status, counts["fatal"] = "failed", str(e)[:300]
        except Exception as e:
            counts["fatal"] = f"Stopped by something this tool did not expect ({type(e).__name__}: {e})"[:300]
            log.exception("hardcover sync for %s stopped", reader)
            raise
    finally:
        try:
            if started:
                con.execute(
                    "update job set finished=?, status=?, detail=? where reader=? and started=?",
                    (state.now(), status, json.dumps(counts), reader, started),
                )
                con.commit()
        finally:
            with _lock:
                _running.discard(reader)
            progress.pop(reader, None)  # after the job is recorded: the page then finds the result where it looks
    log.log(
        logging.INFO if status == "ok" else logging.ERROR,
        "hardcover (%s) for %s: %s",
        "live" if live else "dry run",
        reader,
        {"status": status, **counts},
    )
    return {"status": status, **counts, "books": books}


def check_account(con, reader: str, who: dict) -> None:
    """A token for another Hardcover account than the one the books were put on: nothing is read
    from that shelf, sent to it or switched off for it. The count of missing books (syncback.MANY)
    stays for a token that may not read the shelf, and for state from before the binding."""
    bound = state.hardcover_account(con, reader)
    if bound and bound[0] != who["id"]:
        new, old = who.get("username") or "another account", bound[1] or "another account"
        raise hardcover.HardcoverError(
            f"The Hardcover connection is for @{new}, and your books were put on the shelf of @{old}. "
            f"Nothing was sent or switched off. Connect @{old} again, or start over on @{new} under Settings",
            "account",
        )


def could_not_start(db_path: str, reader: str, live: bool, why: str) -> None:
    """Record a run that never began, so that the page can say why: the
    reader's connection to Hardcover has ended, for one."""
    con = state.connect(db_path)
    at = state.now()
    con.execute(
        "insert into job (reader, started, finished, live, status, detail) values (?,?,?,?,?,?)",
        (reader, at, at, int(live), "failed", json.dumps({"fatal": why[:300]})),
    )
    con.commit()
    con.close()
    log.error("hardcover (%s) for %s did not start: %s", "live" if live else "dry run", reader, why)


INTERRUPTED = "Interrupted by a restart of the server"


def interrupted(db_path: str) -> int:
    """At the start of the process that runs syncs: a run still on "running"
    was cut off by the restart, and says so instead of running for ever."""
    con = state.connect(db_path)
    try:
        n = con.execute(
            "update job set finished=?, status='failed', detail=? where status='running'",
            (state.now(), json.dumps({"fatal": INTERRUPTED})),
        ).rowcount
        con.commit()
    finally:
        con.close()
    if n:
        log.warning("%d sync run(s) cut off by a restart recorded as failed", n)
    return n


EDITION_RECHECK_DAYS = 30


def choose_editions(con, reader: str, client) -> int:
    """Pick an edition (hardcover.choose_edition) for matched books whose
    edition the reader has not chosen on Hardcover. Checked once, and again
    after EDITION_RECHECK_DAYS: the catalogue gains editions over time."""
    cutoff = (datetime.now(UTC) - timedelta(days=EDITION_RECHECK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [
        r
        for r in syncing_rows(con, reader)
        if r["hc_book_id"] and r["hc_edition_by"] != "hardcover" and (not r["hc_edition_checked"] or r["hc_edition_checked"] < cutoff)
    ]
    if not rows:
        return 0
    editions = client.editions_for_books(
        sorted({r["hc_book_id"] for r in rows}), sorted({r["isbn"] for r in rows if r["isbn"]}), audio=any(r["audio"] for r in rows)
    )
    changed = 0
    for r in rows:
        e = hardcover.choose_edition(r["isbn"] or "", r["language"] or "", editions.get(r["hc_book_id"], []), audio=bool(r["audio"]))
        if e and e["id"] != r["hc_edition_id"]:
            con.execute(
                """update book set hc_edition_id=?, hc_edition_by='auto', hc_pages=?, hc_format_id=?, hc_format=?
                           where reader=? and content_id=?""",
                (
                    e["id"],
                    e.get("pages") or r["hc_pages"],
                    e.get("reading_format_id"),
                    hardcover.format_name(e.get("reading_format_id"), e.get("edition_format")),
                    reader,
                    r["content_id"],
                ),
            )
            changed += 1
        elif e:
            con.execute(
                "update book set hc_edition_by='auto', hc_format_id=?, hc_format=? where reader=? and content_id=?",
                (
                    e.get("reading_format_id"),
                    hardcover.format_name(e.get("reading_format_id"), e.get("edition_format")),
                    reader,
                    r["content_id"],
                ),
            )
        con.execute("update book set hc_edition_checked=? where reader=? and content_id=?", (state.now(), reader, r["content_id"]))
    con.commit()
    return changed


def start(db_path: str, reader: str, live: bool, token: str) -> None:
    begin(reader)
    threading.Thread(target=run, args=(db_path, reader, live), kwargs={"token": token}, daemon=True).start()


def pick(con, reader: str, content_id: str, book_id: int, title: str, pages) -> None:
    # What was sent belongs to the book it was sent for: another book starts
    # without it (it takes over the record of a copy that is already there).
    known = con.execute(
        "select last_sent from book where reader=? and hc_book_id=? and content_id!=? and last_sent is not null",
        (reader, book_id, content_id),
    ).fetchone()
    con.execute(
        "update book set last_sent=? where reader=? and content_id=? and hc_book_id is not ?",
        (known["last_sent"] if known else None, reader, content_id, book_id),
    )
    con.execute(
        """update book set hc_how='manual', hc_book_id=?, hc_edition_id=null, hc_pages=?, hc_title=?, hc_error=null,
                   hc_edition_by=null, hc_edition_checked=null, hc_format_id=null, hc_format=null
                   where reader=? and content_id=?""",
        (book_id, pages, title, reader, content_id),
    )
    con.commit()


def remove(con, reader: str, content_id: str, client: hardcover.Client) -> None:
    r = con.execute("select * from book where reader=? and content_id=?", (reader, content_id)).fetchone()
    sent = json.loads(r["last_sent"]) if r and r["last_sent"] else {}
    if sent.get("user_book_id"):
        client.delete_user_book(sent["user_book_id"])
    con.execute("update book set last_sent=null, mode='off' where reader=? and content_id=?", (reader, content_id))
    con.commit()
