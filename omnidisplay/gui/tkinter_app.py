"""
Native Dark-Mode Desktop GUI for OmniDisplay using Tkinter.
Zero external pip dependencies - runs natively on macOS and Windows out of the box.
"""

import sys
import json
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional, Dict, Any

class OmniDisplayTkinterApp:
    """Standalone desktop window application for OmniDisplay."""

    def __init__(self, root: tk.Tk, server_port: int = 5959):
        self.root = root
        self.server_port = server_port
        self.api_url = f"http://127.0.0.1:{server_port}"
        self.current_status: Optional[Dict[str, Any]] = None

        # Window Setup
        self.root.title("OmniDisplay")
        self.root.geometry("780x620")
        self.root.minsize(700, 560)
        self.root.configure(bg="#0d1117")

        # Color Palette
        self.C_BG = "#0d1117"
        self.C_CARD = "#161b22"
        self.C_BORDER = "#30363d"
        self.C_TEXT = "#f0f6fc"
        self.C_MUTED = "#8b949e"
        self.C_BLUE = "#58a6ff"
        self.C_ORANGE = "#f0883e"
        self.C_GREEN = "#3fb950"
        self.C_YELLOW = "#d29922"
        self.C_BTN = "#21262d"
        self.C_BTN_HOVER = "#30363d"

        # Fonts
        self.font_title = tkfont.Font(family="Helvetica", size=18, weight="bold")
        self.font_sub = tkfont.Font(family="Helvetica", size=10)
        self.font_section = tkfont.Font(family="Helvetica", size=11, weight="bold")
        self.font_host = tkfont.Font(family="Helvetica", size=22, weight="bold")
        self.font_btn = tkfont.Font(family="Helvetica", size=11, weight="bold")
        self.font_preset = tkfont.Font(family="Helvetica", size=13, weight="bold")
        self.font_badge = tkfont.Font(family="Helvetica", size=10, weight="bold")

        self._build_ui()
        self._bind_keys()
        self.poll_status()

    def _build_ui(self):
        # 1. Header Frame
        header = tk.Frame(self.root, bg=self.C_BG, padx=24, pady=16)
        header.pack(fill=tk.X)

        title_frame = tk.Frame(header, bg=self.C_BG)
        title_frame.pack(side=tk.LEFT)

        lbl_logo = tk.Label(title_frame, text="🎛️", font=("Helvetica", 22), bg=self.C_BG)
        lbl_logo.pack(side=tk.LEFT, padx=(0, 10))

        text_frame = tk.Frame(title_frame, bg=self.C_BG)
        text_frame.pack(side=tk.LEFT)

        lbl_title = tk.Label(text_frame, text="OmniDisplay", font=self.font_title, fg=self.C_TEXT, bg=self.C_BG)
        lbl_title.pack(anchor=tk.W)

        lbl_sub = tk.Label(text_frame, text="Multi-PC Dual Monitor Coordinator", font=self.font_sub, fg=self.C_MUTED, bg=self.C_BG)
        lbl_sub.pack(anchor=tk.W)

        # Peer Status Badge
        self.badge_frame = tk.Frame(header, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=1, padx=12, pady=6)
        self.badge_frame.pack(side=tk.RIGHT)

        self.lbl_peer_dot = tk.Label(self.badge_frame, text="●", fg=self.C_YELLOW, bg=self.C_CARD, font=self.font_badge)
        self.lbl_peer_dot.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_peer_text = tk.Label(self.badge_frame, text="Connecting...", fg=self.C_TEXT, bg=self.C_CARD, font=self.font_badge)
        self.lbl_peer_text.pack(side=tk.LEFT)

        # Separator line
        sep1 = tk.Frame(self.root, height=1, bg=self.C_BORDER)
        sep1.pack(fill=tk.X, padx=24)

        # 2. Monitor Visualizer Section
        sec_monitors = tk.Frame(self.root, bg=self.C_BG, padx=24, pady=14)
        sec_monitors.pack(fill=tk.X)

        lbl_sec1 = tk.Label(sec_monitors, text="ACTIVE DISPLAY ROUTING", font=self.font_section, fg=self.C_MUTED, bg=self.C_BG)
        lbl_sec1.pack(anchor=tk.W, pady=(0, 10))

        mon_row = tk.Frame(sec_monitors, bg=self.C_BG)
        mon_row.pack(fill=tk.X)

        # Left Monitor Card
        self.frame_left = tk.Frame(mon_row, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=2, padx=16, pady=14)
        self.frame_left.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 10))

        tk.Label(self.frame_left, text="LEFT MONITOR", font=self.font_sub, fg=self.C_MUTED, bg=self.C_CARD).pack()
        self.lbl_host_left = tk.Label(self.frame_left, text="---", font=self.font_host, fg=self.C_TEXT, bg=self.C_CARD)
        self.lbl_host_left.pack(pady=8)

        self.btn_toggle_left = tk.Button(
            self.frame_left, text="⇄ Toggle Display", font=self.font_btn,
            bg=self.C_BTN, fg=self.C_TEXT, activebackground=self.C_BTN_HOVER, activeforeground=self.C_TEXT,
            relief=tk.FLAT, padx=10, pady=6, cursor="hand2",
            command=lambda: self._on_toggle("left")
        )
        self.btn_toggle_left.pack(fill=tk.X, pady=(4, 0))

        # Center Divider
        div = tk.Label(mon_row, text="⚡", font=("Helvetica", 18), fg=self.C_MUTED, bg=self.C_BG)
        div.pack(side=tk.LEFT, padx=10)

        # Right Monitor Card
        self.frame_right = tk.Frame(mon_row, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=2, padx=16, pady=14)
        self.frame_right.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(10, 0))

        tk.Label(self.frame_right, text="RIGHT MONITOR", font=self.font_sub, fg=self.C_MUTED, bg=self.C_CARD).pack()
        self.lbl_host_right = tk.Label(self.frame_right, text="---", font=self.font_host, fg=self.C_TEXT, bg=self.C_CARD)
        self.lbl_host_right.pack(pady=8)

        self.btn_toggle_right = tk.Button(
            self.frame_right, text="⇄ Toggle Display", font=self.font_btn,
            bg=self.C_BTN, fg=self.C_TEXT, activebackground=self.C_BTN_HOVER, activeforeground=self.C_TEXT,
            relief=tk.FLAT, padx=10, pady=6, cursor="hand2",
            command=lambda: self._on_toggle("right")
        )
        self.btn_toggle_right.pack(fill=tk.X, pady=(4, 0))

        # 3. Quick Presets Section
        sec_presets = tk.Frame(self.root, bg=self.C_BG, padx=24, pady=14)
        sec_presets.pack(fill=tk.BOTH, expand=True)

        lbl_sec2 = tk.Label(sec_presets, text="QUICK PRESETS (KEYS 1-4)", font=self.font_section, fg=self.C_MUTED, bg=self.C_BG)
        lbl_sec2.pack(anchor=tk.W, pady=(0, 10))

        grid = tk.Frame(sec_presets, bg=self.C_BG)
        grid.pack(fill=tk.BOTH, expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        self.preset_widgets = {}

        # 4 Preset Definitions
        presets_info = [
            ("pc_both", "1", "🖥️ 🖥️", "PC in Both", "Left: PC • Right: PC", 0, 0),
            ("mac_both", "2", "🍎 🍎", "Mac in Both", "Left: Mac • Right: Mac", 0, 1),
            ("split_pc_mac", "3", "🖥️ 🍎", "Left PC, Right Mac", "Split Workstation A", 1, 0),
            ("split_mac_pc", "4", "🍎 🖥️", "Left Mac, Right PC", "Split Workstation B", 1, 1),
        ]

        for pid, key, icon, name, desc, r, c in presets_info:
            p_card = tk.Frame(grid, bg=self.C_CARD, highlightbackground=self.C_BORDER, highlightthickness=1, padx=12, pady=10, cursor="hand2")
            p_card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

            # Click binding for the whole frame
            p_card.bind("<Button-1>", lambda e, p=pid: self._on_preset(p))

            top_row = tk.Frame(p_card, bg=self.C_CARD)
            top_row.pack(fill=tk.X)
            lbl_ico = tk.Label(top_row, text=icon, font=("Helvetica", 14), bg=self.C_CARD)
            lbl_ico.pack(side=tk.LEFT)
            lbl_ico.bind("<Button-1>", lambda e, p=pid: self._on_preset(p))

            lbl_key = tk.Label(top_row, text=f" [{key}] ", font=self.font_badge, fg=self.C_MUTED, bg=self.C_CARD)
            lbl_key.pack(side=tk.RIGHT)

            lbl_name = tk.Label(p_card, text=name, font=self.font_preset, fg=self.C_TEXT, bg=self.C_CARD)
            lbl_name.pack(anchor=tk.W, pady=(6, 2))
            lbl_name.bind("<Button-1>", lambda e, p=pid: self._on_preset(p))

            lbl_desc = tk.Label(p_card, text=desc, font=self.font_sub, fg=self.C_MUTED, bg=self.C_CARD)
            lbl_desc.pack(anchor=tk.W)
            lbl_desc.bind("<Button-1>", lambda e, p=pid: self._on_preset(p))

            self.preset_widgets[pid] = p_card

        # 4. Footer Status Bar
        footer = tk.Frame(self.root, bg="#11161d", padx=24, pady=10)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_footer_info = tk.Label(footer, text="Host: DETECTING... • http://127.0.0.1:5959", font=self.font_sub, fg=self.C_MUTED, bg="#11161d")
        self.lbl_footer_info.pack(side=tk.LEFT)

        lbl_hint = tk.Label(footer, text="Press keys 1-4 anytime to switch", font=self.font_sub, fg=self.C_MUTED, bg="#11161d")
        lbl_hint.pack(side=tk.RIGHT)

    def _bind_keys(self):
        self.root.bind("1", lambda e: self._on_preset("pc_both"))
        self.root.bind("2", lambda e: self._on_preset("mac_both"))
        self.root.bind("3", lambda e: self._on_preset("split_pc_mac"))
        self.root.bind("4", lambda e: self._on_preset("split_mac_pc"))

    def _on_preset(self, preset_id: str):
        self._api_post("/api/switch", {"preset": preset_id})
        self.poll_status()

    def _on_toggle(self, display_key: str):
        if not self.current_status:
            return
        curr = self.current_status["displays"][display_key]["active_host"]
        target = "pc" if curr == "mac" else "mac"
        self._api_post("/api/set_display", {"display": display_key, "target_host": target})
        self.poll_status()

    def _api_get(self, endpoint: str) -> Optional[dict]:
        try:
            req = urllib.request.Request(f"{self.api_url}{endpoint}")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def _api_post(self, endpoint: str, data: dict):
        try:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(f"{self.api_url}{endpoint}", data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                pass
        except Exception as e:
            print(f"[GUI] API error: {e}")

    def poll_status(self):
        status = self._api_get("/api/status")
        if status:
            self.current_status = status
            self._update_display(status)
        else:
            self.lbl_peer_text.config(text="Daemon offline")
            self.lbl_peer_dot.config(fg=self.C_YELLOW)

        # Reschedule polling every 1.5 seconds
        self.root.after(1500, self.poll_status)

    def _update_display(self, data: dict):
        # Update Peer status
        if data.get("peer_online"):
            self.lbl_peer_dot.config(fg=self.C_GREEN)
            self.lbl_peer_text.config(text=f"Connected ({data.get('peer_host')})")
        else:
            self.lbl_peer_dot.config(fg=self.C_YELLOW)
            self.lbl_peer_text.config(text="Searching LAN...")

        # Update Monitors
        left_host = data["displays"]["left"]["active_host"]
        right_host = data["displays"]["right"]["active_host"]

        self.lbl_host_left.config(text=left_host.upper())
        self.lbl_host_right.config(text=right_host.upper())

        # Color glows
        border_left = self.C_ORANGE if left_host == "mac" else self.C_BLUE
        border_right = self.C_ORANGE if right_host == "mac" else self.C_BLUE

        self.frame_left.config(highlightbackground=border_left)
        self.frame_right.config(highlightbackground=border_right)

        self.btn_toggle_left.config(text=f"⇄ Switch to {'PC' if left_host == 'mac' else 'Mac'}")
        self.btn_toggle_right.config(text=f"⇄ Switch to {'PC' if right_host == 'mac' else 'Mac'}")

        # Update Presets highlight
        curr_preset = data.get("current_preset")
        for pid, card in self.preset_widgets.items():
            if pid == curr_preset:
                card.config(highlightbackground=self.C_BLUE, bg="#1b2533")
            else:
                card.config(highlightbackground=self.C_BORDER, bg=self.C_CARD)

        # Footer
        role = data.get("role", "").upper()
        self.lbl_footer_info.config(text=f"Host Node: {role} • Daemon: http://127.0.0.1:{self.server_port}")

def launch_tkinter_app(port: int = 5959):
    root = tk.Tk()
    app = OmniDisplayTkinterApp(root, server_port=port)
    root.mainloop()

if __name__ == "__main__":
    launch_tkinter_app()
