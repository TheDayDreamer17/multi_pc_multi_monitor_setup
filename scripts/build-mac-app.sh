#!/usr/bin/env bash
# build-mac-app.sh - Build a standalone macOS .app bundle for OmniDisplay

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${REPO_DIR}/OmniDisplay.app"
PYTHON_BIN="$(which python3)"

echo "=== Building macOS OmniDisplay.app ==="

rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}/Contents/MacOS"
mkdir -p "${APP_DIR}/Contents/Resources"

# 1. Info.plist
cat << EOF > "${APP_DIR}/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>OmniDisplay</string>
    <key>CFBundleDisplayName</key>
    <string>OmniDisplay</string>
    <key>CFBundleIdentifier</key>
    <string>com.omnidisplay.app</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>OmniDisplay</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# 2. Executable launcher script
cat << EOF > "${APP_DIR}/Contents/MacOS/OmniDisplay"
#!/usr/bin/env bash
cd "${REPO_DIR}"
exec "${PYTHON_BIN}" -m omnidisplay.gui.launcher
EOF

chmod +x "${APP_DIR}/Contents/MacOS/OmniDisplay"

echo "✓ Created: ${APP_DIR}"
echo "You can now drag OmniDisplay.app to /Applications or open it directly!"
