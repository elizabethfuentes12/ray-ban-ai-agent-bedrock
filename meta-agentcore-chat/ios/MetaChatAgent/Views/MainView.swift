import MWDATCore
import SwiftUI

struct MainView: View {
    let wearables: WearablesInterface
    @ObservedObject var viewModel: WearablesViewModel
    @ObservedObject var auth: CognitoAuthService

    var body: some View {
        if viewModel.registrationState == .registered {
            AgentView(wearables: wearables, wearablesVM: viewModel, auth: auth)
        } else {
            HomeView(viewModel: viewModel, auth: auth)
        }
    }
}

struct HomeView: View {
    @ObservedObject var viewModel: WearablesViewModel
    @ObservedObject var auth: CognitoAuthService

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "eyeglasses")
                .font(.system(size: 64)).foregroundColor(.blue)
            Text("Meta Chat Agent").font(.title).bold()
            Text("Connect your Meta Ray-Ban glasses to chat with AI using voice commands.")
                .multilineTextAlignment(.center).foregroundColor(.secondary).padding(.horizontal)

            Button {
                viewModel.connectGlasses()
            } label: {
                HStack {
                    if viewModel.registrationState == .registering { ProgressView().tint(.white) }
                    Text(viewModel.registrationState == .registering ? "Connecting..." : "Connect Glasses")
                }
                .frame(maxWidth: .infinity).padding()
                .background(Color.blue).foregroundColor(.white).cornerRadius(12)
            }
            .disabled(viewModel.registrationState == .registering)
            .padding(.horizontal, 40)

            Button("Sign Out") { auth.signOut() }
                .font(.footnote).foregroundColor(.secondary)
        }
    }
}
