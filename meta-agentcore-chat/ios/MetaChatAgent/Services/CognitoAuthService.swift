import Foundation
import Security

/// Handles Cognito sign up, sign in, token refresh and secure storage.
/// Uses USER_PASSWORD_AUTH flow via Cognito REST API — no SDK required.
@MainActor
class CognitoAuthService: ObservableObject {
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let session = URLSession.shared

    init() {
        // Check Keychain synchronously before first render
        // so the app never flashes AuthView when a valid session exists
        restoreSession()
    }
    private let endpoint = "https://cognito-idp.\(AppConfig.awsRegion).amazonaws.com/"

    // MARK: - Public API

    func signIn(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let result = try await initiateAuth(flow: "USER_PASSWORD_AUTH", params: [
                "USERNAME": email,
                "PASSWORD": password,
            ])
            try saveTokens(from: result)
            isAuthenticated = true
        } catch let error as CognitoError {
            errorMessage = error.message
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func signUp(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            try await callCognito(target: "SignUp", body: [
                "ClientId": AppConfig.appClientId,
                "Username": email,
                "Password": password,
                "UserAttributes": [["Name": "email", "Value": email]],
            ])
        } catch let error as CognitoError {
            errorMessage = error.message
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func confirmSignUp(email: String, code: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            try await callCognito(target: "ConfirmSignUp", body: [
                "ClientId": AppConfig.appClientId,
                "Username": email,
                "ConfirmationCode": code,
            ])
        } catch let error as CognitoError {
            errorMessage = error.message
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func signOut() {
        Keychain.delete(key: "idToken")
        Keychain.delete(key: "refreshToken")
        isAuthenticated = false
    }

    /// Returns a valid ID token, refreshing if expired.
    func idToken() async throws -> String {
        if let token = Keychain.read(key: "idToken"), !isTokenExpired(token) {
            return token
        }
        guard let refresh = Keychain.read(key: "refreshToken") else {
            // No refresh token at all — must sign in
            signOut()
            throw CognitoError(message: "Session expired. Please sign in again.")
        }
        do {
            let result = try await initiateAuth(flow: "REFRESH_TOKEN_AUTH", params: [
                "REFRESH_TOKEN": refresh,
            ])
            try saveTokens(from: result)
            guard let token = Keychain.read(key: "idToken") else {
                throw CognitoError(message: "Failed to refresh session.")
            }
            return token
        } catch let error as CognitoError {
            // Only force sign-out if Cognito explicitly rejects the token (invalid/revoked)
            // Network errors should NOT sign the user out
            let isAuthError = error.message.lowercased().contains("notauthorized")
                || error.message.lowercased().contains("invalid")
                || error.message.lowercased().contains("expired")
            if isAuthError {
                signOut()
            }
            throw error
        }
    }

    func restoreSession() {
        if let token = Keychain.read(key: "idToken"), !isTokenExpired(token) {
            isAuthenticated = true
        } else if Keychain.read(key: "refreshToken") != nil {
            isAuthenticated = true  // Will refresh lazily on next API call
        }
    }

    // MARK: - Private

    private func initiateAuth(flow: String, params: [String: String]) async throws -> [String: Any] {
        let response = try await callCognito(target: "InitiateAuth", body: [
            "AuthFlow": flow,
            "AuthParameters": params,
            "ClientId": AppConfig.appClientId,
        ])
        guard let auth = response["AuthenticationResult"] as? [String: Any] else {
            throw CognitoError(message: "Invalid auth response.")
        }
        return auth
    }

    @discardableResult
    private func callCognito(target: String, body: [String: Any]) async throws -> [String: Any] {
        var request = URLRequest(url: URL(string: endpoint)!)
        request.httpMethod = "POST"
        request.setValue("application/x-amz-json-1.1", forHTTPHeaderField: "Content-Type")
        request.setValue("AWSCognitoIdentityProviderService.\(target)", forHTTPHeaderField: "X-Amz-Target")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)
        let json = (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]

        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            let message = json["message"] as? String ?? json["Message"] as? String ?? "Authentication error."
            throw CognitoError(message: message)
        }
        return json
    }

    private func saveTokens(from result: [String: Any]) throws {
        guard let idToken = result["IdToken"] as? String else {
            throw CognitoError(message: "Missing ID token in response.")
        }
        Keychain.save(key: "idToken", value: idToken)
        if let refresh = result["RefreshToken"] as? String {
            Keychain.save(key: "refreshToken", value: refresh)
        }
    }

    private func isTokenExpired(_ token: String) -> Bool {
        let parts = token.split(separator: ".")
        guard parts.count == 3,
              let payloadData = Data(base64Encoded: String(parts[1]).paddedBase64),
              let payload = try? JSONSerialization.jsonObject(with: payloadData) as? [String: Any],
              let exp = payload["exp"] as? TimeInterval else {
            return true
        }
        return Date().timeIntervalSince1970 >= exp - 60  // 60s buffer
    }
}

// MARK: - CognitoError

struct CognitoError: Error {
    let message: String
}

// MARK: - Keychain

enum Keychain {
    static func save(key: String, value: String) {
        let data = Data(value.utf8)
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrAccount: key,
            kSecValueData: data,
        ]
        SecItemDelete(query as CFDictionary)
        SecItemAdd(query as CFDictionary, nil)
    }

    static func read(key: String) -> String? {
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrAccount: key,
            kSecReturnData: true,
            kSecMatchLimit: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(key: String) {
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrAccount: key,
        ]
        SecItemDelete(query as CFDictionary)
    }
}

// MARK: - Base64 padding helper

private extension String {
    var paddedBase64: String {
        let remainder = count % 4
        return remainder == 0 ? self : self + String(repeating: "=", count: 4 - remainder)
    }
}
