// Release Notes, in the Help menu: what the latest releases changed, from
// the CHANGELOG.md in the app's Resources (Changelog.swift reads it), on the
// overview's paper. The newest first; all of them are on GitHub.

import AppKit
import SwiftUI

/// The releases the app carries: its own version and the ones before it.
func bundledReleases(count: Int = 6) -> [Release] {
    guard let url = Bundle.main.url(forResource: "CHANGELOG", withExtension: "md"),
          let text = try? String(contentsOf: url, encoding: .utf8) else { return [] }
    return changelogReleases(text, count: count)
}

struct NotesView: View {
    let releases: [Release]
    let running: String

    var body: some View {
        Galley {
            if releases.isEmpty {
                Text("This copy of \(name) has no release notes with it. They are on GitHub.").foregroundStyle(Pencil.graphite)
            }
            ForEach(releases) { release in
                HStack(alignment: .firstTextBaseline) {
                    SheetHead(release.version == running ? "\(release.version), this version" : release.version)
                    Spacer()
                    Text(day(release.date)).font(.callout).foregroundStyle(Pencil.graphite)
                }
                .padding(.top, release == releases.first ? 0 : 14)
                ProofSheet {
                    ForEach(Array(release.parts.enumerated()), id: \.offset) { n, part in
                        if n > 0 { SoftRule() }
                        VStack(alignment: .leading, spacing: 6) {
                            if !part.heading.isEmpty {
                                Text(part.heading).font(.subheadline.weight(.semibold)).foregroundStyle(Pencil.graphite)
                                    .accessibilityAddTraits(.isHeader)
                            }
                            ForEach(Array(part.items.enumerated()), id: \.offset) { _, item in
                                NoteLine(item: item)
                            }
                        }
                        .onSheet()
                    }
                }
            }
            if let link = URL(string: "https://github.com/merlijntishauser/lastread/releases") {
                Link("All release notes on GitHub", destination: link)
                    .padding(.top, 8).padding(.leading, 4)
            }
        }
        .frame(minWidth: 520, minHeight: 360)
    }

    /// 2026-11-03 as this Mac writes a date.
    private func day(_ written: String) -> String {
        let read = DateFormatter()
        read.locale = Locale(identifier: "en_US_POSIX")
        read.dateFormat = "yyyy-MM-dd"
        guard let date = read.date(from: written) else { return written }
        return date.formatted(date: .long, time: .omitted)
    }
}

/// One item: a bullet (indented when nested) or a paragraph, its inline Markdown set.
struct NoteLine: View {
    let item: Release.Item

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            if item.level >= 0 {
                Text(item.level == 0 ? "•" : "–").foregroundStyle(Pencil.faint).accessibilityHidden(true)
            }
            Text(marked(item.text)).foregroundStyle(Pencil.ink).lineSpacing(2).fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)
        }
        .padding(.leading, item.level > 0 ? 18 : 0)
    }

    private func marked(_ text: String) -> AttributedString {
        (try? AttributedString(markdown: text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(text)
    }
}
