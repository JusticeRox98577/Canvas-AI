import SwiftUI

@main
struct CanvasAIApp: App {
    @StateObject private var backend = Backend()
    // Where the Python project lives (contains .venv and .env). Editable in-app.
    @AppStorage("repoPath") private var repoPath = NSHomeDirectory() + "/Canvas-AI"

    var body: some Scene {
        WindowGroup {
            RootGate()
                .environmentObject(backend)
                .tint(.indigo)
                .frame(minWidth: 1000, minHeight: 680)
                .task { await backend.boot(repoPath: repoPath) }
        }
        .windowStyle(.titleBar)
        .commands { SidebarCommands() }
    }
}

/// Manages the lifecycle of the local Python backend process.
@MainActor
final class Backend: ObservableObject {
    enum Phase: Equatable {
        case starting, ready, failed(String)
    }
    @Published var phase: Phase = .starting
    @Published var authName: String?

    private var process: Process?

    func boot(repoPath: String) async {
        phase = .starting
        if await ping() { await refreshAuth(); phase = .ready; return }

        let py = repoPath + "/.venv/bin/python"
        guard FileManager.default.fileExists(atPath: py) else {
            phase = .failed("No Python environment at \(py).\nOpen Settings and point to your Canvas-AI folder.")
            return
        }
        let p = Process()
        p.currentDirectoryURL = URL(fileURLWithPath: repoPath)
        p.executableURL = URL(fileURLWithPath: py)
        p.arguments = ["-m", "uvicorn", "canvas_ai.web.app:app",
                       "--host", "127.0.0.1", "--port", "8765", "--log-level", "warning"]
        do { try p.run() } catch {
            phase = .failed("Couldn't launch backend: \(error.localizedDescription)")
            return
        }
        process = p

        for _ in 0..<60 {  // up to ~30s for first boot
            if await ping() { await refreshAuth(); phase = .ready; return }
            try? await Task.sleep(nanoseconds: 500_000_000)
        }
        phase = .failed("Backend did not become ready. Is the venv set up?")
    }

    func ping() async -> Bool {
        guard let url = URL(string: API.shared.base + "/api/status") else { return false }
        var req = URLRequest(url: url)
        req.timeoutInterval = 2
        guard let (_, resp) = try? await URLSession.shared.data(for: req) else { return false }
        return (resp as? HTTPURLResponse)?.statusCode == 200
    }

    func refreshAuth() async {
        if let s: Status = try? await API.shared.get("/api/status") {
            authName = s.authenticated ? s.name : nil
        }
    }

    func shutdown() { process?.terminate() }
}
