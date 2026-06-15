import SwiftUI

/// Shows a loading / error gate while the backend boots, then the app.
struct RootGate: View {
    @EnvironmentObject var backend: Backend
    @AppStorage("repoPath") private var repoPath = NSHomeDirectory() + "/Canvas-AI"
    @State private var showSettings = false

    var body: some View {
        switch backend.phase {
        case .starting:
            VStack(spacing: 14) {
                ProgressView()
                Text("Starting Canvas-AI…").foregroundStyle(.secondary)
            }
        case .ready:
            ContentView()
        case .failed(let msg):
            VStack(spacing: 16) {
                Image(systemName: "exclamationmark.triangle").font(.largeTitle).foregroundStyle(.orange)
                Text("Couldn't start the backend").font(.headline)
                Text(msg).foregroundStyle(.secondary).multilineTextAlignment(.center).frame(maxWidth: 460)
                HStack {
                    Button("Project Folder…") { showSettings = true }
                    Button("Retry") { Task { await backend.boot(repoPath: repoPath) } }
                        .buttonStyle(.borderedProminent)
                }
            }
            .padding(40)
            .sheet(isPresented: $showSettings) { SettingsSheet() }
        }
    }
}

struct SettingsSheet: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var backend: Backend
    @AppStorage("repoPath") private var repoPath = NSHomeDirectory() + "/Canvas-AI"

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Canvas-AI project folder").font(.headline)
            Text("The folder containing your .venv and .env (where you ran setup).")
                .font(.caption).foregroundStyle(.secondary)
            TextField("/Users/you/Canvas-AI", text: $repoPath)
                .textFieldStyle(.roundedBorder).frame(width: 420)
            HStack {
                Spacer()
                Button("Cancel") { dismiss() }
                Button("Save & Retry") {
                    dismiss(); Task { await backend.boot(repoPath: repoPath) }
                }.buttonStyle(.borderedProminent)
            }
        }
        .padding(20)
    }
}

enum AppTab: String, CaseIterable, Identifiable {
    case modules = "Modules", dueDates = "Due Dates", discussions = "Discussions", chat = "Chat"
    var id: String { rawValue }
}

struct ContentView: View {
    @EnvironmentObject var backend: Backend
    @State private var courses: [Course] = []
    @State private var selected: Course?
    @State private var tab: AppTab = .modules
    @State private var reader: ReaderTarget?
    @State private var loadError: String?

    var body: some View {
        NavigationSplitView {
            List(selection: $selected) {
                Section("Courses") {
                    ForEach(courses) { c in
                        Label(c.name ?? "Course \(c.id)", systemImage: "book.closed")
                            .lineLimit(2).tag(c)
                    }
                }
            }
            .navigationSplitViewColumnWidth(min: 230, ideal: 260)
        } detail: {
            if let course = selected {
                VStack(spacing: 0) {
                    Picker("", selection: $tab) {
                        ForEach(AppTab.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .labelsHidden()
                    .frame(maxWidth: 460)
                    .padding(.vertical, 12).padding(.horizontal, 16)
                    Divider()
                    Group {
                        switch tab {
                        case .modules: ModulesView(course: course) { reader = $0 }
                        case .dueDates: DueDatesView(course: course)
                        case .discussions: DiscussionsView(course: course) { reader = $0 }
                        case .chat: ChatView(course: course)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
                .navigationTitle(course.name ?? "Course")
            } else {
                Text("Select a course").foregroundStyle(.secondary)
            }
        }
        .toolbar {
            ToolbarItem(placement: .automatic) {
                if let n = backend.authName {
                    Label(n, systemImage: "person.crop.circle.fill.badge.checkmark")
                        .foregroundStyle(.green)
                } else {
                    Label("Not signed in", systemImage: "person.crop.circle.badge.exclamationmark")
                        .foregroundStyle(.orange)
                }
            }
        }
        .sheet(item: $reader) { ReaderView(target: $0, course: selected) }
        .task { await loadCourses() }
    }

    private func loadCourses() async {
        do {
            courses = try await API.shared.get("/api/courses")
            if selected == nil { selected = courses.first { ($0.name ?? "").contains("Online Health") } ?? courses.first }
        } catch { loadError = "\(error)" }
    }
}
