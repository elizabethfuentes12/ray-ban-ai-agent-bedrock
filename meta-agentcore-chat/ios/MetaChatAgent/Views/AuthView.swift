import SwiftUI

struct AuthView: View {
    @ObservedObject var auth: CognitoAuthService
    @State private var email = ""
    @State private var password = ""
    @State private var confirmationCode = ""
    @State private var mode: Mode = .signIn
    @State private var pendingEmail = ""

    enum Mode { case signIn, signUp, confirm }

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 24) {
                // Icon + title
                VStack(spacing: 8) {
                    Image(systemName: "eyeglasses")
                        .font(.system(size: 56))
                        .foregroundColor(.blue)
                    Text("Meta Chat Agent")
                        .font(.title2).bold()
                    Text(mode == .confirm ? "Check your email for a verification code" : "Sign in to continue")
                        .font(.subheadline).foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }

                // Form
                VStack(spacing: 12) {
                    if mode == .confirm {
                        TextField("Verification code", text: $confirmationCode)
                            .keyboardType(.numberPad)
                            .textFieldStyle(.roundedBorder)
                    } else {
                        TextField("Email", text: $email)
                            .keyboardType(.emailAddress)
                            .autocapitalization(.none)
                            .textContentType(.emailAddress)
                            .textFieldStyle(.roundedBorder)

                        SecureField("Password", text: $password)
                            .textContentType(mode == .signUp ? .newPassword : .password)
                            .textFieldStyle(.roundedBorder)
                    }
                }

                // Error
                if let error = auth.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .multilineTextAlignment(.center)
                }

                // Primary button
                Button {
                    Task { await primaryAction() }
                } label: {
                    Group {
                        if auth.isLoading {
                            ProgressView().tint(.white)
                        } else {
                            Text(primaryLabel)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }
                .disabled(auth.isLoading || primaryDisabled)

                // Toggle mode
                if mode != .confirm {
                    Button {
                        auth.errorMessage = nil
                        mode = mode == .signIn ? .signUp : .signIn
                    } label: {
                        Text(mode == .signIn ? "Don't have an account? Sign up" : "Already have an account? Sign in")
                            .font(.footnote).foregroundColor(.blue)
                    }
                }
            }
            .padding(32)
            .background(Color(.systemBackground))
            .cornerRadius(20)
            .shadow(color: .black.opacity(0.08), radius: 16, x: 0, y: 4)
            .padding(.horizontal, 24)

            Spacer()
        }
        .background(Color(.systemGroupedBackground).ignoresSafeArea())
    }

    private var primaryLabel: String {
        switch mode {
        case .signIn: return "Sign In"
        case .signUp: return "Create Account"
        case .confirm: return "Verify"
        }
    }

    private var primaryDisabled: Bool {
        switch mode {
        case .signIn, .signUp: return email.isEmpty || password.isEmpty
        case .confirm: return confirmationCode.isEmpty
        }
    }

    private func primaryAction() async {
        switch mode {
        case .signIn:
            await auth.signIn(email: email, password: password)
        case .signUp:
            await auth.signUp(email: email, password: password)
            if auth.errorMessage == nil {
                pendingEmail = email
                mode = .confirm
            }
        case .confirm:
            await auth.confirmSignUp(email: pendingEmail, code: confirmationCode)
            if auth.errorMessage == nil {
                mode = .signIn
                email = pendingEmail
            }
        }
    }
}
