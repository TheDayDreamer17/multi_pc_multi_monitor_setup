#!/usr/bin/env bash
# build-mac-app.sh - Build a standalone native macOS Cocoa .app bundle for OmniDisplay

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${REPO_DIR}/OmniDisplay.app"
PYTHON_BIN="$(which python3)"

echo "=== Building Native macOS OmniDisplay.app ==="

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

# 2. Compile Native Cocoa WebKit window using Swift
echo "Compiling native Cocoa application (Swift)..."
swiftc -O "${REPO_DIR}/omnidisplay/native/mac_app.swift" -o "${APP_DIR}/Contents/MacOS/OmniDisplayNative"
chmod +x "${APP_DIR}/Contents/MacOS/OmniDisplayNative"

# 3. Executable launcher script
cat << EOF > "${APP_DIR}/Contents/MacOS/OmniDisplay"
#!/usr/bin/env bash
REPO_DIR="${REPO_DIR}"
cd "\${REPO_DIR}"

# Ensure background daemon is running
if ! curl -s --connect-timeout 0.5 http://127.0.0.1:5959/api/status >/dev/null 2>&1; then
    nohup "${PYTHON_BIN}" -m omnidisplay.cli start --role mac >/tmp/omnidisplay.log 2>/tmp/omnidisplay.err &
    sleep 0.5
fi

DIR="\$(cd "\$(dirname "\$0")" && pwd)"
exec "\${DIR}/OmniDisplayNative"
EOF

chmod +x "${APP_DIR}/Contents/MacOS/OmniDisplay"

# 4. Link into ~/Applications
mkdir -p "${HOME}/Applications"
ln -sf "${APP_DIR}" "${HOME}/Applications/OmniDisplay.app"

echo "✓ Created: ${APP_DIR}"
echo "✓ Installed to: ${HOME}/Applications/OmniDisplay.app"
echo "You can now open OmniDisplay directly from Spotlight (Cmd+Space) or Applications!"
