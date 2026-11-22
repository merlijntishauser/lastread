// Books, in local mode (docs/plans/2026-10-24-mac-app-native-books-design.md,
// steps 2 and 3): the page's list drawn here, from `books --json`.
// Searching, filtering and sorting happen in the app, on what the tool
// said; a change (Sync, State, a match, removal, Set all) goes through the
// tool (`book ID ...`, `books --sync ...`), which answers the book as it
// is then. What a sync does with a book is still decided in the tool.

import AppKit
import SwiftUI

/// The title font from the tool's package in the app (Paper.swift).
func registerTitleFont() {
    let lib = Bundle.main.resourceURL?.appendingPathComponent("python/lib")
    let python = (try? FileManager.default.contentsOfDirectory(atPath: lib?.path ?? ""))?.first { $0.hasPrefix("python3.") }
    guard let lib, let python else { return }
    registerTitleFont(in: lib.appendingPathComponent(python).appendingPathComponent("site-packages/lastread/web/static/fonts"))
}

extension WindowModel {
    /// The books of the list as chosen: the search, then the filter, in the sort's order.
    var shownBooks: [BooksAnswer.Book] {
        guard let answer = books else { return [] }
        let order = answer.sorts.first { $0.key == sort }?.order ?? Array(answer.books.indices)
        return order.compactMap { answer.books.indices.contains($0) ? answer.books[$0] : nil }
            .filter { found($0) && $0.filters.contains(filter) }
    }

    /// How many books each filter holds, with the search as it is.
    var filterCounts: [String: Int] {
        var out: [String: Int] = [:]
        for book in books?.books ?? [] where found(book) {
            for f in book.filters { out[f, default: 0] += 1 }
        }
        return out
    }

    /// As the tool searches (SQL like): any case, but é is not e, so that Set all takes the books shown.
    private func found(_ book: BooksAnswer.Book) -> Bool {
        let q = search.trimmingCharacters(in: .whitespaces)
        return q.isEmpty || [book.title, book.author].contains { $0.range(of: q, options: .caseInsensitive) != nil }
    }

    /// A change to one book through the tool; `shown` draws it at once, until the tool's answer replaces it.
    func change(_ id: String, _ args: [String], shown: ((inout BooksAnswer.Book) -> Void)? = nil) {
        if isPreview && args.contains("--remove") {  // it would take the book off the real shelf
            problem = previewLeavesHardcover
            return
        }
        if let shown, let n = books?.books.firstIndex(where: { $0.id == id }) { shown(&books!.books[n]) }
        changing.insert(id)
        DispatchQueue.global(qos: .userInitiated).async {
            let found = answer(BookAnswer.self, ["book", id] + args + ["--json"])
            DispatchQueue.main.async {
                self.changing.remove(id)
                switch found {
                case .success(let changed):
                    if let n = self.books?.books.firstIndex(where: { $0.id == id }) { self.books?.books[n] = changed.book }
                    self.status?.books = changed.books
                    self.books?.tip = changed.tip
                    self.books?.tips = changed.tips
                    self.books?.start = changed.start
                    self.books?.needsYou = changed.needsYou
                case .failure(let why):
                    self.problem = said(why)
                    self.loadBooks()  // back to what the tool has
                }
            }
        }
    }

    /// Set all: Sync for every book the search and filter show, while that is still as many.
    func setAll(_ sync: String) {
        let args = ["books", "--sync", sync, "--filter", filter, "--search", search.trimmingCharacters(in: .whitespaces)]
        let expect = ["--expect", String(shownBooks.count), "--json"]
        DispatchQueue.global(qos: .userInitiated).async {
            let found = answer(BooksAnswer.self, args + expect)
            let now = answer(StatusAnswer.self, ["status", "--json"])
            DispatchQueue.main.async {
                switch found {
                case .success(let list): self.books = list
                case .failure(let why): self.problem = said(why)
                }
                if case .success(let status) = now { self.status = status }
            }
        }
    }

    /// A field of a book as a control changes it.
    func binding(_ id: String, _ field: WritableKeyPath<BooksAnswer.Book, String>, _ args: @escaping (String) -> [String]) -> Binding<String> {
        Binding(
            get: { self.books?.books.first { $0.id == id }?[keyPath: field] ?? "" },
            set: { new in
                // A pop-up can set its value again while the list redraws (rows reused after a
                // sync): the same value is no change, and nothing goes to the tool for it. A real
                // choice is made after the redraw, never inside it.
                guard let book = self.books?.books.first(where: { $0.id == id }), book[keyPath: field] != new else { return }
                DispatchQueue.main.async { self.change(id, args(new)) { $0[keyPath: field] = new } }
            })
    }

    /// The State, without the date of the State before: the day a book was
    /// finished is not the day its re-read began. The tool's answer brings the
    /// book back without a date, and Since offers to add one.
    func stateBinding(_ book: BooksAnswer.Book) -> Binding<String> {
        binding(book.id, \.state) { ["--state", $0] }
    }

    func word(_ list: [[String]]?, _ key: String) -> String {
        list?.first { $0.first == key }?.last ?? key
    }
}

struct BooksPane: View {
    @ObservedObject var model: WindowModel

    var body: some View {
        if let books = model.books {
            HStack(spacing: 0) {
                VStack(spacing: 0) {
                    BooksBar(model: model, words: books.words)
                    if let start = books.start { StartSteps(model: model, start: start, compact: true) }
                    HeadNotes(model: model, books: books)
                    if books.books.isEmpty {
                        Spacer()
                        Text("No books yet: nothing was read from a Kobo so far. Plug it in.").foregroundStyle(Pencil.graphite)
                        Spacer()
                    } else {
                        BooksTable(model: model)
                    }
                }
                .frame(minWidth: 440, maxWidth: .infinity)
                .background(Pencil.ground)
                if let id = model.chosenBook, let book = books.books.first(where: { $0.id == id }) {
                    Pencil.rule.frame(width: 1)
                    DetailsPane(model: model, book: book, words: books.words).frame(width: 300).background(Pencil.sheet)
                }
            }

        } else if let broken = model.booksBroken {
            Galley {
                ProofSheet { Row(state: "fail", what: "Books", found: broken).onSheet() }
                if model.status?.mode == "server" {  // an older server, or a proxy that does not let the app through: the page still has them
                    HStack {
                        Spacer()
                        Button(model.pageTitle) { openThePage() }
                    }
                }
            }
        } else {
            VStack {
                Spacer()
                ProgressView().controlSize(.small)
                Spacer()
            }
            .frame(maxWidth: .infinity)
        }
    }
}

/// The notes under the toolbar, in a white box: what asks the reader something, each with the
/// blue disc of the query. Needs you leads, once live: the books switched on that wait, with the
/// way to them. The tip is one quieter line under it: one book of those Show has chosen, with a
/// question, a nudge; Open shows it in Details, Not now puts it aside for a month and the tool
/// gives the next. The discs stand in one column, the buttons end on one edge.
struct HeadNotes: View {
    @ObservedObject var model: WindowModel
    let books: BooksAnswer

    var body: some View {
        let tipped = books.tip(among: model.filter)  // a book of the selection chosen at Show
        if books.needsYou != nil || tipped != nil {
            VStack(alignment: .leading, spacing: 8) {
                if let needs = books.needsYou {
                    HStack(alignment: .center, spacing: 12) {
                        Disc(state: "warn", size: 22)
                        Text(needs.text).font(.system(size: 13, weight: .semibold)).foregroundStyle(Pencil.ink).lineLimit(2)  // no fixedSize above the table: see TopLine
                        if needs.match > 0 && model.filter != "needs_match" {
                            Button { model.filter = "needs_match" } label: {
                                Text("Show them").font(.system(size: 13)).underline().foregroundStyle(Pencil.blue)
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("Show Them")
                        }
                        Spacer(minLength: 8)
                    }
                    .accessibilityElement(children: .contain)
                }
                if case let (tip, book)? = tipped {
                    HStack(alignment: .center, spacing: 12) {
                        Disc(state: "warn", size: 15).frame(width: 22)  // centred under the question above, smaller: a nudge
                        Cover(path: book.cover, width: 20).coverShadow()
                        (Text(book.title).font(titleFont(13)).foregroundColor(Pencil.ink) + Text(" · " + tip.text).font(.system(size: 13)).foregroundColor(Pencil.graphite))
                            .lineLimit(2)  // no fixedSize above the table: see TopLine
                        Spacer(minLength: 8)
                        HStack(spacing: 8) {
                            Button("Open") { model.chosenBook = book.id }.buttonStyle(PageButton())
                            Button("Not now") { model.change(book.id, ["--not-now"]) }.buttonStyle(PageButton()).disabled(model.changing.contains(book.id))
                        }
                    }
                    .accessibilityElement(children: .contain)
                    .accessibilityLabel("A tip: \(book.title). \(tip.text)")
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(Pencil.sheet, in: RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Pencil.rule, lineWidth: 1))
            .padding(.horizontal, 24)
            .padding(.bottom, 12)
        }
    }
}

/// Search, the page's filters and its sort, then the legend of the marks.
struct BooksBar: View {
    @ObservedObject var model: WindowModel
    let words: BooksAnswer.Words
    @FocusState private var searching: Bool

    var body: some View {
        let counts = model.filterCounts
        VStack(alignment: .leading, spacing: 8) {
            ViewThatFits(in: .horizontal) {  // on one line, or the search above the choices
                HStack(spacing: 10) {
                    search.frame(minWidth: 160, maxWidth: 260)
                    choices(counts)
                    Spacer(minLength: 0)
                }
                VStack(alignment: .leading, spacing: 8) {
                    search
                    HStack(spacing: 10) { choices(counts) }
                }
            }
            Legend(legend: words.legend)
        }
        .padding(.horizontal, 24)
        .padding(.top, 14)
        .padding(.bottom, 12)
    }

    private var search: some View {
        TextField("Search title or author", text: $model.search).textFieldStyle(.roundedBorder)
            .focused($searching)
            .help("Search (⌘F)")
            .background {  // ⌘F puts the keyboard in the field, as in a Mac app
                Button("") { searching = true }.keyboardShortcut("f").opacity(0).accessibilityHidden(true)
            }
    }

    @ViewBuilder private func choices(_ counts: [String: Int]) -> some View {
        Picker("Show", selection: $model.filter) {
            ForEach(words.filters, id: \.group) { group in
                Section(group.group) {
                    ForEach(group.keys, id: \.self) { key in
                        Text("\(key.last ?? "") (\(counts[key.first ?? ""] ?? 0))").tag(key.first ?? "")
                    }
                }
            }
        }
        .fixedSize()
        Picker("Sort", selection: $model.sort) {
            ForEach(model.books?.sorts ?? [], id: \.key) { sort in Text(sort.label).tag(sort.key) }
        }
        .fixedSize()
        SetAll(model: model, syncs: words.syncs)
    }
}

/// Set all: Sync for every book in the list as it is shown, asked first.
struct SetAll: View {
    @ObservedObject var model: WindowModel
    let syncs: [[String]]
    @State private var asked: [String]?  // the Sync chosen, while the question is open

    var body: some View {
        let n = model.shownBooks.count
        Menu("Set all \(n)") {
            ForEach(syncs, id: \.self) { sync in Button("Sync: \(sync.last ?? "")") { asked = sync } }
        }
        .fixedSize()
        .disabled(n == 0)
        .confirmationDialog(
            "Set Sync to \(asked?.last ?? "") for \(n == 1 ? "1 book" : "\(n) books")?",
            isPresented: Binding(get: { asked != nil }, set: { if !$0 { asked = nil } })
        ) {
            Button("Set \(n == 1 ? "1 book" : "\(n) books")") {
                if let key = asked?.first { model.setAll(key) }
                asked = nil
            }
        } message: {
            Text("Every book in the list as it is shown now, also those further down.")
        }
    }
}

/// Every mark the list can hold, with what it means (the page's Legend Rule).
struct Legend: View {
    let legend: [[String]]

    var body: some View {
        Flow(spacing: 14, lineSpacing: 4) {
            ForEach(legend, id: \.self) { item in
                HStack(spacing: 5) {
                    Mark(state: item.first ?? "", size: 16, dash: Pencil.faint)  // bare, as the page's legend draws them
                    Text(item.last ?? "")
                }
                .fixedSize()
            }
        }
        .font(.caption)
        .foregroundStyle(Pencil.graphite)
        .accessibilityElement(children: .combine)
    }
}

/// Items side by side, on as many lines as the width needs.
struct Flow: Layout {
    var spacing: CGFloat
    var lineSpacing: CGFloat

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        let rows = lines(subviews, width)
        let height = rows.reduce(0) { $0 + $1.height } + lineSpacing * CGFloat(max(rows.count - 1, 0))
        return CGSize(width: proposal.width ?? rows.map(\.width).max() ?? 0, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var y = bounds.minY
        for row in lines(subviews, bounds.width) {
            var x = bounds.minX
            for n in row.items {
                let size = subviews[n].sizeThatFits(.unspecified)
                subviews[n].place(at: CGPoint(x: x, y: y + (row.height - size.height) / 2), proposal: .unspecified)
                x += size.width + spacing
            }
            y += row.height + lineSpacing
        }
    }

    private func lines(_ subviews: Subviews, _ width: CGFloat) -> [(items: [Int], width: CGFloat, height: CGFloat)] {
        var out: [(items: [Int], width: CGFloat, height: CGFloat)] = []
        for (n, view) in subviews.enumerated() {
            let size = view.sizeThatFits(.unspecified)
            if let last = out.last, last.width + spacing + size.width <= width {
                out[out.count - 1] = (last.items + [n], last.width + spacing + size.width, max(last.height, size.height))
            } else {
                out.append(([n], size.width, size.height))
            }
        }
        return out
    }
}

/// The list in two sides (DESIGN.md, Two Sides): each book's Kobo side on the grey (how far, the
/// cover in grey, the title, the Kobo's gauge, Sync and State), the seam with the book's disc, and
/// Hardcover's side on the white (the cover in colour once it syncs and has its match, and what the
/// next sync does with it). Not a table: its columns cannot carry the two grounds and the seam
/// between them, and its selection would cover both. A click or the arrows open a book's Details;
/// the open book's Kobo side takes the Blue Wash.
struct BooksTable: View {
    @ObservedObject var model: WindowModel
    @FocusState private var focused: Bool

    var body: some View {
        GeometryReader { box in
            let shape = RowShape(width: box.size.width)
            let shown = model.shownBooks
            VStack(spacing: 0) {
                BooksHead(shape: shape)
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(shown) { book in
                                let chosen = model.chosenBook == book.id
                                BookRow(model: model, book: book, shape: shape, chosen: chosen)
                                    .contentShape(Rectangle())
                                    .onTapGesture {  // a click opens its Details, as a table's selection did
                                        model.chosenBook = book.id
                                        focused = true
                                    }
                                    .contextMenu { Button(model.pageTitle) { openAt(book.id) } }
                                    .accessibilityElement(children: .contain)
                                    .accessibilityAddTraits(chosen ? .isSelected : [])
                                    .accessibilityAction(named: "Show Details") { model.chosenBook = book.id }
                                    .id(book.id)
                            }
                        }
                    }
                    .focusable()
                    .withoutFocusRing()  // the open row's wash shows where the keyboard is
                    .focused($focused)
                    .onMoveCommand { move($0, in: shown) }
                    .onChange(of: model.chosenBook) { id in
                        if let id, shown.contains(where: { $0.id == id }) { proxy.scrollTo(id) }  // the arrows keep it in sight
                    }
                }
            }
            .background { shape.sides }  // under the last row the two sides run on to the foot
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Books")
    }

    /// Up and down move the open book along the list, as in a table.
    private func move(_ direction: MoveCommandDirection, in shown: [BooksAnswer.Book]) {
        guard !shown.isEmpty else { return }
        let at = shown.firstIndex { $0.id == model.chosenBook }
        switch direction {
        case .up: model.chosenBook = shown[max((at ?? 1) - 1, 0)].id
        case .down: model.chosenBook = shown[min((at ?? -1) + 1, shown.count - 1)].id
        default: return
        }
    }
}

/// Where the sides of the list fall at this width: Hardcover's side a third of it, at most 420 points.
/// Narrow (Details open beside it), Sync and State go under the book, and the figures are smaller.
struct RowShape {
    let width: CGFloat
    var compact: Bool { width < 940 }
    var hardcover: CGFloat { compact ? max(150, width * 0.36) : min(420, max(220, width * 0.34)) }
    static let sync: CGFloat = 90
    static let state: CGFloat = 150

    var sides: some View {
        HStack(spacing: 0) {
            Pencil.ground
            Pencil.ink.frame(width: 2)
            Pencil.sheet.frame(width: hardcover)
        }
    }
}

/// The heads of the list's columns, on their sides.
struct BooksHead: View {
    let shape: RowShape

    var body: some View {
        HStack(spacing: 0) {
            HStack(spacing: 0) {
                Text("Book").frame(maxWidth: .infinity, alignment: .leading)
                if !shape.compact {
                    Text("Sync").frame(width: RowShape.sync, alignment: .leading)
                    Text("State").frame(width: RowShape.state, alignment: .leading)
                }
            }
            .padding(.leading, shape.compact ? 14 : 24)
            .padding(.trailing, 18)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Pencil.ground)
            Pencil.ink.frame(width: 2)
            Text("Hardcover status").padding(.leading, 24).frame(width: shape.hardcover, alignment: .leading)
                .frame(maxHeight: .infinity).background(Pencil.sheet)
        }
        .font(.system(size: 12, weight: .semibold))
        .foregroundStyle(Pencil.graphite)
        .frame(height: 30)
        .overlay(alignment: .top) { Pencil.rule.frame(height: 1) }
        .accessibilityElement(children: .ignore)
        .accessibilityHidden(true)  // each row says its own: the book, Sync, State, the Hardcover status
    }
}

/// A book in the list, its two sides and the seam between them, the disc centred on the seam.
struct BookRow: View {
    @ObservedObject var model: WindowModel
    let book: BooksAnswer.Book
    let shape: RowShape
    let chosen: Bool

    var body: some View {
        let words = model.books?.words
        HStack(spacing: 0) {
            HStack(alignment: .center, spacing: 0) {
                VStack(alignment: .leading, spacing: 8) {
                    BookCell(book: book, compact: shape.compact)
                    if shape.compact {
                        HStack(alignment: .top, spacing: 6) { sync(words); state(words) }.padding(.leading, 96)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if !shape.compact {
                    sync(words).frame(width: RowShape.sync, alignment: .leading)
                    state(words).frame(width: RowShape.state, alignment: .leading)
                }
            }
            .padding(.leading, shape.compact ? 14 : 24)
            .padding(.trailing, 18)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
            .background(chosen ? Pencil.blueWash : Pencil.ground)
            .overlay(alignment: .top) { Pencil.rule.frame(height: 1) }
            Pencil.ink.frame(width: 2)
                .frame(maxHeight: .infinity)
                .overlay { Disc(state: book.status.kind, size: 24).fixedSize().accessibilityHidden(true) }  // the cell says it in words
                .zIndex(1)
            StatusCell(book: book, cover: true)
                .padding(.leading, 24)
                .padding(.trailing, shape.compact ? 12 : 24)
                .padding(.vertical, 10)
                .frame(width: shape.hardcover, alignment: .leading)
                .frame(maxHeight: .infinity)
                .background(Pencil.sheet)
                .overlay(alignment: .top) { Pencil.ruleSoft.frame(height: 1) }
        }
        .fixedSize(horizontal: false, vertical: true)  // both sides as tall as the taller
    }

    private func sync(_ words: BooksAnswer.Words?) -> some View {
        WordPicker(label: "Sync", options: words?.syncs ?? [], selection: model.binding(book.id, \.sync) { ["--sync", $0] })
    }

    private func state(_ words: BooksAnswer.Words?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            WordPicker(label: "State", options: words?.states ?? [], selection: model.stateBinding(book))
            if !book.stateDate.isEmpty {
                Text(book.stateDate).font(.caption).foregroundStyle(Pencil.graphite).padding(.leading, 4)
            }
        }
    }
}

/// A row's choice of the page's words: a pop-up menu, small.
struct WordPicker: View {
    let label: String
    let options: [[String]]
    @Binding var selection: String

    var body: some View {
        Picker(label, selection: $selection) {
            ForEach(options, id: \.self) { option in Text(option.last ?? "").tag(option.first ?? "") }
        }
        .labelsHidden()
        .pickerStyle(.menu)
        .controlSize(.small)
        .fixedSize()
    }
}

extension WindowModel {
    /// The page outside the app, by the one name it has everywhere: the server's by its name, else the page this Mac serves.
    var pageTitle: String { pageName(mode: status?.mode ?? "", server: status?.server ?? "") }
}

/// "Open on kobo.example.org" with a server, else "Open in Browser": every button that opens the page says this.
/// `short`, inside a form, says "the server" for a host too long for a button there.
func pageName(mode: String, server: String, short: Bool = false) -> String {
    if mode == "server", let host = URL(string: server)?.host { return "Open on \(short && host.count > 20 ? "the server" : host)" }
    return "Open in Browser"
}

/// The page, at this book: for what the app does not change.
func openAt(_ id: String) {
    DispatchQueue.global(qos: .userInitiated).async { _ = tool(["open", "--book", id]) }
}

/// The page, at its start; off the window's thread, as the tool takes a moment to start.
func openThePage() {
    DispatchQueue.global(qos: .userInitiated).async { _ = tool(["open"]) }
}

/// The Kobo's side of a book: how far, large; the cover in grey (faded when it does not sync);
/// the title, the author with when it was last read, and the Kobo's gauge.
struct BookCell: View {
    let book: BooksAnswer.Book
    var compact = false

    var body: some View {
        OnSelection { selected in
            HStack(alignment: .center, spacing: compact ? 10 : 14) {
                Percent(percent: book.percent, size: compact ? 22 : 30, quiet: book.percent == 0)
                    .frame(width: compact ? 50 : 68, alignment: .trailing)
                Cover(path: book.cover, width: compact ? 26 : 34, grey: true).background(Pencil.sheet).coverShadow().opacity(book.syncs ? 1 : 0.6)
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Text(book.title).font(titleFont(15)).foregroundStyle(pencil(Pencil.ink, selected)).lineLimit(2)
                        if book.new {
                            Text("Auto").font(.caption2.weight(.semibold)).foregroundStyle(pencil(Pencil.blue, selected))
                                .padding(.horizontal, 4).overlay(RoundedRectangle(cornerRadius: 3).stroke(pencil(Pencil.blue, selected), lineWidth: 0.75))
                                .help("First opened on this Kobo after this tool started: syncs by itself unless switched off.")
                        }
                        if book.audio == true {
                            Text("Audiobook").font(.caption2.weight(.semibold)).foregroundStyle(quiet(selected))
                                .padding(.horizontal, 4).overlay(RoundedRectangle(cornerRadius: 3).stroke(quiet(selected), lineWidth: 0.75))
                                .help("An audiobook: off until you switch it on. Hardcover then gets its status and dates on an audiobook edition, and no progress.")
                        }
                    }
                    Text(bookByline(book)).font(.system(size: 12).monospacedDigit()).foregroundStyle(quiet(selected)).lineLimit(1)
                    Gauge(percent: book.percent, finished: book.finished, quiet: !book.syncs).padding(.top, 1)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }

}

/// "Herman Melville, last read 30 Sep 2026, 4 h read": the facts after the author, without the percentage the large figure says.
func bookByline(_ book: BooksAnswer.Book) -> String {
    let facts = book.facts.filter { !($0.hasSuffix("%") && Int($0.dropLast()) != nil) }
        .map { $0.prefix(1).lowercased() + $0.dropFirst() }
    return ([book.author].filter { !$0.isEmpty } + facts).joined(separator: ", ")
}

/// Hardcover's side of a book: what the next sync does with it, in words beside its mark (in the
/// list the mark is the disc on the seam; elsewhere it stands bare before the words). The first line in its mark's
/// colour; for a change the old value struck in red and the new one after a caret; then the edition.
/// On the list, the cover in colour once the book syncs and has its match on Hardcover.
struct StatusCell: View {
    let book: BooksAnswer.Book
    var chosen = false  // its row is the selection: grey, not blue, while the window or the table is in the back
    var cover = false  // on the list
    var mark = false  // off the seam (Details, the EPUB Folder's table): the mark bare before the words

    var body: some View {
        OnSelection { selected in
            HStack(alignment: .center, spacing: 12) {
                if mark { Mark(state: book.status.kind, size: 17) }
                if cover && book.syncs && !book.details.link.isEmpty {
                    Cover(path: book.cover, width: 26).background(Pencil.sheet).coverShadow()
                }
                VStack(alignment: .leading, spacing: 2) {
                    first(selected)
                    if kind == "next" && book.status.text.contains(":") {  // as the page: a change it can say
                        Correction(book: book, selected: selected, chosen: chosen)
                    } else if kind != "next" && !rest.isEmpty {
                        Text(rest).font(.system(size: 13)).foregroundStyle(pencil(Pencil.ink, selected)).lineLimit(2)
                    }
                    if !book.edition.isEmpty {
                        HStack(spacing: 4) {
                            if book.stet { Mark(state: "stet", size: 14) }
                            Text(book.edition).lineLimit(1)
                        }
                        .font(.caption).foregroundStyle(quiet(selected))
                    }
                }
            }
        }
        .padding(.vertical, 2)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel([book.status.text, book.edition].filter { !$0.isEmpty }.joined(separator: ". "))
    }

    private var kind: String { book.status.kind }

    /// "Next sync", not "Next sync: …": the correction says the rest.
    private var headline: String { String(book.status.text.split(separator: ":", maxSplits: 1).first ?? "") }
    private var rest: String {
        book.status.text.split(separator: ":", maxSplits: 1).dropFirst().first.map { $0.trimmingCharacters(in: .whitespaces) } ?? ""
    }

    /// The first line: small and bold over a second line, in the colour of the mark; a failure reversed out of ink.
    @ViewBuilder private func first(_ selected: Bool) -> some View {
        let over = kind == "next" || !rest.isEmpty  // a line follows it
        switch kind {
        case "next":
            Text(headline).font(.system(size: over ? 11.5 : 13, weight: .bold)).foregroundStyle(sends(selected, chosen: chosen))
        case "ok":
            Text(headline).font(.system(size: over ? 11.5 : 13, weight: over ? .bold : .semibold)).foregroundStyle(pencil(Pencil.green, selected))
        case "warn":
            Text(headline).font(.system(size: 13, weight: .semibold)).foregroundStyle(pencil(Pencil.blue, selected))
        case "err":
            Text(headline).font(.system(size: 11.5, weight: .bold)).foregroundStyle(selected ? Color(nsColor: .selectedContentBackgroundColor) : Pencil.onFlag)
                .padding(.horizontal, 5).padding(.vertical, 1)
                .background(RoundedRectangle(cornerRadius: 2).fill(selected ? onSelection : Pencil.flag))
        default:
            Text(headline).font(.system(size: 13)).foregroundStyle(quiet(selected))
        }
    }
}

struct Correction: View {
    let book: BooksAnswer.Book
    var selected = false
    var chosen = false

    var body: some View {
        let rest = book.status.text.split(separator: ":", maxSplits: 1).dropFirst().first.map { $0.trimmingCharacters(in: .whitespaces) } ?? ""
        let (kept, was, now) = book.correction.count == 3 ? (book.correction[0], book.correction[1], book.correction[2]) : ("", "", rest)
        HStack(spacing: 4) {
            if !kept.isEmpty { Text(kept) }
            if !was.isEmpty { Text(was).strikethrough(color: selected ? onSelection : chosen ? Pencil.redHeld : Pencil.red).foregroundStyle(quiet(selected)) }
            Mark(state: "next", size: 10)
            Text(now).fontWeight(.bold).foregroundStyle(sends(selected, chosen: chosen))
        }
        .font(.system(size: 13))
        .lineLimit(1)
    }
}

/// What the tool said when it changed nothing, without its name in front.
func said(_ why: NoAnswer) -> String {
    let text = why.said.split(separator: "\n").last.map(String.init) ?? why.said
    return text.hasPrefix("lastread: ") ? String(text.dropFirst("lastread: ".count)) : text
}

/// Everything known of one book, as the page's Details has it, with the changes the page makes.
struct DetailsPane: View {
    @ObservedObject var model: WindowModel
    let book: BooksAnswer.Book
    let words: BooksAnswer.Words
    var spread = false  // beside the cover large (Covers): no small cover, a larger title
    @State private var looking = ""  // what to search Hardcover for
    @State private var removing = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top, spacing: 12) {
                    if !spread { Cover(path: book.cover, width: 56) }
                    VStack(alignment: .leading, spacing: 3) {
                        Text(book.title).font(titleFont(spread ? 28 : 18)).fixedSize(horizontal: false, vertical: true)
                            .accessibilityAddTraits(.isHeader)
                        Text(book.author).font(spread ? .title3 : .body).foregroundStyle(Pencil.graphite)
                    }
                    Spacer(minLength: 0)
                    if model.changing.contains(book.id) { ProgressView().controlSize(.small) }
                    Button {
                        model.chosenBook = nil
                    } label: {
                        Image(systemName: "xmark")
                    }
                    .buttonStyle(.borderless)
                    .keyboardShortcut(model.enlarged == nil ? .cancelAction : nil)  // Escape closes the cover over it first
                    .accessibilityLabel("Close Details")
                }
                StatusCell(book: book, mark: true)
                Grid(alignment: .leading, horizontalSpacing: 10, verticalSpacing: 6) {
                    GridRow {
                        Text("Sync").foregroundStyle(Pencil.graphite)
                        WordPicker(label: "Sync", options: words.syncs, selection: model.binding(book.id, \.sync) { ["--sync", $0] })
                    }
                    GridRow {
                        Text("State").foregroundStyle(Pencil.graphite)
                        WordPicker(label: "State", options: words.states, selection: model.stateBinding(book))
                    }
                    if ["finished", "rereading"].contains(book.state) {
                        GridRow {
                            Text("Since").foregroundStyle(Pencil.graphite)
                            if let date = day(book.stateDate) {
                                DatePicker("Since", selection: Binding(get: { date }, set: { since($0) }), displayedComponents: .date)
                                    .labelsHidden().controlSize(.small).fixedSize()
                            } else {
                                Button("Add a date") { since(Date()) }.controlSize(.small)
                            }
                        }
                    }
                }
                .font(.callout)
                if needsMatch { match }
                pairs(words.sections.first ?? "", book.details.kobo.filter { !["Sync", "State"].contains($0.first ?? "") })
                pairs(words.sections.last ?? "", book.details.hardcover)
                HStack {
                    if let link = URL(string: book.details.link), !book.details.link.isEmpty {
                        Button("Open on Hardcover") { NSWorkspace.shared.open(link) }
                    }
                    Button(model.pageTitle) { openAt(book.id) }
                        .help("This book on the page with your books, in your browser")
                }
                if book.details.onShelf {
                    Button("Remove from Hardcover…", role: .destructive) { removing = true }
                        .confirmationDialog("Remove “\(book.title)” from your Hardcover shelf?", isPresented: $removing) {
                            Button("Remove", role: .destructive) { model.change(book.id, ["--remove"]) }
                        } message: {
                            Text("It is taken off the shelf on Hardcover now, with its reading dates, and no longer synced.")
                        }
                }
            }
            .padding(16)
            .textSelection(.enabled)
            .disabled(model.changing.contains(book.id))
        }
        .onChange(of: book.id) { _ in looking = "" }
    }

    /// No match yet: the books it could be, and looking for others.
    private var needsMatch: Bool { book.details.link.isEmpty && (book.status.kind == "warn" || !book.details.candidates.isEmpty) }

    private var match: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Which book is it?").font(.headline).accessibilityAddTraits(.isHeader)
            if book.details.candidates.isEmpty {
                Text("Hardcover found nothing for it. Look for it by another title. A book Hardcover does not have yet has to be added there first.")
                    .font(.callout).foregroundStyle(Pencil.graphite)
            }
            ForEach(book.details.candidates, id: \.id) { c in
                HStack(alignment: .firstTextBaseline) {
                    VStack(alignment: .leading, spacing: 1) {
                        Text(c.title).font(titleFont(13, .regular))
                        if !c.author.isEmpty { Text(c.author).font(.caption).foregroundStyle(Pencil.graphite) }
                    }
                    Spacer(minLength: 6)
                    Button("Use") { model.change(book.id, ["--pick", String(c.id)]) }.controlSize(.small)
                }
            }
            HStack {
                TextField("Title or author", text: $looking).textFieldStyle(.roundedBorder).onSubmit(look)
                Button("Search Hardcover", action: look).disabled(looking.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            .controlSize(.small)
        }
    }

    private func look() {
        let q = looking.trimmingCharacters(in: .whitespaces)
        if !q.isEmpty { model.change(book.id, ["--search", q]) }
    }

    private func day(_ text: String) -> Date? {
        let read = DateFormatter()
        read.dateFormat = "yyyy-MM-dd"
        read.locale = Locale(identifier: "en_US_POSIX")
        return text.isEmpty ? nil : read.date(from: text)
    }

    private func since(_ date: Date) {
        let write = DateFormatter()
        write.dateFormat = "yyyy-MM-dd"
        write.locale = Locale(identifier: "en_US_POSIX")
        let text = write.string(from: date)
        guard text != book.stateDate else { return }  // the same day again, as a redraw may set it: no change
        let (id, state) = (book.id, book.state)
        DispatchQueue.main.async { model.change(id, ["--state", state, "--date", text]) { $0.stateDate = text } }
    }

    @ViewBuilder private func pairs(_ title: String, _ pairs: [[String]]) -> some View {
        if !pairs.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.headline).accessibilityAddTraits(.isHeader)
                ForEach(pairs, id: \.self) { pair in
                    HStack(alignment: .firstTextBaseline) {
                        Text(pair.first ?? "").foregroundStyle(Pencil.graphite).frame(width: 96, alignment: .leading)
                        Text(pair.last ?? "").fixedSize(horizontal: false, vertical: true)
                    }
                    .font(.callout)
                }
            }
        }
    }
}
