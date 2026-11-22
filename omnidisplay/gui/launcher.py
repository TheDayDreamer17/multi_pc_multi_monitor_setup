"""
Unified Cross-Platform Desktop GUI Launcher for OmniDisplay.
Launches the single unified glassmorphism Web UI across macOS and Windows.
No duplicate code: 100% of UI controls, styling, dropdowns, and presets
are shared directly through the native Web UI.
"""

import os
import sys
import time
import shutil
import subprocess
import threading
import urllib.request

def is_daemon_running(port: int = 5959) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False

def ensure_background_daemon(role: str = "auto", port: int = 5959, config_path: str = None):
    """If daemon is not running, spin it up in a background daemon thread."""
    if not is_daemon_running(port):
        from omnidisplay.cli import get_platform_ddc, detect_role
        from omnidisplay.core.discovery import PeerDiscovery
        from omnidisplay.core.state_manager import StateManager
        from omnidisplay.server.app import run_server

        actual_role = role if role != "auto" else detect_role()
        ddc = get_platform_ddc()
        state_mgr = StateManager(ddc, role=actual_role, config_path=config_path)

        discovery = PeerDiscovery(role=actual_role, service_port=port)
        discovery.set_on_discovered_callback(lambda ip, p, r: state_mgr.set_peer_endpoint(ip, p))
        discovery.start()

        t = threading.Thread(
            target=run_server,
            args=(state_mgr, discovery, port),
            daemon=True,
            name="OmniDisplayServerThread"
        )
        t.start()
        time.sleep(0.5)

def launch_windows_app_mode(url: str, width: int = 920, height: int = 720) -> bool:
    """
    On Windows, launch Edge or Chrome in standalone native app-window mode.
    Renders with zero browser chrome, zero address bar, and pure native window frame.
    """
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    binary = next((p for p in candidates if os.path.exists(p)), None)
    if not binary:
        binary = shutil.which("msedge") or shutil.which("chrome")

    if binary:
        cmd = [
            binary,
            f"--app={url}",
            f"--window-size={width},{height}",
            "--app-id=OmniDisplay"
        ]
        try:
            subprocess.Popen(cmd)
            return True
        except Exception:
            pass
    return False

def start_gui(port: int = 5959, role: str = "auto", config_path: str = None):
    # 1. Ensure backend daemon is active
    ensure_background_daemon(role=role, port=port, config_path=config_path)
    url = f"http://127.0.0.1:{port}"

    # 2. macOS: Native Cocoa WebKit window (with single-instance protection)
    if sys.platform == "darwin":
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        native_app_bin = os.path.join(repo_root, "OmniDisplay.app", "Contents", "MacOS", "OmniDisplayNative")
        if os.path.exists(native_app_bin):
            try:
                subprocess.Popen([native_app_bin])
                return
            except Exception:
                pass

    # 3. Windows & Cross-Platform: Try pywebview (Edge WebView2)
    try:
        from omnidisplay.gui.webview_app import launch_webview_app
        if launch_webview_app(port=port):
            return
    except Exception:
        pass

    # 4. Windows: Try standalone chromeless App Mode (msedge.exe / chrome.exe)
    if sys.platform == "win32":
        if launch_windows_app_mode(url):
            return

    # 5. Fallback: Launch system default browser
    import webbrowser
    webbrowser.open(url)

if __name__ == "__main__":
    start_gui()
