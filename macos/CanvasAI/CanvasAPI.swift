import Foundation

enum CanvasError: LocalizedError {
    case notConfigured
    case http(Int, String)
    var errorDescription: String? {
        switch self {
        case .notConfigured: return "Set your Canvas URL and access token in Settings."
        case .http(let code, let msg):
            if code == 401 { return "Canvas rejected your token (401). Check your access token in Settings." }
            return "Canvas error \(code): \(msg)"
        }
    }
}

/// Talks to the official Canvas REST API using a personal access token.
struct CanvasAPI {
    let baseURL: String
    let token: String

    private var apiRoot: String {
        baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/ ")) + "/api/v1"
    }

    private func get(_ path: String, query: [URLQueryItem] = []) async throws -> Data {
        guard !baseURL.isEmpty, !token.isEmpty, var comps = URLComponents(string: apiRoot + path) else {
            throw CanvasError.notConfigured
        }
        var q = query
        q.append(URLQueryItem(name: "per_page", value: "100"))
        comps.queryItems = q
        var req = URLRequest(url: comps.url!)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, resp) = try await URLSession.shared.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code >= 400 {
            throw CanvasError.http(code, String((String(data: data, encoding: .utf8) ?? "").prefix(160)))
        }
        return data
    }

    func me() async throws -> String {
        struct U: Codable { let name: String? }
        let data = try await get("/users/self")
        return (try? JSONDecoder().decode(U.self, from: data))?.name ?? ""
    }

    func listCourses() async throws -> [Course] {
        let data = try await get("/courses", query: [
            URLQueryItem(name: "enrollment_state", value: "active")
        ])
        return try JSONDecoder().decode([Course].self, from: data).filter { $0.name != nil }
    }

    func listModules(courseID: Int) async throws -> [Module] {
        let data = try await get("/courses/\(courseID)/modules",
                                 query: [URLQueryItem(name: "include[]", value: "items")])
        return try JSONDecoder().decode([Module].self, from: data)
    }

    func listAssignments(courseID: Int) async throws -> [Assignment] {
        let data = try await get("/courses/\(courseID)/assignments")
        return try JSONDecoder().decode([Assignment].self, from: data)
    }

    func readPage(courseID: Int, pageURL: String) async throws -> Page {
        let data = try await get("/courses/\(courseID)/pages/\(pageURL)")
        return try JSONDecoder().decode(Page.self, from: data)
    }
}
