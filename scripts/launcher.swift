import AppKit
import Foundation

struct AnimationSpec: Decodable {
    let fps: Double
    let frameCount: Int
}

final class LauncherDelegate: NSObject, NSApplicationDelegate {
    private var frames = [NSImage]()
    private var fps = 24.0
    private var animationStarted = 0.0
    private var timer: Timer?
    private var animationFinished = false
    private var startupFinished = false
    private var startupError: String?
    private var animationWarning = false
    private var task: Process?
    private var lastFrame = -1
    private let began = ProcessInfo.processInfo.systemUptime
    private var logURL: URL?
    private var outputHandle: FileHandle?

    private func event(_ message: String) {
        print(String(format: "launcher %.3f %@", ProcessInfo.processInfo.systemUptime - began, message))
        fflush(stdout)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            let resources = Bundle.main.resourceURL!
            let spec = try JSONDecoder().decode(AnimationSpec.self, from: Data(contentsOf: resources.appendingPathComponent("animation.json")))
            fps = spec.fps
            for index in 0..<spec.frameCount {
                let file = resources.appendingPathComponent(String(format: "frames/frame-%03d.png", index))
                guard let image = NSImage(contentsOf: file) else {
                    throw NSError(domain: "启动动画无法读取：\(file.lastPathComponent)", code: 1)
                }
                image.size = NSSize(width: 256, height: 256)
                frames.append(image)
            }
            guard fps > 0, !frames.isEmpty else { throw NSError(domain: "启动动画清单无效", code: 1) }
            NSApp.applicationIconImage = frames[0]
            if CommandLine.arguments.contains("--preview") {
                startupFinished = true
                event("preview-only")
            } else {
                try startCodex()
            }
            animationStarted = ProcessInfo.processInfo.systemUptime
            event("animation-start")
            let timer = Timer(timeInterval: 1 / fps, repeats: true) { [weak self] _ in self?.advanceFrame() }
            self.timer = timer
            RunLoop.main.add(timer, forMode: .common)
            advanceFrame()
        } catch {
            startupError = error.localizedDescription
            startupFinished = true
            animationFinished = true
            finishIfReady()
        }
    }

    private func startCodex() throws {
        let root = Bundle.main.bundleURL.deletingLastPathComponent()
        let log = FileManager.default.temporaryDirectory.appendingPathComponent("codex-launcher-\(UUID().uuidString).log")
        try Data().write(to: log)
        let handle = try FileHandle(forWritingTo: log)
        logURL = log
        outputHandle = handle
        let process = Process()
        process.executableURL = URL(fileURLWithPath: Bundle.main.object(forInfoDictionaryKey: "LauncherNodePath") as! String)
        process.arguments = [root.appendingPathComponent("scripts/start.mjs").path]
        process.currentDirectoryURL = root
        var environment = ProcessInfo.processInfo.environment
        environment["CODEX_LAUNCH_ANIMATION_START_MS"] = String(Date().timeIntervalSince1970 * 1000)
        process.environment = environment
        process.standardOutput = handle
        process.standardError = handle
        process.terminationHandler = { [weak self] completed in
            DispatchQueue.main.async {
                guard let self else { return }
                do {
                    try handle.close()
                    self.outputHandle = nil
                    let output = try String(contentsOf: log, encoding: .utf8)
                    try FileManager.default.removeItem(at: log)
                    self.logURL = nil
                    if completed.terminationStatus != 0 {
                        self.animationWarning = completed.terminationStatus == 3
                        self.startupError = self.animationWarning ? output : "启动脚本退出码：\(completed.terminationStatus)\n\(output)"
                    }
                } catch {
                    self.startupError = "读取启动结果失败：\(error.localizedDescription)"
                }
                self.startupFinished = true
                self.event("startup-finished status=\(completed.terminationStatus)")
                self.finishIfReady()
            }
        }
        task = process
        try process.run()
        event("startup-dispatched")
    }

    private func advanceFrame() {
        let index = Int((ProcessInfo.processInfo.systemUptime - animationStarted) * fps)
        if index >= frames.count {
            NSApp.applicationIconImage = frames.last
            timer?.invalidate()
            timer = nil
            animationFinished = true
            event("animation-finished")
            finishIfReady()
        } else if index != lastFrame {
            NSApp.applicationIconImage = frames[index]
            lastFrame = index
        }
    }

    private func finishIfReady() {
        guard startupFinished && animationFinished else { return }
        if let startupError {
            event("startup-error")
            NSApp.activate(ignoringOtherApps: true)
            let alert = NSAlert()
            alert.messageText = animationWarning ? "Codex 已启动，图标动画未完成" : "Codex 项目资料启动失败"
            alert.informativeText = startupError
            alert.alertStyle = .warning
            alert.addButton(withTitle: "好")
            alert.runModal()
        }
        NSApp.applicationIconImage = nil
        event("exit")
        NSApp.terminate(nil)
    }
}

let application = NSApplication.shared
let delegate = LauncherDelegate()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
