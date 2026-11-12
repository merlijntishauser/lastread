"""Which search hit is the book: only one that agrees in title and author,
never the first hit because it is the first. The made-up hits here have the
shapes that turned up on a real shelf."""

import json
from datetime import UTC, datetime, timedelta

from lastread.engine import hardcover, job
from lastread.engine.hardcover import EXACT, PART, PREFIX, agreement, choose
from tests.test_hardcover import READING, FakeHC, row, run, setup


def hit(book_id, title, authors, also=()):
    return {"book_id": book_id, "title": title, "authors": list(authors), "pages": 300, "slug": "s", "also": list(also)}


JORDAN = hit(1, "The Eye of the World", ["Robert Jordan"], also=["Het Oog van de Wereld", "L'Œil du monde", "Das Auge der Welt"])


def test_a_title_agrees_exactly_as_a_part_or_as_a_start():
    blind = hit(80, "Blindness", ["Jose Saramago"])
    assert agreement("Blindness", "José Saramago", blind) == EXACT  # accents and case do not count
    assert agreement("Tempel der winden", "Terry Goodkind", hit(2, "De tempel der winden", ["Terry Goodkind"])) == EXACT  # nor an article
    assert agreement("The", "A", hit(3, "The", ["A"])) == EXACT and hardcover.title_key("The") == "the"  # a title that is only an article
    # One part of the book's own title: the title before its subtitle, or after a series name.
    assert agreement("Helgoland", "Carlo Rovelli", hit(4, "Helgoland: Making Sense of the Quantum Revolution", ["Carlo Rovelli"])) == PART
    lennep = hit(5, "Lopen met Van Lennep: De zomer van 1823: Dagboek", ["Jacob van Lennep"])
    assert agreement("De zomer van 1823", "Jacob van Lennep, Geert Mak", lennep) == PART
    assert agreement("Dune", "Frank Herbert", hit(6, "Dune - The Graphic Novel", ["Frank Herbert"])) == PART
    # One title starts with the other: only believed of the first hit.
    kings = hit(7, "A Clash of Kings", ["George R.R. Martin"])
    assert agreement("A Clash of Kings: A Song of Ice and Fire 2", "George R.R. Martin", kings, first=True) == PREFIX
    assert agreement("A Clash of Kings: A Song of Ice and Fire 2", "George R.R. Martin", kings) == 0
    assert agreement("Item", "A", hit(8, "It", ["A"]), first=True) == 0  # whole words
    # Nothing in common.
    assert agreement("Het verre huis", "Jan Jansen", hit(9, "The Far House", ["Jan Jansen"])) == 0
    assert agreement("", "A", hit(10, "", ["A"])) == 0


def test_a_translation_is_known_by_the_titles_hardcover_lists_for_the_book():
    assert agreement("Het Oog van de Wereld", "Robert Jordan", JORDAN) == EXACT
    assert agreement("L'œil du monde", "Robert Jordan", JORDAN) == EXACT
    # A title Hardcover does not list for it: a translation is never guessed at.
    assert agreement("De strijd der koningen", "George R.R. Martin", hit(7, "A Clash of Kings", ["George R.R. Martin"])) == 0
    # One of the other titles has to be the title: a part or a start of one is not enough.
    assert agreement("Het Oog", "Robert Jordan", JORDAN, first=True) == 0
    assert agreement("Het Oog van de Wereld 2.0", "Robert Jordan", JORDAN, first=True) == 0
    wheel = hit(1, "The Eye of the World", ["Robert Jordan"], also=["Het Rad des Tijds: Het Oog van de Wereld"])
    assert agreement("Het Rad des Tijds", "Robert Jordan", wheel) == 0  # a series name inside another title is not this book
    series = hit(11, "The Final Empire", ["Brandon Sanderson"], also=["Mistborn", "Mistborn: The Final Empire"])
    assert agreement("Mistborn: Secret History", "Brandon Sanderson", series, first=True) == 0


def test_an_author_has_to_agree_and_may_be_any_name_the_kobo_lists():
    fire = hit(12, "The Waking Fire", ["Anthony Ryan"], also=["Het Vuur van de Draak"])
    assert agreement("Het Vuur van de Draak", "Niels van Eekelen, Jet Matla, Anthony Ryan", fire) == EXACT  # translators listed first
    assert agreement("Het Vuur van de Draak", "Niels van Eekelen, Jet Matla", fire) == 0
    assert agreement("Blindness", "", hit(80, "Blindness", ["Jose Saramago"])) == 0  # the Kobo names nobody
    assert agreement("Blindness", "José Saramago", hit(80, "Blindness", [])) == 0  # Hardcover names nobody
    summary = hit(13, "Summary of Carlo Rovelli's Helgoland", ["Everest Media,"])
    assert agreement("Helgoland", "Carlo Rovelli", summary, first=True) == 0  # the same words, someone else's book


def test_which_hit_is_taken():
    summary = hit(13, "Summary of Carlo Rovelli's Helgoland", ["Everest Media,"])
    helgoland = hit(4, "Helgoland: Making Sense of the Quantum Revolution", ["Carlo Rovelli"])
    assert choose("Helgoland", "Carlo Rovelli", [summary, helgoland]) is helgoland  # not the first hit: the one that agrees
    assert choose("Helgoland", "Carlo Rovelli", [summary]) is None and choose("Helgoland", "Carlo Rovelli", []) is None
    # The exact title goes before a title that only starts the same.
    dune, messiah = hit(20, "Dune", ["Frank Herbert"]), hit(21, "Dune Messiah", ["Frank Herbert"])
    assert choose("Dune Messiah", "Frank Herbert", [dune, messiah]) is messiah
    assert choose("Dune", "Frank Herbert", [messiah, dune]) is dune
    # The same book twice in Hardcover's catalogue: the one the search puts first.
    twice = [hit(30, "Blindness", ["Jose Saramago"]), hit(31, "Blindness", ["José Saramago"])]
    assert choose("Blindness", "José Saramago", twice) is twice[0]
    # Two books that agree equally, and neither is the first hit: the reader says which.
    assert choose("Blindness", "José Saramago", [summary, *twice]) is None
    # The same book twice among the hits is one book.
    assert choose("Blindness", "José Saramago", [summary, twice[0], dict(twice[0])]) is twice[0]


def test_a_translation_matches_by_itself_and_what_is_kept_for_the_reader_is_small(tmp_path):
    eye = ("eye", "Het Oog van de Wereld", "Robert Jordan, Lia Belt", "9789000000001", 30, 1, "2026-09-29T10:00:00Z", 900)
    kings = ("kings", "De strijd der koningen", "George R.R. Martin", "9789000000002", 10, 1, "2026-09-29T10:00:00Z", 900)
    st = setup(tmp_path, [eye, kings])
    fake = FakeHC(search={"Het": [JORDAN], "De": [hit(7, "A Clash of Kings", ["George R.R. Martin"], also=["Juego de tronos II"])]})
    r = run(tmp_path, fake, live=False)
    assert (r["matched"], r["uncertain"]) == (1, 1)
    assert (row(st, "eye")["hc_how"], row(st, "eye")["hc_book_id"], row(st, "eye")["hc_title"]) == ("search", 1, "The Eye of the World")
    waiting = row(st, "kings")
    assert waiting["hc_how"] == "uncertain" and json.loads(waiting["hc_candidates"]) == [
        {"book_id": 7, "title": "A Clash of Kings", "authors": ["George R.R. Martin"], "pages": 300, "slug": "s"}
    ]  # the other titles are for matching, not for keeping


class Counting(FakeHC):
    def search(self, text, n=5):
        self.calls.append(("search", text))
        return super().search(text, n)


def test_a_waiting_book_gets_one_more_look_when_the_rules_have_changed(tmp_path):
    eye = ("eye", "Het Oog van de Wereld", "Robert Jordan", "9789000000001", 30, 1, "2026-09-29T10:00:00Z", 900)
    st = setup(tmp_path, [eye, READING])
    # As an earlier version left them: looked up, not sure, waiting.
    st.execute("update book set hc_how = 'uncertain', hc_candidates = '[]', hc_looked = null")
    st.commit()
    fake = Counting(search={"Het": [JORDAN]})  # Hardcover knows the first, not the second
    r = run(tmp_path, fake, live=False)
    # The book the search does not find is looked for among its author's books as well (M12).
    assert sorted(c[1] for c in fake.calls) == ["Blindness José Saramago", "Het Oog van de Wereld Robert Jordan", "José Saramago"]
    assert (r["matched"], r["uncertain"]) == (1, 1) and row(st, "eye")["hc_book_id"] == 1
    assert row(st, "rd")["hc_how"] == "none" and row(st, "rd")["hc_looked"] == hardcover.MATCH_RULES
    # Once: the book that is still not found waits for the reader again.
    fake.calls.clear()
    assert run(tmp_path, fake, live=False)["uncertain"] == 0 and fake.calls == []
    # A match the reader chose in the meantime is not looked up again, whatever version looked last.
    st.execute("update book set hc_how = 'manual', hc_book_id = 99, hc_looked = null where content_id = 'rd'")
    st.commit()
    run(tmp_path, fake, live=False)
    assert fake.calls == [] and row(st, "rd")["hc_book_id"] == 99


def test_a_title_and_an_author_in_another_script_agree_as_any_other():
    master = hit(30, "Мастер и Маргарита", ["Михаил Булгаков"])
    assert agreement("МАСТЕР И МАРГАРИТА", "Михаил Булгаков", master) == EXACT
    assert agreement("Мастер и Маргарита", "Булгаков", master) == EXACT  # the last name is what has to agree
    assert agreement("Собачье сердце", "Михаил Булгаков", master) == 0  # the same author, another book
    assert agreement("Мастер и Маргарита", "Лев Толстой", master) == 0
    assert agreement("ΖΟΡΜΠΑΣ", "Νίκος Καζαντζάκης", hit(31, "Ζορμπάς", ["Νίκος Καζαντζάκης"])) == EXACT  # accents and the last sigma
    wood = hit(32, "ノルウェイの森", ["村上 春樹"])
    assert agreement("ノルウェイの森", "村上 春樹", wood) == EXACT and agreement("海辺のカフカ", "村上 春樹", wood) == 0
    assert choose("Мастер и Маргарита", "Михаил Булгаков", [hit(33, "Белая гвардия", ["Михаил Булгаков"]), master]) is master
    # A book whose title is in two scripts is not the book with the Latin half alone.
    assert agreement("1984 (Русское издание)", "George Orwell", hit(34, "1984", ["George Orwell"])) == 0
    # Latin is compared as before: accents do not count, and neither does which apostrophe was typed.
    assert hardcover.norm("  L'Œil du Monde: Brontë, Straße_1  ") == "l œil du monde bronte strasse 1"
    assert agreement("Ender\u2019s Game", "Orson Scott Card", hit(35, "Ender's Game", ["Orson Scott Card"])) == EXACT


def test_a_hit_that_agrees_in_nothing_is_not_put_to_the_reader(tmp_path):
    """Hardcover's search answers with something for nearly any words. Asked for
    a book it does not have, it gave three that share neither title nor author."""
    eyes = ("eyes", "Vierkante ogen", "Felienne Hermans", "9789044553277", 3, 1, "2026-11-05T19:48:44Z", 360)
    kings = ("kings", "De strijd der koningen", "George R.R. Martin", "9789000000002", 10, 1, "2026-09-29T10:00:00Z", 900)
    unrelated = [
        hit(1200299, "Het vierkant van de wraak", ["Pieter Aspe"]),
        hit(724899, "Health Communism: A Surplus Manifesto", ["Beatrice Adler-Bolton", "Artie Vierkant"]),
    ]
    clash = hit(7, "A Clash of Kings", ["George R.R. Martin"])  # the author agrees: a translation Hardcover does not list
    same_title = hit(8, "De strijd der koningen", ["Iemand Anders"])  # the title agrees: perhaps another author's name on it
    st = setup(tmp_path, [eyes, kings])
    r = run(tmp_path, FakeHC(search={"Vierkante": unrelated, "De": [unrelated[0], clash, same_title]}), live=False)
    assert (r["matched"], r["uncertain"]) == (0, 2)  # both still wait for the reader
    assert (row(st, "eyes")["hc_how"], json.loads(row(st, "eyes")["hc_candidates"])) == ("none", [])
    assert row(st, "kings")["hc_how"] == "uncertain"
    assert [c["book_id"] for c in json.loads(row(st, "kings")["hc_candidates"])] == [7, 8]
    related = hardcover.related
    assert related("Helgoland", "Carlo Rovelli", hit(4, "Helgoland: Making Sense of the Quantum Revolution", ["Someone Else"]))  # a part
    assert related("Dune", "Frank Herbert", hit(21, "Dune Messiah", ["Someone Else"]))  # a start, wherever it stands
    assert related("Het Oog van de Wereld", "", JORDAN) and not related("", "", JORDAN)  # a title Hardcover lists for it
    assert not related("Vierkante ogen", "Felienne Hermans", unrelated[1])


def test_a_book_the_search_does_not_find_is_looked_for_among_its_authors_books(tmp_path):
    """The words of a title can crowd the author out of the search. "Op zee"
    got five books with those words by other authors, while Hardcover had the
    novel in French among the author's own books."""
    sea = ("sea", "Op zee", "Toine Heijmans", "9789493256019", 100, 2, "2026-09-29T10:00:00Z", 900)
    fleet = ("fleet", "Spookvloot", "P.W. Singer, August Cole", "9789000000003", 100, 2, "2026-09-29T10:00:00Z", 900)
    dune = ("dune", "Dune", "Frank Herbert", "9789000000004", 10, 1, "2026-09-29T10:00:00Z", 900)
    kings = ("kings", "De strijd der koningen", "George R.R. Martin", "9789000000002", 10, 1, "2026-09-29T10:00:00Z", 900)
    nameless = ("nameless", "Zonder naam", "", "9789000000005", 10, 1, "2026-09-29T10:00:00Z", 900)
    by_others = [hit(3086761, "Een huwelijk op zee", ["Sophie Elmhirst"]), hit(3051685, "Brommer op zee", ["J.M.A. Biesheuvel"])]
    his = [
        hit(1550299, "Olanda", ["Iperborea", "George Blaustein"]),
        hit(1273808, "En mer", ["Toine Heijmans"]),
        hit(2402580, "Buitendijks", ["Toine Heijmans"]),
    ]
    theirs = [hit(451752, "Burn-In", ["P.W. Singer", "August Cole"]), hit(1090706, "Ghost Fleet", ["P.W. Singer"], also=["Spookvloot"])]
    st = setup(tmp_path, [sea, fleet, dune, kings, nameless])
    fake = Counting(
        search={
            "Op": by_others,
            "Toine": his,
            "P.W.": theirs,
            "Frank": [hit(21, "Dune Messiah", ["Frank Herbert"])],
            "De": [hit(7, "A Clash of Kings", ["George R.R. Martin"])],
        }
    )
    r = run(tmp_path, fake, live=False)
    assert (r["matched"], r["uncertain"]) == (1, 4)
    # Offered: what is by the author. The first hit is about the author's country, by others, and is not.
    assert row(st, "sea")["hc_how"] == "uncertain"
    assert [c["book_id"] for c in json.loads(row(st, "sea")["hc_candidates"])] == [1273808, 2402580]
    # Taken: the book that lists the Kobo's title, wherever it stands among the author's books.
    assert (row(st, "fleet")["hc_how"], row(st, "fleet")["hc_book_id"]) == ("search", 1090706)
    # Not taken: a title that only starts the same is believed of the first hit of a search for the title, not of an author's list.
    assert hardcover.choose("Dune", "Frank Herbert", fake.search_res["Frank"]) and row(st, "dune")["hc_book_id"] is None
    assert [c["book_id"] for c in json.loads(row(st, "dune")["hc_candidates"])] == [21]
    # A search that found something related is not followed by another, and a book without an author has no second one.
    asked = [c[1] for c in fake.calls]
    assert "George R.R. Martin" not in asked and asked.count("Zonder naam ") == 1 and "" not in asked
    assert sorted(asked) == sorted(
        ["Op zee Toine Heijmans", "Toine Heijmans", "Spookvloot P.W. Singer", "P.W. Singer", "Dune Frank Herbert", "Frank Herbert"]
        + ["De strijd der koningen George R.R. Martin", "Zonder naam "]
    )
    assert hardcover.MATCH_RULES == 4  # a book that waited under the rules before is looked up once more (M2)


def test_a_waiting_book_is_looked_up_again_after_a_week(tmp_path, monkeypatch):
    """Hardcover grows. "Vrees niet" waited from the day it was looked up; nine
    days after Hardcover listed that title for the book it still waited."""

    def ago(days):
        return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def looked(cid, days):
        st.execute("update book set hc_looked_at = ? where content_id = ?", (ago(days), cid))
        st.commit()

    eye = ("eye", "Het Oog van de Wereld", "Robert Jordan", "9789000000001", 30, 1, "2026-09-29T10:00:00Z", 900)
    st = setup(tmp_path, [eye, READING])
    fake = Counting()  # Hardcover knows neither yet
    assert run(tmp_path, fake, live=False)["uncertain"] == 2
    assert row(st, "eye")["hc_how"] == "none" and row(st, "eye")["hc_looked_at"] >= ago(1)
    # Within the week: not asked again.
    fake.calls.clear()
    looked("eye", 6)
    assert run(tmp_path, fake, live=False)["uncertain"] == 0 and fake.calls == []
    # After it: asked again, and the book Hardcover has by now is matched.
    looked("eye", 8)
    fake.search_res = {"Het": [JORDAN]}
    r = run(tmp_path, fake, live=False)
    assert (r["matched"], r["uncertain"]) == (1, 0) and row(st, "eye")["hc_book_id"] == 1
    assert [c[1] for c in fake.calls] == ["Het Oog van de Wereld Robert Jordan"]  # the other book's week is not over
    # A book that still waits after its second look is no news: not counted, and its week starts again.
    fake.calls.clear()
    looked("rd", 30)
    r = run(tmp_path, fake, live=False)
    assert (r["matched"], r["uncertain"]) == (0, 0) and len(fake.calls) == 2
    assert row(st, "rd")["hc_how"] == "none" and row(st, "rd")["hc_looked_at"] >= ago(1)
    # A long list of waiting books is not searched for in one run: the longest-waiting first.
    st.execute("update book set hc_how = 'none', hc_book_id = null where content_id = 'eye'")
    looked("eye", 9)
    looked("rd", 12)
    monkeypatch.setattr(job, "LOOK_AGAIN_AT_ONCE", 1)
    fake.calls.clear()
    fake.search_res = {}
    run(tmp_path, fake, live=False)
    assert [c[1] for c in fake.calls] == ["Blindness José Saramago", "José Saramago"]
    fake.calls.clear()
    run(tmp_path, fake, live=False)
    assert [c[1] for c in fake.calls] == ["Het Oog van de Wereld Robert Jordan", "Robert Jordan"]
    # A match the reader chose is never looked up again (M3).
    st.execute("update book set hc_how = 'manual', hc_book_id = 99 where content_id = 'rd'")
    looked("rd", 400)
    fake.calls.clear()
    run(tmp_path, fake, live=False)
    assert fake.calls == [] and row(st, "rd")["hc_book_id"] == 99
