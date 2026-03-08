import MWDATCore
import SwiftUI

@MainActor
class WearablesViewModel: ObservableObject {
    @Published var devices: [DeviceIdentifier]
    @Published var registrationState: RegistrationState
    @Published var showError = false
    @Published var errorMessage = ""

    private var registrationTask: Task<Void, Never>?
    private var deviceStreamTask: Task<Void, Never>?
    private let wearables: WearablesInterface

    init(wearables: WearablesInterface) {
        self.wearables = wearables
        self.devices = wearables.devices
        self.registrationState = wearables.registrationState

        registrationTask = Task {
            for await state in wearables.registrationStateStream() {
                self.registrationState = state
            }
        }
        deviceStreamTask = Task {
            for await devices in wearables.devicesStream() {
                self.devices = devices
            }
        }
    }

    deinit { registrationTask?.cancel(); deviceStreamTask?.cancel() }

    func connectGlasses() {
        guard registrationState != .registering else { return }
        Task {
            do { try await wearables.startRegistration() }
            catch { showError(error.localizedDescription) }
        }
    }

    func disconnectGlasses() {
        Task {
            do { try await wearables.startUnregistration() }
            catch { showError(error.localizedDescription) }
        }
    }

    func showError(_ msg: String) { errorMessage = msg; showError = true }
    func dismissError() { showError = false }
}
