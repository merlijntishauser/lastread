// Release Notes (Help menu, Notes.swift): the releases in the CHANGELOG.md
// the app carries in its Resources (build.sh copies it there). Foundation
// only, so CI can read the repository's own CHANGELOG with it
// (CheckSamples.swift).

import Foundation

/// One released version, as the changelog has it.
struct Release: Identifiable, Equatable {
    var id: String { version }
    let version: String
    let date: String  // as written: 2026-11-03
    var parts: [Part] = []

    /// Added, Changed, Fixed…: a heading and its items.
    struct Part: Equatable {
        let heading: String
        var items: [Item] = []
    }

    /// A list item (level 0, or 1 when nested), or a paragraph (level -1), in inline Markdown.
    struct Item: Equatable {
        let level: Int
        var text: String
    }
}

/// The released versions, newest first, at most `count`. Unreleased is left out.
func changelogReleases(_ changelog: String, count: Int = .max) -> [Release] {
    var found: [Release] = []
    var current: Release?
    var blank = false  // a blank line since the last item: what follows starts anew
    func close() {
        if let c = current, !c.parts.isEmpty { found.append(c) }
        current = nil
    }
    for raw in changelog.components(separatedBy: "\n") {
        let line = raw.trimmingCharacters(in: .whitespaces)
        if raw.hasPrefix("## ") {
            close()
            if found.count == count { return found }
            let words = raw.dropFirst(3).components(separatedBy: " - ")  // "0.23.1 - 2026-11-03"
            if words.count == 2, words[0].first?.isNumber == true {
                current = Release(version: words[0].trimmingCharacters(in: .whitespaces), date: words[1].trimmingCharacters(in: .whitespaces))
            }
            continue
        }
        guard var release = current else { continue }
        defer { current = release }
        if raw.hasPrefix("### ") {
            release.parts.append(.init(heading: String(raw.dropFirst(4))))
            blank = false
            continue
        }
        if line.isEmpty {
            blank = true
            continue
        }
        if release.parts.isEmpty { release.parts.append(.init(heading: "")) }
        let p = release.parts.count - 1
        let indent = raw.prefix { $0 == " " }.count
        if line.hasPrefix("- ") {
            release.parts[p].items.append(.init(level: min(indent / 2, 1), text: String(line.dropFirst(2))))
        } else if let last = release.parts[p].items.indices.last, !blank || indent > 0 {
            release.parts[p].items[last].text += " " + line  // a wrapped line goes on with the item above
        } else {
            release.parts[p].items.append(.init(level: -1, text: line))
        }
        blank = false
    }
    close()
    return Array(found.prefix(count))
}
