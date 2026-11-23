# OmniDisplay 🎛️

**Cross-Platform Dual-PC Dual-Monitor Coordinator**

OmniDisplay eliminates the need for expensive hardware HDMI/DisplayPort KVM switches. If your **Windows PC** and **Mac** are both physically connected to two multi-input monitors, OmniDisplay lets you switch and route any display to any computer over your local network using standard **VESA DDC/CI** commands.

Works seamlessly across **Ethernet** and **Wi-Fi** when connected to the same home router or local subnet.

---

## ⚡ The 4 Display Presets

OmniDisplay gives you instant one-click or hotkey control over all 4 combinations:

| Preset | Shortcut | Left Monitor | Right Monitor | Best For |
| :--- | :---: | :---: | :---: | :--- |
| **PC in Both** | `1` | 🖥️ PC | 🖥️ PC | Full PC Gaming / CAD / Visual Studio |
| **Mac in Both** | `2` | 🍎 Mac | 🍎 Mac | Full Mac Development / Design / Xcode |
| **Left PC, Right Mac** | `3` | 🖥️ PC | 🍎 Mac | Cross-development / Reference setup |
| **Left Mac, Right PC** | `4` | 🍎 Mac | 🖥️ PC | Coding on Mac with Windows testing |

You can also individually toggle the Left or Right display at any time!

---

## 🏛️ System Architecture

```
                 +--------------------------------------+
                 |      Home Router / Local Subnet      |
                 +-------------------+------------------+
                                     |
               +---------------------+---------------------+
               | (Wi-Fi)                                   | (Ethernet)
               v                                           v
       +---------------+                           +---------------+
       |    Mac mini   |                           |   Windows PC  |
       |  (OmniDisplay)|                           |  (OmniDisplay)|
       +-------+-------+                           +-------+-------+
               |                                           |
               | HDMI / Type-C                             | DP / HDMI
               |                                           |
       +-------v-------------------------------------------v-------+
       |   Monitor 1 (Left)             Monitor 2 (Right)          |
       |   [DP: PC | HDMI: Mac]         [DP: PC | Type-C: Mac]     |
       +-----------------------------------------------------------+
```

### Why a Cross-Host Network Coordinator is Necessary
Monitors receive input switch commands via **VESA DDC/CI (VCP Opcode `0x60`)** over the video cable's I2C channel. 

However, many monitors put inactive input ports into a power-saving sleep state. When Monitor 1 switches from Mac to PC, Mac can no longer send DDC commands to take it back. 

**OmniDisplay solves this with Distributed Relay RPC:**
1. Both machines run a lightweight OmniDisplay agent.
2. They automatically discover each other over LAN via UDP broadcast (`59599`).
3. When you trigger "Mac in Both" from your Mac, the Mac agent automatically relays an internal RPC request to the Windows agent: *"Switch Monitor 1 to Mac"*.
4. The Windows machine—which has the active video link—issues the local DDC switch command on behalf of the Mac. The monitor transitions instantly without missing a beat.

---

## 🚀 Quick Start

### 1. Installation on macOS
From your Mac terminal:
```bash
git clone https://github.com/<your-username>/multipcmultimonitorsetup.git
cd multipcmultimonitorsetup
./scripts/install-mac.sh
```
* Compiles the native Apple Silicon DDC helper (`clang`).
* Installs and registers a background **LaunchAgent** (`~/Library/LaunchAgents/com.omnidisplay.agent.plist`).
* Automatically starts the daemon on boot/login.

### 2. Installation on Windows
From your Windows PowerShell (run as Administrator or standard user):
```powershell
git clone https://github.com/<your-username>/multipcmultimonitorsetup.git
cd multipcmultimonitorsetup
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1
```
* Registers a silent background launcher (`OmniDisplay.vbs`) in your Windows Startup folder (`shell:startup`).
* Uses native Win32 `dxva2.dll` to send DDC commands with zero required dependencies.
* Automatically starts on Windows user login.

---

## 🖥️ Desktop Software UI & Daily Usage

OmniDisplay provides a dedicated **Desktop Application Window** for both macOS and Windows, with no browser tabs required!

* **Launch on Mac**: Double-click `OmniDisplay.app` (linked in `~/Applications` or from Spotlight), or run `python3 -m omnidisplay gui`.
* **Launch on Windows**: Double-click the `OmniDisplay` shortcut on your Desktop, or run `python -m omnidisplay gui`.
* **Interactive UI Features**:
  * **Visual Monitor Screens**: Color-coded live screens (Orange for Mac, Blue for PC).
  * **Quick Toggle**: Direct `⇄ Switch to PC / Mac` buttons below each screen.
  * **Quick Presets (1-4)**: Click any preset card or press keyboard keys `1`, `2`, `3`, or `4` anytime the window is open.
  * **Peer Status**: Real-time LAN connection indicator (Green = Connected, Yellow = Searching).

*(Optional: A Web Dashboard is also available at `http://localhost:5959` if you want to switch monitors from a smartphone, iPad, or Stream Deck on your local network).*

### Terminal CLI Usage
You can also trigger switching directly from your terminal or assign them to global OS hotkeys:

```bash
# Switch presets
omnidisplay switch pc_both      # or: omnidisplay switch 1
omnidisplay switch mac_both     # or: omnidisplay switch 2
omnidisplay switch split_pc_mac # or: omnidisplay switch 3
omnidisplay switch split_mac_pc # or: omnidisplay switch 4

# Individual monitor toggling
omnidisplay toggle left
omnidisplay toggle right

# View active status
omnidisplay status

# Scan physical monitors
omnidisplay probe
```

---

## ⚙️ Configuration (`config.json`)

OmniDisplay comes with standard defaults that match most multi-monitor setups. If your monitors use non-standard input numbers, create a `~/.omnidisplay_config.json` file or edit `config.example.json`:

```json
{
  "device_role": "auto",
  "port": 5959,
  "peer_host": null,
  "displays": {
    "left": {
      "name": "Left Monitor",
      "index_mac": 0,
      "index_pc": 0,
      "inputs": {
        "mac": 17,
        "pc": 15
      }
    },
    "right": {
      "name": "Right Monitor",
      "index_mac": 1,
      "index_pc": 1,
      "inputs": {
        "mac": 27,
        "pc": 17
      }
    }
  }
}
```

### Ghost Displays, Keep-Awake & Input Leap (`environment`)
* **Ghost display removal** – a monitor showing the *other* computer is removed from this computer's desktop (macOS: mirrored onto the live display; Windows: detached), so the cursor never crosses an invisible screen. It is restored automatically before any DDC command and when the monitor returns. On macOS this is on by default (`"remove_ghost_displays": false` disables it). On Windows it is **opt-in** via `"remove_ghost_displays_windows": true`, because detaching a display edits persistent Windows display settings.
* **Keep-awake** – while a machine owns at least one monitor it won't sleep its display, so the monitor no longer falls back to the other PC after idle. Disable with `"keep_awake": false`.
* **Input Leap** – on the PC (Input Leap server) set `input_leap.enabled` and `config_path`; OmniDisplay rewrites the screen link (PC left/right of Mac) per preset and runs `restart_command` if set. Screen names must match your Input Leap screen names.

### Standard VESA VCP Code `0x60` Reference
* `15` (`0x0F`): DisplayPort 1
* `16` (`0x10`): DisplayPort 2
* `17` (`0x11`): HDMI 1
* `18` (`0x12`): HDMI 2
* `27` (`0x1B`): USB-C / DisplayPort Alt-Mode

---

## 🛠️ Uninstallation

* **macOS**: `./scripts/uninstall-mac.sh`
* **Windows**: `powershell -ExecutionPolicy Bypass -File .\scripts\uninstall-windows.ps1`

---

## 📜 License
MIT License. Free for personal and commercial use.
