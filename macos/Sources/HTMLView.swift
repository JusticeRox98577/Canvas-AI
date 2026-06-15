import SwiftUI
import PDFKit

/// Renders Canvas HTML natively (no web view) via NSAttributedString.
struct HTMLText: View {
    let html: String

    var body: some View {
        ScrollView {
            Text(Self.attributed(html))
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(2)
        }
    }

    static func attributed(_ html: String) -> AttributedString {
        guard let data = html.data(using: .utf8) else { return AttributedString(html) }
        let opts: [NSAttributedString.DocumentReadingOptionKey: Any] = [
            .documentType: NSAttributedString.DocumentType.html,
            .characterEncoding: String.Encoding.utf8.rawValue,
        ]
        if let ns = try? NSAttributedString(data: data, options: opts, documentAttributes: nil) {
            if let a = try? AttributedString(ns, including: \.appKit) { return a }
            return AttributedString(ns.string)
        }
        return AttributedString(html)
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
