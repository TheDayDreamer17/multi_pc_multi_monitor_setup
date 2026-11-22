#!/usr/bin/env bash
# install-mac.sh - Install OmniDisplay as a background auto-start LaunchAgent on macOS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PLIST_PATH="${HOME}/Library/LaunchAgents/com.omnidisplay.agent.plist"
PYTHON_BIN="$(which python3)"

echo "=== Installing OmniDisplay on macOS ==="
echo "Repository: ${REPO_DIR}"
echo "Python:     ${PYTHON_BIN}"

# 1. Compile native Apple Silicon DDC binary
echo "Compiling native Apple Silicon DDC helper..."
clang -O2 \
  -framework CoreFoundation \
  -framework IOKit \
  -F /System/Library/PrivateFrameworks \
  -framework DisplayServices \
  "${REPO_DIR}/omnidisplay/native/mac_ddc.c" \
  -o "${REPO_DIR}/omnidisplay/native/mac_ddc"
chmod +x "${REPO_DIR}/omnidisplay/native/mac_ddc"
echo "✓ Native helper compiled successfully."

# 2. Generate LaunchAgent plist
mkdir -p "${HOME}/Library/LaunchAgents"

cat << EOF > "${PLIST_PATH}"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.omnidisplay.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>-m</string>
        <string>omnidisplay.cli</string>
        <string>start</string>
        <string>--role</string>
        <string>mac</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${REPO_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/omnidisplay.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/omnidisplay.err</string>
</dict>
</plist>
EOF

# 3. Load LaunchAgent
echo "Registering LaunchAgent..."
launchctl unload "${PLIST_PATH}" 2>/dev/null || true
launchctl load "${PLIST_PATH}"

# 4. Build Desktop App bundle
echo "Building OmniDisplay.app desktop application..."
"${SCRIPT_DIR}/build-mac-app.sh"
mkdir -p "${HOME}/Applications"
ln -sf "${REPO_DIR}/OmniDisplay.app" "${HOME}/Applications/OmniDisplay.app"
echo "✓ Desktop App linked to: ~/Applications/OmniDisplay.app"

echo "✓ OmniDisplay installed and running!"
echo "Desktop App:   Open OmniDisplay.app from Spotlight or ~/Applications"
echo "Web Dashboard: http://localhost:5959"
echo "Logs:          tail -f /tmp/omnidisplay.log"
