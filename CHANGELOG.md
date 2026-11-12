# Changelog

What changed, for people who use the tool. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Before 1.0, a
minor version may change behaviour; the notes will say so.

## Unreleased

### Fixed

- **A book someone else on your Kobo account read first now syncs by itself
  once you open it on your own Kobo.** The Kobo lists such a book with their
  progress before you ever open it, and it was filed as history for good, so
  you had to switch it on by hand. It is new from the day you open it. A
  book that was finished already, one you set something for, and one you
  opened on another Kobo of yours stay as they were.
- **A second Kobo no longer locks the first out of its collection.** The
  collection's id was remembered per name, so when another Kobo of yours got
  the collection too, the first one was refused at every plug-in ("was not
  made by lastread") and never updated again. Each Kobo's collection is now
  remembered, and a new or cleared name reaches each Kobo when it is plugged
  in.
- **One file your computer cannot read no longer stops the EPUB folder.** A
  link to a file that is gone made the folder's list fail, in the app and in
  `lastread to-kobo`, and no book went on the Kobo. Such a file is now left
  out and listed with the reason; the other books go.
- **A book taken out of the EPUB folder while a sync runs is no longer "the
  Kobo was unplugged".** Trouble reading a file on the computer was read as
  the Kobo's, and the books after it stayed behind. That book now waits and
  the rest go.
- **Server mode: one reader's failed sync no longer keeps the hourly sync
  from the readers after them.** Something unexpected in one reader's run
  ended the whole round, every hour, so the others' edits on Hardcover were
  not taken over until their next upload.
- **A book in a folder with a comma in its name can be switched on and off
  from its row.** A book you put on the Kobo yourself is known by its file's
  path, and a path like `Pratchett, Terry/Mort.epub` was read as two books:
  the row's Sync showed the new choice and kept the old one.
- **Reading minutes: a new book counts from its first page.** What you read
  of a book before the first sync that saw it was left out of your minutes,
  so every new book lost its first days.
- **A book switched off while a sync runs is no longer sent by that sync.**
  A long first sync worked from the list it began with, so a book you
  switched off on the page meanwhile still went to Hardcover. Each book is
  now looked at again just before it is sent.
- Local mode: a state database you deleted is filled again at the next
  plug-in also when the page or `lastread token` was used in between. They
  made an empty one, the unchanged Kobo was then not read, and its
  collection came off.
- Details shows the cover of a book whose file name holds `#` or `?`.
- When Hardcover asks to slow down just as the connection is renewed, the
  sync no longer says "Connect again under Settings". The connection is
  fine; the next sync renews it.
- Server mode: an upload whose gzip is broken inside is refused as one that
  cannot be read, and no longer leaves its temporary file in the data
  folder.
- `lastread setup --server ... --check`, and Set up in the Mac app, no
  longer take any web page's answer for "this server knows this computer".
- **An ISBN the Kobo keeps with hyphens, with spaces or as ten digits is
  now taken for the ISBN it is.** Such a book was looked up by title and
  author instead, and its edition was not found by its number.
- **Books in Cyrillic, Greek, Chinese, Japanese and other scripts are now
  matched by title and author.** Only the letters a to z were compared, so
  such a title was empty to the tool and the book waited for you for ever.
  A title typed with a curly apostrophe now also agrees with the same title
  with a straight one. Books that waited under the old rules are looked up
  once more at the next sync.
- **Local mode: `lastread open` no longer opens a page that is not there.**
  A page that was killed, or a computer that lost power while it ran, left
  its note behind, and when another program had its process number by then
  the link went to a port nothing listened on. The port is now tried, and
  the page started again when nobody answers.
- **Linux: `lastread open` and `lastread token` no longer hang until you
  quit the browser.** With no browser running yet, the command that opens
  the page becomes the browser, and the tool waited for it.
- **Searching Hardcover with nothing typed no longer throws away the books
  it found before.** In a book's Details, Search with an empty box asked
  Hardcover for nothing and replaced the books to choose from with that
  answer. Now nothing is asked and the list stays.
- **Server mode: a collection may have any name, also one that starts with
  `<`.** A computer takes such a line for a proxy's sign-in page and left
  the Kobo alone at every sync ("gave an answer that is not from
  lastread"). The server now says in a header that the answer is its own.
  Both sides need this version.
- **Local mode: a sync that read the Kobo but did not get through to
  Hardcover is a sync that failed.** It was called "Kobo synced", in green,
  with the trouble in the small print, and a script saw it end well. Its
  notification now says "Kobo read, Hardcover not reached", the app and the
  history show it as failed, and `lastread sync` ends with status 1. What
  the Kobo said is kept as before, and the next sync sends it.

### Security

- **Server mode: the proxy has to set or remove `Remote-Email` as well as
  `Remote-User`.** The server knows a reader by either header, and the
  README named only the first. Behind a proxy that passes a browser's own
  `Remote-Email` on, someone signed in could be taken for another reader.
  The README, the example compose file and the start-up message now name
  both; check your proxy (with Traefik: both under `authResponseHeaders`).
  And `Remote-User` now goes first: a reader is no longer taken for another
  by an address sent along. The address is still looked at when the name is
  no reader's, so the proxy's setting is what closes this.
- **Server mode: the Mac app's paths read a request only from a computer
  the server knows, and only 64 kB of it.** `/api/app/` is let through the
  sign-in, and a request's whole body was taken into memory before its
  token was looked at, so anyone who could reach the server could fill it.
- **Server mode keeps no access log.** Each request's address went into the
  container's log, and with it the file names of books you put on the Kobo
  yourself and the words you searched for, which the log is meant never to
  hold.
- **Server mode: the upload token no longer follows a redirect.** When a
  proxy in front of the server sent a request on to its sign-in page, this
  computer's token went along to that address, also from https to plain
  http. A redirect is now an answer: the sync says where the server pointed
  and sends nothing there.
- **The release job that may publish to PyPI runs its actions pinned by
  commit**, as the job that signs the Mac app does. A tag or a branch of an
  action can be moved to other code; a commit cannot.
- **Newer FastAPI, Starlette, uvicorn and python-multipart** (0.162.0,
  1.10.0, 0.54.0, 0.0.33). The versions before had fourteen published
  advisories between them, among them a Host header that was not checked
  and limits on a form that were ignored. None is known for these. FastAPI
  now brings `opentelemetry-api` along: the names a program can report
  through, which send nothing by themselves; nothing that could send is
  installed, and a test keeps it so.

## 0.26.0 - 2026-11-06

### Added

- A book you put on the Kobo yourself, or in the EPUB folder, shows the cover
  its own EPUB names, in Books, enlarged, and in the notification when you
  finish it. A sync reads it from the Kobo and keeps it on this computer; in
  server mode it does not go to the server, so the app shows it and the
  server's page does not.

### Fixed

- Privacy: for those books, the "cover number" the Kobo keeps is made from the
  file's path, and Lastread sent it to Kobo's cover server, so that server saw
  their file names. It no longer asks for them. In server mode this needs the
  server on this version too.

## 0.25.0 - 2026-11-05

### Added

- `lastread doctor`, and Check in the app, has a Folder collection line:
  where the books in the Kobo's Lastread folder go (no collection, the one
  of the books that sync, or their own), how many there are, and whether
  their own collection is on the Kobo. It warns when that collection has the
  name of the synced books' collection, or of one that is not this tool's.
- A book you put on the Kobo yourself, or in the EPUB folder, that names no
  ISBN inside its file is looked up by a 13-digit ISBN in its file name, such
  as `9789044553277.epub`. The check digit has to be right, and an ISBN inside
  the book goes first.

### Fixed

- In the Mac app, the sync's Folder collection step shows on the Kobo's link
  of the chain, not on This Mac's.

## 0.24.2 - 2026-11-03

### Fixed

- **An older copy moved to the Trash no longer keeps the widget.** macOS
  went on running the old copy's widget from the Trash, broken, and the
  widget gallery went on showing the old name; the app now stops that
  widget and has macOS forget the copy in the Trash.

## 0.24.1 - 2026-11-03

### Fixed

- **The Mac app's window no longer slides up under its title bar after a
  sync.** The line that says what a sync did, added to the top of the
  window when it ended, sized itself to its own height and pushed
  everything up, the top line and the sidebar's first rows out of sight,
  most of all on EPUB Folder and Books. The same was true of the lines
  above the Books list.

## 0.24.0 - 2026-11-03

### Added

- **Release Notes in the Mac app's Help menu**: what the latest releases
  changed, newest first, read from the notes the app comes with.
- **About Lastread shows how it works, as a machine**: a tabletop proof
  press with your Kobo locked on the bed, the cylinder that is the sync,
  and the proof of your Hardcover shelf with its red carets. In light and
  dark.
- **A collection for the books from your EPUB folder.** They can stay in
  no collection, as before and still the default; join the collection of
  the books that sync; or have one of their own, Lastread unless you name
  it. Every book in the Kobo's Lastread folder counts. Chosen in the Mac
  app's EPUB Folder, or with `lastread to-kobo --collection` and `--name`.

### Fixed

- **The Mac app offers to put an older copy of itself in the Trash**, such
  as "Kobo Hardcover Sync" from before 0.20.0 left in Applications beside
  Lastread. With both installed, notifications could show the old icon and
  the widget the old name. It asks once per copy, when you open the app.
- **The Mac app's window no longer goes blank on EPUB Folder.** With books
  in the folder, the pane could empty the whole window, sidebar and all,
  leaving only grey rows. A line in the folder's bar that sized itself to
  its height, above the list, threw the window's layout off; it no longer
  does.
- **The Mac app's Books list no longer sends a change you did not make.**
  While the list redrew after a sync, a row's Sync or State menu could set
  its own value again, and the app sent that to the tool as a change. The
  same value is now no change, and a real one is made after the redraw.

## 0.23.1 - 2026-11-03

### Fixed

- **The Mac app's EPUB Folder pane says so when it waits.** Reading a folder
  in Documents can wait until macOS's question whether the app may open it
  is answered. Until then the pane showed only a spinner, and every refresh
  of the window started one more look at the folder, each left waiting. Now
  one look waits at a time, and after a few seconds the pane says what it
  is waiting for.

## 0.23.0 - 2026-11-03

### Fixed

- **The Mac app no longer refreshes itself every second** once an EPUB
  folder is chosen. Asking for the folder's list rewrote the file the app
  watches, so each refresh started the next; the Books list jumped back to
  the top, and around a sync the window could lose its sidebar and its
  top line. The list now writes only what changed.
- **Plugging in the Kobo starts a sync again in the Mac app** for those
  who had it before 0.20.0. macOS kept starting the app's program by its
  old name, which the rename took away, so plugging in did nothing. The
  app now registers its launch agent again once after each update; open
  it once to repair this.
- The Trigger check (`lastread doctor`, and the Overview in the app) says
  so when the launch agent starts a program the app no longer has; it
  called that trigger in order.
- **Server mode no longer empties the collection on the Kobo** when a
  proxy in front of the server answers with its sign-in page. That page was
  read as a collection without books; an answer that is not the server's own
  now leaves the Kobo as it is.
- **A sync to Hardcover that breaks on something unexpected now ends.**
  The page went on showing it as running, with Sync now unavailable, until
  the server was restarted; it now says the sync failed and why.
- **A sync cut off by a restart of the server** no longer shows as
  running in the sidebar until the next one ends; it says it was
  interrupted.
- **One book the Kobo will not take no longer holds up the others** in the
  to-Kobo folder. Any error while copying was taken for an unplugged Kobo,
  so the queue stopped at that book at every plug-in. Now that book is said
  once and the rest still go. Long names fit where they did not, and the
  characters the Kobo's storage cannot hold in a name, such as `?` and
  `:`, become `_`.
- **Quitting the Mac app during Sync now** no longer records that sync as
  an unexpected failure to report. The sync runs to its end, and the
  history says how it went.
- **A new server address or a new upload token now gets the Kobo's
  books** at the next plug-in. The upload was skipped while the Kobo had
  not changed, so a new server never had them, and its empty collection
  could take the one on the Kobo away. In local mode, a deleted database
  likewise has the Kobo read again.
- **Removing a reader on a server** now also forgets which Hardcover
  account their books were sent to. Someone who signed up again under the
  same name had every sync refused as being for another account.
- **An upload refused as too large once unpacked** no longer leaves a
  temporary file in the server's data folder.
- **A typo in `config.toml`** is now said with the file and the line,
  instead of a Python traceback from every command; `lastread doctor` and
  the app's Overview name it, and a sync started by plugging in says it in
  its notification.
- **Server mode: a Kobo unplugged right after its collection was written**
  no longer turns a finished sync into an unexpected failure to report.
- **Before the first sync, the app's Overview no longer says 0 books.**
  Opening Settings made an empty database, which then counted as a
  library with nothing in it.
- **A book from the to-Kobo folder is no longer put on the Kobo twice.**
  The app's list, read just before a sync, could write back over what the
  sync had just put; and a book still being downloaded into the folder was
  remembered by half its contents. With kepub conversion, either case put
  the book there again as "Title (2)". A book still being written now waits
  for the next plug-in.
- **The server keeps answering while it takes in an upload.** The import
  ran where every other request waits, so the page, the Mac app and the
  health check stalled for its length, up to half a minute when the
  Hardcover connection was renewed with it.
- **Covers come back as soon as the network does.** Opening the page or
  the Mac app offline marked every cover not yet fetched as missing for a
  week. Now only Kobo's answer that a book has no cover does that; when
  Kobo cannot be reached, covers are asked for again a minute later.
- **Linux: the trigger from before the rename is taken away.** Setup left
  the old `kobo-hardcover-sync.service` in place, so each plug-in started
  two syncs, and uninstalling left one running. Setup and uninstall now
  remove it, and `lastread doctor` says so when it is there.
- **Plugging in while the Mac app is open no longer skips the sync now and
  then.** The app's look at whether a sync runs could, for an instant,
  pass for a sync already running.
- **The first requests after an update no longer fail once** when two of
  them bring the database up to date at the same moment.
- **A Hardcover connection survives a renewal whose answer got lost.** The
  next sync asked again with the same renewal key, which Hardcover takes
  for a stolen one and ends the connection. It now asks again only once
  the current access has run out.
- **A re-read is no longer put on Hardcover twice** when the answer to
  adding it got lost. The next sync added a second read-through; it now
  finds the first and goes on with that one.
- **The Mac app's local page starts as the app's own tool does**, so
  Python packages installed elsewhere on the Mac can no longer stand in
  for the ones the app brings.
- **A full disk at the very end of a sync** no longer turns it into an
  unexpected failure; the sync is kept in the history as it went.
- **The Mac app:**
  - Closing the window during Sync now no longer cuts the sync off; the
    app stays until the sync has said how it went.
  - Sync now is available again as soon as the sync has said how it went,
    not a few seconds later, and is no longer called "started elsewhere".
  - On a fresh install, the window follows a sync started by plugging in
    from the first session on.
  - Moving the app, say from Downloads to Applications, no longer stops
    plugging in from starting a sync.
  - The arrow keys on Covers no longer crash the app after its rows change.
  - Closing the window or quitting ends a Hardcover sign-in still waiting
    for approval, instead of leaving it running.
  - Quit waits while an update replaces the app.
  - Remove… takes the caret icon off the EPUB folder, and the window keeps
    drawing while it works.
  - Setting up again from a check can be cancelled, and Sync now waits
    while setup shows.
  - The Books list no longer jumps back to the top when a refresh brings
    nothing new.

## 0.22.1 - 2026-11-02

### Fixed

- **Server mode** no longer leaves a `-wal` and a `-shm` file in its data
  folder for each upload of a database in WAL mode, as the Kobo keeps its
  own. Files left by earlier versions (`tmp*.sqlite-wal`, `tmp*.sqlite-shm`)
  hold nothing and can be deleted.

## 0.22.0 - 2026-11-01

### Added

- **EPUB Folder in the Mac app.** The folder whose books go on the Kobo
  has its own place in the sidebar: each book in it, by its title and
  author, with whether it is on the Kobo (and since when, as kepub or
  EPUB), refused for DRM, or waiting for the next plug-in, and its
  Hardcover status once a sync has read it from the Kobo. A double-click
  shows the book in Books. The folder is chosen there, in a panel that can
  make a new folder, and gets a Finder icon with the caret.
- `lastread to-kobo --json` lists each book of the folder (`list`).

### Changed

- The folder is no longer chosen in the Mac app's Settings, but in
  *EPUB Folder*.

## 0.21.0 - 2026-11-01

### Added

- **Books from a folder of yours go on the Kobo.** `lastread to-kobo FOLDER`:
  at every plug-in, the EPUBs in that folder that this Kobo has not had yet
  are copied to a folder `Lastread` on it, and the Kobo lists them after the
  eject. Only files are written, never the Kobo's database or a setting.
  They go as kepub: the Mac app comes with kepubify 4.0.4, and the
  Homebrew formula installs it.
  Each book goes on each Kobo once; one deleted on the Kobo stays deleted.
  A book with DRM is not copied, and the sync says so. More than 20 books
  at once only with `--yes`. Installed otherwise, with kepubify on the
  computer, each goes as kepub too, converted on the computer. The folder is
  chosen with the command, in the Mac app's Settings (Advanced, a folder
  picker), or on the page in local mode (Settings, Advanced); each asks
  before a folder puts more than 20 books on the Kobo at once, and shows
  the books that were refused and why. The rules are P1 to P7 in
  `docs/sync-rules.md`.

- **Books you put on the Kobo yourself are found by their ISBN.** The Kobo
  often keeps no ISBN for a sideloaded book; Lastread now reads it from the
  book's own EPUB file, so a DRM-free book bought elsewhere is matched on
  Hardcover as surely as a Kobo-store book. A sideloaded book that was
  waiting for a match gets one more look. The file is only read.

## 0.20.1 - 2026-10-31

### Changed

- **A new icon**: the red caret on white, the mark a proofreader writes where
  something goes in, which is what a sync does. The Mac app, the disk image,
  the page's tab and the site all carry it, and the site's name has the same
  caret before it.

### Fixed

- The disk image's window says *Drag Lastread onto Applications.* In 0.20.0 it
  still named the app by its old name.

## 0.20.0 - 2026-10-31

### Changed

- **The tool is called Lastread now.** The command is `lastread`; the
  package on PyPI, the Homebrew formula, the container image and the Mac
  app carry the name, and the site is at <https://lastread.app/>. It does
  the same thing, and it says so under the name: your Kobo's reading, on
  Hardcover. What stays as it was: the state folder (`~/Library/Application
  Support/kobo-hardcover-sync`, `~/.local/share/kobo-hardcover-sync`), the
  `KHS_` settings, the keychain and keyring entries, the Mac app's bundle
  id and launch agent, and its `kobo-hardcover-sync://` links, so an
  existing install keeps its settings, its token and its trigger. The old
  command name `kobo-hardcover-sync` still works. The Mac app of 0.19 cannot
  fetch this version by itself, because the disk image and the app inside
  it have the new name: download it once from the site and drag it over
  the old one. The repository, the container image and the Pages address
  under the old name redirect.

### Added

- Mac app: About shows a link to the tool's site, lastread.app, with the
  independent-project sentence.
- The site has an address of its own, <https://lastread.app/>; the GitHub
  Pages address still works and sends you there.

### Changed

- The tag on a book first opened after the tool started says *Auto*, the
  word the Sync column and the guide already use for it, instead of *New*,
  and explains itself when pointed at. Same on the page's filter.

### Fixed

- A book's cover reaches the server even when the book is no longer
  reported as touched: a book that came in before its cover id travelled
  with the upload, and that the Kobo has since stopped listing events for,
  kept an empty cover (the crossed box on Covers and Books). The next
  import fills it in.

## 0.19.0 - 2026-10-28

### Fixed

- Mac app: hiding or showing the sidebar no longer flashes a button at the
  top right of the window (the toolbar's overflow chevron, for one frame,
  on macOS 26). The sidebar button now sits at the leading edge of the
  content's title bar, in the app's window and the guide's.

## 0.18.0 - 2026-10-28

### Added

- *Getting started*, the same on the page and in the Mac app: four steps
  from a new reader to a live shelf (connect to Hardcover, plug in your
  Kobo, choose your books, go live), each marked done or to do, with the
  one button that does it right there. On the page it stands above your
  books, and connecting to Hardcover, adding your first computer on a
  server and going live all happen in it, without a trip to Settings. In
  the app it opens the Overview, above the chain, and the same steps sit
  above the list in Books. It goes away once you are live.
- *Needs you*, once you are live: one line above your books, on the page
  and in the app, counts the books switched on that wait for you, with no
  Hardcover match yet or not sent at the last sync, and leads to the ones
  that need a match.

### Changed

- Settings on the page has your name and your Hardcover connection on
  top, and the rest under *Advanced*: folded until you open it, and open
  by itself when a link leads to one of its parts. Nothing was removed.
- Settings in the Mac app has two tabs instead of three: *General*
  (Hardcover, ejecting the Kobo, notifications, updates) and *Advanced*
  (where your reading goes, the upload token, the log, an untested Kobo,
  the webhook, export, removing the app).
- Setting up the Mac app ends with *Continue*, which opens its window and
  Getting started there, instead of opening the page in the browser. *With
  a server* now says it is only for a household that runs one.
- Signing up on a server lands on Getting started instead of Settings.
- The check's advice in the app and on the page points to Getting started
  for choosing your books and going live, and to Settings, Advanced for an
  untested Kobo; in a terminal it says what it said.

## 0.17.0 - 2026-10-28

### Added

- The Mac app updates itself: *Install and Restart*, where it says a
  new version is out, downloads it, installs it only when Apple notarised
  it and it carries the same signature as the app you have, and starts
  it. From the next version on: this one is still installed by hand.
- A guide in the Mac app (*Help*, ⌘?): how it works, each pane, what the
  marks mean, the keys, and what to do when something is wrong.
  Searchable, also from the *Help* menu's own search field, and it no
  longer sends you to GitHub.
- A full-screen cover in the Mac app: on a cover shown large, the button
  in its corner (or F) puts it alone on black over the whole screen; a
  click or any key puts it back.

### Changed

- A new icon for the Mac app: the Kobo itself, a page on its e-ink screen
  and the two-way sync under it in blue, on a blue-to-navy tile. It holds
  its own in the Dock and reads at 16 pixels, which the galley slip did
  not. The disk image's icon and window follow it.
- Covers in the Mac app takes about a third less of the processor while
  the rows drift, and next to nothing while a book or its large cover is
  open over them: each row now moves as one, and the rows stop drawing
  when they stand still.
- The Mac app's overview and History are on the page's paper: your Kobo
  in the rail's blue, Hardcover in the proof margin, the status in its
  mark's colour, and a sync's outcome as the page shows it. The count of
  books a live sync will send is in red.
- The Mac app keeps only the last four large covers in memory, not every
  one opened since it started, and reads each away from the window's
  thread before showing it.

### Fixed

- ⌘V pastes in the Mac app's text fields, the Hardcover token among them:
  the Edit menu had no Paste (nor Cut, Undo and Redo). A new *Sync* menu
  holds *Sync Now* (⌘R), *Check Again* (⇧⌘R) and *Show the Log*.
- VoiceOver says when a sync starts and how it ended, in the Mac app.
- The Mac app's grey text (authors, facts, labels) is dark enough to read
  in light mode, in every pane, Settings and the widget. A book selected
  in Books keeps its status, marks and gauge readable on the selection's
  blue, and the covers on the Covers pile open by keyboard too. Its red
  "Next sync" stays readable on the grey a selected row takes when the
  window is in the back.
- The Mac app's menu bar has a *View* menu (the four panes on ⌘1 to ⌘4,
  the sidebar on ⌃⌘S, full screen on ⌃⌘F), *Zoom* and *Bring All to
  Front* in *Window*, and a *Help* menu with the guide, whose search
  field finds the guide's topics as well as the menus.
- VoiceOver can move by heading through a book's Details, and open a
  cover on the Covers rows. Covers shows its keys for a few seconds each
  time the keyboard comes into its rows.
- *Open the page* in the Mac app no longer holds up the window while the
  tool starts.
- A book's *Open on the Page* in the Mac app opened the server's front
  page in server mode, not the book; `open --book` now lands on the book
  there too, with its details open. The button says where it goes:
  *Open in Browser*, or *Open on* and the server's name. In server mode
  the details open once the server runs 0.17.0.
- On a wide window, the page opened at a book (after an action, or from
  `open --book`) scrolled the whole page as well as the list: its top
  out of view, and no way to scroll back up. Only the list scrolls now.
- With Increase Contrast on (Accessibility, Display), the Mac app's grey
  text, colours and rules are stronger: the words 7:1 on the paper.

## 0.16.0 - 2026-10-27

### Added

- *Show* on Covers in the Mac app: the rows hold only the books of one
  of the list's filters, such as the ones that sync (the books in your
  Kobo collection), the ones you are reading or the ones you have not
  started. Covers and Books each remember what you chose to show.

## 0.15.0 - 2026-10-27

### Added

- In server mode the Mac app has your books too, as in local mode: the
  list with its marks, Details, Sync, State, a match, *Set all* and going
  live, all made on the server for you. It asks with this Mac's upload
  token, so nothing new to set up on the Mac. The server needs 0.15.0
  too, and its proxy has to let `/api/app/` past its sign-in, as it does
  `/upload` (README).
- A tip above the Mac app's list of books: one book from your own shelf,
  asked as a question. A book you stopped halfway through more than half
  a year ago, then one on your Want to read that is already on your Kobo,
  then one you never opened. The same one all day; *Not now* puts it
  aside for a month. It is chosen from what the tool already knows;
  nothing is asked of Hardcover or anyone else. In a terminal,
  `book ID --not-now`.
- *Covers* in the Mac app's sidebar: your library as a press run. Three
  rows of covers drift slowly left: at the front the books you read in
  the last year, behind them the rest you read, at the back the ones you
  never opened. Pointing at a cover stops its row and lifts it, with its
  title, how far you are and what the next sync does. A click opens the
  cover large in a third of the window, with its Details and what you can
  do with it beside it; a click on that cover, or Space, shows it over the
  whole window. The arrow keys walk the rows, two fingers move them. A
  red caret marks a book the next sync changes.
  Below the rows: the book you are reading, and the tip. With Reduce
  motion on, the rows stand still. Full screen with ⌃⌘F.
- Your books in Spotlight on your Mac: type a title, and the app opens
  Covers at that book. The index is your Mac's own; removing the app
  takes the books out again.
- A widget for the desktop and Notification Center (macOS 14 and later):
  the book you are reading with its cover and how far you are, and in the
  medium size the tip beside it. A click opens Covers at that book. It
  needs the signed app from the release; a build of your own, signed ad
  hoc, has no widget.
- When a sync marks a book as read on Hardcover, the Mac app says so in
  a notification of its own, "Finished: …", with the book's cover; on
  Linux the cover is the notification's icon. In local mode: in server
  mode the server marks books read, after the upload.

### Fixed

- Book titles in the Mac app are in the page's serif, Source Serif 4, as
  meant. macOS picked the font's subset without lowercase letters, and
  set them in the system font instead.

## 0.14.0 - 2026-10-26

The Mac app gets an icon of its own, drawn like the page, and the disk
image it comes on says what to do with it.

### Changed

- The Mac app has a new icon, drawn like the page: a galley of your books
  with the next sync's red caret in its margin. On macOS 26 and later it
  is a proper icon for those versions, with the system's glass, where the
  old one was shrunk into a grey tile. At the smallest sizes it is drawn
  for the size, not made smaller.
- The disk image the app comes on has its own icon, and its window shows
  what to do: drag the app onto Applications.

## 0.13.0 - 2026-10-24

The Mac app becomes the home of local mode: an overview that draws the
way a sync goes, your books in the app, changed there, and connecting
to Hardcover and going live without the page.

### Changed

- The Mac app's window has a sidebar: *Overview*, *Books* and *History*.
  Overview draws the way a sync goes, Kobo, this Mac, the server (in
  server mode), Hardcover, each with the page's mark for how it is; a
  click shows its checks, and the first that needs something opens by
  itself. A sync plays out along it. In local mode it counts the books
  as well: how many came from the Kobo, how many the next sync sends,
  how many are in the collection. The marks are the page's, in the
  page's colours, where the window had coloured symbols.
- In local mode the Mac app's *Books* is the list of books itself, as
  the page has it: covers, titles, Sync, State and what the next sync
  does on Hardcover, in the page's marks, with search, filters, sorts
  and each book's Details. Sync, State and its date, a match (from the
  books it could be, or a search on Hardcover), removing a book from
  Hardcover and *Set all* are changed there too, without the page.
- In local mode the Mac app connects to Hardcover itself (*Connect…*, on
  the Hardcover link, above the list and in Settings), with a pasted
  token as the second way, and goes live: the page's first run is above
  the list until then, with a red *Go live*. Settings, Sync, has the
  connection and *Send to Hardcover*. Local mode on a Mac needs no
  browser any more.
- In the Mac app, a sync and the doctor say to connect and to choose a
  match in the app, not on the page.

### Added

- `kobo-hardcover-sync books` lists your books in local mode, each with
  what the next sync does with it; `--covers` fetches the covers this
  computer does not have yet, `--json` is for the Mac app.
- `kobo-hardcover-sync open --book ID` opens the page at that book.
- `status --json` counts the books in local mode (`books`), for the
  app's overview.
- `kobo-hardcover-sync token --json` signs in as lines of JSON (where to
  approve, then who signed in), for the Mac app; `settings --set
  live=true` goes live in local mode, and `settings --json` says whether
  it is live.
- `kobo-hardcover-sync book ID` shows one book and changes what the
  page changes: `--sync`, `--state` (with `--date`), `--search` and
  `--pick` for a match, `--remove` from Hardcover. `books --sync MODE
  --filter F` is the page's Set all; `--expect N` changes nothing unless
  that is still N books.

### Fixed

- In the Mac app, what to do no longer names terminal commands: the
  window's checks and a failed sync point at the app's own buttons and
  Settings (*Set up*, *Sync now*, *Check again*, the untested Kobo
  setting). A Kobo the app may not read says what to allow for the app,
  not for a terminal, and has its *Open Privacy* button again.
- Doctor's line about a collection of someone else's says the name is
  chosen on the page, under Settings.

## 0.12.2 - 2026-10-24

Look for a newer version at once: *Check now* in the Mac app's Settings,
*Check for Updates…* in its menu, and `update` in a terminal.

### Added

- `kobo-hardcover-sync update` asks GitHub now whether there is a newer
  version, also when the Mac app's daily look is switched off; `--json`
  for the app. In the Mac app: *Check now* in Settings, App, and *Check
  for Updates…* in the app menu.

## 0.12.1 - 2026-10-24

The Mac app's window shows a sync that plugging in the Kobo started, and
says when macOS hides what notifications say.

### Fixed

- The Mac app's window shows a sync that plugging in the Kobo started:
  "Syncing…" while it runs, then its outcome. Before, the window looked
  idle until that sync had ended, and *Sync now* during it only said that
  another sync was running.
- *Sync now*'s steps fold into History a few seconds after the sync,
  instead of staying on screen: an old "A sync is already running" read as
  if one still was. An answer that History does not keep ("No Kobo
  found") stays until the next sync.
- The window says when macOS shows only the app's name in a
  notification (*Show previews* set to Never), with a button to its
  settings.

### Added

- `status --json` says whether a sync is running now, and what started
  it (`"syncing"`); `status` says so in a row.

## 0.12.0 - 2026-10-24

The Mac app gets a window and Settings of its own: what `status`,
`doctor`, `history` and the settings tell in a terminal, about this Mac.

### Added

- `kobo-hardcover-sync history`: the last syncs on this computer, newest
  first, with what started each and what it said. The last hundred are
  kept in `history.jsonl` in the tool's folder, without book titles.
- `kobo-hardcover-sync settings`: this computer's settings, and `--set
  NAME=VALUE` to change one that is true or false, instead of editing
  `config.toml`.
- `--json` for `status`, `doctor`, `history` and `settings`, and `sync
  --steps` (each step and the outcome as a line of JSON): what the Mac
  app's window reads, and usable in scripts. Each answer carries
  `"schema": 1`.
- `setup --check`: before anything changes, ask the server whether it
  answers as kobo-hardcover-sync does. A typo in the address, or a
  server that is down, then changes nothing. It also says when the
  server knows this computer already.
- The Mac app has Settings (⌘-,): where the reading goes and the
  server's address, the upload token's hash and a new token, eject after
  a sync, a detailed log, an untested Kobo version, looking for a newer
  version; in local mode also the webhook and *Export my reading…*.
  *Remove…* stops syncing on this Mac, or also deletes what the app
  keeps there, and says how to remove the app itself.

### Changed

- The Mac app has a window of its own, about this Mac: whether it is
  ready for the Kobo, a check of everything a sync depends on with a
  button where the app can mend something, a sync's steps as it runs,
  and the last syncs, with the log a click away. It replaces the dialog
  that showed the last message. While the window is open the app has a
  Dock icon and a menu bar.
- The notification of a sync the Kobo started shows as soon as the sync
  has said it, instead of after the once-a-day look for a newer version.

## 0.11.1 - 2026-10-24

The Mac app's *Sync now* always answers, and notifications are asked for
at a better moment.

### Fixed

- The Mac app: *Sync now* shows that it is busy, and then what the sync
  did, in the app's window. When there was nothing new, or no Kobo is
  plugged in, it says so; before, it said nothing at all.
- The Mac app asks whether it may show notifications after setup's
  windows are closed, and says beforehand that it will ask. Before, the
  question came while they were open, and was easily missed or answered
  no. When notifications are off, the app's window says so, with a
  button to their settings.

## 0.11.0 - 2026-10-24

A Mac app: download it, drag it to Applications, open it.

### Added

- A Mac app, signed and notarised, as a third way to install on a Mac:
  `Kobo-Hardcover-Sync-0.11.0.dmg` on this release, for Apple silicon and
  macOS 13 or newer. Drag it to Applications and open it. It sets itself
  up (on this computer, or with a server) without a terminal, and starts
  a sync when the Kobo is plugged in. It uses the same folder and
  Keychain items as a Homebrew installation, and takes over its trigger.
  See `docs/macos-app.md`. This is its first release: it has not yet
  been tried on many Macs, so please say how it went in an issue.
- The Mac app looks for a newer version once a day at most, after a
  sync, and says so on the page and in its window. It never updates
  itself, and it can be switched off. Homebrew and PyPI installations
  do not look.

### Changed

- `setup` from Homebrew or PyPI, on a Mac where the app has the trigger,
  leaves the trigger to the app instead of installing a second one.

## 0.10.1 - 2026-10-08

Connecting again ends the old connection at Hardcover.

### Fixed

- Connecting to Hardcover again, or pasting a token in place of a
  connection, ends the earlier connection at Hardcover, as Disconnect
  does. Before, it stayed listed and working there.

## 0.10.0 - 2026-10-08

One book on two Kobos, one write for a new collection name, and a
shelf that is known to be yours.

### Added

- The tool remembers which Hardcover account your books were put on. A
  connection to another account now stops the sync from the first book,
  before anything is sent or switched off, and says which two accounts
  they are (before, it was noticed only once three or more books seemed
  gone from the shelf). Moving to another account on purpose: *Start
  over* under Settings, or `kobo-hardcover-sync token --start-over`.

### Changed

- The same book on two of your Kobos is one book: Sync, State and the
  Hardcover match are set for the book, not per Kobo. The page lists it
  once, as the Kobo you read it on last says it, and what you set holds on
  both. A book that turns up on another Kobo later brings what was set for
  it, so a match you chose by hand is no longer looked up again. Where the
  two copies differed before, the one read last decides, once.
- Another collection name: the old collection is taken off and the new
  one made in one write to the Kobo, with one backup instead of two. When
  the new name cannot be used, because a collection of yours already has
  it, the old collection now stays instead of being removed.

## 0.9.0 - 2026-10-06

A webhook: each sync to an address of your own.

### Added

- `kobo-hardcover-sync webhook URL`: after every sync that read something
  new from the Kobo, a POST with JSON to an address of your own, for a
  reading tracker, a database or an automation. It carries the book you
  are reading, the books that changed in that sync, and the reading
  summary. `--token` adds a Bearer token, kept in the Keychain. It is sent
  only over https (plain http only to this computer), a redirect is never
  followed, and a test must be answered before anything is stored. Local
  mode. What is sent: [docs/webhook.md](docs/webhook.md).

## 0.8.0 - 2026-10-05

Your reading as a file: for a database or dashboard of your own, with or
without Hardcover.

### Added

- `kobo-hardcover-sync export`: your reading as JSON, for a database, a
  spreadsheet or a dashboard of your own. Every book the Kobo has seen
  opened, with how far, the dates and whether it syncs, the minutes read
  per day, and the summary `/api/stats` gives. It needs no Hardcover
  account. `--output FILE` writes a file only you can read; on a server,
  `--reader NAME` exports one reader.
- `export --output FILE --every-sync` writes that file again after every
  sync on your own computer, for a dashboard that reads it; `status` says
  where it goes, and `export --stop` ends it. A file that cannot be
  written is said in the sync's notification; the sync itself still
  counts.
- The same export on the page: Settings, *Your reading as a file*, a
  download for the reader who is signed in. On a server that is the way
  for a reader without a shell there.

## 0.7.1 - 2026-10-04

Admin says which versions are running.

### Added

- Admin says which version the server runs (in the card *This server*,
  which was *Storage*), and per reader which version of the tool sent the
  last upload, and whether that is the server's. A computer says its
  version from this release on; an upload from an older one shows as
  such.

## 0.7.0 - 2026-10-04

A long list of books is quicker, and sorts either way round.

### Added

- Sorting either way round: *Sort by* now offers *Last read, oldest
  first*, *Author, Z to A* and *Title, Z to A* as well. A book never opened
  comes last either way.
- A long list shows its first 100 books, with *Show 100 more* at its end;
  the next ones join the same list. On a phone the page with 450 books is
  ready about three times sooner. How many it shows is yours to choose
  under Settings, *The list of books*: 25, 50, 100 or all of them.

### Changed

- *Set all shown* is now *Set all in this list* and acts on every book the
  search and filter match, also the ones not shown yet. It changes nothing
  when the list has changed since you looked (a sync, another tab), and
  says so.

## 0.6.0 - 2026-10-04

On your own computer you connect to Hardcover in the browser, with no code
to compare.

### Added

- On your own computer you connect to Hardcover in the browser: `token`
  and *Connect to Hardcover* on the page open Hardcover, you approve, and
  Hardcover sends the browser back to the tool. No code to compare.
  `token --code` keeps the sign-in with a code, for a computer without a
  browser. A server keeps signing in with a code.

## 0.5.1 - 2026-10-03

*Sync now* shows the sync while it runs, and says what it did.

### Changed

- *Sync now* shows the sync running: the button says *Syncing* and what it
  is doing ("Sending 2 of 5"), with a line that fills as the books go out.
  When it is done the list comes back with its new marks, and a line under
  the button says what happened ("Done: 1 change sent to Hardcover.", or
  why it stopped). Before, the page came back at once, still showing the
  change as waiting while the sync had in fact sent it.
- Help says what *stet* means: Latin for "let it stand", the word a
  proofreader writes to keep the original.

## 0.5.0 - 2026-10-03

A new look: the page reads like a proof of your Hardcover shelf, and a new
reader is shown where to start.

### Changed

- A new look for the page. The Hardcover column now reads like the margin
  of a proof: what the next sync changes is marked there, the value
  Hardcover has struck through and the new one after a caret, and a legend
  above the list says what each mark means. Red is only for what a sync
  sends; blue is your own choice or a question for you. The status dots are
  marks now (a tick, a caret, a question mark, a dash), so they can be told
  apart without their colour. New fonts, Schibsted Grotesk and Source Serif
  4, and no more photographs. Nothing about what the page does changed.

### Added

- A first-run guide at the top of the Books page, for as long as you are
  in dry run: what to do with a Kobo full of books read before (search,
  then switch on everything shown), how many you have switched on so far,
  and the three steps to a live shelf (connect, pick, go live). It goes
  away when you go live.
- A container image for the server, built for amd64 and arm64 at every
  release: `ghcr.io/merlijntishauser/kobo-hardcover-sync`. The example
  compose file pulls it. Building it yourself from the repository keeps
  working.

## 0.4.0 - 2026-10-03

You connect to Hardcover on Hardcover itself: no token to make or paste.

### Changed

- Signing in on Hardcover itself is switched on: the project's app is
  registered there. *Connect to Hardcover* under Settings and
  `kobo-hardcover-sync token` show a link and a short code, you approve on
  Hardcover, done. A pasted token keeps working, and stays possible
  (`token --paste`, or *Paste a token instead* on the page). Seen working
  against Hardcover on a self-hosted server: signing in, a sync, and a
  renewal of the connection.
- The page and the commands say "connect to Hardcover" where they said
  "add a token".

### Fixed

- Homebrew bottles were not made for 0.3.0 at first: the formula's own
  test looked for words that 0.3.0 printed with a capital. A test now
  holds the two together.

## 0.3.0 - 2026-10-03

The commands speak the page's language, Homebrew installs in seconds, and
signing in on Hardcover itself is built and waiting to be switched on.

### Added

- Signing in on Hardcover itself instead of pasting a token: *Connect to
  Hardcover* under Settings, and `kobo-hardcover-sync token`. The tool
  shows a link and a short code, you approve on Hardcover, and that is
  all. The connection renews itself; it is kept where a pasted token was
  kept, and ended at Hardcover when you disconnect. This is switched on
  once the project's app is registered at Hardcover; until then, and
  always as a second way, a pasted token works as before
  (`token --paste`).
- Homebrew installs a ready-made build on Macs with Apple silicon and
  macOS 15 or newer, in seconds instead of minutes. Other Macs build from
  source as before.

### Changed

- What the commands print. `doctor`, `status` and `setup` use the page's
  status language: a coloured mark and plain words, grouped under *This
  computer*, *Your Kobo* and *Hardcover*, folded to the width of the
  terminal. `sync` run by hand says each step as it finishes and then
  names the books that went to Hardcover (or would, in a dry run), each
  with its reading line. Those titles are shown in the terminal and
  written nowhere.
- Colour only on a terminal, and never the only sign: the marks differ in
  shape, and piped output carries the word (`ok`, `note`, `warning`,
  `problem`). `NO_COLOR` switches colour off.
- `kobo-hardcover-sync --help` lists the commands by where you use them.
- Counts read "1 book", "9 books", in notifications too.
- The Check card under Settings groups its lines the same way.

## 0.2.1 - 2026-10-03

Two fixes for 0.2.0, and fewer books that wait for a match.

### Changed

- Fewer books wait for a match. A translation is matched when Hardcover
  itself lists the Kobo's title among the book's other titles. The author
  may be any name the Kobo lists (it lists translators too). The first
  five search hits are looked at instead of the first one, a leading
  article no longer matters, and a title may be the book's title without
  its subtitle or series name. On the shelf this was measured on, 10 of 31
  waiting books now match by themselves; the rest are not on Hardcover
  under a title it can be sure of, and still wait for you.
- Books that already wait for a match are looked up once more after the
  upgrade, at the next sync: one search each.
- A title that only starts like another book's title is no longer enough
  when the book is not the search's first hit, and has to match on whole
  words.

### Fixed

- On a wide screen, pressing *Check* under Settings moved the whole page
  up and cut off the side column, with no way to scroll back (0.2.0).
- Details gave an error for a book Hardcover found nothing for, also
  after a search there that found nothing (since 0.1.0). It now says so
  and keeps the search box.

## 0.2.0 - 2026-10-02

For when something does not work: a command and a card that say what is
wrong and what to do, and messages and a log that do the same.

### Added

- `kobo-hardcover-sync doctor`: checks everything a sync depends on (the
  setup, the trigger, the Kobo and its database, the Hardcover token, the
  collection, the backups) and says per item what to do. It changes
  nothing, and ends with status 1 when something stops syncing from
  working.
- The same check on the page: a *Check* card under Settings. It takes the
  place of the *Test* button next to the token.
- `kobo-hardcover-sync sync --verbose`, and `verbose_log = true` in
  `config.toml`: a log line per book and per request to Hardcover. A
  verbose log contains book titles. On a server: `KHS_LOG=verbose`.

### Changed

- Messages say what to do next. A Kobo that was unplugged during a sync, a
  database another program is using, a Mac that does not let the tool read
  the Kobo and a Kobo whose software has not been tested each have their
  own message, instead of one that guessed at Full Disk Access.
- Log lines carry a level (`info`, `warning`, `error`, `detail`), and the
  log is kept to about a megabyte with one older file beside it. The
  server now logs each run for Hardcover, in counts.
- Something the tool did not expect no longer ends a sync without a word:
  the notification says so and the details go to the log.

### Fixed

- A collection that was written to the Kobo just as it was unplugged is
  recognised as the tool's own at the next sync. Before, it could be taken
  for a collection of yours with the same name and left alone for good.
- The Settings page no longer scrolls sideways on a phone with text at
  200%.

## 0.1.0 - 2026-10-02

The first public release.

### What it does

- Reads a stock Kobo's database when the Kobo is plugged in, and sends
  status, progress and dates to Hardcover for the books switched on.
- Two ways to run it: on your own computer (local mode), or on your own
  server for a household behind a sign-in proxy (server mode).
- A dry run until you go live. A match is never guessed.
- Takes over edits made on Hardcover: a status, a finish date, an edition,
  a book taken off the shelf.
- An optional collection on the Kobo with the books that sync, written
  only behind a version gate and after a backup.
- A page for choosing books, fixing matches and settings; light and dark;
  works on a phone and without JavaScript.
- macOS and desktop Linux: a trigger on plug-in, the secret store for
  tokens, notifications.

### Tested

- With a real device: one Kobo Clara Colour (software 6.0.274403), on
  macOS 27, in server mode.
- Local mode on macOS 27, with that Kobo: installed on a clean account
  from the README, synced, uninstalled.
- The Homebrew formula: built from source and tested on macOS 27; an
  upgrade kept the Full Disk Access permission.
- A Hardcover token with only the four permissions the tool asks for.
- Everything on Linux: tested without a device.

### Known limits

See the end of [docs/sync-rules.md](docs/sync-rules.md).
