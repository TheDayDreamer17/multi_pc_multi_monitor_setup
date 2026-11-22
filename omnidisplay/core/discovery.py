"""
Cross-Machine Peer Auto-Discovery via UDP Broadcast.
Allows Mac on Wi-Fi and PC on Ethernet (same local subnet) to automatically
discover each other without requiring static IP configuration.
"""

import socket
import threading
import json
import time
from typing import Optional, Tuple, Callable

DEFAULT_BEACON_PORT = 59599

class PeerDiscovery:
    """Discovers peer OmniDisplay nodes on the local network using UDP broadcast."""

    def __init__(self, role: str, service_port: int, beacon_port: int = DEFAULT_BEACON_PORT):
        self.role = role  # "mac" or "pc"
        self.service_port = service_port
        self.beacon_port = beacon_port
        self.peer_host: Optional[str] = None
        self.peer_port: Optional[int] = None
        self.peer_role: Optional[str] = None
        self.last_seen: float = 0.0
        self.running = False
        self._on_peer_discovered: Optional[Callable[[str, int, str], None]] = None

    def set_on_discovered_callback(self, callback: Callable[[str, int, str], None]):
        self._on_peer_discovered = callback

    def set_static_peer(self, host: str, port: int):
        self.peer_host = host
        self.peer_port = port
        self.last_seen = time.time()

    def start(self):
        self.running = True
        self.beacon_thread = threading.Thread(target=self._broadcast_loop, daemon=True, name="BeaconBroadcast")
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True, name="BeaconListener")
        self.beacon_thread.start()
        self.listen_thread.start()

    def stop(self):
        self.running = False

    def _broadcast_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)

        while self.running:
            try:
                payload = json.dumps({
                    "service": "omnidisplay",
                    "role": self.role,
                    "port": self.service_port,
                    "timestamp": time.time()
                }).encode("utf-8")
                # Broadcast on standard LAN broadcast address
                sock.sendto(payload, ("<broadcast>", self.beacon_port))
            except Exception:
                pass
            time.sleep(3.0)

        sock.close()

    def _listen_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            # On some platforms SO_REUSEPORT is available
            sock.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_REUSEPORT", socket.SO_REUSEADDR), 1)
        except Exception:
            pass

        try:
            sock.bind(("", self.beacon_port))
            sock.settimeout(1.0)
        except Exception as e:
            print(f"[Discovery] Warning: could not bind beacon port {self.beacon_port}: {e}")
            return

        while self.running:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode("utf-8"))
                if msg.get("service") == "omnidisplay" and msg.get("role") != self.role:
                    peer_ip = addr[0]
                    peer_port = msg.get("port", 5959)
                    peer_role = msg.get("role", "unknown")

                    is_new = (self.peer_host != peer_ip or self.peer_port != peer_port)
                    self.peer_host = peer_ip
                    self.peer_port = peer_port
                    self.peer_role = peer_role
                    self.last_seen = time.time()

                    if is_new and self._on_peer_discovered:
                        self._on_peer_discovered(peer_ip, peer_port, peer_role)
            except socket.timeout:
                continue
            except Exception:
                continue

        sock.close()

    @property
    def is_peer_online(self) -> bool:
        return bool(self.peer_host and (time.time() - self.last_seen < 15.0))
