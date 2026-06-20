import SwiftUI

@MainActor
final class AppState: ObservableObject {
    @AppStorage("canvasURL") var canvasURL = ""
    @AppStorage("canvasToken") var canvasToken = ""
    @AppStorage("anthropicKey") var anthropicKey = ""
    @AppStorage("model") var model = "claude-haiku-4-5-20251001"

    @Published var courses: [Course] = []
    @Published var selectedCourse: Course?
    @Published var status = "Not connected"
    @Published var loading = false

    var canvas: CanvasAPI { CanvasAPI(baseURL: canvasURL, token: canvasToken) }
    var ai: Anthropic { Anthropic(apiKey: anthropicKey, model: model) }
    var configured: Bool { !canvasURL.isEmpty && !canvasToken.isEmpty }

    func loadCourses() async {
        guard configured else { return }
        loading = true
        defer { loading = false }
        do {
            let name = try await canvas.me()
            status = name.isEmpty ? "Connected" : name
            courses = try await canvas.listCourses()
            if selectedCourse == nil { selectedCourse = courses.first }
        } catch {
            status = error.localizedDescription
        }
    }
}
