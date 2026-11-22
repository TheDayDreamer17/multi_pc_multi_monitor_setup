"""
Unified Desktop GUI Launcher for OmniDisplay.
Automatically selects between modern native WebView and native Tkinter desktop UI.
"""

import sys
import time
import threading
import urllib.request
from omnidisplay.gui.tkinter_app import launch_tkinter_app
from omnidisplay.gui.webview_app import launch_webview_app

def is_daemon_running(port: int = 5959) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=0.8) as resp:
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
        # Give server half a second to bind
        time.sleep(0.5)

def start_gui(port: int = 5959, force_tkinter: bool = False, role: str = "auto", config_path: str = None):
    # Ensure daemon is active so GUI connects immediately
    ensure_background_daemon(role=role, port=port, config_path=config_path)

    # 1. Try pywebview if not forced to tkinter
    if not force_tkinter:
        success = launch_webview_app(port=port)
        if success:
            return

    # 2. On macOS, launch modern standalone desktop app window via App Mode (Brave / Chrome / Edge)
    if sys.platform == "darwin" and not force_tkinter:
        import os, subprocess
        for app_name in ["Brave Browser", "Google Chrome", "Microsoft Edge", "Chromium"]:
            app_path = f"/Applications/{app_name}.app"
            if os.path.exists(app_path):
                try:
                    subprocess.Popen(["open", "-a", app_path, "--args", f"--app=http://127.0.0.1:{port}"])
                    return
                except Exception:
                    pass
        # Fallback to standard open in browser
        try:
            subprocess.Popen(["open", f"http://127.0.0.1:{port}"])
            return
        except Exception:
            pass

    # 3. Fall back to pure native Tkinter desktop UI
    launch_tkinter_app(port=port)

if __name__ == "__main__":
    start_gui()
