import Foundation
import UIKit

class ChatAPIService {
    private let session = URLSession.shared
    private let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? "unknown"
    private let auth: CognitoAuthService

    init(auth: CognitoAuthService) {
        self.auth = auth
    }

    func send(prompt: String, sessionId: String) async throws -> String {
        let token = try await auth.idToken()
        let body: [String: Any] = ["prompt": prompt, "device_id": deviceId, "session_id": sessionId]

        var request = URLRequest(url: AppConfig.chatURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(token, forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 60
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        do {
            let (data, response) = try await session.data(for: request)

            guard let http = response as? HTTPURLResponse else {
                throw ChatError.invalidResponse
            }

            guard (200...299).contains(http.statusCode) else {
                print("[ChatAPI] Error status: \(http.statusCode)")
                switch http.statusCode {
                case 401: throw ChatError.unauthorized
                case 403: throw ChatError.forbidden
                default:  throw ChatError.requestFailed
                }
            }

            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let result = json["response"] as? String {
                return result
            }

            // Fallback: try to decode as plain string
            if let plainText = String(data: data, encoding: .utf8), !plainText.isEmpty {
                return plainText
            }

            throw ChatError.invalidResponse
        } catch let error as ChatError {
            throw error
        } catch {
            throw ChatError.networkError(error)
        }
    }
}

enum ChatError: LocalizedError {
    case unauthorized
    case forbidden
    case requestFailed
    case invalidResponse
    case networkError(Error)

    var errorDescription: String? {
        switch self {
        case .unauthorized: return "You are not registered. Please sign in or create an account in the app."
        case .forbidden:    return "Access denied. Please sign out and sign in again."
        case .requestFailed: return "Request failed. Please try again."
        case .invalidResponse: return "Unexpected response from the server."
        case .networkError: return "No connection. Please check your internet and try again."
        }
    }

    /// True if the error means the session is invalid and the user must re-authenticate
    var requiresSignOut: Bool {
        switch self {
        case .unauthorized, .forbidden: return true
        default: return false
        }
    }

    /// Short version for TTS — spoken through the glasses
    var spokenMessage: String {
        switch self {
        case .unauthorized: return "You are not registered. Please open the app and sign in."
        case .forbidden:    return "Access denied. Please sign in again."
        case .requestFailed: return "Something went wrong. Please try again."
        case .invalidResponse: return "I couldn't get a response. Please try again."
        case .networkError: return "No internet connection. Please check your network."
        }
    }
}
