# The site

One static page at <https://lastread.app/> (GitHub Pages, with
the repository's own address redirecting there),
for a Kobo reader who heard of the tool and wants to know in a minute whether
it is for them. It lives in `site/` on `main` and is published by the `pages`
workflow (`.github/workflows/pages.yml`), which uploads the folder as it is;
nothing is built. The workflow's first run switches GitHub Pages on for the
repository, with Actions as its source (`configure-pages` with `enablement`).

`robots.txt` and `sitemap.xml` are for search engines, and the page names its
canonical address. With one page the sitemap has one line and no date to keep
up; a new page gets a line there.

## What is on it

The site has a world of its own, apart from the tool's page (`DESIGN.md`,
the site): the claim, the download, and one row of the tool's own Books page
at full size, then the made-up shelf told as three share cards, on a white
ground by day and a near-black one at night, with the same two faces as the
page from the same files.

- **The first viewport** is the headline and the lede with the download
  card beside them, and under both the sheet:
  one row of the Books page drawn in the page's own markup (`figure.sheet`),
  in the page's own design, Two Sides: the marks' legend as the seam's discs,
  the head row, and *Middlemarch* finished on the Kobo. On the Kobo's grey
  side: 100% set large in Literata, the cover in grey, the Kobo's dotted
  line, the facts, the two switches drawn as fields. Then the seam, an ink
  rule with the red disc of a change on it, and Hardcover's white side: the
  cover in colour, where *Currently reading, 88%* is struck through and
  *Read, finished 21 Sep 2026* is written in after the caret, the tool's own
  motion at the tool's own timing. The sheet carries the tool's colours and
  faces (Literata, Atkinson Hyperlegible Next), scoped to it (`--sh-*`), by
  day and at night. Its caption says the shelf
  is made up, which side is which, and that it starts as a dry run, its
  *Sync now* button saying what it would send (the button itself
  is not drawn: it looked like the page's action beside the download).
  Under it the three the sync runs between, one card each with one fact
  and no figures: the Kobo as it comes, on the photograph of a Kobo being
  read in a park; your computer, plum to coral; Hardcover, teal to lime.
  The download card, the sheet and the cards rise into place once on load,
  60ms apart; under reduced motion nothing moves. Below 900px the claim is
  one column; below 720px the row stacks (the book, the two switches side
  by side, the margin under them) and the download card follows the lede,
  so that the button is within the first screen on a 390x844 phone. Under
  both download buttons one line says it reads the Kobo and writes nothing
  to it unless asked, starts as a dry run, and is beta, Mac and Linux only.
- **The download** goes to the latest release on GitHub. With JavaScript the
  version, date, size and the disk image's own address are read from the
  GitHub API (`releases/latest`, no token, one request); without it the link
  is the releases page, which GitHub redirects to the newest. Homebrew and
  uv follow as the second way. The button comes back twice more: on the Mac
  app's card and on the close.
- **The proof** is real: the Books page rendered from the code with a made-up
  shelf (`browser_tests/shots.py`), light and dark at 2560 pixels wide (on a
  phone a crop of the switches and the Hardcover column, at size), a phone
  at 390, and a book's Details, each in a quiet card with its caption; the
  Mac app by pictures of its window (Overview, Books, Covers at full width)
  as the app draws them: a preview build's `KHS_SNAPSHOT` pictures, in both
  themes, reading a copy of the owner's folder, and shown in the theme the
  page is in (a `<picture>` on the system's theme, swapped by the theme
  switch). They are cropped beside the sidebar, which the snapshot cannot
  draw, and the server's name, the Hardcover handle and the title's
  *(preview)* are painted out: the button says *Open on the server*, the
  app's own short label, built from the glyphs of the line beside it. The row's cover is drawn (`browser_tests/covers/`, a
  publisher's series on bookcloth); the captions say the shelf is made up.
- **The photographs** are four from Unsplash, chosen by the owner, under the
  Unsplash License (`THIRD-PARTY-NOTICES.md` lists them; each file carries
  its origin in its JPEG comment, as does its smaller copy under
  `site/img/small/`, served to narrow screens through `srcset`): a Kobo in a
  park on the first of the three cards, a Kobo in a hammock behind all four
  steps (one photograph drawn at the width of the row, each card showing its
  slice; a quarter each on a phone), a reader looking over a teal book beside *What it does*
  and *What it leaves alone* (*It never guesses a match*), and a reader on a
  quay as the close. They are bundled with the site; the page still loads
  nothing from elsewhere.
- **The rest**: the four steps from the sign-in to the shelf as four cards
  with their figures (on a phone the cards are as tall as their words, the
  Mac app shows its Overview alone and the Books page its day capture and
  the phone's view, so the page is about twelve and a half screens long
  instead of fifteen), what it does and what it leaves alone as a teal and
  an ink card, the comparison with the other tools (the README's table,
  with its date) in a quiet card, the independent-project sentence and the
  photographers' names linked to their pictures, the links, and a theme
  switch kept in the browser, shown only when the script runs.
- **The link preview** (`og.png`, named by an absolute `og:image` with its
  size, `og:url` and a Twitter card) is composed, not cropped: the name,
  the headline and the whole row, without the nav, the lede or the download
  card.

The direction is written down in `.impeccable/surfaces/site-index-html.md`;
the tokens and rules in `DESIGN.md` under *The site*.

## Making the pictures again

The page's screenshots:

    KOBO_TEST_COVERS_DIR=browser_tests/covers SHOT_SCALE=2 DEV_OUT=out \
      uv run --group browser python browser_tests/shots.py

then `shot-books-light.png`, `shot-books-dark.png`, `shot-details-light.png`
and `shot-phone-books-light.png` as JPEG into `site/img/` (quality 84 to 86).

The site's own pictures, for a review and for the link preview:

    DEV_OUT=out uv run --group browser python browser_tests/site_shots.py

serves `site/` on a local port and captures the first viewport and the whole
page at a desk, a laptop and a phone, light and dark, scrolling every lazy
picture into view first (Chromium's full-page capture leaves them blank
otherwise), and `site-og.png`, the link preview at 1200x630 (the name, the
headline and the row, composed by a style the script injects), which is
`site/img/og.png`.

`tests/test_site.py` checks that every file the page names exists (`srcset`
candidates included), that the
words that must be there are, and that the page loads nothing from outside
itself but the one GitHub API request; no analytics, no font host, no script
host.
