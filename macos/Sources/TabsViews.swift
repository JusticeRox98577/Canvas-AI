import SwiftUI

// MARK: - Modules

struct ModulesView: View {
    let course: Course
    let openReader: (ReaderTarget) -> Void
    @State private var modules: [Module] = []
    @State private var error: String?
    @State private var loading = true

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 18) {
                if loading { ProgressView().padding() }
                if let error { Text(error).foregroundStyle(.secondary).padding() }
                ForEach(modules) { m in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(m.name ?? "Module")
                            .font(.title3.weight(.semibold))
                            .padding(.bottom, 6)
                        ForEach(m.items ?? []) { it in
                            if it.type == "SubHeader" {
                                Text(it.title ?? "").font(.subheadline.weight(.medium))
                                    .foregroundStyle(.secondary).padding(.top, 6)
                            } else {
                                Button { if let t = target(it) { openReader(t) } } label: {
                                    HStack(spacing: 11) {
                                        Image(systemName: it.symbol).frame(width: 22)
                                            .foregroundStyle(.tint)
                                        Text(it.title ?? "Item").foregroundStyle(.primary)
                                        Spacer()
                                        Image(systemName: "chevron.right")
                                            .font(.caption2).foregroundStyle(.tertiary)
                                    }
                                    .contentShape(Rectangle())
                                    .padding(.vertical, 7).padding(.horizontal, 8)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    .padding(16)
                    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(.quaternary, lineWidth: 1))
                }
            }
            .padding(16)
        }
        .task(id: course.id) { await load() }
    }

    private func load() async {
        loading = true; error = nil
        do { modules = try await API.shared.get("/api/modules?course_id=\(course.id)") }
        catch { self.error = "\(error)" }
        loading = false
    }

    private func target(_ it: ModuleItem) -> ReaderTarget? {
        switch it.type {
        case "Page": return it.pageUrl.map { .page($0, it.title ?? "Page") }
        case "Assignment": return it.contentId.map { .assignment($0, it.title ?? "Assignment") }
        case "Discussion": return it.contentId.map { .discussion($0, it.title ?? "Discussion") }
        case "File": return it.contentId.map { .file($0, it.title ?? "File") }
        case "Quiz": return it.contentId.map { .quiz($0, it.title ?? "Quiz") }
        case "ExternalUrl", "ExternalTool":
            return (it.externalUrl ?? it.htmlUrl).map { .external($0, it.title ?? "Link") }
        default:
            return it.htmlUrl.map { .external($0, it.title ?? "Item") }
        }
    }
}

// MARK: - Due Dates

struct DueDatesView: View {
    let course: Course
    @State private var rows: [DueItem] = []
    @State private var allCourses = false
    @State private var loading = true
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(allCourses ? "All courses" : (course.name ?? "This course"))
                    .foregroundStyle(.secondary).font(.callout)
                Spacer()
                Toggle("All courses", isOn: $allCourses).toggleStyle(.checkbox)
            }
            .padding(12)
            Divider()
            if loading { ProgressView().padding() }
            if let error { Text(error).foregroundStyle(.secondary).padding() }
            Table(rows) {
                TableColumn("Due") { Text($0.dueAt?.prettyDate ?? "—") }
                TableColumn("Assignment") { Text($0.name ?? "") }
                TableColumn("Course") { Text($0.course ?? "").foregroundStyle(.secondary) }
                TableColumn("Status") { r in
                    Text(r.submitted == true ? "submitted" : "to do")
                        .font(.caption).padding(.horizontal, 8).padding(.vertical, 2)
                        .background((r.submitted == true ? Color.green : Color.orange).opacity(0.2),
                                    in: Capsule())
                }
            }
        }
        .task(id: "\(course.id)-\(allCourses)") { await load() }
    }

    private func load() async {
        loading = true; error = nil
        let q = allCourses ? "" : "?course_id=\(course.id)"
        do { rows = try await API.shared.get("/api/dashboard\(q)") }
        catch { self.error = "\(error)" }
        loading = false
    }
}

// MARK: - Discussions

struct DiscussionsView: View {
    let course: Course
    let openReader: (ReaderTarget) -> Void
    @State private var items: [DiscussionStub] = []
    @State private var loading = true
    @State private var error: String?

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 8) {
                if loading { ProgressView().padding() }
                if let error { Text(error).foregroundStyle(.secondary).padding() }
                ForEach(items) { d in
                    Button { openReader(.discussion(d.id, d.title ?? "Discussion")) } label: {
                        HStack {
                            Image(systemName: "bubble.left.and.bubble.right").foregroundStyle(.tint)
                            Text(d.title ?? "Discussion"); Spacer()
                        }
                        .contentShape(Rectangle())
                        .padding(10)
                        .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(16)
        }
        .task(id: course.id) { await load() }
    }

    private func load() async {
        loading = true; error = nil
        do { items = try await API.shared.get("/api/discussions?course_id=\(course.id)") }
        catch { self.error = "\(error)" }
        loading = false
    }
}

// MARK: - Chat

struct ChatMsg: Identifiable {
    let id = UUID()
    let role: String  // user / ai / sys
    let text: String
}

struct ChatView: View {
    let course: Course
    @State private var messages: [ChatMsg] = []
    @State private var input = ""
    @State private var busy = false

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(messages) { m in bubble(m).id(m.id) }
                    }.padding(16)
                }
                .onChange(of: messages.count) { _ in
                    if let last = messages.last { withAnimation { proxy.scrollTo(last.id) } }
                }
            }
            Divider()
            HStack(spacing: 8) {
                TextField("Ask about \(course.name ?? "this course")…", text: $input)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit(send)            // Return submits the query
                Button(action: send) { Text("Send") }
                    .buttonStyle(.borderedProminent).disabled(busy || input.isEmpty)
            }
            .padding(12)
            .background(.regularMaterial)
        }
    }

    @ViewBuilder private func bubble(_ m: ChatMsg) -> some View {
        if m.role == "user" {
            HStack { Spacer(); Text(m.text).padding(10)
                .background(Color.accentColor, in: RoundedRectangle(cornerRadius: 12))
                .foregroundStyle(.white).frame(maxWidth: 460, alignment: .trailing) }
        } else if m.role == "sys" {
            Text(m.text).font(.caption).foregroundStyle(.secondary)
        } else {
            HStack { Text(m.text).textSelection(.enabled).padding(10)
                .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 12))
                .frame(maxWidth: 560, alignment: .leading); Spacer() }
        }
    }

    private func send() {
        let goal = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !goal.isEmpty else { return }
        messages.append(ChatMsg(role: "user", text: goal))
        input = ""; busy = true
        messages.append(ChatMsg(role: "sys", text: "thinking…"))
        Task {
            do {
                let r: AgentResp = try await API.shared.post("/api/agent",
                    AgentReq(goal: goal, course_id: course.id, course_name: course.name), timeout: 240)
                messages.removeLast()
                messages.append(ChatMsg(role: "ai", text: r.answer))
            } catch {
                messages.removeLast()
                messages.append(ChatMsg(role: "sys", text: "Error: \(error.localizedDescription)"))
            }
            busy = false
        }
    }
}
