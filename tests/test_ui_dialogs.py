# -*- coding: utf-8 -*-
"""UI-тесты диалогов (pytest-qt)."""

import pytest
from PySide6.QtCore import Qt

from ui_qt.dialogs.delete_dialog import (
    DeleteEpisodeDialog,
    DeleteAllDialog,
    DeleteSeriesDialog,
    AddToIgnoreDialog,
    ask_yes_no,
)


# ============================================================
# DeleteEpisodeDialog
# ============================================================

class TestDeleteEpisodeDialog:
    def test_title(self, qtbot):
        files = [
            {"author": "Sanae", "quality": "1080p", "file_size": 1234567},
            {"author": "Alvakarp", "quality": "720p", "file_size": 800000},
        ]
        dlg = DeleteEpisodeDialog(None, 1, files)
        qtbot.addWidget(dlg)
        assert "1" in dlg.windowTitle()

    def test_default_no_selection(self, qtbot):
        """По умолчанию ничего не выбрано — результат пустой."""
        files = [
            {"author": "Sanae", "quality": "1080p", "file_size": 1000},
        ]
        dlg = DeleteEpisodeDialog(None, 1, files)
        qtbot.addWidget(dlg)
        assert dlg.get_selected_files() == []

    def test_selecting_checkbox(self, qtbot):
        files = [
            {"author": "Sanae", "quality": "1080p", "file_size": 1000},
        ]
        dlg = DeleteEpisodeDialog(None, 1, files)
        qtbot.addWidget(dlg)
        dlg.checkboxes[0].setChecked(True)
        dlg._on_accept()
        assert len(dlg.get_selected_files()) == 1


# ============================================================
# DeleteSeriesDialog
# ============================================================

class TestDeleteSeriesDialog:
    def test_default_files_checked(self, qtbot):
        """По умолчанию чекбокс «удалить файлы» отмечен."""
        dlg = DeleteSeriesDialog(
            None, series_title="Test", series_id=1,
            files_count=3, total_size=1000_000,
        )
        qtbot.addWidget(dlg)
        assert dlg.delete_files_cb.isChecked() is True

    def test_ignore_hidden_when_delete_files(self, qtbot):
        """При удалении файлов чекбокс игнора скрыт."""
        dlg = DeleteSeriesDialog(
            None, series_title="Test", series_id=1,
            files_count=3, total_size=1000_000,
        )
        qtbot.addWidget(dlg)
        # Показываем диалог, иначе isVisible() всегда False у детей.
        dlg.show()
        assert dlg.ignore_cb.isVisible() is False

    def test_ignore_visible_when_not_delete_files(self, qtbot):
        """При снятии галочки «удалить файлы» появляется чекбокс игнора."""
        dlg = DeleteSeriesDialog(
            None, series_title="Test", series_id=1,
            files_count=3, total_size=1000_000,
        )
        qtbot.addWidget(dlg)
        dlg.show()
        dlg.delete_files_cb.setChecked(False)
        assert dlg.ignore_cb.isVisible() is True

    def test_result_no_delete_files(self, qtbot):
        dlg = DeleteSeriesDialog(
            None, series_title="Test", series_id=1,
            files_count=3, total_size=1000_000,
        )
        qtbot.addWidget(dlg)
        dlg.show()
        dlg.delete_files_cb.setChecked(False)
        dlg.ignore_cb.setChecked(True)
        dlg._on_accept()
        assert dlg.should_delete_files() is False
        assert dlg.should_ignore() is True

    def test_no_files_case(self, qtbot):
        """Если файлов нет — чекбоксы не создаются."""
        dlg = DeleteSeriesDialog(
            None, series_title="Test", series_id=1,
            files_count=0, total_size=0,
        )
        qtbot.addWidget(dlg)
        assert dlg.delete_files_cb is None
        assert dlg.ignore_cb is None


# ============================================================
# AddToIgnoreDialog
# ============================================================

class TestAddToIgnoreDialog:
    def test_default_not_confirmed(self, qtbot):
        dlg = AddToIgnoreDialog(None, "Test", 1)
        qtbot.addWidget(dlg)
        assert dlg.confirmed() is False

    def test_confirm(self, qtbot):
        dlg = AddToIgnoreDialog(None, "Test", 1)
        qtbot.addWidget(dlg)
        dlg._on_accept()
        assert dlg.confirmed() is True

# ============================================================
# AddSeriesDialog — активация кнопки
# ============================================================

class TestAddSeriesDialogButtonState:
    def _make(self, qtbot, mock_app_for_ui, tmp_library):
        from ui_qt.dialogs.add_series_dialog import AddSeriesDialog
        dlg = AddSeriesDialog(
            None,
            api=mock_app_for_ui.api,
            db=mock_app_for_ui.db,
            library_path=tmp_library,
        )
        qtbot.addWidget(dlg)
        return dlg

    def test_button_disabled_initially(self, qtbot, mock_app_for_ui, tmp_library):
        dlg = self._make(qtbot, mock_app_for_ui, tmp_library)
        assert dlg.add_btn.isEnabled() is False

    def test_button_enabled_on_url_paste(self, qtbot, mock_app_for_ui, tmp_library):
        dlg = self._make(qtbot, mock_app_for_ui, tmp_library)
        dlg.url_edit.setText(
            "https://smotret-anime.org/catalog/yani-neko-41893"
        )
        assert dlg.id_edit.text() == "41893"
        assert dlg.add_btn.isEnabled() is True

    def test_button_enabled_on_id_only(self, qtbot, mock_app_for_ui, tmp_library):
        dlg = self._make(qtbot, mock_app_for_ui, tmp_library)
        dlg.id_edit.setText("41893")
        assert dlg.add_btn.isEnabled() is True

    def test_button_disabled_on_garbage_id(self, qtbot, mock_app_for_ui, tmp_library):
        dlg = self._make(qtbot, mock_app_for_ui, tmp_library)
        dlg.id_edit.setText("abc")
        assert dlg.add_btn.isEnabled() is False

    def test_button_disabled_on_zero(self, qtbot, mock_app_for_ui, tmp_library):
        dlg = self._make(qtbot, mock_app_for_ui, tmp_library)
        dlg.id_edit.setText("0")
        assert dlg.add_btn.isEnabled() is False