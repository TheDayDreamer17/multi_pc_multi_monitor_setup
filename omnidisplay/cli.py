"""
Command Line Interface (CLI) for OmniDisplay.
"""

import sys
import os
import time
import argparse
import json
import urllib.request
import urllib.error
from omnidisplay.core.ddc_mac import MacDDCController
from omnidisplay.core.ddc_windows import WindowsDDCController
from omnidisplay.core.discovery import PeerDiscovery
from omnidisplay.core.state_manager import StateManager, PRESETS
from omnidisplay.server.app import run_server

def get_platform_ddc():
    if sys.platform == "darwin":
        return MacDDCController()
    elif sys.platform == "win32":
        return WindowsDDCController()
    else:
        # Generic / Linux fallback
        return MacDDCController()

def detect_role():
    if sys.platform == "darwin":
        return "mac"
    elif sys.platform == "win32":
        return "pc"
    return "pc"

def send_local_api(endpoint: str, data: dict = None) -> dict:
    url = f"http://127.0.0.1:5959{endpoint}"
    try:
        if data is not None:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return {}

def cmd_start(args):
    import traceback
    def _log_err(exc_type, exc_val, exc_tb):
        try:
            with open(os.path.expanduser("~/.omnidisplay_daemon.log"), "a", encoding="utf-8") as f:
                f.write(f"\n--- Unhandled Exception {time.ctime()} ---\n")
                traceback.print_exception(exc_type, exc_val, exc_tb, file=f)
        except Exception:
            pass

    sys.excepthook = _log_err
    import threading
    if hasattr(threading, "excepthook"):
        threading.excepthook = lambda args: _log_err(args.exc_type, args.exc_value, args.exc_traceback)

    role = args.role if args.role != "auto" else detect_role()
    port = args.port
    ddc = get_platform_ddc()
    state_mgr = StateManager(ddc, role=role, config_path=args.config)

    # Initialize UDP discovery
    discovery = PeerDiscovery(role=role, service_port=port)
    discovery.set_on_discovered_callback(lambda ip, p, r: state_mgr.set_peer_endpoint(ip, p))
    discovery.start()

    # If peer is statically configured in config, set it immediately
    static_peer = state_mgr.config.get("peer_host")
    if static_peer:
        peer_port = state_mgr.config.get("peer_port", 5959)
        state_mgr.set_peer_endpoint(static_peer, peer_port)
        discovery.set_static_peer(static_peer, peer_port)

    run_server(state_mgr, discovery, port=port)

def cmd_switch(args):
    preset = args.preset.lower()
    # Normalize aliases
    preset_map = {
        "1": "pc_both", "pc": "pc_both", "pc_both": "pc_both", "pc-both": "pc_both",
        "2": "mac_both", "mac": "mac_both", "mac_both": "mac_both", "mac-both": "mac_both",
        "3": "split_pc_mac", "split-pc-mac": "split_pc_mac", "left-pc": "split_pc_mac",
        "4": "split_mac_pc", "split-mac-pc": "split_mac_pc", "left-mac": "split_mac_pc"
    }
    target_preset = preset_map.get(preset, preset)
    if target_preset not in PRESETS:
        print(f"Error: Unknown preset '{preset}'. Available presets:")
        for k, v in PRESETS.items():
            print(f"  - {k} ({v['label']})")
        sys.exit(1)

    # Try communicating with running background daemon
    res = send_local_api("/api/switch", {"preset": target_preset})
    if res.get("status") == "ok":
        print(f"Successfully applied preset '{target_preset}' via background daemon.")
    else:
        print(f"Background daemon not running. Executing standalone switch...")
        role = detect_role()
        ddc = get_platform_ddc()
        state_mgr = StateManager(ddc, role=role)
        state_mgr.apply_preset(target_preset)
        print(f"Preset '{target_preset}' applied locally.")

def cmd_toggle(args):
    display = args.display.lower()
    if display not in ("left", "right"):
        print("Error: display must be 'left' or 'right'")
        sys.exit(1)

    status = send_local_api("/api/status")
    if not status:
        print("Error: OmniDisplay daemon is not running. Please start it with 'omnidisplay start'.")
        sys.exit(1)

    current_host = status["displays"][display]["active_host"]
    target_host = "pc" if current_host == "mac" else "mac"
    res = send_local_api("/api/set_display", {"display": display, "target_host": target_host})
    if res.get("status") == "ok":
        print(f"Toggled {display} display from {current_host} to {target_host}.")
    else:
        print(f"Failed to toggle display.")

def cmd_status(args):
    status = send_local_api("/api/status")
    if not status:
        print("OmniDisplay daemon is not running.")
        sys.exit(1)

    print("=== OmniDisplay Status ===")
    print(f"Host Role:       {status.get('role', '').upper()}")
    print(f"Peer Status:     {'ONLINE (' + status.get('peer_host', '') + ')' if status.get('peer_online') else 'OFFLINE / SEARCHING'}")
    print(f"Current Preset:  {status.get('current_preset')}")
    print(f"Left Monitor:    {status['displays']['left']['name']} -> {status['displays']['left']['active_host'].upper()}")
    print(f"Right Monitor:   {status['displays']['right']['name']} -> {status['displays']['right']['active_host'].upper()}")

def cmd_probe(args):
    print("Probing physical display devices via DDC/CI...")
    ddc = get_platform_ddc()
    displays = ddc.list_displays()
    print(f"Found {len(displays)} display(s):")
    for d in displays:
        print(f"  [{d.get('index', 0)}] {d.get('name')} (Driver: {d.get('driver')})")

def cmd_logs(args):
    res = send_local_api(f"/api/logs?lines={args.lines}")
    if res and "logs" in res:
        for line in res["logs"]:
            print(line)
    else:
        from omnidisplay.core.logger import get_recent_logs
        for line in get_recent_logs(lines=args.lines):
            print(line)

def main():
    parser = argparse.ArgumentParser(description="OmniDisplay Dual-PC Monitor Switcher")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # start
    p_start = subparsers.add_parser("start", help="Start background daemon and web UI")
    p_start.add_argument("--role", choices=["mac", "pc", "auto"], default="auto", help="Machine role")
    p_start.add_argument("--port", type=int, default=5959, help="HTTP server port")
    p_start.add_argument("--config", type=str, default=None, help="Path to custom config.json")
    p_start.add_argument("--gui", action="store_true", help="Also open Desktop GUI window")

    # gui
    p_gui = subparsers.add_parser("gui", help="Launch native desktop GUI application")
    p_gui.add_argument("--port", type=int, default=5959, help="HTTP server port")
    p_gui.add_argument("--force-tkinter", action="store_true", help="Force Tkinter GUI over WebView")

    # switch
    p_switch = subparsers.add_parser("switch", help="Switch to a preset (1-4 or name)")
    p_switch.add_argument("preset", help="Preset name (pc_both, mac_both, split_pc_mac, split_mac_pc, or 1-4)")

    # toggle
    p_toggle = subparsers.add_parser("toggle", help="Toggle individual monitor between Mac and PC")
    p_toggle.add_argument("display", choices=["left", "right"], help="Display to toggle")

    # status
    subparsers.add_parser("status", help="Show current routing status")

    # probe
    subparsers.add_parser("probe", help="Probe connected displays")

    # logs
    p_logs = subparsers.add_parser("logs", help="View recent daemon activity logs")
    p_logs.add_argument("-n", "--lines", type=int, default=50, help="Number of log lines to show (default: 50)")

    args = parser.parse_args()
    if not args.command:
        # Default action when double-clicked or invoked bare: start Desktop GUI
        from omnidisplay.gui.launcher import start_gui
        start_gui()
        sys.exit(0)

    if args.command == "start":
        if getattr(args, "gui", False):
            import threading
            threading.Thread(target=lambda: cmd_start(args), daemon=True).start()
            from omnidisplay.gui.launcher import start_gui
            start_gui(port=args.port, config_path=args.config)
        else:
            cmd_start(args)
    elif args.command == "gui":
        from omnidisplay.gui.launcher import start_gui
        start_gui(port=args.port, force_tkinter=args.force_tkinter)
    elif args.command == "switch":
        cmd_switch(args)
    elif args.command == "toggle":
        cmd_toggle(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "probe":
        cmd_probe(args)
    elif args.command == "logs":
        cmd_logs(args)

if __name__ == "__main__":
    main()
