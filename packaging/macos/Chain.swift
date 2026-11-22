// The overview (docs/plans/2026-10-24-mac-app-native-books-design.md): the
// sync drawn as the path it takes, Kobo → This Mac → (Server) → Hardcover,
// each link with its mark in a disc, in the page's colours (DESIGN.md, Two
// Sides): your links on the Kobo's grey, Hardcover on the white past the
// seam, and the hop between them as a disc on the seam (Window.swift).

import AppKit
import SwiftUI

// ---------- the chain ----------
/// A link of the chain: a part the sync passes through, with the checks of `doctor` about it.
struct ChainLink: Identifiable {
    let id: String  // "Kobo", "This Mac", "Server", "Hardcover"
    let checks: [Check]
    let line: String  // how it is, in a few words, when nothing is wrong with it

    /// The worst of its checks, else what its own check says: a Kobo not
    /// plugged in, or Hardcover not connected yet, is the dash, never a warning.
    var state: String {
        if checks.contains(where: { $0.state == "fail" }) { return "fail" }
        if checks.contains(where: { $0.state == "warn" }) { return "warn" }
        if checks.first(where: { $0.what == own })?.state == "note" { return "note" }
        return checks.isEmpty ? "note" : "ok"
    }

    /// The check that says whether the link itself is there.
    private var own: String {
        switch id {
        case "This Mac": return "Trigger"
        default: return id  // "Kobo", "Server", "Hardcover"
        }
    }

    /// What is wrong, else how it is.
    var said: String {
        checks.first { $0.state == "fail" }.map(\.found) ?? checks.first { $0.state == "warn" }.map(\.found) ?? line
    }
}

/// Where a step of `sync --steps` happens on the chain.
func linkOf(step: String) -> String {
    switch step {
    case "Kobo", "Collection", "Folder collection": return "Kobo"
    case "Upload": return "Server"
    case "Hardcover", "Matches": return "Hardcover"
    default: return "This Mac"
    }
}

extension WindowModel {
    /// The links in the order a sync takes them, from doctor's groups: the
    /// Server check is a link of its own, the notifications belong to this Mac.
    var links: [ChainLink] {
        let checks = (self.checks ?? []) + [notificationsCheck]
        let status = self.status
        let books = status?.books
        let server = status?.mode == "server"
        var out = [
            ChainLink(
                id: "Kobo", checks: checks.filter { $0.group == "Your Kobo" },
                line: status?.kobo != nil ? "Plugged in" : status?.lastSync?.date.map { "Last seen \(spokenInSentence($0))" } ?? "Not plugged in"),
            ChainLink(
                id: "This Mac", checks: checks.filter { ($0.group == "This computer" || $0.group == "Also") && $0.what != "Server" },
                line: "Syncs when the Kobo is plugged in"),
        ]
        if server {
            out.append(
                ChainLink(id: "Server", checks: checks.filter { $0.what == "Server" }, line: URL(string: status?.server ?? "")?.host ?? ""))
        }
        let who = hardcoverWho
        let hardcover: String
        if let who, !who.user.isEmpty {
            hardcover = who.live ? "Live · @\(who.user)" : "Dry run · @\(who.user)"
        } else if who == nil && server {
            hardcover = "Checked on the server"  // the server's books not answered yet
        } else {
            hardcover = "Not connected yet"
        }
        out.append(ChainLink(id: "Hardcover", checks: checks.filter { $0.group == "Hardcover" }, line: hardcover))
        return out
    }

    /// Who, and live or a dry run: from the status in local mode, from the books answer (the server's) in server mode.
    var hardcoverWho: (live: Bool, user: String)? {
        status?.books.map { ($0.live, $0.user) } ?? books.map { ($0.live, $0.user) }
    }

    /// The head of Hardcover's side of the overview: how the sync stands there.
    var hardcoverWord: String {
        guard let who = hardcoverWho, !who.user.isEmpty else { return status?.mode == "server" && hardcoverWho == nil ? "On the server" : "Not connected" }
        return who.live ? "Live" : "Dry run"
    }

    /// A link's state as the overview shows it: while a sync runs, how it went there so far.
    func shownState(_ link: ChainLink) -> String {
        let running = syncing || !elsewhere.isEmpty || outcome != nil
        return running ? passed[link.id] ?? link.state : link.state
    }

    /// The notifications as a check of this Mac: what only macOS knows.
    var notificationsCheck: Check {
        let (state, found): (String, String)
        switch notifications {
        case .denied: (state, found) = ("warn", "Off: a sync started by plugging in the Kobo does not say what it did.")
        case .notDetermined: (state, found) = ("note", "Not allowed yet: they say what a sync did.")
        default:
            (state, found) =
                previews == .never
                ? ("note", "On, but they show only the app's name: Show previews is Never in macOS's settings.")
                : ("ok", "On: each sync says what it did.")
        }
        return Check(group: "This computer", what: "Notifications", state: state, found: found, todo: "")
    }

    /// The links a sync now running has passed, with how it went there.
    var passed: [String: String] {
        var out: [String: String] = [:]
        for step in steps {
            let link = linkOf(step: step.step ?? "")
            let state = step.state ?? "note"
            if out[link] != "fail" && (out[link] != "warn" || state == "fail") { out[link] = state }
        }
        if out["Kobo"] != nil && out["This Mac"] == nil { out["This Mac"] = "ok" }  // the Mac read it
        return out
    }
}

/// Where the hop to Hardcover leaves your side: the disc of the last of your links, so that the
/// seam's disc stands level with it.
struct HopKey: PreferenceKey {
    static var defaultValue: Anchor<CGRect>?
    static func reduce(value: inout Anchor<CGRect>?, nextValue: () -> Anchor<CGRect>?) { value = value ?? nextValue() }
}

/// Your side of the chain: the Kobo, this Mac and the server, and the way out to the seam, where
/// Hardcover's side begins. A narrow window has the links from top to bottom.
struct ChainView: View {
    @ObservedObject var model: WindowModel
    @Binding var open: String?

    var body: some View {
        let links = model.links
        let mine = links.filter { $0.id != "Hardcover" }
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .top, spacing: 0) {
                ForEach(Array(mine.enumerated()), id: \.element.id) { n, link in
                    if n > 0 {
                        ArrowView(above: above(n, links), below: below(n, links), working: working(n, links), sends: sends(n, links))
                            .frame(minWidth: 64, maxWidth: 110)
                    }
                    linkView(link, hop: n == mine.count - 1).frame(width: 128)
                }
                if mine.count < links.count {  // the way to Hardcover, ending on the seam
                    ArrowView(
                        above: above(mine.count, links), below: below(mine.count, links), working: working(mine.count, links),
                        sends: sends(mine.count, links)
                    )
                    .frame(minWidth: 64, maxWidth: 110)
                    .padding(.trailing, -28)  // to the seam, through the side's own margin
                }
            }
            VStack(alignment: .leading, spacing: 4) {  // a narrow window: the chain from top to bottom
                ForEach(Array(mine.enumerated()), id: \.element.id) { n, link in linkView(link, hop: n == mine.count - 1) }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func linkView(_ link: ChainLink, hop: Bool) -> some View {
        LinkView(link: link, state: model.shownState(link), checking: model.checks == nil, chosen: open == link.id, hop: hop) {
            open = open == link.id ? "" : link.id
        }
    }

    /// The counts the arrows carry, in local mode, where the books are on this Mac.
    private func above(_ n: Int, _ links: [ChainLink]) -> String {
        guard let books = model.status?.books else { return "" }
        switch links[n].id {
        case "This Mac": return "\(books.total) \(books.total == 1 ? "book" : "books")"
        case "Hardcover":
            if books.next == 0 { return books.on == 0 ? "None switched on" : "Nothing to send" }
            return books.live ? "\(books.next) to send" : "\(books.next) would be sent"
        default: return ""
        }
    }

    /// Live, with books to send: the count on the way to Hardcover is what the next sync sends.
    private func sends(_ n: Int, _ links: [ChainLink]) -> Bool {
        guard let books = model.status?.books else { return false }
        return links[n].id == "Hardcover" && books.live && books.next > 0
    }

    private func below(_ n: Int, _ links: [ChainLink]) -> String {
        guard links[n].id == "This Mac", let books = model.status?.books, !books.collection.isEmpty else { return "" }
        return "← \(books.on) in \(books.collection)"
    }

    /// The arrow a sync now running is working on: after the last link it passed.
    private func working(_ n: Int, _ links: [ChainLink]) -> Bool {
        guard model.outcome == nil else { return false }
        if !model.elsewhere.isEmpty && !model.syncing { return n == 1 }  // started by the Kobo: no steps come here
        guard model.syncing else { return false }
        let passed = model.passed
        let reached = links.prefix { passed[$0.id] != nil }.count
        return n == max(reached, 1)
    }
}

/// A link of your side of the chain, on the Kobo's grey: its disc, its name, and how it is in a few
/// words, in the colour of its mark when it needs you: blue for a question, ink for a failure.
struct LinkView: View {
    let link: ChainLink
    let state: String
    let checking: Bool
    let chosen: Bool
    var hop = false  // the last of your links: the seam's disc stands level with this one's
    let choose: () -> Void

    private var line: Color {
        switch state {
        case "warn": return Pencil.blue
        case "fail": return Pencil.ink
        default: return Pencil.graphite
        }
    }

    var body: some View {
        Button(action: choose) {
            VStack(spacing: 10) {
                Group {
                    if checking && link.id != "Kobo" && link.checks.count <= 1 {
                        ProgressView().controlSize(.small)
                    } else {
                        Disc(state: state, size: 40)
                    }
                }
                .frame(width: 40, height: 40)
                .anchorPreference(key: HopKey.self, value: .bounds) { hop ? $0 : nil }
                Text(link.id).font(.system(size: 16, weight: .bold)).foregroundStyle(Pencil.ink)
                Text(link.said).font(.system(size: 12.5, weight: state == "fail" ? .semibold : .regular)).foregroundStyle(line)
                    .multilineTextAlignment(.center).lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)  // wrapped in the link's width: the overview scrolls, nothing is pushed
            }
            .padding(.vertical, 12)
            .padding(.horizontal, 6)
            .frame(maxWidth: .infinity)
            .overlay(alignment: .bottom) {  // the open link: a rule under it, as the page marks where you are
                if chosen { Rectangle().fill(Pencil.ink).frame(height: 2).padding(.horizontal, 18) }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(chosen ? .isSelected : [])
        .accessibilityHint(chosen ? "Hides its checks" : "Shows its checks")
    }
}

/// Hardcover, on the white past the seam: a book as it lies on the shelf there (the last read that
/// syncs and has its match, in colour), the name and how it is. Its mark is the disc on the seam.
struct HardcoverLink: View {
    @ObservedObject var model: WindowModel
    let link: ChainLink
    let chosen: Bool
    let choose: () -> Void

    var body: some View {
        let state = model.shownState(link)
        Button(action: choose) {
            VStack(spacing: 10) {
                if let book = shelved { Cover(path: book.cover, width: 64).background(Pencil.sheet).coverShadow().padding(.bottom, 4) }
                Text(link.id).font(.system(size: 16, weight: .bold)).foregroundStyle(Pencil.ink)
                Text(link.said).font(.system(size: 12.5, weight: state == "fail" ? .semibold : .regular))
                    .foregroundStyle(state == "warn" ? Pencil.blue : state == "fail" ? Pencil.ink : Pencil.graphite)
                    .multilineTextAlignment(.center).lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)  // wrapped in the link's width: the overview scrolls, nothing is pushed
            }
            .padding(.vertical, 12)
            .padding(.horizontal, 6)
            .frame(maxWidth: .infinity)
            .overlay(alignment: .bottom) {
                if chosen { Rectangle().fill(Pencil.ink).frame(height: 2).padding(.horizontal, 18) }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Hardcover, \(markWords(state)). \(link.said)")
        .accessibilityAddTraits(chosen ? [.isButton, .isSelected] : .isButton)
        .accessibilityHint(chosen ? "Hides its checks" : "Shows its checks")
    }

    /// The book read last that syncs and has its match on Hardcover, with a cover.
    private var shelved: BooksAnswer.Book? {
        model.books?.books.filter { $0.syncs && !$0.details.link.isEmpty && !$0.cover.isEmpty && $0.opened }
            .max { $0.lastRead < $1.lastRead }
    }
}

/// The way from one link to the next, with the books it carries; while a
/// sync works on it, the page's red line gauge sweeps along it.
struct ArrowView: View {
    let above: String
    let below: String
    let working: Bool
    var sends = false  // what it carries goes to Hardcover at the next sync: in red, with the caret
    @Environment(\.accessibilityReduceMotion) private var still
    @State private var sweep = false

    var body: some View {
        VStack(spacing: 3) {
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                if sends { Mark(state: "next", size: 12).alignmentGuide(.firstTextBaseline) { $0[.bottom] - 2 } }
                Text(above).font(.caption.monospacedDigit().weight(sends ? .semibold : .regular))
                    .foregroundStyle(sends ? Pencil.red : Pencil.graphite).lineLimit(2).multilineTextAlignment(.center)
            }
            .frame(minHeight: 16, alignment: .bottom)
            GeometryReader { box in
                let w = box.size.width
                ZStack(alignment: .leading) {
                    Path { p in
                        p.move(to: CGPoint(x: 0, y: 5))
                        p.addLine(to: CGPoint(x: w - 1, y: 5))
                        p.move(to: CGPoint(x: w - 7, y: 1))
                        p.addLine(to: CGPoint(x: w - 1, y: 5))
                        p.addLine(to: CGPoint(x: w - 7, y: 9))
                    }
                    .stroke(Pencil.edge, style: StrokeStyle(lineWidth: 1.2, lineCap: .round, lineJoin: .round))
                    if working {
                        Rectangle().fill(Pencil.red).frame(width: still ? w - 8 : w / 3, height: 2)
                            .offset(x: still ? 0 : (sweep ? w * 2 / 3 - 8 : 0), y: 0)
                            .onAppear {
                                guard !still else { return }
                                withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) { sweep = true }
                            }
                            .onDisappear { sweep = false }
                    }
                }
            }
            .frame(height: 10)
            Text(below).font(.caption.monospacedDigit()).foregroundStyle(Pencil.graphite).lineLimit(2).multilineTextAlignment(.center)
        }
        .padding(.horizontal, 6)
        .padding(.top, 8)
        .accessibilityElement(children: .combine)
        .accessibilityLabel([above, below, working ? "Syncing" : ""].filter { !$0.isEmpty }.joined(separator: ", "))
    }
}
