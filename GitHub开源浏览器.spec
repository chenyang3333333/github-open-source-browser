# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

# 正式打包规格：保留图标和用户插件，避免一体化程序启动后找不到可选翻译插件。
project_root = Path(r'D:\工具\GitHub\github-open-source-browser')
source_path = project_root / 'github_open_source_browser' / 'main.py'
icon_path = project_root / 'github_open_source_browser' / 'app.ico'
plugin_path = project_root / 'github_open_source_browser' / 'user_plugins'

analysis = Analysis(
    [str(source_path)],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(icon_path), 'github_open_source_browser'),
        (str(plugin_path), 'github_open_source_browser/user_plugins'),
    ],
    hiddenimports=[
        'webbrowser',
        'winreg',
        'mimetypes',
        'hashlib',
        'hmac',
        'json',
        'threading',
        'concurrent.futures',
        'urllib.parse',
        'datetime',
        'github_open_source_browser.translator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Qt6Core需要使用Windows系统自带的ICU接口，排除构建环境中Poppler带入的冲突动态库。
incompatible_icu_files = {'icuuc.dll', 'icudt78.dll'}
analysis.binaries = [
    entry
    for entry in analysis.binaries
    if Path(entry[1]).name.lower() not in incompatible_icu_files
]

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name='GitHub开源浏览器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(icon_path)],
)
