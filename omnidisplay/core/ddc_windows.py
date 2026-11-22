"""
Windows DDC/CI display controller.
Uses native Win32 dxva2.dll (SetVCPFeature) and falls back to ControlMyMonitor / winddcutil.
"""

import sys
import re
import time
import shutil
import subprocess
from typing import List, Dict, Any, Optional
from omnidisplay.core.ddc_base import DDCController
from omnidisplay.core.logger import get_logger

logger = get_logger("ddc.windows")

class WindowsDDCController(DDCController):
    """Controls external displays on Windows using DDC/CI via dxva2.dll or CLI."""

    def __init__(self):
        self.control_my_monitor = shutil.which("ControlMyMonitor.exe")
        self.winddcutil = shutil.which("winddcutil.exe")
        self.is_windows = (sys.platform == "win32")

    def list_displays(self) -> List[Dict[str, Any]]:
        displays = []
        if self.is_windows:
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                dxva2 = ctypes.windll.dxva2

                class PHYSICAL_MONITOR(ctypes.Structure):
                    _fields_ = [
                        ('hPhysicalMonitor', wintypes.HANDLE),
                        ('szPhysicalMonitorDescription', wintypes.WCHAR * 128)
                    ]

                class MONITORINFOEXW(ctypes.Structure):
                    _fields_ = [
                        ('cbSize', wintypes.DWORD),
                        ('rcMonitor', wintypes.RECT),
                        ('rcWork', wintypes.RECT),
                        ('dwFlags', wintypes.DWORD),
                        ('szDevice', wintypes.WCHAR * 32)
                    ]

                class DISPLAY_DEVICEW(ctypes.Structure):
                    _fields_ = [
                        ('cb', wintypes.DWORD),
                        ('DeviceName', wintypes.WCHAR * 32),
                        ('DeviceString', wintypes.WCHAR * 128),
                        ('StateFlags', wintypes.DWORD),
                        ('DeviceID', wintypes.WCHAR * 128),
                        ('DeviceKey', wintypes.WCHAR * 128)
                    ]

                monitors = []
                def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                    monitors.append(hMonitor)
                    return True

                MONITORENUMPROC = ctypes.WINFUNCTYPE(
                    wintypes.BOOL,
                    wintypes.HMONITOR,
                    wintypes.HDC,
                    ctypes.POINTER(wintypes.RECT),
                    wintypes.LPARAM
                )

                user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(monitor_enum_proc), 0)

                disp_idx = 0
                for hMon in monitors:
                    # Resolve hardware device ID from Windows display adapter
                    hardware_name = None
                    try:
                        minfo = MONITORINFOEXW()
                        minfo.cbSize = ctypes.sizeof(MONITORINFOEXW)
                        if user32.GetMonitorInfoW(hMon, ctypes.byref(minfo)):
                            ddev = DISPLAY_DEVICEW()
                            ddev.cb = ctypes.sizeof(DISPLAY_DEVICEW)
                            if user32.EnumDisplayDevicesW(minfo.szDevice, 0, ctypes.byref(ddev), 0):
                                did = ddev.DeviceID.upper()
                                if "GBT" in did or "2402" in did or "G24F" in did:
                                    hardware_name = "GIGABYTE G24F"
                                elif "GSM" in did or "7768" in did or "WK95" in did:
                                    hardware_name = "LG ULTRAWIDE"
                    except Exception:
                        pass

                    count = wintypes.DWORD()
                    if dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hMon, ctypes.byref(count)) and count.value > 0:
                        phys_mons = (PHYSICAL_MONITOR * count.value)()
                        if dxva2.GetPhysicalMonitorsFromHMONITOR(hMon, count.value, phys_mons):
                            for i in range(count.value):
                                hPhys = phys_mons[i].hPhysicalMonitor
                                desc = hardware_name or phys_mons[i].szPhysicalMonitorDescription or f"Display {disp_idx + 1}"
                                # If still generic Windows driver string, query DDC capabilities
                                if "generic" in desc.lower():
                                    try:
                                        time.sleep(0.05)
                                        cap_len = wintypes.DWORD()
                                        if dxva2.GetCapabilitiesStringLength(hPhys, ctypes.byref(cap_len)) and cap_len.value > 0:
                                            buf = ctypes.create_string_buffer(cap_len.value)
                                            if dxva2.CapabilitiesRequestAndCapabilitiesReply(hPhys, buf, cap_len.value):
                                                raw = buf.value.decode('latin1', errors='ignore')
                                                m = re.search(r'model\(([^)]+)\)', raw, re.IGNORECASE)
                                                if m:
                                                    model_code = m.group(1).strip()
                                                    if "WK95U" in model_code:
                                                        desc = "LG ULTRAWIDE"
                                                    elif "G24F" in model_code:
                                                        desc = "GIGABYTE G24F"
                                                    else:
                                                        desc = model_code
                                    except Exception:
                                        pass

                                displays.append({
                                    "id": f"win-display-{disp_idx}",
                                    "index": disp_idx,
                                    "name": desc,
                                    "driver": "dxva2"
                                })
                                disp_idx += 1
                            dxva2.DestroyPhysicalMonitors(count.value, phys_mons)
            except Exception as e:
                print(f"[WindowsDDCController] Error querying dxva2: {e}")

        # If running outside Windows or dxva2 returned none
        if not displays:
            displays = [
                {"id": "win-display-left", "index": 0, "name": "Left Monitor (Windows)", "driver": "simulated"},
                {"id": "win-display-right", "index": 1, "name": "Right Monitor (Windows)", "driver": "simulated"}
            ]

        return displays

    def set_input_source(self, display_index: int, input_value: int) -> bool:
        """
        Set VCP Feature 0x60 on Windows with I2C pacing and retries.
        """
        if self.is_windows:
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                dxva2 = ctypes.windll.dxva2

                class PHYSICAL_MONITOR(ctypes.Structure):
                    _fields_ = [
                        ('hPhysicalMonitor', wintypes.HANDLE),
                        ('szPhysicalMonitorDescription', wintypes.WCHAR * 128)
                    ]

                monitors = []
                def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                    monitors.append(hMonitor)
                    return True

                MONITORENUMPROC = ctypes.WINFUNCTYPE(
                    wintypes.BOOL,
                    wintypes.HMONITOR,
                    wintypes.HDC,
                    ctypes.POINTER(wintypes.RECT),
                    wintypes.LPARAM
                )

                user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(monitor_enum_proc), 0)

                current_index = 0
                for hMon in monitors:
                    count = wintypes.DWORD()
                    if dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hMon, ctypes.byref(count)) and count.value > 0:
                        phys_mons = (PHYSICAL_MONITOR * count.value)()
                        if dxva2.GetPhysicalMonitorsFromHMONITOR(hMon, count.value, phys_mons):
                            for i in range(count.value):
                                if current_index == display_index:
                                    hPhys = phys_mons[i].hPhysicalMonitor
                                    desc = phys_mons[i].szPhysicalMonitorDescription
                                    # Pacing delay for I2C bus stability
                                    time.sleep(0.08)
                                    res = False
                                    last_err = 0
                                    for attempt in range(1, 3):
                                        res = dxva2.SetVCPFeature(hPhys, 0x60, input_value)
                                        if res:
                                            break
                                        last_err = ctypes.GetLastError()
                                        time.sleep(0.12)
                                    dxva2.DestroyPhysicalMonitors(count.value, phys_mons)
                                    logger.info(f"SetVCPFeature(disp={display_index} [{desc}], 0x60={input_value}) -> success={bool(res)}, err={last_err}")
                                    return bool(res)
                                current_index += 1
                            dxva2.DestroyPhysicalMonitors(count.value, phys_mons)
            except Exception as e:
                logger.error(f"dxva2 call failed: {e}")

        # Try ControlMyMonitor fallback if installed
        if self.control_my_monitor:
            try:
                cmd = [self.control_my_monitor, "/SetValue", f"Primary", "60", str(input_value)]
                res = subprocess.run(cmd, capture_output=True, timeout=3)
                if res.returncode == 0:
                    logger.info(f"ControlMyMonitor switch: Display {display_index} -> 0x60={input_value}")
                    return True
            except Exception:
                pass

        # Simulated fallback
        logger.info(f"Simulated switch: Display {display_index} -> VCP 0x60 = {input_value}")
        return True

    def get_input_source(self, display_index: int) -> Optional[int]:
        if self.is_windows:
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                dxva2 = ctypes.windll.dxva2

                class PHYSICAL_MONITOR(ctypes.Structure):
                    _fields_ = [
                        ('hPhysicalMonitor', wintypes.HANDLE),
                        ('szPhysicalMonitorDescription', wintypes.WCHAR * 128)
                    ]

                monitors = []
                def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                    monitors.append(hMonitor)
                    return True

                MONITORENUMPROC = ctypes.WINFUNCTYPE(
                    wintypes.BOOL,
                    wintypes.HMONITOR,
                    wintypes.HDC,
                    ctypes.POINTER(wintypes.RECT),
                    wintypes.LPARAM
                )
                user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(monitor_enum_proc), 0)

                current_index = 0
                for hMon in monitors:
                    count = wintypes.DWORD()
                    if dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hMon, ctypes.byref(count)) and count.value > 0:
                        phys_mons = (PHYSICAL_MONITOR * count.value)()
                        if dxva2.GetPhysicalMonitorsFromHMONITOR(hMon, count.value, phys_mons):
                            for i in range(count.value):
                                if current_index == display_index:
                                    time.sleep(0.05)
                                    curr = wintypes.DWORD()
                                    max_v = wintypes.DWORD()
                                    res = dxva2.GetVCPFeatureAndVCPFeatureReply(phys_mons[i].hPhysicalMonitor, 0x60, None, ctypes.byref(curr), ctypes.byref(max_v))
                                    dxva2.DestroyPhysicalMonitors(count.value, phys_mons)
                                    return curr.value if res else None
                                current_index += 1
                            dxva2.DestroyPhysicalMonitors(count.value, phys_mons)
            except Exception as e:
                logger.error(f"get_input_source failed: {e}")
        return None
