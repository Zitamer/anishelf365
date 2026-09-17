# -*- coding: utf-8 -*-
"""Диалог добавления тайтла по ссылке или ID."""

import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame,
)

from core import i18n
from core.api import Anime365API
from core.covers import get_or_download
from core.url_parser import parse_series_id
from core.scanner import scan_series_files


logger = logging.getLogger(__name__)


# ============================================================
# Фоновый поток загрузки метаданных
# ============================================================

class LoadSeriesWorker(QThread):
    loaded = Signal(dict)          # data
    not_found = Signal(int)        # series_id
    failed = Signal(str)           # error

    def __init__(self, api: Anime365API, series_id: int, parent=None):
        super().__init__(parent)
        self.api = api
        self.series_id = series_id

    def run(self):
        try:
            logger.info(f"Загрузка метаданных тайтла {self.series_id}")
            data = self.api.get_series(self.series_id)
            if data and data.get("id"):
                self.loaded.emit(data)
            else:
                self.not_found.emit(self.series_id)
        except Exception as e:
            logger.exception(f"Ошибка загрузки метаданных {self.series_id}")
            self.failed.emit(str(e))


# ============================================================
# Диалог
# ============================================================

class AddSeriesDialog(QDialog):
    """Окно добавления тайтла в библиотеку."""

    def __init__(self, parent, api: Anime365API, db, library_path: str):
        super().__init__(parent)
        self.api = api
        self.db = db
        self.library_path = library_path

        self.result_series_id = None
        self._worker = None

        self._build_ui()

    # ============================================================
    # Разметка
    # ============================================================

    def _build_ui(self):
        self.setWindowTitle(i18n.tr("add_series.title"))
        self.setModal(True)
        self.resize(620, 420)
        self.setMinimumSize(560, 380)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        # Заголовок
        title = QLabel(i18n.tr("add_series.title"))
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        # ---- Поле: ссылка ----
        url_label = QLabel(i18n.tr("add_series.url_label"))
        url_label.setStyleSheet("font-weight: bold;")
        root.addWidget(url_label)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://smotret-anime.org/catalog/yani-neko-41893"
        )
        self.url_edit.setFixedHeight(38)
        self.url_edit.textChanged.connect(self._on_url_changed)
        root.addWidget(self.url_edit)

        # ---- Поле: ID ----
        id_label = QLabel(i18n.tr("add_series.id_label"))
        id_label.setStyleSheet("font-weight: bold;")
        root.addWidget(id_label)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("41893")
        self.id_edit.setFixedHeight(38)
        self.id_edit.setMaximumWidth(200)
        root.addWidget(self.id_edit, alignment=Qt.AlignmentFlag.AlignLeft)

        # ---- Подсказка ----
        hint_frame = QFrame()
        hint_frame.setObjectName("card")
        hint_frame.setStyleSheet(
            "QFrame#card {"
            "  background-color: rgba(60, 60, 60, 0.25);"
            "  border: 1px solid rgba(120, 120, 120, 0.3);"
            "  border-radius: 8px;"
            "}"
        )
        hint_layout = QVBoxLayout(hint_frame)
        hint_layout.setContentsMargins(14, 12, 14, 12)
        hint_layout.setSpacing(4)

        hint = QLabel(i18n.tr("add_series.hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        hint_layout.addWidget(hint)
        root.addWidget(hint_frame)

        # ---- Статус ----
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 12px;")
        root.addWidget(self.status_label)

        root.addStretch()

        # ---- Кнопки ----
        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch()

        self.cancel_btn = QPushButton(i18n.tr("common.cancel"))
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.setFixedWidth(160)
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.clicked.connect(self.reject)
        btns.addWidget(self.cancel_btn)

        self.add_btn = QPushButton(i18n.tr("add_series.button"))
        self.add_btn.setFixedWidth(240)
        self.add_btn.setFixedHeight(40)
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self._on_add_clicked)
        btns.addWidget(self.add_btn)

        root.addLayout(btns)

    # ============================================================
    # Обработчики
    # ============================================================

    def _on_url_changed(self, text: str):
        """Автоматически парсит ID из ссылки."""
        text = text.strip()
        if not text:
            self.add_btn.setEnabled(bool(self.id_edit.text().strip()))
            return

        sid = parse_series_id(text)
        if sid:
            self.id_edit.setText(str(sid))
            self._set_status("")
        # Если не удалось — не стираем ID (пользователь мог ввести его вручную)

    def _on_add_clicked(self):
        sid_str = self.id_edit.text().strip()
        if not sid_str.isdigit():
            self._set_status(
                i18n.tr("add_series.invalid_url"), error=True
            )
            return

        sid = int(sid_str)

        # Уже в БД?
        existing = self.db.get_series(sid)
        if existing:
            title = existing["title"] or f"ID {sid}"
            answer = QMessageBox.question(
                self,
                i18n.tr("add_series.already_exists"),
                f"«{title}» уже есть в библиотеке.\nОткрыть его?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.result_series_id = sid
                self.accept()
            return

        # Запускаем фоновую загрузку
        self._set_status("Загрузка метаданных…")
        self.add_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        self._worker = LoadSeriesWorker(self.api, sid, parent=self)
        self._worker.loaded.connect(self._on_loaded)
        self._worker.not_found.connect(self._on_not_found)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self):
        self.add_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)

    # ============================================================
    # Результаты загрузки
    # ============================================================

    def _on_loaded(self, data: dict):
        sid = data.get("id")
        logger.info(f"Метаданные получены для {sid}")

        try:
            # 1. Сохраняем сериал
            self.db.upsert_series(data)

            # 2. Эпизоды
            episodes = data.get("episodes") or []
            if episodes:
                self.db.upsert_episodes(episodes)
                logger.info(f"Сохранено эпизодов: {len(episodes)}")

            # 3. Обложка
            poster_url = data.get("posterUrl")
            if poster_url:
                local = get_or_download(sid, poster_url)
                if local:
                    self.db.set_local_poster(sid, local)
                    logger.info(f"Обложка скачана: {local}")

            # 4. Сканирование локальных файлов
            if self.library_path:
                found = scan_series_files(self.db, sid, self.library_path)
                logger.info(f"Найдено локальных файлов: {found}")
        except Exception as e:
            logger.exception(f"Ошибка сохранения {sid}")
            self._set_status(f"Ошибка сохранения: {e}", error=True)
            return

        self.result_series_id = sid
        self.accept()

    def _on_not_found(self, series_id: int):
        logger.warning(f"Тайтл {series_id} не найден")
        self._set_status(
            f"{i18n.tr('add_series.not_found')} (ID: {series_id})",
            error=True,
        )

    def _on_failed(self, error: str):
        logger.error(f"Ошибка загрузки: {error}")
        self._set_status(f"Ошибка: {error}", error=True)

    # ============================================================
    # Вспомогательные
    # ============================================================

    def _set_status(self, text: str, error: bool = False):
        self.status_label.setText(text)
        if error:
            self.status_label.setStyleSheet("font-size: 12px; color: #d97a7a;")
        else:
            self.status_label.setStyleSheet("font-size: 12px; color: #888888;")

    # ============================================================
    # Публичное API
    # ============================================================

    def get_series_id(self):
        return self.result_series_id