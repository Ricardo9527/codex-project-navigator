import AppKit
import Foundation
let app = CommandLine.arguments[1]
let icon = CommandLine.arguments[2]
guard let image = NSImage(contentsOfFile: icon) else { fatalError("无法读取图标：\(icon)") }
guard NSWorkspace.shared.setIcon(image, forFile: app, options: []) else { fatalError("无法设置启动器静态图标") }
print("已设置与动画首帧相同的透明静态图标")
