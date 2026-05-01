#!/bin/bash
set -e

# Build Claude Code Usage as a macOS .app and .dmg
# Run this on macOS: bash scripts/build_mac.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VERSION="1.0.1"
APP_NAME="Claude Code Usage"
DMG_NAME="Claude-Code-Usage-${VERSION}"

cd "$PROJECT_DIR"

echo "==> Setting up build environment..."
python3 -m pip install --quiet pyinstaller pillow 2>/dev/null || \
    pip3 install --quiet pyinstaller pillow

echo "==> Generating app icon..."
python3 scripts/create_icon.py 2>/dev/null || echo "   (icon generation skipped, using default)"

echo "==> Installing project dependencies..."
python3 -m pip install --quiet -e . 2>/dev/null || pip3 install --quiet -e .

echo "==> Building macOS app with PyInstaller..."
python3 -m PyInstaller \
    --clean \
    --noconfirm \
    claude_usage_app.spec

echo "==> App bundle created at: dist/${APP_NAME}.app"

# Create DMG
if command -v create-dmg &>/dev/null; then
    echo "==> Creating DMG installer..."
    rm -f "dist/${DMG_NAME}.dmg"
    create-dmg \
        --volname "$APP_NAME" \
        --volicon "assets/AppIcon.icns" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 128 \
        --icon "$APP_NAME.app" 150 200 \
        --app-drop-link 450 200 \
        --hide-extension "$APP_NAME.app" \
        "dist/${DMG_NAME}.dmg" \
        "dist/${APP_NAME}.app" \
        2>/dev/null || \
    # Fallback: simpler create-dmg call if fancy options fail
    create-dmg \
        --volname "$APP_NAME" \
        --app-drop-link 400 200 \
        "dist/${DMG_NAME}.dmg" \
        "dist/${APP_NAME}.app"

    echo "==> DMG created at: dist/${DMG_NAME}.dmg"
else
    echo ""
    echo "==> create-dmg not found. Install it for DMG creation:"
    echo "    brew install create-dmg"
    echo ""
    echo "    Or create a DMG manually:"
    echo "    hdiutil create -volname '${APP_NAME}' -srcfolder 'dist/${APP_NAME}.app' -ov -format UDZO 'dist/${DMG_NAME}.dmg'"
    echo ""

    # Fallback to hdiutil (built-in macOS)
    echo "==> Creating DMG with hdiutil (basic layout)..."
    hdiutil create \
        -volname "$APP_NAME" \
        -srcfolder "dist/${APP_NAME}.app" \
        -ov -format UDZO \
        "dist/${DMG_NAME}.dmg" 2>/dev/null && \
        echo "==> DMG created at: dist/${DMG_NAME}.dmg" || \
        echo "==> DMG creation failed (not on macOS?)"
fi

echo ""
echo "==> Build complete!"
echo "    App: dist/${APP_NAME}.app"
echo "    DMG: dist/${DMG_NAME}.dmg (if created)"
echo ""
echo "    To test: open 'dist/${APP_NAME}.app'"
