"""
State Manager for OmniDisplay.
Orchestrates the 4 dual-monitor presets and cross-host switching logic.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from omnidisplay.core.ddc_base import DDCController
from omnidisplay.core.logger import get_logger

logger = get_logger("state_manager")

PRESETS = {
    "pc_both": {
        "id": "pc_both",
        "label": "Both on PC",
        "description": "GIGABYTE & LG -> PC",
        "left": "pc",
        "right": "pc"
    },
    "mac_both": {
        "id": "mac_both",
        "label": "Both on Mac",
        "description": "GIGABYTE & LG -> Mac",
        "left": "mac",
        "right": "mac"
    },
    "split_pc_mac": {
        "id": "split_pc_mac",
        "label": "GIGABYTE: PC • LG: Mac",
        "description": "Left (GIGABYTE) -> PC, Right (LG) -> Mac",
        "left": "pc",
        "right": "mac"
    },
    "split_mac_pc": {
        "id": "split_mac_pc",
        "label": "GIGABYTE: Mac • LG: PC",
        "description": "Left (GIGABYTE) -> Mac, Right (LG) -> PC",
        "left": "mac",
        "right": "pc"
    }
}

DEFAULT_CONFIG = {
    "device_role": "auto",  # "mac" or "pc" or "auto"
    "port": 5959,
    "peer_host": None,      # auto-discovered via UDP, or static IP
    "peer_port": 5959,
    "displays": {
        "left": {
            "name": "GIGABYTE G24F",
            "index_mac": 1,
            "index_pc": 1,
            "inputs": {
                "mac": 17,  # HDMI-1 (0x11)
                "pc": 18    # HDMI-2 (0x12)
            }
        },
        "right": {
            "name": "LG ULTRAWIDE",
            "index_mac": 0,
            "index_pc": 0,
            "inputs": {
                "mac": 17,  # HDMI (0x11)
                "pc": 15    # DisplayPort (0x0F)
            }
        }
    }
}

class StateManager:
    """Manages active display routing, configuration, and DDC dispatch."""

    def __init__(self, ddc_controller: DDCController, role: str, config_path: Optional[str] = None):
        self.ddc = ddc_controller
        self.role = role  # "mac" or "pc"
        self.config_path = config_path or os.path.expanduser("~/.omnidisplay_config.json")
        self.config = self._load_or_create_config()

        # Initial display states (default: mac for mac, pc for pc)
        self.current_state = {
            "left": "mac" if self.role == "mac" else "pc",
            "right": "mac" if self.role == "mac" else "pc"
        }
        self.peer_url: Optional[str] = None

    def _load_or_create_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[StateManager] Warning: failed reading config {self.config_path}: {e}")
        # Write default
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
        except Exception:
            pass
        return DEFAULT_CONFIG.copy()

    def _save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Saved configuration to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def map_display(self, slot: str, display_name: str) -> bool:
        """Assign a display name to slot 'left' or 'right' without auto-mutating the other slot."""
        if slot not in ("left", "right"):
            raise ValueError(f"Invalid slot: {slot}")

        self.config["displays"][slot]["name"] = display_name
        detected = self.ddc.list_displays()
        found = next((d for d in detected if d.get("name") == display_name), None)
        if found:
            idx_key = "index_mac" if self.role == "mac" else "index_pc"
            self.config["displays"][slot][idx_key] = found["index"]
            # Auto-assign verified inputs based on hardware model
            if "gigabyte" in display_name.lower():
                self.config["displays"][slot]["inputs"] = {"mac": 17, "pc": 18}
            elif "lg" in display_name.lower() or "ultrawide" in display_name.lower():
                self.config["displays"][slot]["inputs"] = {"mac": 17, "pc": 15}
        elif "gigabyte" in display_name.lower():
            self.config["displays"][slot]["index_pc"] = 1
            self.config["displays"][slot]["index_mac"] = 1
            self.config["displays"][slot]["inputs"] = {"mac": 17, "pc": 18}
        elif "lg" in display_name.lower() or "ultrawide" in display_name.lower():
            self.config["displays"][slot]["index_pc"] = 0
            self.config["displays"][slot]["index_mac"] = 0
            self.config["displays"][slot]["inputs"] = {"mac": 17, "pc": 15}

        self._save_config()
        return True

    def swap_displays(self) -> bool:
        """Swap left and right display configuration."""
        self.config["displays"]["left"], self.config["displays"]["right"] = (
            self.config["displays"]["right"],
            self.config["displays"]["left"]
        )
        self.current_state["left"], self.current_state["right"] = (
            self.current_state["right"],
            self.current_state["left"]
        )
        self._save_config()
        return True

    def set_peer_endpoint(self, host: str, port: int):
        self.peer_url = f"http://{host}:{port}"
        logger.info(f"Peer endpoint updated: {self.peer_url}")

    def get_status(self) -> Dict[str, Any]:
        matched_preset = "custom"
        for preset_id, preset_data in PRESETS.items():
            if (self.current_state["left"] == preset_data["left"] and
                self.current_state["right"] == preset_data["right"]):
                matched_preset = preset_id
                break

        # Match detected hardware EDID display names by configured index
        detected = self.ddc.list_displays()
        target_idx_left = self.config["displays"]["left"]["index_mac" if self.role == "mac" else "index_pc"]
        target_idx_right = self.config["displays"]["right"]["index_mac" if self.role == "mac" else "index_pc"]

        name_left = self.config["displays"]["left"]["name"]
        name_right = self.config["displays"]["right"]["name"]

        for d in detected:
            d_name = d.get("name", "")
            if d_name and "generic" not in d_name.lower():
                if d.get("index") == target_idx_left:
                    name_left = d_name
                elif d.get("index") == target_idx_right:
                    name_right = d_name

        return {
            "role": self.role,
            "peer_url": self.peer_url,
            "current_preset": matched_preset,
            "detected_displays": detected,
            "displays": {
                "left": {
                    "id": f"disp-{target_idx_left}",
                    "name": name_left,
                    "index": target_idx_left,
                    "active_host": self.current_state["left"],
                    "inputs": self.config["displays"]["left"]["inputs"]
                },
                "right": {
                    "id": f"disp-{target_idx_right}",
                    "name": name_right,
                    "index": target_idx_right,
                    "active_host": self.current_state["right"],
                    "inputs": self.config["displays"]["right"]["inputs"]
                }
            },
            "available_presets": list(PRESETS.values())
        }

    def apply_preset(self, preset_id: str) -> bool:
        """Apply one of the 4 standard presets."""
        if preset_id not in PRESETS:
            raise ValueError(f"Unknown preset: {preset_id}. Choose from: {list(PRESETS.keys())}")

        target = PRESETS[preset_id]
        logger.info(f"Applying preset '{preset_id}' -> Left: {target['left']}, Right: {target['right']}")
        success_left = self.set_display_host("left", target["left"], sync_peer=False)
        success_right = self.set_display_host("right", target["right"], sync_peer=False)

        # Notify peer of updated state
        self._sync_state_to_peer()
        return success_left and success_right

    def set_display_host(self, display_key: str, target_host: str, sync_peer: bool = True) -> bool:
        """
        Switch an individual display ('left' or 'right') to a target host ('mac' or 'pc').
        """
        if display_key not in ("left", "right"):
            raise ValueError(f"Invalid display_key: {display_key}")
        if target_host not in ("mac", "pc"):
            raise ValueError(f"Invalid target_host: {target_host}")

        disp_cfg = self.config["displays"][display_key]
        target_vcp_code = disp_cfg["inputs"].get(target_host)
        if target_vcp_code is None:
            raise ValueError(f"No VCP input configured for host '{target_host}' on {display_key}")

        current_host = self.current_state[display_key]
        idx = disp_cfg["index_mac"] if self.role == "mac" else disp_cfg["index_pc"]

        # If current node is the host actively holding the display:
        # We can issue local DDC command directly!
        if current_host == self.role:
            logger.info(f"Local DDC switch: {display_key} (idx {idx}) -> {target_host} (vcp 0x{target_vcp_code:X})")
            self.ddc.set_input_source(idx, target_vcp_code)
        else:
            # The display is currently with the peer!
            # Relay request to peer so the peer sends the DDC command from its active port!
            logger.info(f"Relay switch request to peer for {display_key} -> {target_host}")
            self._relay_to_peer(display_key, target_host)
            # Also attempt local DDC as fallback in case monitor listens to local port or peer is offline
            logger.info(f"Fallback local DDC attempt for {display_key} (idx {idx}) -> {target_host} (vcp 0x{target_vcp_code:X})")
            self.ddc.set_input_source(idx, target_vcp_code)

        self.current_state[display_key] = target_host

        if sync_peer:
            self._sync_state_to_peer()

        return True

    def execute_relayed_switch(self, display_key: str, target_host: str) -> bool:
        """Called when peer asks us to switch an input locally."""
        if display_key not in ("left", "right"):
            return False

        disp_cfg = self.config["displays"][display_key]
        target_vcp_code = disp_cfg["inputs"].get(target_host)
        idx = disp_cfg["index_mac"] if self.role == "mac" else disp_cfg["index_pc"]

        logger.info(f"Executing peer-relayed switch: {display_key} (idx {idx}) -> {target_host} (vcp 0x{target_vcp_code:X})")
        self.ddc.set_input_source(idx, target_vcp_code)
        self.current_state[display_key] = target_host
        return True

    def _relay_to_peer(self, display_key: str, target_host: str):
        if not self.peer_url:
            logger.warning("Cannot relay to peer; peer_url not established.")
            return

        url = f"{self.peer_url}/api/relay_switch"
        payload = json.dumps({"display": display_key, "target_host": target_host}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                logger.info(f"Relayed switch to peer successful: {display_key} -> {target_host}")
        except Exception as e:
            logger.error(f"Error relaying command to peer: {e}")

    def _sync_state_to_peer(self):
        if not self.peer_url:
            return

        url = f"{self.peer_url}/api/sync_state"
        payload = json.dumps({"state": self.current_state}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                pass
        except Exception as e:
            logger.warning(f"Failed syncing state to peer: {e}")

    def update_state_from_peer(self, state: Dict[str, str]):
        if "left" in state and "right" in state:
            logger.info(f"State sync received from peer: {state}")
            self.current_state["left"] = state["left"]
            self.current_state["right"] = state["right"]
