import SwiftUI
import AppKit

struct ContentView: View {
    @EnvironmentObject var app: AppState
    @State private var tab = "study"
    @State private var showSettings = false

    var body: some View {
        NavigationSplitView {
            List(selection: Binding(
                get: { app.selectedCourse?.id },
                set: { id in app.selectedCourse = app.courses.first { $0.id == id } }
            )) {
                Section("Courses") {
                    ForEach(app.courses) { c in Text(c.displayName).tag(c.id) }
                }
            }
            .frame(minWidth: 210)
            .overlay {
                if app.courses.isEmpty {
                    Text(app.configured ? "No courses yet" : "Add your Canvas details in Settings")
                        .font(.callout).foregroundStyle(.secondary).padding()
                        .multilineTextAlignment(.center)
                }
            }
        } detail: {
            VStack(spacing: 0) {
                Picker("", selection: $tab) {
                    Text("Study").tag("study")
                    Text("Modules").tag("modules")
                    Text("Due Dates").tag("due")
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .frame(maxWidth: 360)
                .padding(10)
                Divider()
                switch tab {
                case "modules": ModulesView()
                case "due": DueDatesView()
                default: StudyView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .toolbar {
                ToolbarItem(placement: .automatic) {
                    Text(app.status).foregroundStyle(.secondary).lineLimit(1)
                }
                ToolbarItem(placement: .automatic) {
                    Button { showSettings = true } label: { Image(systemName: "gearshape") }
                }
            }
        }
        .sheet(isPresented: $showSettings) { SettingsView() }
        .task {
            if app.configured { await app.loadCourses() } else { showSettings = true }
        }
    }
}

// MARK: - Study

struct StudyView: View {
    @EnvironmentObject var app: AppState
    @State private var topic = ""
    @State private var output = ""
    @State private var busy = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if let c = app.selectedCourse {
                    Text("Study · \(c.displayName)").font(.title2).bold()
                    Text("Grounded in your real course material.").foregroundStyle(.secondary)
                    TextField("Optional: focus on a topic or module", text: $topic)
                        .textFieldStyle(.roundedBorder)
                    HStack {
                        btn("Quiz me") { "Write 5 practice quiz questions to test my understanding\(topicPart) in the course \"\(c.displayName)\", then give an answer key at the end." }
                        btn("Flashcards") { "Make 8 flashcards as \"Term — Definition\" for the key concepts\(topicPart) in the course \"\(c.displayName)\"." }
                        btn("Explain") { "Explain the most important concepts I should understand\(topicPart) in the course \"\(c.displayName)\", in simple plain terms." }
                        btn("Summarize") { "Give me a concise review summary of the key points\(topicPart) in the course \"\(c.displayName)\"." }
                    }
                    if busy { ProgressView().padding(.top, 4) }
                    if !output.isEmpty {
                        Text(output)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                            .background(Color(nsColor: .controlBackgroundColor))
                            .cornerRadius(10)
                    }
                } else {
                    Text("Pick a course on the left to study it.").foregroundStyle(.secondary)
                }
            }
            .padding(20)
        }
    }

    private var topicPart: String { topic.trimmingCharacters(in: .whitespaces).isEmpty ? "" : " about \(topic)" }

    private func btn(_ label: String, _ goal: @escaping () -> String) -> some View {
        Button(label) { run(goal()) }.disabled(busy || app.anthropicKey.isEmpty)
    }

    private func run(_ goal: String) {
        busy = true; output = ""
        Task {
            defer { busy = false }
            do {
                output = try await app.ai.complete(
                    system: "You are a study tutor helping a student learn. Be clear, accurate, and concise.",
                    user: goal)
            } catch { output = error.localizedDescription }
        }
    }
}

// MARK: - Modules

struct ModulesView: View {
    @EnvironmentObject var app: AppState
    @State private var modules: [Module] = []
    @State private var pageTitle = ""
    @State private var pageText = ""
    @State private var showPage = false

    var body: some View {
        Group {
            if app.selectedCourse == nil {
                Text("Pick a course.").foregroundStyle(.secondary)
            } else if modules.isEmpty {
                Text("No modules in this course.").foregroundStyle(.secondary)
            } else {
                List {
                    ForEach(modules) { m in
                        Section(m.name ?? "Module") {
                            ForEach(m.items ?? []) { it in
                                Button { open(it) } label: {
                                    HStack {
                                        Text((it.type ?? "").uppercased())
                                            .font(.caption2).foregroundStyle(.secondary)
                                            .frame(width: 86, alignment: .leading)
                                        Text(it.title ?? "")
                                        Spacer()
                                    }
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
            }
        }
        .task(id: app.selectedCourse?.id) { await load() }
        .sheet(isPresented: $showPage) { PageSheet(title: pageTitle, text: pageText) }
    }

    private func load() async {
        guard let c = app.selectedCourse else { return }
        modules = (try? await app.canvas.listModules(courseID: c.id)) ?? []
    }

    private func open(_ it: ModuleItem) {
        if it.type == "Page", let pu = it.page_url, let c = app.selectedCourse {
            Task {
                if let p = try? await app.canvas.readPage(courseID: c.id, pageURL: pu) {
                    pageTitle = p.title ?? "Page"
                    pageText = htmlToText(p.body ?? "")
                    showPage = true
                }
            }
        } else if let u = it.html_url, let url = URL(string: u) {
            NSWorkspace.shared.open(url)
        }
    }
}

struct PageSheet: View {
    let title: String
    let text: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(title).font(.title3).bold()
                Spacer()
                Button("Done") { dismiss() }
            }
            ScrollView {
                Text(text.isEmpty ? "(no text)" : text)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding()
        .frame(width: 580, height: 520)
    }
}

// MARK: - Due Dates

struct DueDatesView: View {
    @EnvironmentObject var app: AppState
    @State private var rows: [Assignment] = []

    var body: some View {
        Group {
            if app.selectedCourse == nil {
                Text("Pick a course.").foregroundStyle(.secondary)
            } else {
                let due = rows.filter { $0.due_at != nil }
                if due.isEmpty {
                    Text("Nothing with a due date.").foregroundStyle(.secondary)
                } else {
                    List(due) { a in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(a.name ?? "").bold()
                                Text(fmt(a.due_at)).font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if let u = a.html_url, let url = URL(string: u) { Link("Open", destination: url) }
                        }
                    }
                }
            }
        }
        .task(id: app.selectedCourse?.id) { await load() }
    }

    private func load() async {
        guard let c = app.selectedCourse else { return }
        rows = (try? await app.canvas.listAssignments(courseID: c.id)) ?? []
    }

    private func fmt(_ s: String?) -> String {
        guard let s, let d = ISO8601DateFormatter().date(from: s) else { return s ?? "" }
        let f = DateFormatter(); f.dateStyle = .medium; f.timeStyle = .short
        return f.string(from: d)
    }
}

// MARK: - Settings

struct SettingsView: View {
    @EnvironmentObject var app: AppState
    @Environment(\.dismiss) private var dismiss
    @AppStorage("canvasURL") private var canvasURL = ""
    @AppStorage("canvasToken") private var canvasToken = ""
    @AppStorage("anthropicKey") private var anthropicKey = ""
    @AppStorage("model") private var model = "claude-haiku-4-5-20251001"

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Settings").font(.title2).bold()

            field("Canvas URL", "https://yourschool.instructure.com", text: $canvasURL)

            VStack(alignment: .leading, spacing: 4) {
                Text("Canvas access token").bold()
                Text("Canvas → Account → Settings → + New Access Token")
                    .font(.caption).foregroundStyle(.secondary)
                SecureField("token", text: $canvasToken).textFieldStyle(.roundedBorder)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Anthropic API key").bold()
                Text("Powers the study features. Get one at console.anthropic.com")
                    .font(.caption).foregroundStyle(.secondary)
                SecureField("sk-ant-…", text: $anthropicKey).textFieldStyle(.roundedBorder)
            }

            field("AI model", "claude-haiku-4-5-20251001", text: $model)

            HStack {
                Button("Save & Connect") {
                    Task { await app.loadCourses(); dismiss() }
                }
                .keyboardShortcut(.defaultAction)
                Button("Close") { dismiss() }
                Spacer()
                Text(app.status).font(.caption).foregroundStyle(.secondary)
            }
            Text("Your token and key stay on this Mac. Canvas-AI is not affiliated with Instructure.")
                .font(.caption2).foregroundStyle(.secondary)
        }
        .padding(24)
        .frame(width: 480)
    }

    private func field(_ label: String, _ placeholder: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).bold()
            TextField(placeholder, text: text).textFieldStyle(.roundedBorder)
        }
    }
}
