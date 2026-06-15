import Foundation

struct Status: Codable {
    let authenticated: Bool
    let name: String?
    let base_url: String?
}

struct Course: Codable, Identifiable, Hashable {
    let id: Int
    let name: String?
}

struct ModuleItem: Codable, Identifiable, Hashable {
    let itemId: Int?
    let title: String?
    let type: String?
    let contentId: Int?
    let pageUrl: String?
    let externalUrl: String?
    let htmlUrl: String?

    enum CodingKeys: String, CodingKey {
        case itemId = "id", title, type
        case contentId = "content_id", pageUrl = "page_url"
        case externalUrl = "external_url", htmlUrl = "html_url"
    }
    var id: String { "\(itemId ?? 0)-\(title ?? "")-\(type ?? "")" }
    var symbol: String {
        switch type {
        case "Page": return "doc.richtext"
        case "Assignment": return "square.and.pencil"
        case "Quiz": return "checklist"
        case "Discussion": return "bubble.left.and.bubble.right"
        case "File": return "paperclip"
        case "ExternalUrl", "ExternalTool": return "link"
        case "SubHeader": return "minus"
        default: return "doc"
        }
    }
}

struct Module: Codable, Identifiable, Hashable {
    let id: Int
    let name: String?
    let items: [ModuleItem]?
}

struct DueItem: Codable, Identifiable, Hashable {
    let assignmentId: Int
    let name: String?
    let course: String?
    let courseId: Int?
    let dueAt: String?
    let htmlUrl: String?
    let submitted: Bool?

    enum CodingKeys: String, CodingKey {
        case assignmentId = "id", name, course
        case courseId = "course_id", dueAt = "due_at", htmlUrl = "html_url", submitted
    }
    var id: String { "\(courseId ?? 0)-\(assignmentId)" }
}

struct Page: Codable {
    let title: String?
    let html: String?
}

struct AssignmentDetail: Codable {
    let id: Int?
    let name: String?
    let description: String?
    let due_at: String?
    let html_url: String?
}

struct Quiz: Codable {
    let id: Int?
    let title: String?
    let description: String?
    let points_possible: Double?
    let question_count: Int?
    let time_limit: Int?
    let due_at: String?
    let allowed_attempts: Int?
    let html_url: String?
}

struct DiscussionStub: Codable, Identifiable, Hashable {
    let id: Int
    let title: String?
}

struct Entry: Codable, Identifiable, Hashable {
    let id: Int?
    let user_id: Int?
    let message: String?
    let replies: [Entry]?
    var localID: String { "\(id ?? Int.random(in: 1...1_000_000))" }
}

struct DiscussionDetail: Codable {
    let title: String?
    let message: String?
    let entries: [Entry]?
}

struct FileMeta: Codable {
    let id: Int?
    let display_name: String?
    let content_type: String?
    let size: Int?
}

struct FileText: Codable {
    let display_name: String?
    let text: String?
}

struct AgentResp: Codable { let answer: String }

struct AgentReq: Encodable {
    let goal: String
    let course_id: Int?
    let course_name: String?
}
struct ReplyReq: Encodable {
    let course_id: Int
    let topic_id: Int
    let message: String
    let entry_id: Int?
}
struct SubmitReq: Encodable {
    let course_id: Int
    let assignment_id: Int
    let body: String
    let confirm: Bool
}
