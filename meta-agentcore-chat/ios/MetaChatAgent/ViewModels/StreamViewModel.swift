import MWDATCamera
import MWDATCore
import SwiftUI

@MainActor
class StreamViewModel: ObservableObject {
    @Published var currentFrame: UIImage?
    @Published var capturedPhoto: UIImage?
    @Published var showPhotoPreview = false
    @Published var streamingStatus: StreamingStatus = .stopped
    @Published var hasActiveDevice = false
    @Published var showError = false
    @Published var errorMessage = ""

    var isStreaming: Bool { streamingStatus != .stopped }

    private var streamSession: StreamSession
    private var stateToken: AnyListenerToken?
    private var frameToken: AnyListenerToken?
    private var errorToken: AnyListenerToken?
    private var photoToken: AnyListenerToken?
    private let wearables: WearablesInterface
    private let deviceSelector: AutoDeviceSelector
    private var deviceTask: Task<Void, Never>?

    enum StreamingStatus { case streaming, waiting, stopped }

    init(wearables: WearablesInterface) {
        self.wearables = wearables
        self.deviceSelector = AutoDeviceSelector(wearables: wearables)
        let config = StreamSessionConfig(videoCodec: .raw, resolution: .low, frameRate: 24)
        streamSession = StreamSession(streamSessionConfig: config, deviceSelector: deviceSelector)

        deviceTask = Task { @MainActor in
            for await device in deviceSelector.activeDeviceStream() {
                self.hasActiveDevice = device != nil
            }
        }

        stateToken = streamSession.statePublisher.listen { [weak self] state in
            Task { @MainActor in self?.updateStatus(state) }
        }
        frameToken = streamSession.videoFramePublisher.listen { [weak self] frame in
            Task { @MainActor in self?.currentFrame = frame.makeUIImage() }
        }
        errorToken = streamSession.errorPublisher.listen { [weak self] error in
            Task { @MainActor in self?.showError(self?.formatError(error) ?? "Unknown error") }
        }
        photoToken = streamSession.photoDataPublisher.listen { [weak self] photoData in
            Task { @MainActor in
                guard let self else { return }
                if let img = UIImage(data: photoData.data) {
                    self.capturedPhoto = img
                    self.showPhotoPreview = true
                }
            }
        }
        updateStatus(streamSession.state)
    }

    func startStreaming() async {
        do {
            let status = try await wearables.checkPermissionStatus(.camera)
            if status != .granted {
                let req = try await wearables.requestPermission(.camera)
                guard req == .granted else { showError("Camera permission denied"); return }
            }
            await streamSession.start()
        } catch { showError("Permission error: \(error.localizedDescription)") }
    }

    func stopStreaming() async { await streamSession.stop() }
    func capturePhoto() { streamSession.capturePhoto(format: .jpeg) }
    func capturedPhotoData() -> Data? { capturedPhoto?.jpegData(compressionQuality: 0.8) }
    func dismissPhotoPreview() { showPhotoPreview = false; capturedPhoto = nil }
    func showError(_ msg: String) { errorMessage = msg; showError = true }
    func dismissError() { showError = false; errorMessage = "" }

    private func updateStatus(_ state: StreamSessionState) {
        switch state {
        case .stopped: currentFrame = nil; streamingStatus = .stopped
        case .streaming: streamingStatus = .streaming
        default: streamingStatus = .waiting
        }
    }

    private func formatError(_ error: StreamSessionError) -> String {
        switch error {
        case .deviceNotConnected: return "Device not connected."
        case .permissionDenied: return "Camera permission denied."
        case .hingesClosed: return "Glasses hinges are closed."
        case .timeout: return "Connection timed out."
        default: return "Streaming error occurred."
        }
    }
}
