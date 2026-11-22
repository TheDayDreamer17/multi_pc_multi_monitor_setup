"""
HTTP Server and REST API for OmniDisplay.
Pure Python standard library implementation with zero external pip dependencies.
"""

import sys
import os
import time
import json
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from omnidisplay.core.state_manager import StateManager
from omnidisplay.core.discovery import PeerDiscovery
from omnidisplay.core.logger import get_logger, get_recent_logs

logger = get_logger("server")

class OmniDisplayHandler(BaseHTTPRequestHandler):
    """Handles REST API requests and serves static web UI assets."""

    state_mgr: StateManager = None
    discovery: PeerDiscovery = None
    static_dir: str = ""

    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        try:
            # API Status Endpoint
            if self.path == "/api/status":
                status = self.state_mgr.get_status()
                status["peer_online"] = self.discovery.is_peer_online if self.discovery else False
                status["peer_host"] = self.discovery.peer_host if self.discovery else None
                status["peer_port"] = self.discovery.peer_port if self.discovery else None
                self._send_json(200, status)
                return

            # API Logs Endpoint
            if self.path.startswith("/api/logs"):
                lines = 100
                if "?" in self.path:
                    try:
                        import urllib.parse
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                        if "lines" in qs:
                            lines = int(qs["lines"][0])
                    except Exception:
                        pass
                recent = get_recent_logs(lines=lines)
                self._send_json(200, {"lines": len(recent), "logs": recent})
                return

            # Serve Web UI Root
            rel_path = self.path.split("?")[0].lstrip("/")
            if not rel_path or rel_path == "":
                rel_path = "index.html"
            elif rel_path.startswith("static/"):
                rel_path = rel_path[len("static/"):]

            filepath = os.path.join(self.static_dir, rel_path)
            if os.path.exists(filepath) and os.path.isfile(filepath):
                mime_type, _ = mimetypes.guess_type(filepath)
                mime_type = mime_type or "application/octet-stream"
                try:
                    with open(filepath, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("Content-Length", str(len(content)))
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(content)
                    return
                except Exception as e:
                    self._send_json(500, {"error": str(e)})
                    return

            self._send_json(404, {"error": "Not Found"})
        except Exception as e:
            try:
                self._send_json(500, {"error": f"Internal server error: {e}"})
            except Exception:
                pass

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        # 1. Apply Preset
        if self.path == "/api/switch":
            preset = payload.get("preset")
            if not preset:
                self._send_json(400, {"error": "Missing 'preset' parameter"})
                return
            try:
                self.state_mgr.apply_preset(preset)
                self._send_json(200, {"status": "ok", "state": self.state_mgr.current_state})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        # 2. Set Individual Display
        if self.path == "/api/set_display":
            display = payload.get("display")
            target_host = payload.get("target_host")
            if not display or not target_host:
                self._send_json(400, {"error": "Missing 'display' or 'target_host'"})
                return
            try:
                self.state_mgr.set_display_host(display, target_host)
                self._send_json(200, {"status": "ok", "state": self.state_mgr.current_state})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        # 3. Relay Switch Command from Peer
        if self.path == "/api/relay_switch":
            display = payload.get("display")
            target_host = payload.get("target_host")
            success = self.state_mgr.execute_relayed_switch(display, target_host)
            self._send_json(200 if success else 500, {"status": "ok" if success else "failed"})
            return

        # 4. Sync State Notification from Peer
        if self.path == "/api/sync_state":
            state = payload.get("state", {})
            self.state_mgr.update_state_from_peer(state)
            self._send_json(200, {"status": "synced"})
            return

        # 5. Map Display to Slot (Left or Right)
        if self.path == "/api/map_display":
            slot = payload.get("slot")
            display_name = payload.get("display_name")
            if not slot or not display_name:
                self._send_json(400, {"error": "Missing 'slot' or 'display_name'"})
                return
            try:
                self.state_mgr.map_display(slot, display_name)
                self._send_json(200, {"status": "ok", "displays": self.state_mgr.config["displays"]})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        # 6. Swap Left and Right Displays
        if self.path == "/api/swap_displays":
            try:
                self.state_mgr.swap_displays()
                self._send_json(200, {"status": "ok", "displays": self.state_mgr.config["displays"]})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        # 7. Wake Host Display
        if self.path == "/api/wake":
            self.state_mgr.wake_host()
            self._send_json(200, {"status": "awake"})
            return

        self._send_json(404, {"error": "Endpoint Not Found"})

    def _send_json(self, code: int, data: dict):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

def run_server(state_mgr: StateManager, discovery: PeerDiscovery, port: int = 5959):
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    OmniDisplayHandler.state_mgr = state_mgr
    OmniDisplayHandler.discovery = discovery
    OmniDisplayHandler.static_dir = static_dir

    if sys.platform == "win32":
        HTTPServer.allow_reuse_address = False

    try:
        server = HTTPServer(("0.0.0.0", port), OmniDisplayHandler)
    except OSError as e:
        print(f"[Server] Note: port {port} already in use ({e}). Server already running.", flush=True)
        return
    print(f"\n=======================================================")
    print(f"  OmniDisplay Daemon running on port {port}")
    print(f"  Web Dashboard: http://localhost:{port}")
    print(f"  Role: {state_mgr.role.upper()}")
    print(f"=======================================================\n")
    log_path = os.path.expanduser("~/.omnidisplay_lifecycle.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{time.ctime()}] Server starting on port {port} (PID: {os.getpid()})\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.ctime()}] Server KeyboardInterrupt\n")
        server.server_close()
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.ctime()}] Server exception: {e}\n")
    finally:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.ctime()}] Server exited serve_forever\n")
