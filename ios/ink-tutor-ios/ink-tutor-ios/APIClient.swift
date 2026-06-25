//  APIClient.swift
//  Thin client for the InkTutor FastAPI backend (LAN, port 8000).
//
//  Backend must be reachable from the iPad — use the Mac's LAN IP, not
//  localhost (the iPad is not the container host). Plaintext HTTP needs an
//  ATS exception in Info.plist for the LAN IP, or run the backend over TLS.

import Foundation

// Mirrors api/services/worksheet/models.py — keep field names in sync.
struct SkillNode: Codable, Identifiable, Hashable {
    let id: String
    let label: String
    let description: String?
}

struct SkillEdge: Codable, Hashable {
    let source: String
    let target: String
    let label: String?
}

struct SkillGraph: Codable, Hashable {
    let nodes: [SkillNode]
    let edges: [SkillEdge]
}

enum APIError: Error {
    case badStatus(Int)
    case notHTTP
}

struct APIClient {
    /// e.g. URL(string: "http://192.168.1.42:8000")!
    let baseURL: URL

    /// POST /worksheet — raw PDF bytes -> skill graph.
    func worksheet(pdf: Data) async throws -> SkillGraph {
        var req = URLRequest(url: baseURL.appending(path: "worksheet"))
        req.httpMethod = "POST"
        req.setValue("application/pdf", forHTTPHeaderField: "Content-Type")

        let (data, resp) = try await URLSession.shared.upload(for: req, from: pdf)
        guard let http = resp as? HTTPURLResponse else { throw APIError.notHTTP }
        guard http.statusCode == 200 else { throw APIError.badStatus(http.statusCode) }
        return try JSONDecoder().decode(SkillGraph.self, from: data)
    }

    // /attempt fn added when backend route exists (currently TBD).
}
