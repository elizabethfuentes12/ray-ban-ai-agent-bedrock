import Speech
import AVFoundation

/// Two-phase voice: wake word detection → then capture the actual question.
@MainActor
class VoiceCommandService: ObservableObject {
    @Published var isListening = false
    @Published var phase: Phase = .idle
    @Published var userQuestion = ""
    @Published var triggered = false

    enum Phase {
        case idle       // Not listening
        case wakeWord   // Listening for "Hey Penelope"
        case question   // Wake word heard, capturing the question
    }

    static let wakeWord = "penelope"

    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private let audioEngine = AVAudioEngine()
    private let feedbackSynth = AVSpeechSynthesizer()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var silenceTask: Task<Void, Never>?
    private var restartTask: Task<Void, Never>?
    private var hasTapInstalled = false

    // SFSpeechRecognizer has a ~1 min limit per session — restart before it cuts off
    private static let sessionDuration: Double = 50

    func requestPermission() async -> Bool {
        await withCheckedContinuation { c in
            SFSpeechRecognizer.requestAuthorization { c.resume(returning: $0 == .authorized) }
        }
    }

    /// Start listening for the wake word "Hey Penelope"
    func startWakeWordListening() throws {
        stop()
        phase = .wakeWord
        scheduleSessionRestart()
        try startRecognition { [weak self] text in
            guard let self, self.phase == .wakeWord else { return }
            if text.lowercased().contains(Self.wakeWord) {
                print("[VoiceCommand] 🔴 Wake word detected!")

                // Set phase to idle immediately to prevent re-triggering
                self.phase = .idle

                // Speak "Ready" BEFORE stopping — audio session is still active
                let utterance = AVSpeechUtterance(string: "Ready")
                utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
                utterance.rate = 0.55
                utterance.volume = 1.0
                self.feedbackSynth.speak(utterance)

                // Stop recognition and wait for "Ready" to finish, then start question
                self.stop()
                Task { @MainActor [weak self] in
                    try? await Task.sleep(for: .seconds(1))
                    try? self?.startQuestionListening()
                }
            }
        }
    }

    /// After wake word, capture the user's question until 2s of silence.
    /// If no speech detected within 6s, cancels and returns to wake word listening.
    private func startQuestionListening() throws {
        phase = .question
        userQuestion = ""

        // No-speech timeout: if user says nothing, go back to wake word after 6s
        silenceTask = Task { @MainActor [weak self] in
            guard let self else { return }
            do {
                try await Task.sleep(for: .seconds(6))
                guard self.phase == .question, self.userQuestion.isEmpty else { return }
                print("[VoiceCommand] No speech detected — returning to wake word")
                self.stop()
                try? self.startWakeWordListening()
            } catch {}
        }

        try startRecognition { [weak self] text in
            guard let self, self.phase == .question else { return }

            // Remove wake word and ignore empty results (emitted when session closes)
            let cleaned = text.lowercased()
                .replacingOccurrences(of: Self.wakeWord, with: "")
                .trimmingCharacters(in: .whitespaces)
            guard !cleaned.isEmpty else { return }
            self.userQuestion = cleaned

            // Cancel previous silence countdown and restart it
            self.silenceTask?.cancel()
            self.silenceTask = Task { @MainActor [weak self] in
                guard let self else { return }
                do {
                    try await Task.sleep(for: .seconds(2))
                    self.triggered = true
                    self.stop()
                } catch {}
            }
        }
    }

    private func scheduleSessionRestart() {
        restartTask?.cancel()
        restartTask = Task { @MainActor [weak self] in
            guard let self else { return }
            do {
                try await Task.sleep(for: .seconds(Self.sessionDuration))
                guard self.phase == .wakeWord else { return }
                print("[VoiceCommand] Restarting session (50s limit)")
                try? self.startWakeWordListening()
            } catch {}
        }
    }

    func stop() {
        silenceTask?.cancel()
        silenceTask = nil
        restartTask?.cancel()
        restartTask = nil

        if audioEngine.isRunning {
            audioEngine.stop()
        }

        if hasTapInstalled {
            audioEngine.inputNode.removeTap(onBus: 0)
            hasTapInstalled = false
        }

        request?.endAudio()
        request = nil
        task?.cancel()
        task = nil
        isListening = false
        if !triggered { phase = .idle }
    }

    func resetTrigger() {
        silenceTask?.cancel()
        silenceTask = nil
        triggered = false
        userQuestion = ""
        phase = .idle
    }

    private func startRecognition(onResult: @escaping (String) -> Void) throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .voiceChat, options: [.allowBluetoothHFP, .mixWithOthers])
        try session.setActive(true, options: .notifyOthersOnDeactivation)

        // Force audio input to Bluetooth (Meta glasses mic)
        let route = session.currentRoute
        for input in route.inputs {
            print("[VoiceCommand] Audio input: \(input.portName) type: \(input.portType.rawValue)")
        }
        if let btInput = session.availableInputs?.first(where: { $0.portType == .bluetoothHFP }) {
            try session.setPreferredInput(btInput)
            print("[VoiceCommand] Using Bluetooth mic: \(btInput.portName)")
        } else {
            print("[VoiceCommand] No Bluetooth mic found, using iPhone mic")
        }

        request = SFSpeechAudioBufferRecognitionRequest()
        guard let request, let recognizer, recognizer.isAvailable else {
            print("[VoiceCommand] Recognizer not available")
            return
        }
        request.shouldReportPartialResults = true

        let node = audioEngine.inputNode
        let recordingFormat = node.inputFormat(forBus: 0)

        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard self != nil else { return }

            if let error {
                let nsError = error as NSError
                // Expected errors when we cancel deliberately — suppress them
                let expectedErrors: [(String, Int)] = [
                    ("kAFAssistantErrorDomain", 1110), // No speech detected
                    ("kLSRErrorDomain", 301),          // Recognition request was canceled
                ]
                let isExpected = expectedErrors.contains { nsError.domain == $0 && nsError.code == $1 }
                if !isExpected {
                    print("[VoiceCommand] Error: \(error)")
                }
                if result == nil { return }
            }

            guard let result else { return }

            let text = result.bestTranscription.formattedString
            print("[VoiceCommand] Heard: '\(text)'")
            DispatchQueue.main.async { onResult(text) }
            // Don't call stop() on isFinal — silenceTask handles stopping for question phase
        }

        node.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            // Ignore empty buffers during engine transitions
            guard buffer.frameLength > 0 else { return }
            request.append(buffer)
        }
        hasTapInstalled = true

        audioEngine.prepare()
        try audioEngine.start()
        isListening = true
        print("[VoiceCommand] Recognition started, phase: \(phase)")
    }
}
