import SwiftUI
import AppKit

enum ReaderTarget: Identifiable {
    case page(String, String)        // pageUrl, title
    case file(Int, String)           // fileId, title
    case quiz(Int, String)           // quizId, title
    case discussion(Int, String)     // topicId, title
    case assignment(Int, String)     // assignmentId, title
    case external(String, String)    // url, title

    var id: String {
        switch self {
        case .page(let u, _): return "page-\(u)"
        case .file(let i, _): return "file-\(i)"
        case .quiz(let i, _): return "quiz-\(i)"
        case .discussion(let i, _): return "disc-\(i)"
        case .assignment(let i, _): return "asg-\(i)"
        case .external(let u, _): return "ext-\(u)"
        }
    }
    var title: String {
        switch self {
        case .page(_, let t), .file(_, let t), .quiz(_, let t),
             .discussion(_, let t), .assignment(_, let t), .external(_, let t):
            return t
        }
    }
}

struct ReaderView: View {
    let target: ReaderTarget
    let course: Course?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(target.title).font(.headline).lineLimit(1)
                Spacer()
                Button("Done") { dismiss() }
            }
            .padding(12)
            Divider()
            content.frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(minWidth: 620, minHeight: 480)
    }

    @ViewBuilder private var content: some View {
        switch target {
        case .page(let url, _): PageReader(courseId: course?.id, pageUrl: url)
        case .file(let id, _): FileReader(fileId: id, course: course)
        case .quiz(let id, _): QuizReader(quizId: id, course: course)
        case .discussion(let id, _): DiscussionReader(topicId: id, course: course)
        case .assignment(let id, _): AssignmentReader(assignmentId: id, course: course)
        case .external(let url, _): ExternalReader(urlString: url)
        }
    }
}

// MARK: - Page

struct PageReader: View {
    let courseId: Int?
    let pageUrl: String
    @State private var page: Page?
    @State private var error: String?

    var body: some View {
        Group {
            if let p = page {
                ScrollView { HTMLText(html: p.html ?? "").padding(14) }
            }
            else if let error { Text(error).foregroundStyle(.secondary) }
            else { ProgressView() }
        }
        .task {
            guard let cid = courseId else { return }
            do { page = try await API.shared.get("/api/page?course_id=\(cid)&page_url=\(API.q(pageUrl))") }
            catch { self.error = "\(error)" }
        }
    }
}

// MARK: - File

struct FileReader: View {
    let fileId: Int
    let course: Course?
    @State private var meta: FileMeta?
    @State private var text: String?
    @State private var aiAnswer: String?
    @State private var busy = false

    var rawURL: URL { URL(string: API.shared.base + "/api/file/raw?file_id=\(fileId)")! }

    var body: some View {
        Group {
            if let m = meta {
                let ct = (m.content_type ?? "").lowercased()
                if ct.contains("pdf") {
                    PDFKitView(url: rawURL)
                } else if ct.hasPrefix("image/") {
                    ScrollView { AsyncImage(url: rawURL) { $0.resizable().scaledToFit() } placeholder: { ProgressView() } }
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(text ?? "Loading…").textSelection(.enabled)
                            Button(busy ? "Thinking…" : "Explain with AI") { explain() }
                                .disabled(busy || text == nil)
                            if let a = aiAnswer {
                                Text(a).padding(10)
                                    .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 10))
                            }
                        }.padding(12)
                    }
                    .task { await loadText() }
                }
            } else { ProgressView() }
        }
        .task { meta = try? await API.shared.get("/api/file?file_id=\(fileId)") }
    }

    private func loadText() async {
        if let t: FileText = try? await API.shared.get("/api/file/text?file_id=\(fileId)") { text = t.text }
    }
    private func explain() {
        guard let t = text, let c = course else { return }
        busy = true; aiAnswer = nil
        Task {
            do {
                let r: AgentResp = try await API.shared.post("/api/agent",
                    AgentReq(goal: "Explain this document simply:\n\n" + String(t.prefix(4000)),
                             course_id: c.id, course_name: c.name), timeout: 240)
                aiAnswer = r.answer.isEmpty ? "The AI returned nothing — try again." : r.answer
            } catch { aiAnswer = "Failed: \(error.localizedDescription)" }
            busy = false
        }
    }
}

// MARK: - Quiz (study only)

struct QuizReader: View {
    let quizId: Int
    let course: Course?
    @State private var quiz: Quiz?
    @State private var study: String?
    @State private var busy = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let q = quiz {
                    HTMLText(html: q.description ?? "<em>No description</em>")
                    Text(metaLine(q)).font(.callout).foregroundStyle(.secondary)
                    Text("Quizzes are taken in Canvas. The AI won't answer graded work — use Study mode to learn the material.")
                        .font(.caption).foregroundStyle(.secondary)
                    HStack {
                        Button(busy ? "Thinking…" : "Study this with AI") { runStudy(q) }.disabled(busy)
                        if let url = q.html_url {
                            Button("Open quiz in Canvas") { open(url) }
                        }
                    }
                    if let s = study {
                        Text(s).padding(10)
                            .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 10))
                    }
                } else { ProgressView() }
            }.padding(14)
        }
        .task {
            guard let cid = course?.id else { return }
            quiz = try? await API.shared.get("/api/quiz?course_id=\(cid)&quiz_id=\(quizId)")
        }
    }

    private func metaLine(_ q: Quiz) -> String {
        var p: [String] = []
        if let v = q.points_possible { p.append("Points: \(Int(v))") }
        if let v = q.question_count { p.append("Questions: \(v)") }
        if let v = q.time_limit { p.append("\(v) min") }
        if let v = q.due_at { p.append("Due: \(v.prettyDate)") }
        return p.joined(separator: " · ")
    }
    private func runStudy(_ q: Quiz) {
        guard let c = course else { return }
        busy = true; study = nil
        Task {
            do {
                let r: AgentResp = try await API.shared.post("/api/agent",
                    AgentReq(goal: "I have a quiz '\(q.title ?? "")'. Explain the key concepts I should understand to do well. Description: \(q.description ?? "")",
                             course_id: c.id, course_name: c.name), timeout: 240)
                study = r.answer.isEmpty ? "The AI returned nothing — try again." : r.answer
            } catch { study = "Failed: \(error.localizedDescription)" }
            busy = false
        }
    }
    private func open(_ s: String) { if let u = URL(string: s) { NSWorkspace.shared.open(u) } }
}

// MARK: - Discussion

struct DiscussionReader: View {
    let topicId: Int
    let course: Course?
    @State private var detail: DiscussionDetail?
    @State private var reply = ""
    @State private var busy = false
    @State private var confirming = false
    @State private var status: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let d = detail {
                    HTMLText(html: d.message ?? "")
                    Divider()
                    Text("Replies").font(.headline)
                    ForEach(d.entries ?? []) { e in
                        VStack(alignment: .leading, spacing: 4) {
                            Text("User \(e.user_id.map(String.init) ?? "?")").font(.caption).foregroundStyle(.secondary)
                            Text(HTMLText.attributed(e.message ?? "")).textSelection(.enabled)
                        }
                        .padding(10)
                        .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
                    }
                    Text("Your reply").font(.headline)
                    TextEditor(text: $reply).frame(height: 100)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(.quaternary))
                    HStack {
                        Button(busy ? "Drafting…" : "Draft with AI") { draft() }.disabled(busy)
                        Button("Post reply…") { confirming = true }
                            .buttonStyle(.borderedProminent)
                            .disabled(reply.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                    if let s = status { Text(s).foregroundStyle(.secondary) }
                } else { ProgressView() }
            }.padding(14)
        }
        .task {
            guard let cid = course?.id else { return }
            detail = try? await API.shared.get("/api/discussion?course_id=\(cid)&topic_id=\(topicId)")
        }
        .alert("Post this reply?", isPresented: $confirming) {
            Button("Cancel", role: .cancel) {}
            Button("Post") { post() }
        } message: { Text(reply) }
    }

    private func draft() {
        guard let c = course, let d = detail else { return }
        busy = true; status = "Drafting… (the local model can take ~30–60s)"
        Task {
            do {
                let r: AgentResp = try await API.shared.post("/api/agent",
                    AgentReq(goal: "Draft a thoughtful discussion reply for topic \(topicId). Prompt: \(d.message ?? "")",
                             course_id: c.id, course_name: c.name), timeout: 240)
                if r.answer.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    status = "The AI returned an empty draft — try again."
                } else { reply = r.answer; status = nil }
            } catch { status = "Draft failed: \(error.localizedDescription)" }
            busy = false
        }
    }
    private func post() {
        guard let c = course else { return }
        Task {
            do {
                try await API.shared.postVoid("/api/discussion/reply",
                    ReplyReq(course_id: c.id, topic_id: topicId, message: reply, entry_id: nil))
                status = "Posted."; reply = ""
                detail = try? await API.shared.get("/api/discussion?course_id=\(c.id)&topic_id=\(topicId)")
            } catch { status = "Error: \(error.localizedDescription)" }
        }
    }
}

// MARK: - Assignment

struct AssignmentReader: View {
    let assignmentId: Int
    let course: Course?
    @State private var asg: AssignmentDetail?
    @State private var body_ = ""
    @State private var busy = false
    @State private var confirming = false
    @State private var status: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let a = asg {
                    HTMLText(html: a.description ?? "<em>No description</em>")
                    if let due = a.due_at { Text("Due: \(due.prettyDate)").foregroundStyle(.secondary) }
                    Text("Your submission (text)").font(.headline)
                    TextEditor(text: $body_).frame(height: 160)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(.quaternary))
                    HStack {
                        Button(busy ? "Drafting…" : "Draft with AI") { draft(a) }.disabled(busy)
                        Button("Submit…") { confirming = true }
                            .buttonStyle(.borderedProminent)
                            .disabled(body_.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                    if let s = status { Text(s).foregroundStyle(.secondary) }
                } else { ProgressView() }
            }.padding(14)
        }
        .task {
            guard let cid = course?.id else { return }
            asg = try? await API.shared.get("/api/assignment?course_id=\(cid)&assignment_id=\(assignmentId)")
        }
        .alert("Submit graded work?", isPresented: $confirming) {
            Button("Cancel", role: .cancel) {}
            Button("Submit", role: .destructive) { submit() }
        } message: {
            Text("This submits to the assignment as you — it counts as your graded work.")
        }
    }

    private func draft(_ a: AssignmentDetail) {
        guard let c = course else { return }
        busy = true; status = "Drafting… (the local model can take ~30–60s)"
        Task {
            do {
                let r: AgentResp = try await API.shared.post("/api/agent",
                    AgentReq(goal: "Draft a response for the assignment '\(a.name ?? "")'. Description: \(a.description ?? "")",
                             course_id: c.id, course_name: c.name), timeout: 240)
                if r.answer.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    status = "The AI returned an empty draft — try again."
                } else { body_ = r.answer; status = nil }
            } catch { status = "Draft failed: \(error.localizedDescription)" }
            busy = false
        }
    }
    private func submit() {
        guard let c = course else { return }
        Task {
            do {
                try await API.shared.postVoid("/api/assignment/submit",
                    SubmitReq(course_id: c.id, assignment_id: assignmentId, body: body_, confirm: true))
                status = "Submitted."
            } catch { status = "Error: \(error.localizedDescription)" }
        }
    }
}

// MARK: - External

struct ExternalReader: View {
    let urlString: String
    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "link.circle").font(.largeTitle).foregroundStyle(.tint)
            Text("This item is an external web page or tool.")
            Text(urlString).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
            Button("Open in browser") { if let u = URL(string: urlString) { NSWorkspace.shared.open(u) } }
                .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}
