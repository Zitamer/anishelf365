# -*- coding: utf-8 -*-
"""Диалог выбора перевода и качества для скачивания."""

import logging

from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QRadioButton, QButtonGroup, QScrollArea, QWidget,
)

from core import i18n
from core.api import Anime365API, extract_video_urls


logger = logging.getLogger(__name__)


def format_episode_number(num) -> str:
    if num is None:
        return "?"
    try:
        f = float(num)
        if f.is_integer():
            return f"{int(f):02d}"
        return f"{f:g}"
    except (ValueError, TypeError):
        return str(num)


class LoadWorker(QObject):
    translations_loaded = Signal(list)
    qualities_loaded = Signal(dict)
    error = Signal(str)

    def __init__(self, api: Anime365API):
        super().__init__()
        self.api = api

    def load_translations(self, episode_id: int):
        try:
            trs = self.api.get_translations(episode_id)
            trs = [t for t in trs if t.get("isActive", 1)]
            self.translations_loaded.emit(trs)
        except Exception as e:
            self.error.emit(str(e))

    def load_qualities(self, translation_id: int):
        try:
            embed = self.api.get_embed(translation_id)
            if not embed:
                self.qualities_loaded.emit({})
                return
            urls = extract_video_urls(embed)
            self.qualities_loaded.emit(urls)
        except Exception as e:
            self.error.emit(str(e))


class DownloadDialog(QDialog):
    """Окно выбора перевода и качества."""

    def __init__(self, parent, api: Anime365API, episode_id: int,
                 episode_number=None, preferred_lang=None,
                 preferred_type=None):
        super().__init__(parent)
        self.api = api
        self.episode_id = episode_id
        self.episode_number = episode_number
        self.preferred_lang = preferred_lang
        self.preferred_type = preferred_type

        self.translations = []
        self.qualities = {}
        self.selected_translation = None
        self.selected_quality = None

        self.result_data = None

        self._worker_thread = None
        self._q_thread = None

        self._build_ui()

        # Отложенный старт загрузки, чтобы UI успел отрисоваться
        QTimer.singleShot(50, self._start_load_translations)

    def _build_ui(self):
        num = format_episode_number(self.episode_number)
        self.setWindowTitle(f"Скачать серию №{num}")
        self.setModal(True)
        self.resize(760, 560)
        self.setMinimumSize(700, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(15)

        title = QLabel(i18n.tr("dialog.download.title", number=num))
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        filter_parts = []
        if self.preferred_type:
            filter_parts.append(f"тип: {self.preferred_type}")
        if self.preferred_lang:
            filter_parts.append(f"язык: {self.preferred_lang}")
        if filter_parts:
            filter_info = QLabel("Фильтр: " + ", ".join(filter_parts))
            filter_info.setObjectName("subtitle")
            root.addWidget(filter_info)

        columns = QHBoxLayout()
        columns.setSpacing(15)

        # Левая — переводы
        left = QVBoxLayout()
        left.setSpacing(8)

        lbl_tr = QLabel(i18n.tr("dialog.download.translation"))
        lbl_tr.setStyleSheet("font-weight: bold;")
        left.addWidget(lbl_tr)

        self.tr_scroll = QScrollArea()
        self.tr_scroll.setWidgetResizable(True)
        self.tr_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tr_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.tr_container = QWidget()
        self.tr_layout = QVBoxLayout(self.tr_container)
        self.tr_layout.setContentsMargins(0, 0, 0, 0)
        self.tr_layout.setSpacing(4)
        self.tr_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tr_scroll.setWidget(self.tr_container)

        self.tr_group = QButtonGroup(self)
        left.addWidget(self.tr_scroll, 1)

        self.tr_status = QLabel("Загрузка переводов…")
        self.tr_status.setObjectName("subtitle")
        self.tr_status.setWordWrap(True)
        left.addWidget(self.tr_status)

        left_widget = QWidget()
        left_widget.setLayout(left)
        columns.addWidget(left_widget, 1)

        # Правая — качества
        right = QVBoxLayout()
        right.setSpacing(8)

        lbl_q = QLabel(i18n.tr("dialog.download.quality"))
        lbl_q.setStyleSheet("font-weight: bold;")
        right.addWidget(lbl_q)

        self.q_scroll = QScrollArea()
        self.q_scroll.setWidgetResizable(True)
        self.q_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.q_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.q_container = QWidget()
        self.q_layout = QVBoxLayout(self.q_container)
        self.q_layout.setContentsMargins(0, 0, 0, 0)
        self.q_layout.setSpacing(4)
        self.q_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.q_scroll.setWidget(self.q_container)

        self.q_group = QButtonGroup(self)
        right.addWidget(self.q_scroll, 1)

        self.q_status = QLabel("Сначала выберите перевод")
        self.q_status.setObjectName("subtitle")
        right.addWidget(self.q_status)

        right_widget = QWidget()
        right_widget.setLayout(right)
        columns.addWidget(right_widget, 1)

        root.addLayout(columns, 1)

        btns = QHBoxLayout()
        btns.addStretch()

        self.cancel_btn = QPushButton(i18n.tr("dialog.download.cancel"))
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.setFixedWidth(160)
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.clicked.connect(self.reject)
        btns.addWidget(self.cancel_btn)

        self.download_btn = QPushButton(i18n.tr("dialog.download.start"))
        self.download_btn.setFixedWidth(200)
        self.download_btn.setFixedHeight(40)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._on_accept)
        btns.addWidget(self.download_btn)

        root.addLayout(btns)

    # ============================================================
    # Загрузка переводов
    # ============================================================

    def _start_load_translations(self):
        self._worker_thread = QThread()
        self._worker = LoadWorker(self.api)
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(
            lambda: self._worker.load_translations(self.episode_id)
        )
        self._worker.translations_loaded.connect(self._on_translations_loaded)
        self._worker.error.connect(self._on_load_error)

        self._worker_thread.start()

    def _on_translations_loaded(self, translations: list):
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None

        self.translations = translations
        total_all = len(translations)

        if not translations:
            self.tr_status.setText("Переводы не найдены")
            return

        filtered = []
        for tr in translations:
            tr_kind = (tr.get("typeKind") or "").lower()
            tr_lang = (tr.get("typeLang") or "").lower()
            if self.preferred_type and tr_kind != self.preferred_type:
                continue
            if self.preferred_lang and tr_lang != self.preferred_lang:
                continue
            filtered.append(tr)

        fallback_used = False
        if not filtered:
            filtered = translations
            fallback_used = True

        def sort_key(tr):
            tr_lang = (tr.get("typeLang") or "").lower()
            tr_kind = (tr.get("typeKind") or "").lower()
            lang_priority = 0 if (self.preferred_lang
                                   and tr_lang == self.preferred_lang) else 1
            kind_priority = {"sub": 0, "voice": 1, "raw": 2}.get(tr_kind, 3)
            api_priority = -(tr.get("priority") or 0)
            return (lang_priority, kind_priority, api_priority)

        filtered.sort(key=sort_key)

        if fallback_used:
            self.tr_status.setText(
                f"Нет переводов с типом «{self.preferred_type}» и языком "
                f"«{self.preferred_lang}». Показаны все ({total_all})."
            )
        else:
            self.tr_status.setText(f"Найдено: {len(filtered)} из {total_all}")

        for tr in filtered:
            tr_id = tr.get("id")
            tr_lang = (tr.get("typeLang") or "").lower()
            author = (tr.get("authorsSummary")
                      or (tr.get("authorsList") or ["?"])[0]
                      or "?")
            tr_kind = (tr.get("typeKind") or "").lower()

            kind_label = {"sub": "Sub", "voice": "Voice",
                          "raw": "Raw"}.get(tr_kind, tr.get("type") or "?")
            lang_display = tr_lang.upper() if tr_lang else ""

            text = f"{author}  ·  {kind_label}"
            if lang_display:
                text += f" [{lang_display}]"

            rb = QRadioButton(text)
            rb.setProperty("translation_id", tr_id)
            rb.setProperty("translation_type", tr_kind or "sub")
            rb.setProperty("author", author)
            self.tr_group.addButton(rb)
            self.tr_layout.addWidget(rb)

            rb.toggled.connect(
                lambda checked, btn=rb: self._on_translation_selected(btn)
                if checked else None
            )

        buttons = self.tr_group.buttons()
        if buttons:
            buttons[0].setChecked(True)

    def _on_translation_selected(self, rb: QRadioButton):
        self.selected_translation = {
            "id": rb.property("translation_id"),
            "type": rb.property("translation_type"),
            "author": rb.property("author"),
        }
        self.selected_quality = None
        self.download_btn.setEnabled(False)

        self._clear_qualities()
        self.q_status.setText("Загрузка качеств…")
        self._start_load_qualities(rb.property("translation_id"))

    # ============================================================
    # Загрузка качеств
    # ============================================================

    def _start_load_qualities(self, translation_id: int):
        self._q_thread = QThread()
        self._q_worker = LoadWorker(self.api)
        self._q_worker.moveToThread(self._q_thread)

        self._q_thread.started.connect(
            lambda: self._q_worker.load_qualities(translation_id)
        )
        self._q_worker.qualities_loaded.connect(self._on_qualities_loaded)
        self._q_worker.error.connect(self._on_load_error)

        self._q_thread.start()

    def _on_qualities_loaded(self, urls: dict):
        if self._q_thread is not None:
            self._q_thread.quit()
            self._q_thread.wait()
            self._q_thread = None

        self.qualities = urls

        if not urls:
            self.q_status.setText("Не удалось получить качества")
            return

        def quality_key(label):
            digits = "".join(ch for ch in label if ch.isdigit())
            return int(digits) if digits else 0

        sorted_quals = sorted(urls.keys(), key=quality_key, reverse=True)

        self.q_status.setText(f"Доступно: {len(sorted_quals)}")

        for q in sorted_quals:
            rb = QRadioButton(q)
            rb.setProperty("quality_label", q)
            self.q_group.addButton(rb)
            self.q_layout.addWidget(rb)
            rb.toggled.connect(
                lambda checked, b=rb: self._on_quality_selected(b)
                if checked else None
            )

        if self.q_group.buttons():
            self.q_group.buttons()[0].setChecked(True)

    def _on_quality_selected(self, rb: QRadioButton):
        self.selected_quality = rb.property("quality_label")
        if self.selected_translation and self.selected_quality:
            self.download_btn.setEnabled(True)

    # ============================================================
    # Очистка / ошибки
    # ============================================================

    def _clear_qualities(self):
        for btn in list(self.q_group.buttons()):
            self.q_group.removeButton(btn)
            btn.deleteLater()

        while self.q_layout.count():
            item = self.q_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.qualities = {}
        self.selected_quality = None

    def _on_load_error(self, error: str):
        logger.error(f"Ошибка загрузки: {error}")
        self.tr_status.setText(f"Ошибка: {error}")
        self.q_status.setText("")

    # ============================================================
    # Подтверждение / закрытие
    # ============================================================

    def _on_accept(self):
        if not self.selected_translation or not self.selected_quality:
            return
        self.result_data = {
            "translation_id": self.selected_translation["id"],
            "translation_type": self.selected_translation["type"] or "sub",
            "author": self.selected_translation["author"],
            "quality": self.selected_quality,
        }
        self.accept()

    def get_result(self) -> dict:
        return self.result_data or {}

    def closeEvent(self, event):
        # Останавливаем все активные потоки
        for thread in (self._worker_thread, self._q_thread):
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait(1000)
        self._worker_thread = None
        self._q_thread = None
        super().closeEvent(event)