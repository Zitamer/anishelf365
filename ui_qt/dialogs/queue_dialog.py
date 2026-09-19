# -*- coding: utf-8 -*-
"""Окно очереди загрузок."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QProgressBar,
)

from core import i18n


logger = logging.getLogger(__name__)


# ============================================================
# Строка задачи
# ============================================================

class QueueRow(QFrame):
    """Строка задачи: активная (с прогрессом) или ожидающая."""

    def __init__(self, task, active: bool, on_cancel=None):
        super().__init__()
        self.task = task
        self.episode_id = task["episode_id"]
        self.active = active
        self.on_cancel = on_cancel
        self._percent = task.get("percent", 0)
        self._stage = task.get("stage", "video")

        self.setObjectName("queueRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QFrame#queueRow {"
            "  background-color: rgba(60, 60, 60, 0.22);"
            "  border-radius: 6px;"
            "}"
        )
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Название + мета
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title = self.task.get("series_title") or f"ID {self.task.get('series_id')}"
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        title_label.setWordWrap(True)
        info_layout.addWidget(title_label)

        meta_parts = []
        num = self.task.get("episode_number")
        if num is not None:
            try:
                f = float(num)
                n = int(f) if f.is_integer() else num
            except (ValueError, TypeError):
                n = num
            meta_parts.append(i18n.tr("queue.episode", number=n))

        author = (self.task.get("author") or "").strip()
        if author:
            meta_parts.append(author)
        quality = (self.task.get("quality") or "").strip()
        if quality:
            meta_parts.append(quality)

        meta_text = " · ".join(meta_parts) if meta_parts else ""
        self.meta_label = QLabel(meta_text)
        self.meta_label.setStyleSheet("font-size: 11px; color: #a0a0a0;")
        info_layout.addWidget(self.meta_label)

        layout.addLayout(info_layout, 1)

        # Прогресс-бар или метка «в очереди»
        if self.active:
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(self._percent))
            self.progress_bar.setFixedSize(220, 18)
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setStyleSheet(
                "QProgressBar {"
                "  border: 1px solid #444;"
                "  border-radius: 6px;"
                "  background-color: #2a2a2a;"
                "  color: #e0e0e0;"
                "  font-size: 10px;"
                "}"
                "QProgressBar::chunk {"
                "  background-color: #1f6aa5;"
                "  border-radius: 5px;"
                "}"
            )
            layout.addWidget(
                self.progress_bar, 0, Qt.AlignmentFlag.AlignVCenter
            )
        else:
            waiting_label = QLabel(i18n.tr("queue.waiting"))
            waiting_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
            waiting_label.setFixedWidth(220)
            waiting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(waiting_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Кнопка отмены
        cancel_btn = QPushButton("✕")
        cancel_btn.setFixedSize(34, 30)
        cancel_btn.setToolTip(i18n.tr("queue.cancel"))
        cancel_btn.setStyleSheet(
            "QPushButton {"
            "  font-size: 13px; font-weight: bold;"
            "  background-color: #3a3a3a; color: #e0e0e0;"
            "  border: none; border-radius: 6px;"
            "}"
            "QPushButton:hover { background-color: #a04040; }"
            "QPushButton:pressed { background-color: #8a3030; }"
        )
        if self.on_cancel:
            cancel_btn.clicked.connect(
                lambda: self.on_cancel(self.episode_id)
            )
        layout.addWidget(cancel_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_progress(self, stage: str, percent: int):
        self._stage = stage
        self._percent = percent
        if self.active and hasattr(self, "progress_bar"):
            self.progress_bar.setValue(int(percent))


# ============================================================
# Диалог
# ============================================================

class QueueDialog(QDialog):
    """Окно очереди загрузок."""

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self._rows = {}   # episode_id -> QueueRow

        self._build_ui()

        try:
            manager.queue_changed.connect(self.refresh)
            manager.progress.connect(self._on_progress)
        except Exception:
            logger.exception("Не удалось подписаться на сигналы менеджера")

        self.refresh()

    def _build_ui(self):
        self.setWindowTitle(i18n.tr("queue.title"))
        self.setModal(True)
        self.resize(720, 480)
        self.setMinimumSize(560, 380)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel(i18n.tr("queue.title"))
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

        btns = QHBoxLayout()
        btns.addStretch()
        close_btn = QPushButton(i18n.tr("queue.close"))
        close_btn.setObjectName("secondary")
        close_btn.setFixedWidth(160)
        close_btn.setFixedHeight(40)
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        root.addLayout(btns)

    def refresh(self):
        """Полностью перестроить список."""
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._rows = {}

        active = self.manager.get_active_task()
        pending = self.manager.get_pending()

        if active is None and not pending:
            empty = QLabel(i18n.tr("queue.empty"))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                "color: #888888; font-size: 13px; padding: 60px;"
            )
            self.list_layout.addWidget(empty)
            return

        if active is not None:
            row = QueueRow(active, active=True, on_cancel=self._on_cancel)
            self.list_layout.addWidget(row)
            self._rows[active["episode_id"]] = row

        for task in pending:
            row = QueueRow(task, active=False, on_cancel=self._on_cancel)
            self.list_layout.addWidget(row)
            self._rows[task["episode_id"]] = row

    def _on_progress(self, episode_id, stage, percent):
        row = self._rows.get(episode_id)
        if row is not None and row.active:
            row.set_progress(stage, percent)

    def _on_cancel(self, episode_id):
        active = self.manager.get_active_task()
        is_active = active is not None and active["episode_id"] == episode_id

        if is_active:
            from ui_qt.dialogs.delete_dialog import ask_yes_no
            if not ask_yes_no(
                self,
                i18n.tr("queue.cancel_active_confirm_title"),
                i18n.tr("queue.cancel_active_confirm_text"),
            ):
                return

        ok = self.manager.cancel(episode_id)
        if ok:
            # Для ожидающей задачи manager уже эмитит queue_changed → refresh.
            # Для активной поток завершится асинхронно и queue_changed придёт
            # позже. На случай задержки — refresh сразу, чтобы визуально
            # кнопка отреагировала.
            self.refresh()