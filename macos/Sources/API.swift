import Foundation

struct APIError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

/// Talks to the local FastAPI backend over 127.0.0.1.
final class API {
    static let shared = API()
    let base = "http://127.0.0.1:8765"

    func get<T: Decodable>(_ path: String) async throws -> T {
        guard let url = URL(string: base + path) else { throw APIError(message: "Bad URL") }
        let (data, resp) = try await URLSession.shared.data(from: url)
        try check(resp, data)
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw APIError(message: "Decode failed: \(error)") }
    }

    @discardableResult
    func post<T: Decodable, B: Encodable>(_ path: String, _ body: B, timeout: TimeInterval = 60) async throws -> T {
        let data = try await postData(path, body, timeout: timeout)
        return try JSONDecoder().decode(T.self, from: data)
    }

    func postVoid<B: Encodable>(_ path: String, _ body: B, timeout: TimeInterval = 60) async throws {
        _ = try await postData(path, body, timeout: timeout)
    }

    private func postData<B: Encodable>(_ path: String, _ body: B, timeout: TimeInterval) async throws -> Data {
        guard let url = URL(string: base + path) else { throw APIError(message: "Bad URL") }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = timeout
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(body)
        let (data, resp) = try await URLSession.shared.data(for: req)
        try check(resp, data)
        return data
    }

    private func check(_ resp: URLResponse, _ data: Data) throws {
        guard let h = resp as? HTTPURLResponse else { return }
        if h.statusCode == 401 {
            throw APIError(message: "Not signed in. Run `canvas-ai login` in Terminal, then reload.")
        }
        if h.statusCode >= 400 {
            let detail = (try? JSONDecoder().decode([String: String].self, from: data))?["detail"]
            throw APIError(message: detail ?? "HTTP \(h.statusCode)")
        }
    }

    static func q(_ s: String) -> String {
        s.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? s
    }
}
