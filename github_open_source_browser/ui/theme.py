# -*- coding: utf-8 -*-
"""主题管理：亮色/暗色主题、QSS 样式表。"""
from __future__ import annotations

from PyQt6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# 亮色主题
# ---------------------------------------------------------------------------

LIGHT_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #f5f5f5;
    color: #1a1a1a;
}
QListWidget {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 4px;
    color: #1a1a1a;
    font-size: 13px;
}
QListWidget::item {
    padding: 8px 16px 8px 8px;
    border-bottom: 1px solid #eeeeee;
}
QListWidget::item:selected {
    background-color: #cce5ff;
    color: #1a1a1a;
}
QListWidget::item:hover {
    background-color: #e8f0fe;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 6px 16px;
    color: #1a1a1a;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #e8f0fe;
    border-color: #4a9eff;
}
QPushButton:pressed {
    background-color: #cce5ff;
}
QPushButton#primaryButton {
    background-color: #0969da;
    color: #ffffff;
    border-color: #0969da;
}
QPushButton#primaryButton:hover {
    background-color: #0550ae;
}
QComboBox {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 6px 12px;
    color: #1a1a1a;
    font-size: 13px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #4a9eff;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    color: #1a1a1a;
    selection-background-color: #cce5ff;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 6px;
    color: #1a1a1a;
    font-size: 13px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #4a9eff;
}
QLabel {
    color: #1a1a1a;
    font-size: 13px;
}
QLabel#titleLabel {
    font-size: 16px;
    font-weight: bold;
}
QLabel#descLabel {
    color: #57606a;
    font-size: 12px;
}
QSplitter::handle {
    background-color: #d0d0d0;
    width: 2px;
}
QTabWidget::pane {
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    background-color: #ffffff;
}
QTabBar::tab {
    background-color: #f5f5f5;
    border: 1px solid #d0d0d0;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    color: #57606a;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1a1a1a;
    font-weight: bold;
}
QCheckBox {
    color: #1a1a1a;
    font-size: 13px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
/* SpinBox uses native rendering for proper button behavior */
QStatusBar {
    background-color: #f5f5f5;
    color: #57606a;
    border-top: 1px solid #d0d0d0;
    font-size: 12px;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #999999;
    border-radius: 4px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover {
    background: #666666;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #c0c0c0;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #a0a0a0;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QGroupBox {
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QProgressBar {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    text-align: center;
    background-color: #e8e8e8;
}
QProgressBar::chunk {
    background-color: #0969da;
    border-radius: 3px;
}
"""

# ---------------------------------------------------------------------------
# 暗色主题
# ---------------------------------------------------------------------------

DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #0d1117;
    color: #e6edf3;
}
QListWidget {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px;
    color: #e6edf3;
    font-size: 13px;
}
QListWidget::item {
    padding: 8px 16px 8px 8px;
    border-bottom: 1px solid #21262d;
}
QListWidget::item:selected {
    background-color: #1f3a5f;
    color: #e6edf3;
}
QListWidget::item:hover {
    background-color: #1c2533;
}
QPushButton {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 16px;
    color: #e6edf3;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #30363d;
    border-color: #58a6ff;
}
QPushButton:pressed {
    background-color: #1f3a5f;
}
QPushButton#primaryButton {
    background-color: #238636;
    color: #ffffff;
    border-color: #238636;
}
QPushButton#primaryButton:hover {
    background-color: #2ea043;
}
QComboBox {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e6edf3;
    font-size: 13px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #58a6ff;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    color: #e6edf3;
    selection-background-color: #1f3a5f;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px;
    color: #e6edf3;
    font-size: 13px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #58a6ff;
}
QLabel {
    color: #e6edf3;
    font-size: 13px;
}
QLabel#titleLabel {
    font-size: 16px;
    font-weight: bold;
}
QLabel#descLabel {
    color: #8b949e;
    font-size: 12px;
}
QSplitter::handle {
    background-color: #30363d;
    width: 2px;
}
QTabWidget::pane {
    border: 1px solid #30363d;
    border-radius: 6px;
    background-color: #161b22;
}
QTabBar::tab {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    color: #8b949e;
}
QTabBar::tab:selected {
    background-color: #161b22;
    color: #e6edf3;
    font-weight: bold;
}
QCheckBox {
    color: #e6edf3;
    font-size: 13px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
/* SpinBox uses native rendering for proper button behavior */
QStatusBar {
    background-color: #0d1117;
    color: #8b949e;
    border-top: 1px solid #30363d;
    font-size: 12px;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #555555;
    border-radius: 4px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover {
    background: #888888;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #484f58;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #6e7681;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QGroupBox {
    border: 1px solid #30363d;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    color: #e6edf3;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QProgressBar {
    border: 1px solid #30363d;
    border-radius: 4px;
    text-align: center;
    background-color: #21262d;
}
QProgressBar::chunk {
    background-color: #238636;
    border-radius: 3px;
}
"""


def apply_theme(app: QApplication, dark: bool) -> None:
    """应用主题到整个应用程序。"""
    app.setStyleSheet(DARK_THEME_QSS if dark else LIGHT_THEME_QSS)
