"""Whose Kobo is plugged in (rules W1-W5): the computer keeps which Kobos
are the reader's, and one it has not met is not read until the reader has
said whose it is. Before this, a second Kobo plugged into the same login
was read as the reader's own."""

import json
import os
import sqlite3

import pytest

from lastread import cli, doctor
from lastread.computer import config, history, kobos, runner
from lastread.computer.platform import KOBO_DB
from lastread.engine import kobo_db, state
from lastread.server import upload
from tests import said
from tests.kobo_fixture import BOOKS
from tests.test_app_answers import answer
from tests.test_computer import FakeComputer, members, plug_in, register, server, uploads  # noqa: F401 (server is a fixture)
from tests.test_local import LOCAL

MINE, THEIRS = "N36XXXXXXXX", "N24YYYYYYYY"


def says(home, serial, model="393"):
    """The Kobo that is plugged in says it is this one."""
    mount = home / "Volumes" / "KOBOeReader"
    (mount / ".kobo" / "version").write_text(f"{serial},4.9.77,6.0.274403,4.9.77,4.9.77,00000000-0000-0000-0000-000000000{model}\n")
    return kobo_db.device(str(mount))


def read_on(db, n, percent):
    con = sqlite3.connect(db)
    con.execute("update content set ___PercentRead = ? where ContentID = ?", (percent, BOOKS[n]))
    con.commit()
    con.close()


def on_server(server, sql):  # noqa: F811
    con = sqlite3.connect(os.path.join(server.data, "state.db"))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


@pytest.fixture
def synced(home, server):  # noqa: F811
    """A computer in server mode that has synced the reader's own Kobo once."""
    db = plug_in(home)
    mine = says(home, MINE)
    mac = FakeComputer(home / "Volumes")
    register(server, mac)
    cfg = config.Config(server=server.url)
    config.save(cfg)
    assert runner.sync(mac, cfg).message == "9 books updated."
    return mac, cfg, db, mine


def test_the_first_kobo_a_computer_syncs_is_the_readers(synced, home):
    _, _, _, mine = synced
    (known,) = kobos.listed(str(home / "state"))
    assert (known["id"], known["whose"], known["model"]) == (mine.name, "mine", "Kobo Clara Colour") and known["since"]
    assert MINE not in (home / "state" / kobos.FILE).read_text()  # the serial number is kept nowhere


def test_another_kobo_is_not_read_until_the_reader_says_whose_it_is(synced, home, server):  # noqa: F811
    mac, cfg, db, _ = synced
    says(home, THEIRS, "390")
    read_on(db, 4, 99)
    before = open(db, "rb").read()
    for _ in range(2):  # asked at every plug-in, until it is answered
        out = runner.sync(mac, cfg, trigger="mount")
        assert (out.ok, out.title, out.about) == (False, "Is this Kobo yours?", "Kobo")
        assert out.message == (
            "This computer has not synced this Kobo (Kobo Libra Colour) before. Nothing was read from it, and nothing was sent. "
            "Say whose it is: `lastread kobo mine` or `lastread kobo not-mine`."
        )
    assert uploads(server) == 1 and open(db, "rb").read() == before and os.listdir(home / "scratch") == []
    assert len(history.syncs()) == 1  # a question is not a sync
    mac.in_app = True
    assert runner.sync(mac, cfg, trigger="app").message.endswith("Open Lastread to say whose it is.")


def test_in_local_mode_another_kobo_is_not_imported_either(home):
    db = plug_in(home)
    says(home, MINE)
    mac = FakeComputer(home / "Volumes")
    assert runner.sync(mac, LOCAL).ok
    con = state.connect(str(home / "state" / "state.db"))
    imports = lambda: con.execute("select count(*) from import").fetchone()[0]  # noqa: E731
    assert imports() == 1
    theirs = says(home, THEIRS)
    read_on(db, 4, 99)
    out = runner.sync(mac, LOCAL)
    assert (out.ok, out.title) == (False, "Is this Kobo yours?") and imports() == 1
    # Someone else's: left alone, and the rest of the sync goes on without a Kobo.
    kobos.say(str(home / "state"), theirs.name, False)
    assert runner.sync(mac, LOCAL).ok and imports() == 1
    assert [r[0] for r in con.execute("select device from device")] == [kobo_db.Device(serial=MINE).name]


def test_a_kobo_that_is_someone_elses_is_left_alone(synced, home, server):  # noqa: F811
    mac, cfg, db, _ = synced
    server.page.post("/settings/collection", data={"collection": "On Hardcover"})
    server.page.post("/mode", data={"ids": ",".join(BOOKS[:3]), "mode": "on"})
    theirs = says(home, THEIRS)
    read_on(db, 4, 99)
    kobos.say(str(home / "state"), theirs.name, False, theirs.model)
    before = open(db, "rb").read()
    plugged = runner.sync(mac, config.Config(server=server.url, eject_after_sync=True), trigger="mount")
    assert (plugged.ok, plugged.message) == (True, "")  # nothing to tell: it is not this reader's business
    assert mac.ejected == []  # and it stays mounted, for whoever wants to put a file on it
    clicked = runner.sync(mac, cfg, trigger="app")
    assert (clicked.ok, clicked.message) == (True, "The Kobo that is plugged in is not yours: it is left alone.")
    assert uploads(server) == 1 and open(db, "rb").read() == before and members(db, "On Hardcover") == set()
    # The reader's own Kobo again: read as ever.
    says(home, MINE)
    assert runner.sync(mac, cfg, trigger="mount").message.startswith("1 book updated. Collection 'On Hardcover': 3 books")
    assert uploads(server) == 2


def test_a_second_kobo_of_the_reader_is_a_device_of_its_own_on_the_server(synced, home, server, capsys):  # noqa: F811
    mac, cfg, db, mine = synced
    was = on_server(server, f"select percent from book where device = 'kobo-sam' and content_id = '{BOOKS[4]}'")
    second = says(home, THEIRS, "390")
    read_on(db, 4, 99)
    assert runner.sync(mac, cfg).title == "Is this Kobo yours?"
    cli.main(["kobo", "mine"], computer=mac)
    assert "Kobo Libra Colour (plugged in): yours, it syncs" in said(capsys)
    assert runner.sync(mac, cfg).message == "9 books updated."
    beside = f"kobo-sam-{second.name.removeprefix('kobo-')}"
    assert on_server(server, "select device, kobo from device order by device") == [("kobo-sam", mine.name), (beside, second.name)]
    # The first Kobo's books are as that Kobo left them: the second one did not overwrite them.
    assert on_server(server, f"select percent from book where device = 'kobo-sam' and content_id = '{BOOKS[4]}'") == was
    assert on_server(server, f"select percent from book where device = '{beside}' and content_id = '{BOOKS[4]}'") == [(99,)]
    # And the first one, plugged in again, is still the device it was.
    says(home, MINE)
    read_on(db, 5, 50)
    runner.sync(mac, cfg)
    assert on_server(server, f"select percent from book where device = 'kobo-sam' and content_id = '{BOOKS[5]}'") == [(50,)]
    assert len(on_server(server, "select 1 from device")) == 2


def test_an_upload_that_names_no_kobo_is_the_tokens_device(tmp_path):
    con = state.connect(str(tmp_path / "state.db"))
    state.import_books(con, "sam", "kobo-sam", [])
    one, two = "kobo-1a2b3c4d", "kobo-5e6f7a8b"
    assert upload.device_of(con, "sam", "kobo-sam", one) == "kobo-sam"  # the first Kobo this computer sends
    upload.note_kobo(con, "sam", "kobo-sam", one)
    assert upload.device_of(con, "sam", "kobo-sam", one) == "kobo-sam"
    assert upload.device_of(con, "sam", "kobo-sam", two) == "kobo-sam-5e6f7a8b"
    upload.note_kobo(con, "sam", "kobo-sam", two)  # the first one stays what the device is
    assert con.execute("select kobo from device").fetchone()[0] == one
    # A computer on an older version says nothing, and something that is not a Kobo's name is not believed.
    for nothing in ("", "kobo", "../../etc/passwd", "kobo-1A2B3C4D", "kobo-1a2b3c4d5"):
        assert upload.device_of(con, "sam", "kobo-sam", nothing) == "kobo-sam"
    assert upload.device_of(con, "sam", "kobo-new", two) == "kobo-new"  # a device the server has not seen yet


def test_a_kobo_that_does_not_say_which_it_is_syncs_as_before(synced, home, server):  # noqa: F811
    mac, cfg, db, mine = synced
    os.unlink(home / "Volumes" / "KOBOeReader" / ".kobo" / "version")
    read_on(db, 4, 99)
    assert runner.sync(mac, cfg, trigger="mount").message == "1 book updated."
    assert [k["id"] for k in kobos.listed(str(home / "state"))] == [mine.name]  # and it is not kept as a Kobo
    assert on_server(server, "select device from device") == [("kobo-sam",)]


def test_the_kobos_from_before_are_known_without_asking(tmp_path):
    mine, later = kobo_db.Device(serial=MINE, model="Kobo Clara Colour"), kobo_db.Device(serial=THEIRS)
    # Local mode kept every Kobo by its name in the state database.
    local = tmp_path / "local"
    local.mkdir()
    con = state.connect(str(local / "state.db"))
    state.import_books(con, "me", mine.name, [])
    con.close()
    assert (kobos.whose(str(local), mine), kobos.whose(str(local), later)) == ("mine", "")
    # Server mode kept none, but the folder's books are remembered per Kobo: the one that got them first.
    with_server = tmp_path / "server-mode"
    with_server.mkdir()
    per_kobo = {
        later.name: {"h1": {"at": "2026-11-20T21:32:11Z"}},
        mine.name: {"h1": {"at": "2026-11-02T20:05:35Z"}, "h2": {"at": "2026-11-21T08:00:00Z"}},
    }
    (with_server / "to-kobo.json").write_text(json.dumps({"files": {}, "kobos": per_kobo}))
    assert (kobos.whose(str(with_server), mine), kobos.whose(str(with_server), later)) == ("mine", "")
    assert not (with_server / kobos.FILE).exists()  # looking changes nothing
    assert kobos.meet(str(with_server), later) == "" and kobos.meet(str(with_server), mine) == "mine"
    (known,) = kobos.listed(str(with_server))
    assert (known["id"], known["model"]) == (mine.name, "Kobo Clara Colour") and known["since"]
    # Nothing to go by at all: the first Kobo is the reader's, and the next one is asked about.
    fresh = tmp_path / "fresh"
    assert kobos.meet(str(fresh), later) == "mine" and kobos.whose(str(fresh), mine) == ""
    # A record that cannot be read is no record of anyone's Kobo: everything is asked about again.
    (fresh / kobos.FILE).write_text("{not json")
    assert kobos.whose(str(fresh), later) == ""


def test_the_answer_for_a_kobo_is_given_and_changed_with_the_kobo_command(synced, home, capsys):
    mac, _, _, mine = synced
    theirs = says(home, THEIRS, "390")
    state_dir = str(home / "state")
    cli.main(["kobo"], computer=mac)
    listed = said(capsys)
    assert "Kobo Clara Colour: yours, it syncs" in listed and "Kobo Libra Colour (plugged in): not synced here before" in listed
    assert answer(capsys, "status", "--json", computer=mac)["plugged"] == {"id": theirs.name, "model": "Kobo Libra Colour", "whose": ""}
    cli.main(["status"], computer=mac)
    assert "not synced here before, so nothing is read from it" in said(capsys)

    cli.main(["kobo", "not-mine"], computer=mac)
    assert "Kobo Libra Colour (plugged in): not yours, left alone" in said(capsys) and kobos.whose(state_dir, theirs) == "other"
    assert answer(capsys, "status", "--json", computer=mac)["plugged"]["whose"] == "other"
    cli.main(["status"], computer=mac)
    assert "not yours, left alone" in said(capsys)
    # A change of mind, by name: the Kobo need not be plugged in for it.
    says(home, MINE)
    found = answer(capsys, "kobo", "mine", theirs.name, "--json", computer=mac)
    assert sorted((k["id"], k["whose"], k["model"]) for k in found["kobos"]) == sorted(
        [(mine.name, "mine", "Kobo Clara Colour"), (theirs.name, "mine", "Kobo Libra Colour")]
    )
    assert found["plugged"] == {"id": mine.name, "model": "Kobo Clara Colour", "whose": "mine"}
    cli.main(["kobo", "forget", theirs.name], computer=mac)
    capsys.readouterr()
    assert kobos.whose(state_dir, theirs) == "" and kobos.whose(state_dir, mine) == "mine"
    for wrong, why in (
        (["kobo", "mine", "the-blue-one"], "is not the name of a Kobo"),
        (["kobo", "forget", theirs.name], "is not a Kobo this computer knows"),
    ):
        with pytest.raises(SystemExit) as ended:
            cli.main(wrong, computer=mac)
        assert why in str(ended.value)


def test_the_doctor_reads_nothing_from_a_kobo_that_is_not_the_readers(synced, home):
    mac, cfg, _, _ = synced
    theirs = says(home, THEIRS)
    checks = doctor.kobo_checks(mac, cfg, None, str(home / "state" / "collection"), KOBO_DB)
    assert [c.what for c in checks][:1] == ["Kobo"] and "Database" not in [c.what for c in checks]
    assert checks[0].state == "warn" and "has not synced it before, so nothing is read from it" in checks[0].found
    assert "lastread kobo mine" in checks[0].todo
    kobos.say(str(home / "state"), theirs.name, False)
    mac.in_app = True
    checks = doctor.kobo_checks(mac, cfg, None, str(home / "state" / "collection"), KOBO_DB)
    assert checks[0].state == "note" and "It is not yours, so it is left alone" in checks[0].found
    assert checks[0].todo == "Choose It is mine if it is yours after all." and "Database" not in [c.what for c in checks]
    assert os.listdir(home / "scratch") == []
