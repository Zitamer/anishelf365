# -*- coding: utf-8 -*-
"""Тесты окна очереди загрузок."""

import pytest
from PySide6.QtWidgets import QLabel, QProgressBar

from ui_qt.dialogs.queue_dialog import QueueDialog, QueueRow

# Импортируем фейковый поток и подменяем им настоящий на весь модуль.
# Без этого в тестах запускался бы реальный QThread с api=None, что
# приводило к Qt-краху на teardown.
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


class TestQueueDialogEmpty:
    def test_creates_without_error(self, qtbot, download_manager):
        dlg = _make_dialog(qtbot, download_manager)
        assert dlg is not None

    def test_shows_empty_placeholder(self, qtbot, download_manager):
        dlg = _make_dialog(qtbot, download_manager)
        labels = dlg.findChildren(QLabel)
        texts = [l.text().lower() for l in labels]
        assert any("пуст" in t or "empty" in t for t in texts)


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

        row = dlg._rows[100]
        assert row.progress_bar.value() == 55


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