import Foundation
import MWDATCore
import SwiftUI

@main
struct MetaChatAgentApp: App {
    @StateObject private var auth = CognitoAuthService()
    @StateObject private var wearablesVM: WearablesViewModel

    init() {
        do { try Wearables.configure() } catch {
            print("Failed to configure Wearables SDK: \(error)")
        }
        let w = Wearables.shared
        _wearablesVM = StateObject(wrappedValue: WearablesViewModel(wearables: w))
    }

    var body: some Scene {
        WindowGroup {
            Group {
                if auth.isAuthenticated {
                    MainView(wearables: Wearables.shared, viewModel: wearablesVM, auth: auth)
                        .alert("Error", isPresented: $wearablesVM.showError) {
                            Button("OK") { wearablesVM.dismissError() }
                        } message: {
                            Text(wearablesVM.errorMessage)
                        }
                        .onOpenURL { url in
                            Task {
                                do {
                                    _ = try await Wearables.shared.handleUrl(url)
                                } catch {
                                    print("Failed to handle callback URL: \(error)")
                                }
                            }
                        }
                } else {
                    AuthView(auth: auth)
                }
            }
        }
    }
}
