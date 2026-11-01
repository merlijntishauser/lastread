# A folder of yours, put on the Kobo when it is plugged in

Design, proposed on 2026-11-01, **agreed and built** the same day: steps
1, 2 and 3, then the three open questions decided (below: in scope,
kepubify bundled, copy).
Step 2 as built: kepubify on the PATH, or in Homebrew's or Go's folder
(the plug-in trigger's PATH lacks them); `kepubify -o OUT IN` on the
computer, five minutes at most per book, a failure goes as EPUB. Rule P7.
Checked against kepubify 4.0.4 (2022-03-09, MIT, the latest release).
Step 3 as built: a card under Advanced on the page, in local mode only
(the folder is the computer's; a server's page has none), with a text
field, since a browser cannot hand over a folder's path; a section in
the Mac app's Advanced tab, in both modes, with a folder picker. Both
read `to-kobo --json` / `tokobo.summary` and choose through
`tokobo.choose`; the question before more than 20 books is a blue
(question) flash on the page and an alert in the app. Then kepubify
bundled: in the Mac app (`Contents/Resources/bin`, looked at first) and
as a dependency of the Homebrew formula. After 0.21.0 the Mac app moved the folder out of Settings into a pane of
its own, *EPUB Folder*: each book of the folder (`tokobo.books`, `list`
in `to-kobo --json`) with its Kobo state and, joined on the Kobo's
ContentID, its Hardcover status from Books; *New Folder* in the open
panel; and a Finder icon with the caret on the chosen folder. It follows rule M10
(`7b2c568`): a sideloaded book is matched on Hardcover by the ISBN in its
own EPUB. This is the other half: getting the book onto the Kobo.

## Why

Books bought outside the Kobo store, DRM-free (most Dutch stores
watermark instead of locking; Humble Bundle, Tor, Standard Ebooks), have
three ways onto a stock Kobo today:

- **Drag them over by hand**, every time, and remember which went where.
- **Calibre**: a whole library program for the job of copying a file.
- **Calibre-Web Automated**: a server, and the Kobo's `api_endpoint` in
  `Kobo eReader.conf` changed to point at it. That edit is the thing to
  avoid, and with the store proxy on it stalled the device here.

Lastread already runs at the moment that matters: the Kobo is plugged
in, mounted, and about to be ejected. Copying a few files then costs the
reader nothing: put a book in a folder, plug in the Kobo as you would
anyway, and it is there after the eject. With M10 it is then matched on
Hardcover by its ISBN, and because it is first opened after the first
import it syncs by itself (B3).

## What it changes about the tool

The README says "it does not manage books: it works with whatever is on
the Kobo". This design makes that "it puts the books from one folder of
yours on the Kobo, and otherwise does not manage books". PRODUCT.md's
core stays true: no KOReader, no Calibre in between, nothing installed on
the Kobo, no setting on the Kobo changed.

It is a second kind of write to the Kobo, after the collection. It is the
milder one: **files only, never KoboReader.sqlite**. The Kobo finds new
files by itself after the eject ("Importing content"); the tool does not
tell it.

## Decisions (proposed)

| Topic | Proposal | Turned down |
|---|---|---|
| Off or on | **Off until a folder is chosen.** `lastread to-kobo PATH`, `--off`; on the page under *Advanced*; in the Mac app a folder picker in Settings. | A default folder that exists from install: surprising writes. |
| Which files | **EPUB only** (`.epub`, `.kepub.epub`). PDFs and comics later, if asked. | Everything the Kobo opens: no matching for most, and no ISBN. |
| DRM | **Detected, refused, said.** `META-INF/rights.xml` (Adobe), `META-INF/license.lcpl` (Readium LCP), or `encryption.xml` encrypting more than fonts: "has DRM; open it with Adobe Digital Editions". Font obfuscation (IDPF, Adobe) is not DRM and passes. Nothing is ever decrypted. | Copying it anyway: it would not open on the Kobo. |
| Where on the Kobo | **`/Lastread/` on the Kobo's own storage**, the file's own name. The Kobo lists books from any folder that does not start with a dot. | The root, among the Kobo's own files; one folder per author. |
| Copy or move | **Copy, and remember** per Kobo by the file's SHA-256 in `to-kobo.json` in the state folder. The folder stays the reader's library; two Kobos in a household each get every book once. | Moving the file into a *Copied* folder: visible, but it breaks the second Kobo and it writes in the reader's folder. |
| Removed on the Kobo | **Stays removed.** A book the reader deletes on the Kobo is not put back; it is remembered as copied. Taking it out of the folder removes nothing from the Kobo (like B5). | Mirroring the folder: a delete on the computer would delete on the Kobo. |
| Same name, other book | **A suffix** (`Title (2).epub`), never an overwrite. The same file a second time: skipped. | Overwrite: loses the reading position if the Kobo keys on the path. |
| The write | **Atomic per file**: copied to `.lastread-<name>.partial` (hidden, the Kobo skips it), flushed, renamed. A Kobo pulled out halfway leaves a hidden partial, removed at the next sync, and nothing remembered (like K9). Free space checked first, with 50 MB to spare. | Copying in place: a half book in the library. |
| kepub | **As is in step 1. In step 2 converted with kepubify when it is installed** (MIT, a Go binary); the line says which. Bundling it in the Mac app is a step 3, to decide then. | Writing a kepub converter: Kobo's span markup is kepubify's whole job. |
| Modes | **Both.** The computer the Kobo is plugged into does the copy; in server mode the server is not involved and no book leaves the computer. | Uploading books to the server: the household's books on one more machine, for nothing. |
| When in the sync | **After the Kobo's database is copied and read, before the collection and the eject.** The new books appear in the database at the next plug-in, and are matched then. | Before the read: the read would not see them anyway. |

## What the reader sees

- The sync's rows get one more: `To Kobo  2 books put on the Kobo`, or
  `To Kobo  1 not put on the Kobo: Een Boek.epub has DRM`.
- The notification says it in the same words as the rest: *"2 books put
  on the Kobo. Eject before unplugging."*
- The page and the app, under *Advanced*: the folder, how many books in
  it are on this Kobo, and the ones that were refused, with why.
- The first sync after a folder is chosen copies everything in it. When
  that is more than 20 books, it asks first (the page, the app, or `--yes`
  on the command line), since a folder of 400 books is more likely a
  mistake than a wish.

## Rules for docs/sync-rules.md

A new section, *Books put on the Kobo*, each with its test:

- **P1** Only from the one folder you chose; nothing when none is chosen.
- **P2** Only EPUB; a book with DRM is not copied, and you are told why.
- **P3** A book is put on each Kobo once. Deleted on the Kobo, it stays
  deleted; taken out of the folder, it stays on the Kobo.
- **P4** Never an overwrite; a name that is taken gets a number.
- **P5** A copy happens completely or not at all, also when the Kobo is
  pulled out in the middle.
- **P6** Only files are written: the Kobo's database is never touched for
  this.

## Steps

1. The folder, the checks and the atomic copy, in the engine
   (`engine/tokobo.py`) and the runner; `lastread to-kobo`; the row, the
   notification; P1-P6 with tests. README and site sentences.
2. kepubify when it is on the PATH.
3. The page's and the app's *Advanced* entry and folder picker; the
   first-time question for a large folder.

## Decided (2026-11-01, the maintainer)

1. **Lastread's job**: yes, it is functionality the maintainer needs.
2. **kepub**: kepubify is bundled. The Mac app carries kepubify 4.0.4
   (the release binary for Apple silicon, pinned by SHA-256 in build.sh,
   signed with the app; its licence and those of Go and its libraries in
   `kepubify-NOTICES.txt`), and the tool looks there first. The Homebrew
   formula depends on Homebrew's `kepubify`. Installed another way, it is
   used when the reader has it.
3. **Copy or move**: copy, and remember. The folder stays the reader's.

## To find out before building

- **What a plain EPUB writes to KoboReader.sqlite.** Lastread lives on
  `___PercentRead`, `ReadStatus`, `TimeSpentReading`,
  `LastTimeFinishedReading`. Store kepubs fill them; whether a sideloaded
  plain EPUB (the older renderer) does too is not known here. The one real
  database looked at (2026-11-01, 688 books) has no sideloaded book in it. One book copied over, read for ten minutes and finished
  answers it, and decides whether kepub is step 2 or step 1.
- **Does the Kobo leave `ISBN` empty for a sideload**, as M10 assumes,
  or fill it from the OPF? The same test book answers it.
- **Whether the Kobo keys reading position on the path** (P4 assumes it
  does).
