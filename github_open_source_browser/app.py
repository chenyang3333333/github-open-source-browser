# -*- coding: utf-8 -*-
"""应用程序入口。"""
from __future__ import annotations
from github_open_source_browser.i18n import tr

import logging
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QSpinBox, QDoubleSpinBox

# Fix spinbox auto-select on focus
_orig_spin = QSpinBox.focusInEvent
_orig_dspin = QDoubleSpinBox.focusInEvent
def _fix_spin_focus(self, event):
    _orig_spin(self, event)
    le = self.lineEdit()
    if le:
        le.deselect()
def _fix_dspin_focus(self, event):
    _orig_dspin(self, event)
    le = self.lineEdit()
    if le:
        le.deselect()
QSpinBox.focusInEvent = _fix_spin_focus
QDoubleSpinBox.focusInEvent = _fix_dspin_focus

from github_open_source_browser.config import load_config_file, normalize_config
from github_open_source_browser.services.github_service import GitHubService
from github_open_source_browser.ui.main_window import MainWindow
from github_open_source_browser.ui import enhancements  # noqa: F401
from github_open_source_browser.ui.theme import apply_theme

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def get_config_dir() -> Path:
    """获取配置目录。"""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    config_dir = base / "GitHubOpenSourceBrowser"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def main():
    """主入口函数。"""
    # 高 DPI 支持
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(tr("app.title"))
    app.setApplicationVersion(tr("app.version"))

    # 图标
    icon_path = Path(__file__).parent / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 配置目录
    config_dir = get_config_dir()
    config_path = config_dir / "config.json"

    # 初始化服务
    service = GitHubService(str(config_path))
    logger.info("config: %s", config_path)
    logger.info("database: %s", getattr(service.db, 'db_path', 'N/A'))

    # 应用主题
    dark_mode = service.config.get("dark_mode", False)
    apply_theme(app, dark_mode)

    # 创建主窗口
    window = MainWindow(service)
    window.show()

    logger.info("application started")

    # 运行事件循环
    exit_code = app.exec()

    # 清理
    service.save_config()
    service.http.close()
    logger.info("application exited: %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
