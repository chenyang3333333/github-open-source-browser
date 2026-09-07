# -*- coding: utf-8 -*-
"""Loading animation widget for search and translation."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout


class LoadingSpinner(QWidget):
    """Animated spinning indicator."""
    def __init__(self, parent=None, size=20, color=None):
        super().__init__(parent)
        self._size = size
        self._color = color or QColor(100, 100, 100)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.setFixedSize(size, size)

    def start(self):
        self._angle = 0
        self._timer.start(50)
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _rotate(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        rect = self.rect().adjusted(3, 3, -3, -3)
        painter.drawArc(rect, self._angle * 16, 120 * 16)


class LoadingIndicator(QWidget):
    """Loading indicator with spinner and text."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 4)
        self._layout.setSpacing(6)
        self._spinner = LoadingSpinner(self, size=18)
        self._label = QLabel("")
        self._layout.addWidget(self._spinner)
        self._layout.addWidget(self._label)
        self.hide()

    def show_loading(self, text="Loading..."):
        self._label.setText(text)
        self._spinner.start()
        self.show()

    def hide_loading(self):
        self._spinner.stop()
        self.hide()

    def set_text(self, text):
        self._label.setText(text)
