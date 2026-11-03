// CI: the app's reading of the tool's answers (Model.swift) against the
// samples in packaging/macos/samples, which the tool is held to as well
// (tests/test_app_answers.py). Built and run by the macos-app job:
//
//   swiftc -parse-as-library Model.swift Changelog.swift CheckSamples.swift -o check && ./check samples

import Foundation

@main
struct CheckSamples {
    static func main() throws {
        let folder = URL(fileURLWithPath: CommandLine.arguments.dropFirst().first ?? "samples")
        func text(_ name: String) throws -> String { try String(contentsOf: folder.appendingPathComponent(name), encoding: .utf8) }
        var failed = false
        func check<T>(_ name: String, _ result: Result<T, Error>, _ fine: (T) -> Bool) {
            switch result {
            case .success(let answer) where fine(answer):
                print("ok    \(name)")
            case .success:
                print("wrong \(name): read, but not as expected")
                failed = true
            case .failure(let error):
                print("fail  \(name): \(error)")
                failed = true
            }
        }
        check("status.json", decode(StatusAnswer.self, try text("status.json"))) { $0.lastSync?.date != nil && $0.kobo != nil }
        check("status-local.json", decode(StatusAnswer.self, try text("status-local.json"))) { $0.books?.needsMatch == 2 && $0.kobo == nil }
        check("books.json", decode(BooksAnswer.self, try text("books.json"))) {
            $0.books.first?.details.onShelf == true && $0.sorts.allSatisfy { $0.order == [0] } && $0.words.legend.count == 7
                && $0.start?.steps.map(\.state) == ["done", "done", "done", "now"] && $0.needsYou == nil && $0.tip?.rule == "left_off"
        }
        check("book.json", decode(BookAnswer.self, try text("book.json"))) {
            $0.book.details.candidates.first?.id == 12345 && $0.books.on == 41 && $0.tip == nil && $0.start == nil && $0.needsYou?.failed == 1
        }
        check("doctor.json", decode(DoctorAnswer.self, try text("doctor.json"))) { !$0.checks.isEmpty }
        check("history.json", decode(HistoryAnswer.self, try text("history.json"))) { $0.syncs.allSatisfy { $0.date != nil } }
        check("settings.json", decode(SettingsAnswer.self, try text("settings.json"))) { !$0.uploadTokenHash.isEmpty }
        let token = try text("token.jsonl").split(separator: "\n").map { decode(TokenLine.self, String($0)) }
        for (n, line) in token.enumerated() {
            check("token.jsonl line \(n + 1)", line) { n == token.count - 1 ? $0.done?.user == "sam" : $0.code == "ABCD-EFGH" }
        }
        check("update.json", decode(UpdateAnswer.self, try text("update.json"))) { $0.newer && !$0.latest.isEmpty }
        check("tokobo.json", decode(ToKoboAnswer.self, try text("tokobo.json"))) { $0.refused.first?.name == "Locked.epub" && $0.tooMany == 0 && $0.list.map(\.kobo) == ["on", "refused", "waiting"] }
        let lines = try text("steps.jsonl").split(separator: "\n").map { decode(StepLine.self, String($0)) }
        for (n, line) in lines.enumerated() {
            check("steps.jsonl line \(n + 1)", line) { n == lines.count - 1 ? $0.done?.finished?.first?.title == "Blindness" : $0.step != nil }
        }
        if case .success = decode(HistoryAnswer.self, #"{"schema": 2, "syncs": []}"#) {
            print("wrong another schema: read as if it were this one")
            failed = true
        } else {
            print("ok    another schema: refused")
        }
        // Release Notes (Changelog.swift) read the repository's own CHANGELOG.md, which build.sh puts in the app.
        let changelog = try String(contentsOf: folder.appendingPathComponent("../../../CHANGELOG.md").standardized, encoding: .utf8)
        let notes = changelogReleases(changelog)
        let sample = """
        ## Unreleased

        Nothing yet.

        ## 1.2.0 - 2026-12-01

        A paragraph
        on two lines.

        ### Fixed

        - **One** thing,
          wrapped.
        - Two:
          - nested,
            wrapped too.

        ## 1.1.0 - 2026-11-30

        ### Added

        - Three.
        """
        let read = changelogReleases(sample, count: 1)
        let expected = [Release(version: "1.2.0", date: "2026-12-01", parts: [
            .init(heading: "", items: [.init(level: -1, text: "A paragraph on two lines.")]),
            .init(heading: "Fixed", items: [.init(level: 0, text: "**One** thing, wrapped."), .init(level: 0, text: "Two:"), .init(level: 1, text: "nested, wrapped too.")]),
        ])]
        if read == expected {
            print("ok    a changelog: its parts, items, nesting and wrapped lines")
        } else {
            print("wrong a changelog: read as \(read)")
            failed = true
        }
        if notes.count > 3, notes.allSatisfy({ !$0.parts.isEmpty && $0.parts.allSatisfy { !$0.items.isEmpty } && $0.version.first?.isNumber == true }),
           notes.contains(where: { $0.parts.contains { $0.items.contains { $0.level == 1 } } }) {
            print("ok    CHANGELOG.md: \(notes.count) releases, the newest \(notes[0].version)")
        } else {
            print("wrong CHANGELOG.md: \(notes.count) releases, not as expected")
            failed = true
        }
        exit(failed ? 1 : 0)
    }
}
