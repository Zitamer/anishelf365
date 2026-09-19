# -*- coding: utf-8 -*-
"""
Тесты менеджера загрузок.

Стратегия: полностью подменяем DownloadThread на синхронный фейк.
Реальные потоки не запускаются — это делает тесты детерминированными
и защищает от Qt-краха "QThread: Destroyed while running".
"""

import pytest
from PySide6.QtCore import QObject, Signal

from ui_qt.download_manager import DownloadManager


# ============================================================
# Фейковый поток
# ============================================================

class ControlledThread(QObject):
    """
    Замена DownloadThread в тестах.

    start() ничего не делает — тест сам решает, когда «завершить»
    задачу, через finish_ok() или fail(). Сигналы идентичны
    реальному DownloadThread.
    """

    progress = Signal(int, str, int)
    finished_ok = Signal(int)
    failed = Signal(int, str)
    finished = Signal()

    instances: list = []

    def __init__(self, api=None, db=None, library_path=None,
                 series_id=None, episode_id=None, episode_number=None,
                 translation_id=None, quality=None, author=None,
                 translation_type=None, translation_lang=None,
                 parent=None):
        super().__init__(parent)
        self.episode_id = episode_id
        ControlledThread.instances.append(self)

    def start(self):
        pass

    def finish_ok(self):
        self.finished_ok.emit(self.episode_id)
        self.finished.emit()

    def fail(self, msg: str = "boom"):
        self.failed.emit(self.episode_id, msg)
        self.finished.emit()

    def cancel(self):
        pass

    def isRunning(self):
        return False

    def wait(self, ms: int = 0):
        return True

    def deleteLater(self):
        # No-op. Менеджер зовёт deleteLater() из _cleanup_thread, но наш
        # фейк уже имеет parent'а (manager), и Qt сам удалит его при
        # разрушении родителя. Отложенный deleteLater привёл бы к
        # двойному delete C++-объекта и abort'у в следующем тесте.
        pass


@pytest.fixture(autouse=True)
def _patch_download_thread(mocker):
    """Меняем реальный поток на фейк и очищаем instances между тестами."""
    ControlledThread.instances = []
    mocker.patch(
        "ui_qt.download_manager.DownloadThread",
        ControlledThread,
    )
    yield
    ControlledThread.instances = []


# ============================================================
# Вспомогательные
# ============================================================

def _start(mgr, episode_id=100, series_id=1):
    mgr.start(
        api=None, db=None, library_path="/tmp",
        series_id=series_id, episode_id=episode_id,
        episode_number=1, translation_id=1000,
        quality="1080p", author="Test",
        translation_type="sub", translation_lang="ru",
    )


# ============================================================
# Начальное состояние
# ============================================================

class TestInitialState:
    def test_is_qobject(self, download_manager):
        assert isinstance(download_manager, QObject)

    def test_queue_empty(self, download_manager):
        assert download_manager.get_queue_info() == (None, 0)

    def test_nothing_downloading(self, download_manager):
        assert download_manager.is_downloading(1) is False
        assert download_manager.is_active_download(1) is False

    def test_no_state(self, download_manager):
        assert download_manager.get_state(1) is None


# ============================================================
# Добавление задач
# ============================================================

class TestStartTask:
    def test_start_emits_queue_changed(self, qtbot, download_manager):
        with qtbot.waitSignal(download_manager.queue_changed, timeout=1000):
            _start(download_manager, episode_id=100)

    def test_episode_becomes_active(self, download_manager):
        _start(download_manager, episode_id=100)
        active, queued = download_manager.get_queue_info()
        assert active == 100
        assert queued == 0

    def test_is_downloading_true_after_start(self, download_manager):
        _start(download_manager, episode_id=100)
        assert download_manager.is_downloading(100) is True

    def test_is_active_after_start(self, download_manager):
        _start(download_manager, episode_id=100)
        assert download_manager.is_active_download(100) is True

    def test_duplicate_start_ignored(self, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=100)
        active, queued = download_manager.get_queue_info()
        assert active == 100
        assert queued == 0

    def test_second_episode_goes_to_queue(self, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        active, queued = download_manager.get_queue_info()
        assert active == 100
        assert queued == 1
        assert download_manager.is_downloading(200) is True

    def test_queue_fifo_order(self, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        _start(download_manager, episode_id=300)
        assert download_manager.get_queue_info() == (100, 2)

        # Завершаем первый — стартует второй
        ControlledThread.instances[-1].finish_ok()
        assert download_manager.get_queue_info() == (200, 1)

        # Завершаем второй — стартует третий
        ControlledThread.instances[-1].finish_ok()
        assert download_manager.get_queue_info() == (300, 0)


# ============================================================
# Завершение задачи
# ============================================================

class TestFinish:
    def test_finished_emitted(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        thread = ControlledThread.instances[-1]
        with qtbot.waitSignal(download_manager.finished, timeout=1000):
            thread.finish_ok()

    def test_queue_empty_after_finish(self, download_manager):
        _start(download_manager, episode_id=100)
        ControlledThread.instances[-1].finish_ok()
        assert download_manager.get_queue_info() == (None, 0)
        assert download_manager.is_downloading(100) is False

    def test_error_emitted_on_failure(self, qtbot, download_manager):
        _start(download_manager, episode_id=100)
        thread = ControlledThread.instances[-1]
        with qtbot.waitSignal(download_manager.error, timeout=1000):
            thread.fail("boom")

    def test_queue_empty_after_error(self, download_manager):
        _start(download_manager, episode_id=100)
        ControlledThread.instances[-1].fail("boom")
        assert download_manager.get_queue_info() == (None, 0)

    def test_progress_state_saved(self, download_manager):
        _start(download_manager, episode_id=100)
        thread = ControlledThread.instances[-1]
        thread.progress.emit(100, "video", 42)
        state = download_manager.get_state(100)
        assert state == ("video", 42)


# ============================================================
# Shutdown
# ============================================================

class TestShutdown:
    def test_shutdown_clears_queue(self, download_manager):
        _start(download_manager, episode_id=100)
        _start(download_manager, episode_id=200)
        download_manager.shutdown(timeout_ms=100)
        assert download_manager.get_queue_info() == (None, 0)

    def test_shutdown_idempotent(self, download_manager):
        download_manager.shutdown(timeout_ms=100)
        download_manager.shutdown(timeout_ms=100)
        assert download_manager.get_queue_info() == (None, 0)

    def test_shutdown_when_empty(self, download_manager):
        download_manager.shutdown(timeout_ms=100)
        assert download_manager.get_queue_info() == (None, 0)