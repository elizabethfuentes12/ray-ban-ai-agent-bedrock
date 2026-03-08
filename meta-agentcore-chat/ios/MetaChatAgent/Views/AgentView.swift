import AVFoundation
import MWDATCore
import SwiftUI

struct AgentView: View {
    let wearables: WearablesInterface
    @ObservedObject var wearablesVM: WearablesViewModel
    @ObservedObject var auth: CognitoAuthService
    @StateObject private var voiceService = VoiceCommandService()
    @StateObject private var speechService = SpeechService()
    @State private var messages: [ChatMessage] = []
    @State private var isProcessing = false
    // New UUID per AgentView instance = new conversation each time glasses connect
    private let sessionId = UUID().uuidString
    private let api: ChatAPIService

    init(wearables: WearablesInterface, wearablesVM: WearablesViewModel, auth: CognitoAuthService) {
        self.wearables = wearables
        self.wearablesVM = wearablesVM
        self.auth = auth
        self.api = ChatAPIService(auth: auth)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Status
                VStack(spacing: 12) {
                    Image(systemName: "eyeglasses")
                        .font(.system(size: 48))
                        .foregroundColor(statusColor)
                    Text(statusText)
                        .font(.headline)
                        .multilineTextAlignment(.center)
                }.padding(.vertical, 30)

                Divider()

                // Chat history
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 10) {
                            ForEach(messages) { msg in MessageBubble(message: msg).id(msg.id) }
                        }.padding()
                    }
                    .onChange(of: messages.count) {
                        if let last = messages.last { proxy.scrollTo(last.id, anchor: .bottom) }
                    }
                }

                if isProcessing { ProgressView("Thinking...").padding(6) }

                // Manual text input (fallback)
                HStack {
                    TextField("Or type a question...", text: $manualText).textFieldStyle(.roundedBorder)
                    Button { Task { await sendManual() } } label: {
                        Image(systemName: "arrow.up.circle.fill").font(.title2)
                    }
                    .disabled(manualText.trimmingCharacters(in: .whitespaces).isEmpty || isProcessing)
                }.padding()

                // Disconnect
                Button { wearablesVM.disconnectGlasses() } label: {
                    Text("Disconnect Glasses").font(.caption).foregroundColor(.red)
                }.padding(.bottom, 8)
            }
            .navigationTitle("Meta Chat Agent")
            .navigationBarTitleDisplayMode(.inline)
            .task { await startListening() }
            .onChange(of: voiceService.triggered) { _, triggered in
                if triggered {
                    Task { await sendVoiceQuery(question: voiceService.userQuestion) }
                }
            }
            // Restart wake word listening when app returns to foreground
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                guard !isProcessing, voiceService.phase == .idle else { return }
                Task { await startListening() }
            }
            // Restart if speech recognition stops unexpectedly (not during intentional transitions)
            .onChange(of: voiceService.isListening) { _, isListening in
                guard !isListening else { return }
                Task {
                    // Wait long enough for intentional transitions (wake→question takes ~1s)
                    try? await Task.sleep(for: .seconds(2))
                    // Only restart if still idle and not processing after the delay
                    guard !isProcessing, voiceService.phase == .idle else { return }
                    await startListening()
                }
            }
        }
    }

    @State private var manualText = ""

    private var statusColor: Color {
        switch voiceService.phase {
        case .idle: return isProcessing ? .orange : .green
        case .wakeWord: return .green
        case .question: return .red
        }
    }

    private var statusText: String {
        switch voiceService.phase {
        case .idle: return isProcessing ? "Processing..." : "Say \"Hey Penelope\""
        case .wakeWord: return "Listening for \"Hey Penelope\"..."
        case .question: return "🔴 Ask your question..."
        }
    }

    private func startListening() async {
        guard await voiceService.requestPermission() else {
            print("[AgentView] Speech permission denied")
            return
        }
        do {
            try voiceService.startWakeWordListening()
            print("[AgentView] Wake word listening started")
        } catch {
            print("[AgentView] Failed to start wake word: \(error)")
        }
    }

    /// Voice triggered: send question directly (no photo capture)
    private func sendVoiceQuery(question: String) async {
        guard !isProcessing else { return }
        isProcessing = true
        let prompt = question.isEmpty ? "Hello, how can you help me?" : question
        messages.append(ChatMessage(text: "🎤 \(prompt)", isUser: true))

        do {
            let response = try await api.send(prompt: prompt, sessionId: sessionId)
            messages.append(ChatMessage(text: response, isUser: false))
            await speechService.speak(response)
        } catch let error as ChatError {
            messages.append(ChatMessage(text: error.errorDescription ?? "", isUser: false))
            await speechService.speak(error.spokenMessage)
        } catch {
            let msg = "Something went wrong. Please try again."
            messages.append(ChatMessage(text: msg, isUser: false))
            await speechService.speak(msg)
        }

        // Restart wake word listening only after TTS is fully done
        isProcessing = false
        voiceService.resetTrigger()
        try? voiceService.startWakeWordListening()
    }

    private func sendManual() async {
        let text = manualText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return }
        manualText = ""
        messages.append(ChatMessage(text: text, isUser: true))
        isProcessing = true
        defer { isProcessing = false }
        do {
            let response = try await api.send(prompt: text, sessionId: sessionId)
            messages.append(ChatMessage(text: response, isUser: false))
            await speechService.speak(response)
        } catch {
            messages.append(ChatMessage(text: "Error: \(error.localizedDescription)", isUser: false))
        }
    }
}
