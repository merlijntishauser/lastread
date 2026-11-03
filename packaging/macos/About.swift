// About Lastread: the app drawn as a tabletop proof press (About-light.png,
// About-dark.png, made by packaging/macos/about/build.mjs), with its name, its
// version, the site and the independent-project sentence beneath it. The
// pictures are drawn on the proof sheet's own paper, so they sit on the window
// without an edge.

import AppKit
import SwiftUI

struct AboutView: View {
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        VStack(spacing: 6) {
            if let picture {
                Image(nsImage: picture)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFit()
                    .frame(width: 640)
                    .accessibilityLabel(Self.described)
            }
            Text(name).font(titleFont(28)).foregroundStyle(Pencil.ink)
            Text("Version \(bundleVersion())").font(.callout).foregroundStyle(Pencil.graphite).textSelection(.enabled)
            Link("lastread.app", destination: site).font(.callout)
                .padding(.top, 2)
            Text("An independent project: not affiliated with, endorsed by or sponsored by Rakuten Kobo or Hardcover.")
                .font(.caption).foregroundStyle(Pencil.graphite).multilineTextAlignment(.center)
                .padding(.top, 6).padding(.horizontal, 40)
        }
        .padding(.top, 8)
        .padding(.bottom, 24)
        .frame(width: 680)
        .background(Pencil.sheet.ignoresSafeArea())  // under the transparent title bar too
    }

    private var picture: NSImage? {
        Bundle.main.url(forResource: scheme == .dark ? "About-dark" : "About-light", withExtension: "png").flatMap(NSImage.init(contentsOf:))
    }

    static let described = """
        \(name) drawn as a tabletop proof press. A Kobo lies locked on the bed; a carriage with an impression cylinder \
        runs over it. On the feed board lies the proof of the Hardcover shelf, with red carets in the margin where the \
        sync changes something. A cable runs from the Kobo to the trip box: plugging in starts the run.
        """
}

extension App {
    /// About Lastread, in a window of its own.
    @objc func showAbout() {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        if let about { return about.makeKeyAndOrderFront(nil) }
        let about = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 680, height: 560),
            styleMask: [.titled, .closable, .fullSizeContentView], backing: .buffered, defer: false)
        about.title = "About \(name)"
        about.titleVisibility = .hidden
        about.titlebarAppearsTransparent = true
        about.isMovableByWindowBackground = true
        let view = NSHostingView(rootView: AboutView())
        about.contentView = view
        about.setContentSize(view.fittingSize)
        about.isReleasedWhenClosed = false
        about.delegate = self
        about.center()
        self.about = about
        begin()  // as Help: the app stays while it is open
        about.makeKeyAndOrderFront(nil)
    }
}
