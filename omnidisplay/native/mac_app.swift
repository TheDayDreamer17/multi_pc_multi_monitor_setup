/*
 * mac_app.swift - Standalone Native macOS Desktop Window for OmniDisplay
 * Uses Cocoa & WebKit (WKWebView) to render the modern glassmorphism UI
 * in a dedicated native desktop window without any browser chrome or external dependencies.
 */

import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var window: NSWindow!
    var webView: WKWebView!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let rect = NSRect(x: 0, y: 0, width: 920, height: 720)
        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "OmniDisplay"
        window.titlebarAppearsTransparent = true
        window.backgroundColor = NSColor(red: 0.05, green: 0.07, blue: 0.09, alpha: 1.0)
        window.isReleasedWhenClosed = false
        window.center()
        window.minSize = NSSize(width: 740, height: 580)
        window.delegate = self

        let config = WKWebViewConfiguration()
        webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.setValue(false, forKey: "drawsBackground")

        // Load the local OmniDisplay daemon UI
        if let url = URL(string: "http://127.0.0.1:5959") {
            webView.load(URLRequest(url: url))
        }

        window.contentView?.addSubview(webView)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            window?.makeKeyAndOrderFront(nil)
        }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

// Single instance check: if OmniDisplay is already running, activate it and exit immediately.
let myPID = ProcessInfo.processInfo.processIdentifier
for running in NSWorkspace.shared.runningApplications {
    if running.processIdentifier != myPID {
        let name = running.localizedName ?? ""
        let bid = running.bundleIdentifier ?? ""
        if bid == "com.omnidisplay.app" || name == "OmniDisplayNative" || name == "OmniDisplay" {
            running.activate()
            exit(0)
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
