# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Claude Code Usage Mac app."""

import os
import sys
from pathlib import Path

block_cipher = None

src_dir = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'src')
static_dir = os.path.join(src_dir, 'claude_usage', 'static')
icon_path = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'assets', 'AppIcon.icns')

a = Analysis(
    [os.path.join(src_dir, 'claude_usage', 'app.py')],
    pathex=[src_dir],
    binaries=[],
    datas=[
        (static_dir, 'claude_usage/static'),
    ],
    hiddenimports=[
        'claude_usage',
        'claude_usage.parser',
        'claude_usage.app',
        'flask',
        'flask.json',
        'jinja2',
        'markupsafe',
        'psutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Claude Code Usage',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Claude Code Usage',
)

app = BUNDLE(
    coll,
    name='Claude Code Usage.app',
    icon=icon_path if os.path.exists(icon_path) else None,
    bundle_identifier='com.buaajoseph.claude-code-usage',
    info_plist={
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleName': 'Claude Code Usage',
        'CFBundleDisplayName': 'Claude Code Usage',
        'LSMinimumSystemVersion': '10.15',
        'LSApplicationCategoryType': 'public.app-category.developer-tools',
        'NSHighResolutionCapable': True,
    },
)
