#!/usr/bin/env bash
# uninstall-mac.sh - Remove OmniDisplay LaunchAgent from macOS

PLIST_PATH="${HOME}/Library/LaunchAgents/com.omnidisplay.agent.plist"

echo "=== Uninstalling OmniDisplay LaunchAgent ==="
if [ -f "${PLIST_PATH}" ]; then
    launchctl unload "${PLIST_PATH}" 2>/dev/null || true
    rm -f "${PLIST_PATH}"
    echo "✓ LaunchAgent removed."
else
    echo "LaunchAgent was not installed."
fi
