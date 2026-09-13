# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
try:
    # PyInstaller 注入的 spec 所在目录，可移植于任意开发环境
    project_root = Path(SPECPATH)
except NameError:
    project_root = Path(__file__).resolve().parent
source_path = project_root / 'github_open_source_browser' / 'app.py'
icon_path = project_root / 'github_open_source_browser' / 'app.ico'
i18n_dir = project_root / 'github_open_source_browser' / 'i18n'
analysis = Analysis(
    [str(source_path)],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(icon_path), 'github_open_source_browser'),
        (str(i18n_dir / 'zh_CN.json'), 'github_open_source_browser/i18n'),
        (str(i18n_dir / 'en_US.json'), 'github_open_source_browser/i18n'),
    ],
    hiddenimports=[
        'webbrowser', 'winreg', 'mimetypes', 'hashlib', 'hmac',
        'json', 'threading', 'concurrent.futures', 'urllib.parse', 'datetime',
        'github_open_source_browser.translator',
        'github_open_source_browser.database',
        'github_open_source_browser.plugins',
        'github_open_source_browser.config',
        'github_open_source_browser.i18n',
        'github_open_source_browser.services.http_client',
        'github_open_source_browser.services.github_service',
        'github_open_source_browser.services.translation_service',
        'github_open_source_browser.ui.main_window',
        'github_open_source_browser.ui.settings_dialog',
        'github_open_source_browser.ui.theme',
        'github_open_source_browser.ui.enhancements',
        'github_open_source_browser.app',
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False, optimize=0,
)
incompatible_icu_files = {'icuuc.dll', 'icudt78.dll'}
analysis.binaries = [e for e in analysis.binaries if Path(e[1]).name.lower() not in incompatible_icu_files]
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz, analysis.scripts, analysis.binaries, analysis.datas, [],
    name='GitHub开源浏览器', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, disable_windowed_traceback=False,
    argv_emulation=False, target_arch=None, codesign_identity=None,
    entitlements_file=None, icon=[str(icon_path)],
)
