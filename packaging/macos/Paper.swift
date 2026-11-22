// The paper both the window and the widget are drawn on (DESIGN.md, Two
// Sides): the page's colours, its marks and their discs, the title type, the
// Kobo's gauge and a cover.

import AppKit
import CoreImage
import CoreText
import ImageIO
import SwiftUI

// ---------- the page's colours, light and dark ----------
/// A colour of the page; `more` is the stronger pair Increase Contrast takes (light, dark).
func tone(_ light: Int, _ dark: Int, more: (Int, Int)? = nil) -> Color {
    Color(
        NSColor(name: nil) { look in
            let hex: Int
            switch look.bestMatch(from: [.aqua, .darkAqua, .accessibilityHighContrastAqua, .accessibilityHighContrastDarkAqua]) {
            case .darkAqua?: hex = dark
            case .accessibilityHighContrastDarkAqua?: hex = more?.1 ?? dark
            case .accessibilityHighContrastAqua?: hex = more?.0 ?? light
            default: hex = light
            }
            return NSColor(
                srgbRed: CGFloat(hex >> 16 & 0xff) / 255, green: CGFloat(hex >> 8 & 0xff) / 255, blue: CGFloat(hex & 0xff) / 255, alpha: 1)
        })
}

enum Pencil {
    // Two Sides (DESIGN.md): the Kobo's grey e-ink paper, Hardcover's white, ink between them.
    // With Increase Contrast, the words reach 7:1 on the grey and the rules 3:1.
    static let ground = tone(0xe2e1db, 0x2b2c28)  // e-ink paper: the Kobo's side, the run of covers, the panes
    static let sheet = tone(0xffffff, 0x171816)  // Hardcover's side, cards, notes, a cover's ground
    static let margin = tone(0xf2f1ec, 0x1f201d)  // a code or a token shown once
    static let ink = tone(0x1c1c1a, 0xecebe4)  // words, the seam, the read part of the Kobo's gauge
    static let graphite = tone(0x4b4a44, 0xb9b8af, more: (0x3d3c37, 0xcbcac2))  // what was found, facts, labels
    static let faint = tone(0x5a5953, 0xa5a49b, more: (0x46453f, 0xc0bfb7))  // the lightest grey a word may have
    static let edge = tone(0x76756d, 0x8d8c83, more: (0x5a5953, 0xa5a49b))  // fields, the gauge's dots, a grey disc's ring
    static let rule = tone(0xbdbcb4, 0x4a4b45, more: (0x7e7d76, 0x7a7a73))
    static let ruleSoft = tone(0xd3d2cb, 0x383934, more: (0x95958e, 0x656661))  // between rows on Hardcover's side
    static let red = tone(0xbb1d2a, 0xff7f86, more: (0x8a1520, 0xffa3a8))  // what a sync sends
    static let redHeld = tone(0xbb1d2a, 0xff9ba0, more: (0x87151e, 0xffd5d7))  // on a row chosen in a window in the back: 4.5:1 on its grey
    static let fill = tone(0xbb1d2a, 0xbb1d2a)  // a native prominent button that sends (Go live): its white words need the darker red at night too
    static let send = tone(0xbb1d2a, 0xff7f86)  // Sync now on the band, and the disc of a change: with On Fill words
    static let onFill = tone(0xffffff, 0x121311)
    static let blue = tone(0x22509c, 0x93b8ff, more: (0x1a4280, 0xb0caff))  // the reader's choice, or a question for them
    static let blueWash = tone(0xdde6f5, 0x1f2b45)  // behind the Kobo's side of the row that is open
    static let green = tone(0x256535, 0x84d197, more: (0x1d4f29, 0x9ddcab))
    static let greenWash = tone(0xdcefe1, 0x1a3121)  // behind a message that something worked
    static let flag = tone(0x1c1c1a, 0xecebe4)  // failed, and every filled button that does not send
    static let onFlag = tone(0xffffff, 0x121311)
    // The band: the tool itself, dark in both lights; its marks have their own lighter colours.
    static let band = tone(0x1c1c1a, 0x0e0e0d)
    static let bandInk = tone(0xefeee8, 0xefeee8)
    static let bandGraphite = tone(0xb8b7ae, 0xb0afa6)
    static let bandGreen = tone(0x7dcf92, 0x7dcf92)
    static let bandBlue = tone(0x9dc0ff, 0x9dc0ff)
    static let bandRed = tone(0xff8f93, 0xff8f93)
}

// ---------- the marks ----------
/// One of the page's marks, drawn in the strokes of web/marks.py (a 20 by
/// 20 box, stroke 1.9). A state of the tool's answers picks it: a check, a
/// step or a sync ("ok", "note", "warn", "fail") or a book ("next", "wait",
/// "err", "none", "stet"). Bare beside words; on the seam it sits in a Disc.
struct Mark: View {
    let state: String
    var size: CGFloat = 18
    var dash = Pencil.faint  // the dash and the dashed caret; in a disc, Graphite
    var onBand = false  // on the dark band: the band's own lighter colours
    var tint: Color? = nil  // every stroke in this one colour (the white caret on the red disc), also on a selected row

    var body: some View {
        OnSelection { selected in
            if state == "stet" {  // the word itself: kept as Hardcover has it
                Text("stet").font(.system(size: size * 0.7, weight: .heavy)).italic().foregroundStyle(selected ? onSelection : Pencil.blue)
                    .frame(minWidth: size, minHeight: size).accessibilityLabel("Kept as on Hardcover")
            } else {
                drawn(selected && tint == nil)
            }
        }
    }

    private var green: Color { onBand ? Pencil.bandGreen : Pencil.green }
    private var red: Color { onBand ? Pencil.bandRed : Pencil.red }
    private var blue: Color { onBand ? Pencil.bandBlue : Pencil.blue }
    private var flag: Color { onBand ? Pencil.bandInk : Pencil.flag }
    private var onFlag: Color { onBand ? Pencil.band : Pencil.onFlag }
    private var dashed: Color { onBand ? Pencil.bandGraphite : dash }

    /// On a selected row every stroke is the selection's white, and the ink square's cross its blue.
    private func drawn(_ selected: Bool) -> some View {
        Canvas { context, box in
            func pencil(_ color: Color) -> Color { tint ?? (selected ? onSelection : color) }
            let s = box.width / 20
            func at(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x * s, y: y * s) }
            func stroke(_ path: Path, _ color: Color, _ width: CGFloat = 1.9, dash: [CGFloat] = []) {
                context.stroke(
                    path, with: .color(color),
                    style: StrokeStyle(lineWidth: width * s, lineCap: .round, lineJoin: .round, dash: dash.map { $0 * s }))
            }
            let caret = Path { p in
                p.move(to: at(4, 15.5))
                p.addLine(to: at(10, 5))
                p.addLine(to: at(16, 15.5))
            }
            switch kind {
            case "ok":
                stroke(Path { p in
                    p.move(to: at(4, 10.5))
                    p.addLine(to: at(8, 15))
                    p.addLine(to: at(16.5, 5))
                }, pencil(green))
            case "next":
                stroke(caret, pencil(red))
            case "wait":
                stroke(caret, pencil(dashed), dash: [2.2, 2.6])
            case "warn":
                stroke(Path(ellipseIn: CGRect(x: 2.4 * s, y: 2.4 * s, width: 15.2 * s, height: 15.2 * s)), pencil(blue), 1.7)
                stroke(Path { p in  // the hook of the query: the arc of marks.py, then its curve down
                    p.move(to: at(7.9, 8.1))
                    p.addArc(center: at(10.1, 8.1), radius: 2.2 * s, startAngle: .degrees(180), endAngle: .degrees(60), clockwise: false)
                    p.addCurve(to: at(10, 11.7), control1: at(10.4, 10.5), control2: at(10, 10.9))
                }, pencil(blue), 1.7)
                context.fill(Path(ellipseIn: CGRect(x: 9.4 * s, y: 13.5 * s, width: 1.2 * s, height: 1.2 * s)), with: .color(pencil(blue)))
            case "err":
                context.fill(Path(roundedRect: CGRect(x: 2.5 * s, y: 2.5 * s, width: 15 * s, height: 15 * s), cornerRadius: 1.5 * s), with: .color(pencil(flag)))
                stroke(Path { p in
                    p.move(to: at(7, 7))
                    p.addLine(to: at(13, 13))
                    p.move(to: at(13, 7))
                    p.addLine(to: at(7, 13))
                }, selected ? Color(nsColor: .selectedContentBackgroundColor) : onFlag, 1.8)
            default:
                stroke(Path { p in
                    p.move(to: at(5, 10))
                    p.addLine(to: at(15, 10))
                }, pencil(dashed))
            }
        }
        .frame(width: size, height: size)
        .accessibilityElement()
        .accessibilityLabel(markWords(state))
    }

    private var kind: String { markKind(state) }
}

/// The tool's states in the page's marks: a problem is the ink square, what needs the reader the query, a note the dash.
func markKind(_ state: String) -> String {
    switch state {
    case "fail": return "err"
    case "warn": return "warn"
    case "note": return "none"
    default: return state
    }
}

/// What a mark says, for VoiceOver.
func markWords(_ state: String) -> String {
    switch markKind(state) {
    case "ok": return "In order"
    case "next": return "Changes at the next sync"
    case "wait": return "Waiting"
    case "warn": return "Needs you"
    case "err": return "Problem"
    case "stet": return "Kept as on Hardcover"
    default: return "Note"
    }
}

/// A mark on the seam (DESIGN.md, The seam and its marks): a disc with the mark in it.
/// A change is filled red with an On Fill caret, a question filled blue, up to date a
/// white disc in a green ring, a failure a white disc in an ink ring round the ink
/// square, and not syncing (or nothing to send yet) a grey disc in an Edge ring.
/// The disc keeps its colours on a selected row: it is its own ground.
struct Disc: View {
    let state: String
    var size: CGFloat = 24

    var body: some View {
        let kind = markKind(state)
        ZStack {
            Circle().fill(fill(kind))
            if let ring = ring(kind) { Circle().strokeBorder(ring.0, lineWidth: ring.1) }
            if kind == "stet" {
                Mark(state: "stet", size: size * 0.62)
            } else {
                Mark(state: state, size: size * (kind == "err" ? 0.62 : 0.58), dash: Pencil.graphite, tint: tint(kind))
            }
        }
        .frame(width: size, height: size)
        .accessibilityElement()
        .accessibilityLabel(markWords(state))
    }

    private func fill(_ kind: String) -> Color {
        switch kind {
        case "next": return Pencil.send
        case "warn": return Pencil.blue
        case "ok", "err", "stet": return Pencil.sheet
        default: return Pencil.ground
        }
    }

    private func ring(_ kind: String) -> (Color, CGFloat)? {
        switch kind {
        case "next", "warn": return nil
        case "ok": return (Pencil.green, 1.5)
        case "err": return (Pencil.ink, 1.5)
        case "stet": return (Pencil.blue, 1.5)
        default: return (Pencil.edge, 1)
        }
    }

    /// The mark on a filled disc in the fill's words colour; on the others the mark's own, never the selection's.
    private func tint(_ kind: String) -> Color? {
        switch kind {
        case "next", "warn": return Pencil.onFill
        case "ok": return Pencil.green
        case "none", "wait": return Pencil.graphite
        default: return nil
        }
    }
}

/// Literata for book titles and the large percentage: the page's own book face, in the
/// tool's package inside the app (the widget carries a copy).
/// The page has it as two subsets under one name, and the latin-ext one holds no lowercase
/// letters; registered side by side, macOS took that one and set the rest in the system font.
/// So a title is the latin subset, with latin-ext behind it for the letters only it has.
private var titleFaces: (latin: CTFontDescriptor, ext: CTFontDescriptor?)?

func registerTitleFont(in fonts: URL) {
    func face(_ file: String) -> CTFontDescriptor? {
        (CTFontManagerCreateFontDescriptorsFromURL(fonts.appendingPathComponent(file) as CFURL) as? [CTFontDescriptor])?.first
    }
    guard let latin = face("Literata-latin.woff2") else { return }
    titleFaces = (latin, face("Literata-latin-ext.woff2"))
}

/// A book title: Literata at this weight, sized optically as on the page; else the serif macOS has.
/// Tabular: figures of one width, for the percentages that stand in a column.
func titleFont(_ size: CGFloat, _ weight: Font.Weight = .semibold, tabular: Bool = false) -> Font {
    guard let faces = titleFaces else {
        let serif = Font.system(size: size, weight: weight, design: .serif)
        return tabular ? serif.monospacedDigit() : serif
    }
    let wght = weight == .regular ? 400 : weight == .medium ? 500 : weight == .bold ? 700 : weight == .heavy ? 800 : 600
    let axes: [Int: CGFloat] = [0x7767_6874: CGFloat(wght), 0x6F70_737A: min(max(size, 7), 72)]  // "wght", "opsz"
    var common: [CFString: Any] = [kCTFontVariationAttribute: axes]
    if tabular {
        common[kCTFontFeatureSettingsAttribute] = [[kCTFontOpenTypeFeatureTag: "tnum", kCTFontOpenTypeFeatureValue: 1]]
    }
    func at(_ face: CTFontDescriptor) -> CTFontDescriptor {
        CTFontDescriptorCreateCopyWithAttributes(face, common as CFDictionary)
    }
    var attributes = common
    if let ext = faces.ext { attributes[kCTFontCascadeListAttribute] = [at(ext)] }
    return Font(CTFontCreateWithFontDescriptor(CTFontDescriptorCreateCopyWithAttributes(faces.latin, attributes as CFDictionary), size, nil))
}

/// How far a book is read, large in Literata at 700, the sign small after it, as on the Kobo's side of the page.
struct Percent: View {
    let percent: Int
    var size: CGFloat = 30
    var quiet = false  // not opened yet: Faint

    var body: some View {
        OnSelection { selected in
            (Text("\(percent)").font(titleFont(size, .bold, tabular: true)).tracking(-size * 0.04)
                + Text("%").font(titleFont(size * 0.43, .bold)))
                .foregroundStyle(selected ? AnyShapeStyle(onSelection) : AnyShapeStyle(quiet ? Pencil.faint : Pencil.ink))
                .lineLimit(1)
        }
        .accessibilityLabel("\(percent)%")
    }
}

/// The Kobo's own line of progress: a rule in Edge with a dot every tenth, the part read a 3 point bar of ink.
/// In a row that does not sync the bar is Faint.
struct Gauge: View {
    let percent: Int
    let finished: Bool
    var quiet = false
    var width: CGFloat = 130

    var body: some View {
        OnSelection { selected in gauge(selected) }
            .frame(maxWidth: width)
            .frame(height: 7)
            .accessibilityElement()
            .accessibilityLabel(finished ? "Finished" : "\(percent)%")
    }

    private func gauge(_ selected: Bool) -> some View {
        Canvas { context, box in
            let w = box.width
            let edge = selected ? onSelection.opacity(0.6) : Pencil.edge
            context.fill(Path(CGRect(x: 0, y: 3, width: w, height: 1)), with: .color(edge))
            for n in 0..<10 {
                let x = w * (CGFloat(n) + 0.5) / 10
                context.fill(Path(ellipseIn: CGRect(x: x - 1.2, y: 2.3, width: 2.4, height: 2.4)), with: .color(edge))
            }
            let read = CGRect(x: 0, y: 2, width: w * CGFloat(finished ? 100 : min(max(percent, 0), 100)) / 100, height: 3)
            context.fill(Path(read), with: .color(selected ? onSelection : quiet ? Pencil.faint : Pencil.ink))
        }
    }
}

// ---------- on a selected row ----------
/// The words and marks on a selected row of a list: white on the selection's blue.
let onSelection = Color(nsColor: .alternateSelectedControlTextColor)

/// Whether this is drawn on a selected row (the key window's, in its blue), where
/// the pencils' colours would sink: macOS 14 and later say; before, never.
struct OnSelection<Content: View>: View {
    @ViewBuilder let content: (Bool) -> Content

    var body: some View {
        if #available(macOS 14, *) { Prominence(content: content) } else { content(false) }
    }
}

@available(macOS 14, *)
private struct Prominence<Content: View>: View {
    let content: (Bool) -> Content
    @Environment(\.backgroundProminence) private var prominence

    var body: some View { content(prominence == .increased) }
}

/// Graphite for what was found, facts and labels; on a selected row the selection's quieter white.
func quiet(_ selected: Bool) -> AnyShapeStyle { selected ? AnyShapeStyle(.secondary) : AnyShapeStyle(Pencil.graphite) }

/// A pencil's colour; on a selected row the selection's white.
func pencil(_ color: Color, _ selected: Bool) -> AnyShapeStyle { selected ? AnyShapeStyle(onSelection) : AnyShapeStyle(color) }

/// What a sync sends, on a row: the selection's white, else on a chosen row the red that holds on its grey.
func sends(_ selected: Bool, chosen: Bool) -> AnyShapeStyle {
    selected ? AnyShapeStyle(onSelection) : AnyShapeStyle(chosen ? Pencil.redHeld : Pencil.red)
}

/// A cover from the tool's cache, or the crossed box of a book without one.
/// The small ones (240 points wide, the run's) are all kept, as the run shows
/// them again and again; of the large ones (`book --large-cover`, some 9 MB
/// each when drawn) only the last few. `whole`: this is the large one, shown
/// as it is; any other is read small, whatever the file holds.
struct Cover: View {
    let path: String
    let width: CGFloat
    var whole = false
    var grey = false  // on the Kobo's side: in greyscale, as its screen shows it
    private static var cache: [String: NSImage] = [:]
    private static var greyCache: [String: NSImage] = [:]
    private static let drawing = CIContext()
    private static var large: [(path: String, image: NSImage)] = []  // the last used first
    private static let largeKept = 4

    var body: some View {
        Group {
            if let image = grey ? Self.grey(path) : Self.image(path, whole: whole) {
                Image(nsImage: image).resizable().aspectRatio(contentMode: .fill)
            } else {
                Canvas { context, box in
                    var cross = Path(CGRect(origin: .zero, size: box).insetBy(dx: 0.5, dy: 0.5))
                    cross.move(to: .zero)
                    cross.addLine(to: CGPoint(x: box.width, y: box.height))
                    cross.move(to: CGPoint(x: box.width, y: 0))
                    cross.addLine(to: CGPoint(x: 0, y: box.height))
                    context.stroke(cross, with: .color(Pencil.edge), lineWidth: 1)
                }
            }
        }
        .frame(width: width, height: width * 1.5)
        .clipShape(RoundedRectangle(cornerRadius: 2))
        .accessibilityHidden(true)
    }

    /// The small cover in grey, a touch of contrast added, as the Kobo's screen has it: made once and
    /// kept, a picture of its own rather than a filter, so that it costs nothing while the list scrolls.
    private static func grey(_ path: String) -> NSImage? {
        if let kept = greyCache[path] { return kept }
        guard let colour = image(path, whole: false), let picture = colour.cgImage(forProposedRect: nil, context: nil, hints: nil) else { return nil }
        let filter = CIFilter(name: "CIColorControls")
        filter?.setValue(CIImage(cgImage: picture), forKey: kCIInputImageKey)
        filter?.setValue(0, forKey: kCIInputSaturationKey)
        filter?.setValue(1.04, forKey: kCIInputContrastKey)
        guard let out = filter?.outputImage, let made = drawing.createCGImage(out, from: out.extent) else { return colour }
        let image = NSImage(cgImage: made, size: colour.size)
        greyCache[path] = image
        return image
    }

    private static func image(_ path: String, whole: Bool) -> NSImage? {
        guard !path.isEmpty else { return nil }
        if whole {
            if let n = large.firstIndex(where: { $0.path == path }) {
                let kept = large.remove(at: n)
                large.insert(kept, at: 0)
                return kept.image
            }
            guard let image = NSImage(contentsOfFile: path) else { return nil }  // one that had gone from the last few
            keep(path, image)
            return image
        }
        if let kept = cache[path] { return kept }
        guard var image = NSImage(contentsOfFile: path) else { return nil }
        if (image.representations.first?.pixelsWide ?? 0) > 600 { image = small(path) ?? image }
        cache[path] = image
        return image
    }

    /// A list cover read small. A book's own EPUB can hold a picture of several megabytes: it was decoded
    /// whole while drawing, counted as a large one, and decoded again once more than a few of them were
    /// shown, pushing the cover that was open large out of what is kept.
    private static func small(_ path: String) -> NSImage? {
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: 720,  // the run's 240 points at 2x, on the long side
            kCGImageSourceShouldCacheImmediately: true,
        ]
        guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
            let image = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary)
        else { return nil }
        return NSImage(cgImage: image, size: NSSize(width: image.width, height: image.height))
    }

    /// A large cover, read and decoded away from the main thread, so that showing it does not wait on either.
    static func prepare(_ path: String) -> NSImage? {
        guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
            let image = CGImageSourceCreateImageAtIndex(source, 0, [kCGImageSourceShouldCacheImmediately: true] as CFDictionary)
        else { return nil }
        return NSImage(cgImage: image, size: NSSize(width: image.width, height: image.height))
    }

    /// A large cover kept, on the main thread: the oldest goes when there are more than a few.
    static func keep(_ path: String, _ image: NSImage) {
        large.removeAll { $0.path == path }
        large.insert((path, image), at: 0)
        if large.count > largeKept { large.removeLast(large.count - largeKept) }
    }
}

extension View {
    /// The cover shadow: a cover lying on the paper.
    func coverShadow() -> some View {
        shadow(color: .black.opacity(0.28), radius: 1, y: 1).shadow(color: .black.opacity(0.12), radius: 4, y: 3)
    }
}
