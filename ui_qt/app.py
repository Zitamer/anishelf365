# -*- coding: utf-8 -*-
"""Главное окно приложения на PySide6."""

import logging
import os
import subprocess
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QStackedWidget,
    QApplication, QDialog,
)

from core.constants import (
    APP_NAME, APP_VERSION, DEFAULT_LANGUAGE,
    DATA_DIR, COVERS_DIR, DB_PATH,
)
from core.db import Database
from core.settings import Settings
from core.api import Anime365API
from core import i18n
from ui_qt.styles.loader import apply_theme
from ui_qt.download_manager import DownloadManager


logger = logging.getLogger(__name__)


class AnimeLibraryApp(QMainWindow):
    """Главное окно приложения."""

    def __init__(self):
        super().__init__()

        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(COVERS_DIR, exist_ok=True)

        self.db = Database(DB_PATH)
        self.settings = Settings(self.db)
        self.api = Anime365API()
        self.logger = logging.getLogger("app")

        lang = self.settings.language or DEFAULT_LANGUAGE
        i18n.load(lang)
        logger.info(f"Загружен язык: {lang}")

        theme = self.settings.theme or "dark"
        apply_theme(theme)
        logger.info(f"Применена тема: {theme}")

        self.download_manager = DownloadManager(self)

        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        self.setMinimumSize(1100, 650)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self._current_view = None

        QTimer.singleShot(50, self._start)

    # ============================================================
    # Управление экранами
    # ============================================================

    def _set_view(self, widget: QWidget):
        old = self._current_view
        if old is not None and hasattr(old, "disconnect_downloads"):
            try:
                old.disconnect_downloads()
            except Exception:
                logger.exception("Ошибка отписки от менеджера")

        while self.stack.count() > 0:
            old_w = self.stack.widget(0)
            self.stack.removeWidget(old_w)
            old_w.deleteLater()

        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        self._current_view = widget

    def show_onboarding(self):
        logger.info("Показываем онбординг")
        from ui_qt.onboarding import OnboardingWindow
        self._set_view(OnboardingWindow(self))

    def show_library(self):
        logger.info("Показываем библиотеку")
        from ui_qt.library_view import LibraryView
        self._set_view(LibraryView(self))

    def show_series(self, series_id: int):
        logger.info(f"Показываем экран тайтла {series_id}")
        from ui_qt.series_view import SeriesView
        self._set_view(SeriesView(self, series_id))

    def show_add_series(self):
        logger.info("Открываем диалог добавления тайтла")
        from ui_qt.dialogs.add_series_dialog import AddSeriesDialog

        library_path = self.settings.library_path or ""
        dlg = AddSeriesDialog(
            self, api=self.api, db=self.db, library_path=library_path,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        sid = dlg.get_series_id()
        if not sid:
            return
        logger.info(f"Тайтл {sid} добавлен — открываем экран")
        self.show_series(sid)

    def show_settings(self):
        logger.info("Открываем настройки")
        from ui_qt.settings_dialog import SettingsDialog

        dlg = SettingsDialog(self)
        result = dlg.exec()

        if result == QDialog.DialogCode.Accepted and dlg.need_restart:
            self.restart_app()

    # ============================================================
    # Перезапуск приложения
    # ============================================================

    def restart_app(self):
        """Перезапускает приложение (для применения настроек)."""
        logger.info("Перезапуск приложения…")

        # Закрываем менеджер загрузок
        try:
            self.download_manager.shutdown(timeout_ms=2000)
        except Exception:
            logger.exception("Ошибка остановки загрузок")

        # Закрываем БД
        try:
            self.db.close()
        except Exception:
            logger.exception("Ошибка закрытия БД")

        # Формируем команду запуска
        if getattr(sys, "frozen", False):
            # Скомпилированный .exe — sys.executable = сам .exe
            args = [sys.executable]
        else:
            # Из исходников — python script.py
            args = [sys.executable] + sys.argv

        logger.info(f"Запуск: {args}")

        try:
            subprocess.Popen(args, close_fds=True)
        except OSError as e:
            logger.error(f"Не удалось перезапустить: {e}")
            QApplication.instance().quit()
            return

        # Жёсткий выход, чтобы не сработал closeEvent дважды
        os._exit(0)

    # ============================================================
    # Вспомогательные
    # ============================================================

    def _make_placeholder(self, text: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(text)
        label.setObjectName("placeholderText")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        return w

    # ============================================================
    # Запуск / завершение
    # ============================================================

    def _start(self):
        if not self.settings.onboarding_completed:
            logger.info("Онбординг не пройден — запускаем онбординг")
            self.show_onboarding()
        else:
            logger.info("Онбординг пройден — запускаем библиотеку")
            self.show_library()

    def closeEvent(self, event):
        logger.info("=" * 60)
        logger.info("closeEvent: начало закрытия приложения")

        try:
            self.download_manager.shutdown(timeout_ms=3000)
        except Exception:
            logger.exception("closeEvent: ошибка shutdown")

        try:
            self.db.close()
            logger.info("closeEvent: БД закрыта")
        except Exception:
            logger.exception("closeEvent: ошибка закрытия БД")

        logger.info("closeEvent: завершение, accept")
        event.accept()