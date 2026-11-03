// EPUB Folder: the books of the folder that goes on the Kobo at every
// plug-in (`to-kobo`, rules P1-P7, docs/plans/2026-11-01-to-kobo-folder-design.md),
// each with where it is with the Kobo and, once a sync has read it from
// the Kobo, its Hardcover status as Books has it. The folder is chosen
// here, in both modes: it is this Mac's, and this Mac does the copying.
// In the Finder it has the folder icon with the caret.

import AppKit
import SwiftUI
import UniformTypeIdentifiers

extension WindowModel {
    /// The folder and its books (`to-kobo --json`); with args a change, whose answer then gets.
    func loadFolder(_ args: [String] = [], then: @escaping (ToKoboAnswer) -> Void = { _ in }) {
        guard status?.mode == "local" || status?.mode == "server" else { return }
        // One look at a time. Reading a folder in Documents can wait on macOS's
        // question whether the app may; every refresh would start one more.
        let look = args.isEmpty
        if look {
            guard !folderAsking else { return }
            folderAsking = true
        }
        DispatchQueue.global(qos: .userInitiated).async {
            let found = answer(ToKoboAnswer.self, ["to-kobo"] + args + ["--json"])
            DispatchQueue.main.async {
                if look { self.folderAsking = false }
                switch found {
                case .success(let a):
                    self.folder = a
                    self.folderBroken = nil
                    FolderIcon.follow(a.folder, there: a.there)
                    then(a)
                case .failure(let why):
                    if !args.isEmpty {
                        self.problem = said(why)
                    } else if self.folder == nil {
                        self.folderBroken = why.said
                    }
                }
            }
        }
    }

    /// The book of Books this one of the folder is, once a sync has read it from the Kobo.
    func book(_ b: ToKoboAnswer.Book) -> BooksAnswer.Book? {
        b.ids.isEmpty ? nil : books?.books.first { b.ids.contains($0.id) }
    }
}

struct FolderPane: View {
    @ObservedObject var model: WindowModel
    @State private var chosen: String?  // a book's name in the folder
    @State private var tooMany: (folder: String, n: Int)?  // the folder asked for holds this many: asked first
    @State private var stopping = false
    @State private var waited = false  // the folder's first look is taking long

    var body: some View {
        Group {
            if let found = model.folder {
                if found.folder.isEmpty {
                    NoFolder(choose: choose)
                } else {
                    VStack(spacing: 0) {
                        FolderBar(found: found, choose: choose, stop: { stopping = true })
                        Divider()
                        if !found.there {
                            Spacer()
                            Text("The folder is not there. Plug in the disk it is on, or choose another.").foregroundStyle(Pencil.graphite)
                            Spacer()
                        } else if found.list.isEmpty {
                            Spacer()
                            Text("No EPUBs in this folder yet. Put one in, and it goes on the Kobo at the next plug-in.").foregroundStyle(Pencil.graphite)
                            Spacer()
                        } else {
                            FolderTable(model: model, found: found, chosen: $chosen)
                        }
                    }
                }
            } else if let broken = model.folderBroken {
                Galley { ProofSheet { Row(state: "fail", what: Pane.folder.rawValue, found: broken).onSheet() } }
            } else {
                VStack(spacing: 12) {
                    Spacer()
                    ProgressView().controlSize(.small)
                    if waited {
                        Text("Still waiting for the folder. If macOS asks whether \(name) may open it, answer that question.")
                            .foregroundStyle(Pencil.graphite)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 40)
                    }
                    Spacer()
                }
                .frame(maxWidth: .infinity)
                .task {  // a look takes a fraction of a second; longer, and something is in the way
                    try? await Task.sleep(nanoseconds: 5_000_000_000)
                    waited = true
                }
            }
        }
        .onAppear { model.loadFolder() }
        .confirmationDialog(
            "\(tooMany?.n ?? 0) books at once",
            isPresented: Binding(get: { tooMany != nil }, set: { if !$0 { tooMany = nil } })
        ) {
            Button("Put Them on the Kobo") {
                if let folder = tooMany?.folder { model.loadFolder([folder, "--yes"]) }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("All \(tooMany?.n ?? 0) books in \(tooMany?.folder ?? "") would go on the Kobo at the next plug-in.")
        }
        .confirmationDialog("Stop putting books on the Kobo?", isPresented: $stopping) {
            Button("Stop") { model.loadFolder(["--off"]) }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("No more books from \(model.folder?.folder ?? "the folder") go on the Kobo. The ones on it stay.")
        }
    }

    private func choose() {
        guard !isPreview else {
            model.problem = "The preview changes nothing on this Mac. The app would now ask for a folder whose books go on the Kobo."
            return
        }
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true  // New Folder: one just for the Kobo's books
        panel.allowsMultipleSelection = false
        panel.prompt = "Choose"
        panel.message = "The EPUBs in this folder go on the Kobo at every plug-in."
        if let now = model.folder?.folder, !now.isEmpty { panel.directoryURL = URL(fileURLWithPath: now).deletingLastPathComponent() }
        let chosen = { (response: NSApplication.ModalResponse) in
            guard response == .OK, let folder = panel.url?.path else { return }
            model.loadFolder([folder]) { a in
                if a.tooMany > 0 { tooMany = (folder, a.tooMany) }
            }
        }
        if let window = NSApp.keyWindow {
            panel.beginSheetModal(for: window, completionHandler: chosen)
        } else {
            chosen(panel.runModal())
        }
    }
}

/// No folder yet: what it does, and the way to one.
struct NoFolder: View {
    let choose: () -> Void

    var body: some View {
        Galley {
            SheetHead(Pane.folder.rawValue)
            ProofSheet {
                HStack(alignment: .top, spacing: 14) {
                    Image(nsImage: FolderIcon.image).resizable().frame(width: 48, height: 48).accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Books from other shops, on the Kobo").font(.headline)
                        Text("""
                            Choose a folder for EPUBs you bought elsewhere without DRM, or got for free. At every plug-in, \
                            the ones the Kobo has not had yet are copied to its folder Lastread, as kepub. \
                            Each book goes on each Kobo once; one you delete on the Kobo stays deleted. A book with DRM is not copied.
                            """)
                            .foregroundStyle(Pencil.graphite).fixedSize(horizontal: false, vertical: true)
                        Text("Once the Kobo has one, the next sync finds it on Hardcover by the ISBN in the book, and this list shows its Hardcover status too.")
                            .foregroundStyle(Pencil.graphite).fixedSize(horizontal: false, vertical: true)
                    }
                }
                .onSheet()
            }
            HStack {
                Spacer()
                Button("Choose a Folder…", action: choose)
            }
        }
    }
}

/// The folder: its icon, name and where it is; how many books, and how they go; Show in Finder, another, Stop.
struct FolderBar: View {
    let found: ToKoboAnswer
    let choose: () -> Void
    let stop: () -> Void

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            Image(nsImage: FolderIcon.image).resizable().frame(width: 36, height: 36).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(URL(fileURLWithPath: found.folder).lastPathComponent).font(.headline)
                Text(found.folder).font(.callout).foregroundStyle(Pencil.graphite).lineLimit(1).truncationMode(.middle).textSelection(.enabled)
                if found.there {
                    // No fixedSize here: a line that sizes itself to its height in this bar,
                    // above the table, made the whole window go blank (macOS 27, 0.23.1).
                    Text(state).font(.callout).foregroundStyle(Pencil.graphite).lineLimit(2)
                }
            }
            Spacer(minLength: 12)
            Button("Show in Finder") { NSWorkspace.shared.open(URL(fileURLWithPath: found.folder)) }.disabled(!found.there)
            Button("Choose Another…", action: choose)
            Button("Stop…", action: stop).help("No more books from this folder go on the Kobo; the ones on it stay")
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .accessibilityElement(children: .contain)
    }

    /// "12 books, as kepub. 2 wait for the next plug-in."
    private var state: String {
        let books = found.books == 1 ? "1 book" : "\(found.books) books"
        let how = found.kepubify.isEmpty ? "as EPUB (with kepubify installed, as kepub)" : "as kepub"
        let waiting = found.waiting == 0 ? "Every one is on a Kobo." : found.waiting == 1 ? "1 waits for the next plug-in." : "\(found.waiting) wait for the next plug-in."
        return "\(books), \(how). \(waiting)"
    }
}

struct FolderTable: View {
    @ObservedObject var model: WindowModel
    let found: ToKoboAnswer
    @Binding var chosen: String?

    var body: some View {
        Table(found.list, selection: $chosen) {
            TableColumn("Book") { b in FolderBookCell(book: b) }
                .width(min: 180, ideal: 260)
            TableColumn("Kobo") { b in KoboCell(book: b, kepub: !found.kepubify.isEmpty) }
                .width(min: 140, ideal: 180)
            TableColumn("Hardcover status") { b in
                if let book = model.book(b) {
                    StatusCell(book: book, chosen: chosen == b.id)
                } else {
                    NotYet(book: b)
                }
            }
            .width(min: 160, ideal: 220)
        }
        .contextMenu(forSelectionType: String.self) { names in
            if let name = names.first, let b = found.list.first(where: { $0.name == name }) {
                if model.book(b) != nil { Button("Show in Books") { show(b) } }
                Button("Show in Finder") { reveal(b) }
            }
        } primaryAction: { names in
            if let name = names.first, let b = found.list.first(where: { $0.name == name }) {
                if model.book(b) != nil { show(b) } else { reveal(b) }
            }
        }
    }

    /// Its row in Books, with its Details open.
    private func show(_ b: ToKoboAnswer.Book) {
        guard let book = model.book(b) else { return }
        model.chosenBook = book.id
        model.pane = .books
    }

    private func reveal(_ b: ToKoboAnswer.Book) {
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: found.folder).appendingPathComponent(b.name)])
    }
}

/// The book as it says it is, and its file.
struct FolderBookCell: View {
    let book: ToKoboAnswer.Book

    var body: some View {
        OnSelection { selected in
            VStack(alignment: .leading, spacing: 2) {
                Text(book.title.isEmpty ? book.name : book.title).font(titleFont(14)).lineLimit(2)
                if !book.author.isEmpty {
                    Text(book.author).font(.callout).foregroundStyle(quiet(selected)).lineLimit(1)
                }
                Text(book.name).font(.caption).foregroundStyle(quiet(selected)).lineLimit(1).truncationMode(.middle)
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }
}

/// Where the book is with the Kobo: on it (since when, and how), refused (why), or waiting.
struct KoboCell: View {
    let book: ToKoboAnswer.Book
    let kepub: Bool  // a book that waits goes as kepub

    var body: some View {
        OnSelection { selected in
            HStack(alignment: .top, spacing: 6) {
                Mark(state: mark, size: 16).padding(.top, 1)
                VStack(alignment: .leading, spacing: 2) {
                    Text(headline).font(.callout).fixedSize(horizontal: false, vertical: true)
                    if !more.isEmpty {
                        Text(more).font(.caption).foregroundStyle(quiet(selected)).fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel([headline, more].filter { !$0.isEmpty }.joined(separator: ". "))
    }

    private var mark: String {
        switch book.kobo {
        case "on": return "ok"
        case "refused": return "warn"
        default: return "wait"
        }
    }

    private var headline: String {
        switch book.kobo {
        case "on": return "On the Kobo"
        case "refused": return "Not put on the Kobo"
        default: return "At the next plug-in"
        }
    }

    private var more: String {
        switch book.kobo {
        case "on":
            let format = book.format == "kepub" ? "as kepub" : "as EPUB"
            guard let date = ISO8601DateFormatter().date(from: book.at) else { return format }
            return "\(format), \(date.formatted(date: .abbreviated, time: .omitted))"
        case "refused": return String(book.why.prefix(1)).uppercased() + String(book.why.dropFirst()) + "."
        default: return book.name.lowercased().hasSuffix(".kepub.epub") || kepub ? "As kepub" : "As EPUB"
        }
    }
}

/// No Hardcover status yet: on the Kobo, but not read from it by a sync; or not on the Kobo.
struct NotYet: View {
    let book: ToKoboAnswer.Book

    var body: some View {
        OnSelection { selected in
            HStack(alignment: .top, spacing: 6) {
                Mark(state: "none", size: 16).padding(.top, 1)
                VStack(alignment: .leading, spacing: 2) {
                    Text(headline).font(.callout).foregroundStyle(quiet(selected)).fixedSize(horizontal: false, vertical: true)
                    if book.kobo != "refused" {
                        Text(book.isbn.isEmpty ? "No ISBN in the book: to be found by title and author" : "To be found by its ISBN, \(book.isbn)")
                            .font(.caption).foregroundStyle(quiet(selected)).fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }

    private var headline: String {
        switch book.kobo {
        case "on": return "At the next sync: the Kobo adds it after the eject"
        case "refused": return "Not on the Kobo"
        default: return "Once it is on the Kobo"
        }
    }
}

/// The Finder's folder with the app's caret on it: the folder whose books go on the Kobo shows it.
/// Put on once per folder chosen, never over an icon the reader gave it, and taken off again
/// (only the one put here) when the folder is changed or stopped.
enum FolderIcon {
    static let image: NSImage = {
        let folder = NSWorkspace.shared.icon(for: .folder)
        let out = NSImage(size: NSSize(width: 512, height: 512))
        for px in [16, 32, 64, 128, 256, 512, 1024] {
            if let rep = drawn(folder, px) { out.addRepresentation(rep) }
        }
        return out
    }()

    private static let handled = "FolderIconFor"  // the folder last given the icon, or looked at for it
    private static let put = "FolderIconPut"  // the icon on it is this app's

    /// The folder of `to-kobo` as it is now: the icon on it, and off the one before.
    static func follow(_ folder: String, there: Bool) {
        guard !isPreview else { return }  // the preview changes nothing on this Mac
        let was = UserDefaults.standard.string(forKey: handled) ?? ""
        guard folder != was, folder.isEmpty || there else { return }
        if !was.isEmpty && UserDefaults.standard.bool(forKey: put) {
            NSWorkspace.shared.setIcon(nil, forFile: was, options: [])
        }
        let own = FileManager.default.fileExists(atPath: (folder as NSString).appendingPathComponent("Icon\r"))  // the reader's
        let done = !folder.isEmpty && !own && NSWorkspace.shared.setIcon(image, forFile: folder, options: [])
        UserDefaults.standard.set(folder, forKey: handled)
        UserDefaults.standard.set(done, forKey: put)
    }

    /// Remove…: the icon off the folder it is on, and nothing remembered of it.
    static func forget() {
        follow("", there: false)
        UserDefaults.standard.removeObject(forKey: handled)
        UserDefaults.standard.removeObject(forKey: put)
    }

    /// The caret of the app's icon (art.py: CARET, its width and red), smaller, on the folder's front.
    private static func drawn(_ folder: NSImage, _ px: Int) -> NSBitmapImageRep? {
        guard
            let rep = NSBitmapImageRep(
                bitmapDataPlanes: nil, pixelsWide: px, pixelsHigh: px, bitsPerSample: 8, samplesPerPixel: 4,
                hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
            let context = NSGraphicsContext(bitmapImageRep: rep)
        else { return nil }
        let side = CGFloat(px)
        rep.size = NSSize(width: side, height: side)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = context
        folder.draw(in: NSRect(x: 0, y: 0, width: side, height: side))
        let caret = NSBezierPath()  // y up: the caret's point on top, on the middle of the folder's front
        caret.move(to: NSPoint(x: side * 0.355, y: side * 0.30))
        caret.line(to: NSPoint(x: side * 0.5, y: side * 0.545))
        caret.line(to: NSPoint(x: side * 0.645, y: side * 0.30))
        caret.lineWidth = max(1.5, side * 0.085)
        caret.lineJoinStyle = .miter
        caret.miterLimit = 10
        NSColor(srgbRed: 0xe8 / 255, green: 0x34 / 255, blue: 0x3f / 255, alpha: 1).setStroke()
        caret.stroke()
        NSGraphicsContext.restoreGraphicsState()
        return rep
    }
}
