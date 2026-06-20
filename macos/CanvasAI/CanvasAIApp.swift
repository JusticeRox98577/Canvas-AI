import SwiftUI

@main
struct CanvasAIApp: App {
    @StateObject private var app = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(app)
                .frame(minWidth: 940, minHeight: 600)
        }
    }
}
