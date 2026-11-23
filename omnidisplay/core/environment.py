"""
Local desktop environment management for OmniDisplay.

Fixes two side effects of DDC input switching:

1. Ghost displays: a monitor showing the *other* computer is still part of this
   computer's desktop, so the mouse (and Input Leap) can travel onto an invisible
   screen. We remove such "ghost" displays from the local desktop
   (macOS: mirror it onto the live display; Windows: detach it).
2. Idle sleep: while you work on the other machine via Input Leap, this machine
   sees no input, sleeps its display, and the monitor falls back to the other
   input. We hold a keep-awake assertion while this machine owns any monitor.

Optionally (Windows/server side) it also rewrites the Input Leap server layout so
the screen link direction follows the active preset.

All operations are best-effort: failures are logged and never break switching.
"""

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from typing import Dict, Optional

from omnidisplay.core.logger import get_logger

logger = get_logger("environment")

SLOTS = ("left", "right")


class NullEnvironment:
    """No-op environment (tests / disabled)."""

    def prepare_for_ddc(self):
        pass

    def apply(self, owned: Dict[str, bool], state: Dict[str, str]):
        pass

    def shutdown(self):
        pass


# --------------------------------------------------------------------------- #
# macOS
# --------------------------------------------------------------------------- #

class MacEnvironment(NullEnvironment):
    def __init__(self, opts: dict):
        self.keep_awake = opts.get("keep_awake", True)
        self.remove_ghost = opts.get("remove_ghost_displays", True)
        self._caffeinate: Optional[subprocess.Popen] = None
        self._ghost_slot: Optional[str] = None
        self._owned: Optional[Dict[str, bool]] = None
        self._lock = threading.RLock()
        self._watcher: Optional[threading.Thread] = None
        native = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "native")
        helper = os.path.join(native, "mac_layout")
        self.helper = helper if os.path.exists(helper) else None
        if self.remove_ghost and not self.helper:
            logger.warning("mac_layout helper not built; ghost display removal disabled (re-run install-mac.sh)")

    # keep-awake -----------------------------------------------------------
    def _set_awake(self, on: bool):
        if on and not self._caffeinate:
            try:
                self._caffeinate = subprocess.Popen(["caffeinate", "-d", "-i", "-w", str(os.getpid())])
                logger.info("Keep-awake enabled (Mac owns a monitor)")
            except Exception as e:
                logger.warning(f"caffeinate failed: {e}")
        elif not on and self._caffeinate:
            self._caffeinate.terminate()
            self._caffeinate = None
            logger.info("Keep-awake released")

    # layout ---------------------------------------------------------------
    def _run(self, *args):
        res = subprocess.run([self.helper, *args], capture_output=True, text=True, timeout=5)
        return res.returncode, res.stdout

    def _list(self):
        rc, out = self._run("list")
        return json.loads(out).get("displays", []) if rc == 0 else []

    def _apply_layout(self, owned: Dict[str, bool]):
        displays = self._list()
        any_mirrored = any(d["mirrored"] for d in displays)

        ghosts = [s for s in SLOTS if not owned[s]]
        wanted = ghosts[0] if len(ghosts) == 1 else None

        if wanted and wanted == self._ghost_slot and any_mirrored:
            return  # already in desired state
        if any_mirrored:
            self._run("unmirror-all")
            self._ghost_slot = None
            time.sleep(0.8)
            displays = self._list()
        if not wanted:
            return
        if len(displays) != 2:
            if getattr(self, "_last_skip", None) != len(displays):
                logger.info(f"Ghost removal waiting: expected 2 external displays, found {len(displays)}")
                self._last_skip = len(displays)
            return
        by_x = sorted(displays, key=lambda d: d["x"])
        ghost = by_x[0] if wanted == "left" else by_x[1]
        main = by_x[1] if wanted == "left" else by_x[0]
        rc, _ = self._run("mirror", str(ghost["id"]), str(main["id"]))
        if rc == 0:
            self._ghost_slot = wanted
            logger.info(f"Mirrored ghost {wanted} display ({ghost['id']}) onto live display ({main['id']})")
        else:
            logger.warning(f"Mirroring failed (rc={rc})")

    def _watch(self):
        """A monitor drops offline briefly after an input switch; re-check until the
        layout matches the desired state (also self-heals later hot-plugs)."""
        while True:
            time.sleep(3)
            with self._lock:
                if self._owned is None:
                    continue
                try:
                    self._apply_layout(self._owned)
                except Exception as e:
                    logger.debug(f"Layout watcher: {e}")

    def apply(self, owned, state):
        with self._lock:
            self._owned = dict(owned)
            self._set_awake(any(owned.values()) and self.keep_awake)
            if self.remove_ghost and self.helper:
                try:
                    self._apply_layout(owned)
                except Exception as e:
                    logger.warning(f"Ghost display handling failed: {e}")
                if not self._watcher:
                    self._watcher = threading.Thread(target=self._watch, daemon=True)
                    self._watcher.start()

    def shutdown(self):
        self._set_awake(False)


# --------------------------------------------------------------------------- #
# Windows
# --------------------------------------------------------------------------- #

def _win_structs():
    from ctypes import wintypes

    class DEVMODEW(ctypes.Structure):
        _fields_ = [
            ("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
            ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
            ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
            ("dmPositionX", wintypes.LONG), ("dmPositionY", wintypes.LONG),
            ("dmDisplayOrientation", wintypes.DWORD), ("dmDisplayFixedOutput", wintypes.DWORD),
            ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
            ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
            ("dmCollate", ctypes.c_short), ("dmFormName", wintypes.WCHAR * 32),
            ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD),
            ("dmPelsWidth", wintypes.DWORD), ("dmPelsHeight", wintypes.DWORD),
            ("dmDisplayFlags", wintypes.DWORD), ("dmDisplayFrequency", wintypes.DWORD),
            ("dmICMMethod", wintypes.DWORD), ("dmICMIntent", wintypes.DWORD),
            ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD),
            ("dmReserved1", wintypes.DWORD), ("dmReserved2", wintypes.DWORD),
            ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD),
        ]

    class DISPLAY_DEVICEW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32),
            ("DeviceString", wintypes.WCHAR * 128), ("StateFlags", wintypes.DWORD),
            ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128),
        ]

    return DEVMODEW, DISPLAY_DEVICEW


class WindowsEnvironment(NullEnvironment):
    DM_POSITION, DM_PELSWIDTH, DM_PELSHEIGHT, DM_FREQ = 0x20, 0x80000, 0x100000, 0x400000
    CDS_UPDATEREGISTRY, CDS_SET_PRIMARY, CDS_NORESET = 0x1, 0x10, 0x10000000
    ATTACHED = 0x1
    ENUM_CURRENT = -1

    def __init__(self, opts: dict):
        self.keep_awake = opts.get("keep_awake", True)
        self.remove_ghost = opts.get("remove_ghost_displays", True)
        self.il = opts.get("input_leap", {}) or {}
        self.snapshot_path = os.path.expanduser("~/.omnidisplay_layout_snapshot.json")
        self._awake_thread: Optional[threading.Thread] = None
        self._awake_stop = threading.Event()
        self._il_last: Optional[str] = None

    # keep-awake -----------------------------------------------------------
    def _awake_worker(self):
        ES_CONTINUOUS, ES_SYSTEM, ES_DISPLAY = 0x80000000, 0x1, 0x2
        k32 = ctypes.windll.kernel32
        k32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM | ES_DISPLAY)
        self._awake_stop.wait()
        k32.SetThreadExecutionState(ES_CONTINUOUS)

    def _set_awake(self, on: bool):
        if on and not self._awake_thread:
            self._awake_stop.clear()
            self._awake_thread = threading.Thread(target=self._awake_worker, daemon=True)
            self._awake_thread.start()
            logger.info("Keep-awake enabled (PC owns a monitor)")
        elif not on and self._awake_thread:
            self._awake_stop.set()
            self._awake_thread.join(timeout=2)
            self._awake_thread = None
            logger.info("Keep-awake released")

    # display layout -------------------------------------------------------
    def _enum_active(self):
        DEVMODEW, DISPLAY_DEVICEW = _win_structs()
        user32 = ctypes.windll.user32
        out, i = [], 0
        while True:
            dd = DISPLAY_DEVICEW()
            dd.cb = ctypes.sizeof(dd)
            if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
                break
            i += 1
            if not (dd.StateFlags & self.ATTACHED):
                continue
            dm = DEVMODEW()
            dm.dmSize = ctypes.sizeof(dm)
            if user32.EnumDisplaySettingsW(dd.DeviceName, self.ENUM_CURRENT, ctypes.byref(dm)):
                out.append({"name": dd.DeviceName, "x": dm.dmPositionX, "y": dm.dmPositionY,
                            "w": dm.dmPelsWidth, "h": dm.dmPelsHeight, "freq": dm.dmDisplayFrequency})
        return sorted(out, key=lambda d: d["x"])

    def _set_mode(self, dev, x, y, w, h, freq=0, primary=False):
        DEVMODEW, _ = _win_structs()
        dm = DEVMODEW()
        dm.dmSize = ctypes.sizeof(dm)
        dm.dmFields = self.DM_POSITION | self.DM_PELSWIDTH | self.DM_PELSHEIGHT
        if w and freq:
            dm.dmFields |= self.DM_FREQ
            dm.dmDisplayFrequency = freq
        dm.dmPositionX, dm.dmPositionY, dm.dmPelsWidth, dm.dmPelsHeight = x, y, w, h
        flags = self.CDS_UPDATEREGISTRY | self.CDS_NORESET | (self.CDS_SET_PRIMARY if primary else 0)
        rc = ctypes.windll.user32.ChangeDisplaySettingsExW(dev, ctypes.byref(dm), None, flags, None)
        if rc != 0:
            logger.warning(f"ChangeDisplaySettingsEx({dev}) returned {rc}")
        return rc == 0

    def _commit(self):
        ctypes.windll.user32.ChangeDisplaySettingsExW(None, None, None, 0, None)
        time.sleep(1.5)  # let monitors/DDC handles re-enumerate

    def _load_snapshot(self):
        try:
            with open(self.snapshot_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _clear_snapshot(self):
        try:
            os.remove(self.snapshot_path)
        except OSError:
            pass

    def _restore(self):
        snap = self._load_snapshot()
        if not snap:
            return
        for d in snap["layout"]:
            self._set_mode(d["name"], d["x"], d["y"], d["w"], d["h"], d.get("freq", 0), primary=(d["x"] == 0 and d["y"] == 0))
        self._commit()
        self._clear_snapshot()
        logger.info("Restored full Windows display layout")

    def prepare_for_ddc(self):
        """Detached monitors vanish from DDC enumeration; re-attach before sending DDC."""
        if sys.platform == "win32" and self.remove_ghost:
            try:
                self._restore()
            except Exception as e:
                logger.warning(f"Layout restore failed: {e}")

    def _apply_layout(self, owned):
        ghosts = [s for s in SLOTS if not owned[s]]
        wanted = ghosts[0] if len(ghosts) == 1 else None

        snap = self._load_snapshot()
        if snap and wanted and snap.get("slot") == wanted:
            return  # already in desired state
        if snap:
            self._restore()
        if not wanted:
            return

        active = self._enum_active()
        if len(active) != 2:
            logger.info(f"Ghost removal skipped: expected 2 active displays, found {len(active)}")
            return
        ghost = active[0] if wanted == "left" else active[1]
        main = active[1] if wanted == "left" else active[0]
        with open(self.snapshot_path, "w", encoding="utf-8") as f:
            json.dump({"slot": wanted, "layout": active}, f)

        # A primary display can't be detached: make the live one primary first.
        if ghost["x"] == 0 and ghost["y"] == 0:
            self._set_mode(main["name"], 0, 0, main["w"], main["h"], main["freq"], primary=True)
        self._set_mode(ghost["name"], 0, 0, 0, 0)  # 0x0 size => detach
        self._commit()
        logger.info(f"Detached ghost {wanted} display ({ghost['name']})")

    # Input Leap -----------------------------------------------------------
    def _apply_input_leap(self, state):
        if not self.il.get("enabled") or not self.il.get("config_path"):
            return
        if state["left"] == "pc" and state["right"] == "mac":
            pc_side, mac_side = "right", "left"
        elif state["left"] == "mac" and state["right"] == "pc":
            pc_side, mac_side = "left", "right"
        else:
            return  # both on one machine: keep the last link direction
        pc, mac = self.il.get("pc_screen", "PC"), self.il.get("mac_screen", "MAC")
        conf = (
            "section: screens\n"
            f"\t{pc}:\n\t{mac}:\n"
            "end\n"
            "section: links\n"
            f"\t{pc}:\n\t\t{pc_side} = {mac}\n"
            f"\t{mac}:\n\t\t{mac_side} = {pc}\n"
            "end\n"
        )
        if conf == self._il_last:
            return
        try:
            with open(self.il["config_path"], "w", encoding="utf-8") as f:
                f.write(conf)
            self._il_last = conf
            logger.info(f"Input Leap layout written: {pc} {pc_side} of ... {mac}")
            cmd = self.il.get("restart_command")
            if cmd:
                subprocess.Popen(cmd, shell=True)
        except Exception as e:
            logger.warning(f"Input Leap config update failed: {e}")

    def apply(self, owned, state):
        if sys.platform != "win32":
            return
        self._set_awake(any(owned.values()) and self.keep_awake)
        if self.remove_ghost:
            try:
                self._apply_layout(owned)
            except Exception as e:
                logger.warning(f"Ghost display handling failed: {e}")
        self._apply_input_leap(state)

    def shutdown(self):
        self._set_awake(False)
        self.prepare_for_ddc()


def create_environment(role: str, config: dict):
    opts = (config or {}).get("environment", {}) or {}
    if opts.get("enabled", True) is False or os.environ.get("OMNIDISPLAY_DISABLE_ENV"):
        return NullEnvironment()
    if role == "mac" and sys.platform == "darwin":
        return MacEnvironment(opts)
    if role == "pc" and sys.platform == "win32":
        return WindowsEnvironment(opts)
    return NullEnvironment()
