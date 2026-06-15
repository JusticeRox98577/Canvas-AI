import SwiftUI
import AppKit
import PDFKit

/// Renders Canvas HTML natively (no web view) via NSAttributedString, restyled
/// to use the system font and adaptive colors so it matches the app.
struct HTMLText: View {
    let html: String

    var body: some View {
        Text(Self.attributed(html))
            .textSelection(.enabled)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    static func attributed(_ html: String) -> AttributedString {
        guard let data = html.data(using: .utf8) else { return AttributedString(html) }
        let opts: [NSAttributedString.DocumentReadingOptionKey: Any] = [
            .documentType: NSAttributedString.DocumentType.html,
            .characterEncoding: String.Encoding.utf8.rawValue,
        ]
        guard let ns = try? NSMutableAttributedString(data: data, options: opts, documentAttributes: nil) else {
            return AttributedString(html)
        }
        let full = NSRange(location: 0, length: ns.length)
        let manager = NSFontManager.shared

        // Replace the HTML's serif fonts with the system font, keeping bold/italic.
        ns.enumerateAttribute(.font, in: full) { value, range, _ in
            var font = NSFont.systemFont(ofSize: 14)
            if let existing = value as? NSFont {
                let traits = manager.traits(of: existing)
                if traits.contains(.boldFontMask) {
                    font = manager.convert(font, toHaveTrait: .boldFontMask)
                }
                if traits.contains(.italicFontMask) {
                    font = manager.convert(font, toHaveTrait: .italicFontMask)
                }
            }
            ns.addAttribute(.font, value: font, range: range)
        }
        // Adaptive text color (works in light + dark mode).
        ns.addAttribute(.foregroundColor, value: NSColor.labelColor, range: full)

        if let a = try? AttributedString(ns, including: \.appKit) { return a }
        return AttributedString(ns.string)
    }

    /// Plain-text version of HTML (strips tags) for feeding prompts to the model.
    static func plain(_ html: String) -> String {
        String(attributed(html).characters).trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

/// Native PDF rendering via PDFKit.
struct PDFKitView: NSViewRepresentable {
    let url: URL
    func makeNSView(context: Context) -> PDFView {
        let v = PDFView()
        v.autoScales = true
        DispatchQueue.global().async {
            let doc = PDFDocument(url: url)
            DispatchQueue.main.async { v.document = doc }
        }
        return v
    }
    func updateNSView(_ nsView: PDFView, context: Context) {}
}

extension String {
    /// "2026-06-20T23:59:00Z" -> a friendly local string.
    var prettyDate: String {
        let iso = ISO8601DateFormatter()
        guard let d = iso.date(from: self) else { return self }
        let out = DateFormatter()
        out.dateStyle = .medium
        out.timeStyle = .short
        return out.string(from: d)
    }
}
