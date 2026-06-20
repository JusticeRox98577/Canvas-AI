import Foundation

/// Calls the Anthropic Messages API directly with the user's own API key.
struct Anthropic {
    let apiKey: String
    var model: String

    func complete(system: String, user: String) async throws -> String {
        guard !apiKey.isEmpty else {
            throw err("Add your Anthropic API key in Settings to use AI study features.")
        }
        var req = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
        req.httpMethod = "POST"
        req.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        req.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        req.setValue("application/json", forHTTPHeaderField: "content-type")
        let payload: [String: Any] = [
            "model": model,
            "max_tokens": 1400,
            "system": system,
            "messages": [["role": "user", "content": user]],
        ]
        req.httpBody = try JSONSerialization.data(withJSONObject: payload)

        let (data, resp) = try await URLSession.shared.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code >= 400 {
            throw err("AI error \(code): \(String((String(data: data, encoding: .utf8) ?? "").prefix(200)))")
        }
        guard let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let content = obj["content"] as? [[String: Any]] else { return "" }
        return content.compactMap { $0["text"] as? String }.joined()
    }

    private func err(_ msg: String) -> NSError {
        NSError(domain: "Anthropic", code: 0, userInfo: [NSLocalizedDescriptionKey: msg])
    }
}
