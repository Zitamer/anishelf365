# -*- coding: utf-8 -*-
"""Тесты окна очереди загрузок."""

import pytest
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton

from ui_qt.dialogs.queue_dialog import QueueDialog, QueueRow

# Импортируем фейковый поток и подменяем им настоящий на весь модуль.
from tests.test_ui_download_manager import ControlledThread


@pytest.fixture(autouse=True)
def _patch_download_thread(mocker):
    ControlledThread.instances = []
    mocker.patch(
        "ui_qt.download_manager.DownloadThread",
        ControlledThread,
    )
    yield
    ControlledThread.instances = []


# ============================================================
# Хелперы
# ============================================================

def _start(mgr, episode_id=100, series_id=1, series_title="Test Series",
           episode_number=1, author="Author", quality="1080p"):
    mgr.start(
        api=None, db=None, library_path="/tmp",
        series_id=series_id, episode_id=episode_id,
        series_title=series_title,
        episode_number=episode_number,
        translation_id=1000, quality=quality, author=author,
        translation_type="sub", translation_lang="ru",
    )


def _make_dialog(qtbot, download_manager):
    dlg = QueueDialog(None, download_manager)
    qtbot.addWidget(dlg)
    return dlg


def _pending_ids_from_manager(mgr):
    return [t["episode_id"] for t in mgr.get_pending()]


# ============================================================
# Пустое состояние
# ============================================================

class TestQueueDialogEmpty:
    def test_creates_without_error(self, qtbot, download_manager):
        dlg = _make_dialog(qtbot, download_manager)
        assert dlg is not None

    def test_shows_empty_placeholder(self, qtbot, download_manager):
        dlg = _make_dialog(qtbot, download_manager)
        labels = dlg.findChildren(QLabel)
        texts = [l.text().lower() for l in labels]
        assert any("пуст" in t or "empty" in t for t in texts)


# ============================================================
# Активная задача
# ============================================================

class TestQueueDialogActive:
    def test_active_row_shown(self, qtbot, download_manager):
        _start(download_manager, episode_id=100, series_title="Наруто")
        dlg = _make_dialog(qtbot, download_manager)
        assert 100 in dlg._rows
        assert dlg._rows[100].active is True

    def test_active_has_progress_bar(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        dlg = _make_dialog(qtbot, download_manager)
        row = dlg._rows[100]
        assert row.findChild(QProgressBar) is not None

    def test_active_has_no_move_buttons(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        dlg = _make_dialog(qtbot, download_manager)
        row = dlg._rows[100]
        for btn in row.findChildren(QPushButton):
            assert btn.text() not in ("↑", "↓")

    def test_series_title_shown(self, qtbot, download_manager):
        _start(download_manager, episode_id=100, series_title="Наруто")
        dlg = _make_dialog(qtbot, download_manager)
        labels = dlg._rows[100].findChildren(QLabel)
        texts = [l.text() for l in labels]
        assert "Наруто" in texts

    def test_meta_shows_episode_author_quality(self, qtbot, download_manager):
        _start(download_manager, episode_id=100,
               episode_number=5, author="Sanae", quality="1080p")
        dlg = _make_dialog(qtbot, download_manager)
        labels = dlg._rows[100].findChildren(QLabel)
        texts = [l.text() for l in labels]
        assert any("5" in t for t in texts)
        assert any("Sanae" in t for t in texts)
        assert any("1080p" in t for t in texts)


# ============================================================
# Ожидающие задачи
# ============================================================

class TestQueueDialogPending:
    def test_pending_rows_shown(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        _start(download_manager, episode_id=300)
        dlg = _make_dialog(qtbot, download_manager)
        assert 100 in dlg._rows
        assert 200 in dlg._rows
        assert 300 in dlg._rows
        assert dlg._rows[200].active is False
        assert dlg._rows[300].active is False

    def test_pending_has_no_progress_bar(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        dlg = _make_dialog(qtbot, download_manager)
        assert dlg._rows[200].findChild(QProgressBar) is None

    def test_pending_has_move_buttons(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        dlg = _make_dialog(qtbot, download_manager)
        row = dlg._rows[200]
        texts = [b.text() for b in row.findChildren(QPushButton)]
        assert "↑" in texts
        assert "↓" in texts


# ============================================================
# Перемещение в очереди
# ============================================================

class TestQueueDialogMove:
    def test_move_up(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        _start(download_manager, episode_id=300)
        _make_dialog(qtbot, download_manager)

        assert _pending_ids_from_manager(download_manager) == [200, 300]
        download_manager.move_up(300)
        assert _pending_ids_from_manager(download_manager) == [300, 200]

    def test_move_down(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        _start(download_manager, episode_id=300)
        _make_dialog(qtbot, download_manager)

        download_manager.move_down(200)
        assert _pending_ids_from_manager(download_manager) == [300, 200]

    def test_move_up_at_top_does_nothing(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        _make_dialog(qtbot, download_manager)

        ok = download_manager.move_up(200)
        assert ok is False
        assert _pending_ids_from_manager(download_manager) == [200]

    def test_move_down_at_bottom_does_nothing(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        _make_dialog(qtbot, download_manager)

        ok = download_manager.move_down(200)
        assert ok is False
        assert _pending_ids_from_manager(download_manager) == [200]

    def test_move_to_top(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        _start(download_manager, episode_id=300)
        _start(download_manager, episode_id=400)
        _make_dialog(qtbot, download_manager)

        download_manager.move_to_top(400)
        assert _pending_ids_from_manager(download_manager) == [400, 200, 300]

    def test_move_to_bottom(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        _start(download_manager, episode_id=300)
        _make_dialog(qtbot, download_manager)

        download_manager.move_to_bottom(200)
        assert _pending_ids_from_manager(download_manager) == [300, 200]

    def test_up_btn_style_at_top_is_transparent(self, qtbot, download_manager):
        """
        На верхней границе кнопка ↑ остаётся enabled, но её стиль —
        без фона. Клик — no-op.
        """
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        dlg = _make_dialog(qtbot, download_manager)

        row = dlg._rows[200]
        assert row.up_btn.isEnabled() is True
        assert "transparent" in row.up_btn.styleSheet()

        before = _pending_ids_from_manager(download_manager)
        row.up_btn.click()
        after = _pending_ids_from_manager(download_manager)
        assert before == after

    def test_down_btn_style_at_bottom_is_transparent(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        dlg = _make_dialog(qtbot, download_manager)

        row = dlg._rows[200]
        assert row.down_btn.isEnabled() is True
        assert "transparent" in row.down_btn.styleSheet()

        before = _pending_ids_from_manager(download_manager)
        row.down_btn.click()
        after = _pending_ids_from_manager(download_manager)
        assert before == after

    def test_btn_styles_reflect_position(self, qtbot, download_manager):
        """У средних кнопок — фон, у граничных — прозрачный."""
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        _start(download_manager, episode_id=300)
        dlg = _make_dialog(qtbot, download_manager)

        first = dlg._rows[200]
        assert "transparent" in first.up_btn.styleSheet()
        assert "transparent" not in first.down_btn.styleSheet()

        last = dlg._rows[300]
        assert "transparent" not in last.up_btn.styleSheet()
        assert "transparent" in last.down_btn.styleSheet()

    def test_click_up_button_moves(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        _start(download_manager, episode_id=300)
        dlg = _make_dialog(qtbot, download_manager)

        dlg._rows[300].up_btn.click()
        assert _pending_ids_from_manager(download_manager) == [300, 200]


# ============================================================
# Обновление списка
# ============================================================

class TestQueueDialogRefresh:
    def test_refresh_after_finish(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        dlg = _make_dialog(qtbot, download_manager)
        assert 100 in dlg._rows

        ControlledThread.instances[-1].finish_ok()
        assert 100 not in dlg._rows

    def test_new_task_appears(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        dlg = _make_dialog(qtbot, download_manager)
        assert 200 not in dlg._rows

        _start(download_manager, episode_id=200)
        assert 200 in dlg._rows

    def test_progress_updates_bar(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        dlg = _make_dialog(qtbot, download_manager)

        ControlledThread.instances[-1].progress.emit(100, "video", 55)
        assert dlg._rows[100].progress_bar.value() == 55


# ============================================================
# Отмена
# ============================================================

class TestQueueDialogCancel:
    def test_cancel_pending_removes_row(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        dlg = _make_dialog(qtbot, download_manager)
        assert 200 in dlg._rows

        dlg._on_cancel(200)
        assert 200 not in dlg._rows

    def test_cancel_active_calls_thread_cancel(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        _ = _make_dialog(qtbot, download_manager)
        thread = ControlledThread.instances[-1]

        ok = download_manager.cancel(100)
        assert ok is True
        assert thread.cancel_called is True