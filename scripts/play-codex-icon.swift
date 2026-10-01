import AppKit
import Foundation
let appPath = CommandLine.arguments[1]
let assets = URL(fileURLWithPath: CommandLine.arguments[2])
struct Spec: Decodable { let fps: Double; let frameCount: Int; let readyDelayMs: Double }
let spec = try JSONDecoder().decode(Spec.self, from: Data(contentsOf: assets.appendingPathComponent("animation.json")))
let workspace = NSWorkspace.shared
func set(_ image: NSImage, phase: String = "恢复彩色") throws {
    guard workspace.setIcon(image, forFile: appPath, options: []) else { throw NSError(domain:"CodexIcon",code:1,userInfo:[NSLocalizedDescriptionKey:"图标更新失败（\(phase)）：macOS 拒绝设置自定义图标，目标 \(appPath)"]) }
}
func image(_ name: String) throws -> NSImage {
    guard let result = NSImage(contentsOf:assets.appendingPathComponent(name)) else { throw NSError(domain:"图标帧读取失败：\(name)",code:1) }
    return result
}
do {
if CommandLine.arguments.contains("--idle") {
    try set(image("idle.png"), phase:"待机图标")
    print("Codex idle icon applied")
} else {
    let frames = try (0..<spec.frameCount).map { try image(String(format:"frames/frame-%03d.png",$0)) }
    let final = try image("source/official.png")
    try set(image("idle.png"), phase:"待机图标")
    Thread.sleep(forTimeInterval:spec.readyDelayMs/1000)
    let start=ProcessInfo.processInfo.systemUptime
    var index=0,updates=0
    do {
        while index<frames.count {
            try set(frames[index], phase:"动画帧 \(index)"); updates += 1
            let elapsed=ProcessInfo.processInfo.systemUptime-start
            let next=max(index+1,Int(elapsed*spec.fps))
            let delay=Double(next)/spec.fps-elapsed
            if delay>0 { Thread.sleep(forTimeInterval:delay) }
            index=next
        }
        try set(final)
    } catch {
        // Restore the running icon before surfacing the original frame failure.
        do { try set(final) } catch { fputs("Codex 图标恢复失败：\(error)\n",stderr) }
        throw error
    }
    print("Codex animation completed: \(updates)/\(frames.count) updates, \(ProcessInfo.processInfo.systemUptime-start)s")
}

} catch {
    fputs("\(error.localizedDescription)\n",stderr)
    exit(1)
}
