# -*- coding: utf-8 -*-
"""Smoke-тесты UI: базовые проверки, что виджеты создаются."""

import pytest
from PySide6.QtWidgets import QApplication


class TestUIApp:
    """Проверяем, что модули UI импортируются и основные виджеты создаются."""

    def test_import_library_view(self):
        from ui_qt.library_view import LibraryView
        assert LibraryView is not None

    def test_import_series_view(self):
        from ui_qt.series_view import SeriesView
        assert SeriesView is not None

    def test_import_settings_dialog(self):
        from ui_qt.settings_dialog import SettingsDialog
        assert SettingsDialog is not None

    def test_import_onboarding(self):
        from ui_qt.onboarding import OnboardingWindow
        assert OnboardingWindow is not None

    def test_import_download_manager(self):
        from ui_qt.download_manager import DownloadManager
        assert DownloadManager is not None

    def test_download_manager_init(self, qtbot, db, mock_api):
        from ui_qt.download_manager import DownloadManager
        # DownloadManager — QObject, не QWidget, поэтому addWidget не нужен.
        manager = DownloadManager()
        assert manager.get_queue_info() == (None, 0)
        assert manager.is_downloading(380000) is False