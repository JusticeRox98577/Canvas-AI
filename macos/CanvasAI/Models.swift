import Foundation

struct Course: Identifiable, Codable, Hashable {
    let id: Int
    let name: String?
    var displayName: String { name ?? "Course \(id)" }
}

struct ModuleItem: Identifiable, Codable, Hashable {
    let id: Int
    let title: String?
    let type: String?
    let page_url: String?
    let content_id: Int?
    let html_url: String?
}

struct Module: Identifiable, Codable, Hashable {
    let id: Int
    let name: String?
    let items: [ModuleItem]?
}

struct Assignment: Identifiable, Codable, Hashable {
    let id: Int
    let name: String?
    let due_at: String?
    let html_url: String?
    let points_possible: Double?
}

struct Page: Codable {
    let title: String?
    let body: String?
}

/// Cheap HTML → plain text (no main-thread NSAttributedString needed).
func htmlToText(_ html: String) -> String {
    html.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        .replacingOccurrences(of: "&nbsp;", with: " ")
        .replacingOccurrences(of: "&amp;", with: "&")
        .replacingOccurrences(of: "&#39;", with: "'")
        .replacingOccurrences(of: "&quot;", with: "\"")
        .trimmingCharacters(in: .whitespacesAndNewlines)
}
