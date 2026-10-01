// Applies only the static idle icon after Codex exits. Runtime playback uses
// Codex's own icon-switching handler through codex-runtime-icon.mjs.
import AppKit
import Foundation
do {
    guard CommandLine.arguments.count == 4, ["--idle","--watch"].contains(CommandLine.arguments[3]) else {
        throw NSError(domain:"CodexIcon",code:1,userInfo:[NSLocalizedDescriptionKey:"用法：play-codex-icon APP_PATH ASSETS_PATH --idle"])
    }
    let appPath=CommandLine.arguments[1]
    if CommandLine.arguments[3] == "--watch" {
        let identifier=Bundle(path:appPath)!.bundleIdentifier!
        let application=NSApplication.shared
        application.setActivationPolicy(.prohibited)
        let observer=NSWorkspace.shared.notificationCenter.addObserver(forName:NSWorkspace.didTerminateApplicationNotification,object:nil,queue:.main){ notification in
            if let app=notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication,app.bundleIdentifier==identifier {
                print("idle");fflush(stdout)
            }
        }
        if NSRunningApplication.runningApplications(withBundleIdentifier:identifier).isEmpty { print("idle");fflush(stdout) }
        application.run()
        NSWorkspace.shared.notificationCenter.removeObserver(observer)
        exit(0)
    }
    let path=URL(fileURLWithPath:CommandLine.arguments[2]).appendingPathComponent("idle.png")
    guard let image=NSImage(contentsOf:path) else { throw NSError(domain:"CodexIcon",code:1,userInfo:[NSLocalizedDescriptionKey:"无法读取待机图标：\(path.path)"]) }
    guard NSWorkspace.shared.setIcon(image,forFile:appPath,options:[]) else { throw NSError(domain:"CodexIcon",code:1,userInfo:[NSLocalizedDescriptionKey:"macOS 拒绝更新待机图标：\(appPath)"]) }
    print("Codex idle icon applied")
} catch { fputs("\(error.localizedDescription)\n",stderr);exit(1) }
