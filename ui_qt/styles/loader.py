# -*- coding: utf-8 -*-
"""Загрузка QSS-стилей и применение темы."""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from core.constants import BUNDLE_DIR


# Ресурсы (QSS) читаются из bundle:
#   - из исходников: корень проекта
#   - из .exe (PyInstaller): _MEIPASS (= dist/AniShelf365/_internal)
STYLES_DIR = os.path.join(BUNDLE_DIR, "ui_qt", "styles")


def _read_qss(name: str) -> str:
    path = os.path.join(STYLES_DIR, name)
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def get_stylesheet(theme: str) -> str:
    """Содержимое QSS для 'dark' или 'light'."""
    if theme == "light":
        return _read_qss("light.qss")
    return _read_qss("dark.qss")


def detect_system_theme() -> str:
    """Определяет системную тему: 'dark' или 'light'."""
    app = QApplication.instance()
    if app is None:
        return "dark"
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
        if scheme == Qt.ColorScheme.Light:
            return "light"
    except Exception:
        pass
    return "dark"


def apply_theme(theme: str):
    """
    Применяет тему ко всему приложению.
    theme: 'dark' | 'light' | 'system'.
    """
    app = QApplication.instance()
    if app is None:
        return
    if theme == "system":
        theme = detect_system_theme()
    qss = get_stylesheet(theme)
    app.setStyleSheet(qss)