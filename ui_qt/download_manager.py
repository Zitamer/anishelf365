# -*- coding: utf-8 -*-
"""Глобальный менеджер скачиваний с очередью."""

import logging
import time

from PySide6.QtCore import QObject, QThread, Signal

from core.downloader import download_episode, DownloadError, DownloadCancelled


logger = logging.getLogger(__name__)


class DownloadThread(QThread):
    progress = Signal(int, str, int)
    finished_ok = Signal(int)
    failed = Signal(int, str)

    def __init__(self, api, db, library_path, series_id, episode_id,
                 episode_number, translation_id, quality, author,
                 translation_type, translation_lang, parent=None):
        super().__init__(parent)
        self.api = api
        self.db = db
        self.library_path = library_path
        self.series_id = series_id
        self.episode_id = episode_id
        self.episode_number = episode_number
        self.translation_id = translation_id
        self.quality = quality
        self.author = author
        self.translation_type = translation_type
        self.translation_lang = translation_lang
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        eid = self.episode_id
        t_start = time.time()
        logger.info(f"[{eid}] Поток стартовал: перевод={self.translation_id}, "
                    f"качество={self.quality}")
        try:
            def on_progress(stage, percent, d, t):
                self.progress.emit(eid, stage, percent)

            result = download_episode(
                api=self.api, db=self.db, library_path=self.library_path,
                series_id=self.series_id, episode_id=self.episode_id,
                episode_number=self.episode_number,
                translation_id=self.translation_id,
                quality_label=self.quality, author=self.author,
                translation_type=self.translation_type,
                translation_lang=self.translation_lang,
                progress_cb=on_progress,
                cancel_check=lambda: self._cancel,
            )
            _, _, size = result
            logger.info(f"[{eid}] Успех за {time.time() - t_start:.1f} с, "
                        f"{size} байт")
            self.finished_ok.emit(eid)
        except DownloadCancelled:
            logger.info(f"[{eid}] Отменено")
            self.failed.emit(eid, "Отменено")
        except DownloadError as e:
            logger.error(f"[{eid}] Ошибка: {e}")
            self.failed.emit(eid, str(e))
        except Exception as e:
            logger.exception(f"[{eid}] Непредвиденная ошибка")
            self.failed.emit(eid, str(e))
        finally:
            logger.info(f"[{eid}] Поток завершён")


class DownloadManager(QObject):
    """Очередь скачиваний — по одному за раз."""

    progress = Signal(int, str, int)
    finished = Signal(int)
    error = Signal(int, str)
    queue_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_thread = None
        self._current_episode_id = None
        self._current_task = None
        self._queue = []
        self._all_threads = []
        self._states = {}

    # ---------- Публичное API ----------

    def is_downloading(self, episode_id: int) -> bool:
        if episode_id == self._current_episode_id:
            return True
        return any(t["episode_id"] == episode_id for t in self._queue)

    def is_active_download(self, episode_id: int) -> bool:
        return episode_id == self._current_episode_id

    def get_state(self, episode_id: int):
        state = self._states.get(episode_id)
        if not state:
            return None
        return state.get("stage", "video"), state.get("percent", 0)

    def get_queue_info(self):
        return self._current_episode_id, len(self._queue)

    def get_active_task(self):
        """
        Информация об активной задаче или None.
        Словарь — копия task + stage/percent из _states.
        """
        if self._current_task is None:
            return None
        info = dict(self._current_task)
        state = self._states.get(self._current_episode_id)
        if state:
            info["stage"] = state.get("stage", "video")
            info["percent"] = state.get("percent", 0)
        else:
            info["stage"] = "video"
            info["percent"] = 0
        return info

    def get_pending(self):
        """Список ожидающих задач (копии)."""
        return [dict(t) for t in self._queue]

    def start(self, api, db, library_path, series_id, episode_id,
              episode_number, translation_id, quality, author,
              translation_type, translation_lang, series_title=None):
        if self.is_downloading(episode_id):
            logger.info(f"[{episode_id}] Уже в очереди/качается")
            return

        task = {
            "api": api, "db": db, "library_path": library_path,
            "series_id": series_id, "series_title": series_title,
            "episode_id": episode_id,
            "episode_number": episode_number,
            "translation_id": translation_id, "quality": quality,
            "author": author,
            "translation_type": translation_type,
            "translation_lang": translation_lang,
        }
        self._queue.append(task)
        self._states[episode_id] = {"stage": "video", "percent": 0}
        logger.info(f"[{episode_id}] Добавлено в очередь "
                    f"(всего в очереди: {len(self._queue)})")
        self.queue_changed.emit()
        self._process_next()

    def cancel(self, episode_id: int) -> bool:
        """
        Отменить задачу — активную или ожидающую.
        Возвращает True, если что-то было отменено.
        """
        # 1. Активная
        if episode_id == self._current_episode_id and self._current_thread:
            try:
                self._current_thread.cancel()
                logger.info(f"[{episode_id}] Запрошена отмена активной задачи")
                return True
            except Exception:
                logger.exception("cancel: ошибка отмены активной задачи")
                return False

        # 2. Ожидающая
        for i, task in enumerate(self._queue):
            if task["episode_id"] == episode_id:
                self._queue.pop(i)
                self._states.pop(episode_id, None)
                logger.info(f"[{episode_id}] Убрано из очереди")
                self.queue_changed.emit()
                return True

        return False

    def shutdown(self, timeout_ms: int = 3000):
        logger.info(f"shutdown: {len(self._all_threads)} потоков, "
                    f"{len(self._queue)} в очереди")
        self._queue.clear()
        self._states.clear()
        if self._current_thread is not None:
            self._current_thread.cancel()
        for thread in list(self._all_threads):
            try:
                if thread.isRunning():
                    thread.wait(timeout_ms)
            except RuntimeError:
                pass
        self._all_threads.clear()
        self._current_thread = None
        self._current_episode_id = None
        self._current_task = None

    # ---------- Внутренние ----------

    def _process_next(self):
        if self._current_thread is not None:
            return
        if not self._queue:
            return

        task = self._queue.pop(0)
        self.queue_changed.emit()

        eid = task["episode_id"]
        logger.info(f"[{eid}] Старт из очереди")

        thread = DownloadThread(
            api=task["api"], db=task["db"],
            library_path=task["library_path"],
            series_id=task["series_id"], episode_id=eid,
            episode_number=task["episode_number"],
            translation_id=task["translation_id"],
            quality=task["quality"], author=task["author"],
            translation_type=task["translation_type"],
            translation_lang=task["translation_lang"],
            parent=self,
        )
        thread.progress.connect(self._on_progress)
        thread.finished_ok.connect(self._on_finished)
        thread.failed.connect(self._on_error)
        thread.finished.connect(lambda t=thread: self._cleanup_thread(t))

        self._current_thread = thread
        self._current_episode_id = eid
        self._current_task = task
        self._all_threads.append(thread)
        thread.start()

    def _on_progress(self, episode_id, stage, percent):
        state = self._states.get(episode_id)
        if state is not None:
            state["stage"] = stage
            state["percent"] = percent
        self.progress.emit(episode_id, stage, percent)

    def _on_finished(self, episode_id):
        logger.info(f"[{episode_id}] Менеджер: finished")
        self._states.pop(episode_id, None)
        self._current_thread = None
        self._current_episode_id = None
        self._current_task = None
        self.finished.emit(episode_id)
        self._process_next()
        self.queue_changed.emit()

    def _on_error(self, episode_id, error):
        logger.info(f"[{episode_id}] Менеджер: error")
        self._states.pop(episode_id, None)
        self._current_thread = None
        self._current_episode_id = None
        self._current_task = None
        self.error.emit(episode_id, error)
        self._process_next()
        self.queue_changed.emit()

    def _cleanup_thread(self, thread):
        if thread in self._all_threads:
            self._all_threads.remove(thread)
        try:
            thread.deleteLater()
        except RuntimeError:
            pass