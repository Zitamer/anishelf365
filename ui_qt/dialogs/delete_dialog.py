# -*- coding: utf-8 -*-
"""Диалоги удаления файлов."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame, QMessageBox,
)

from core import i18n


logger = logging.getLogger(__name__)


class DeleteEpisodeDialog(QDialog):
    """Диалог удаления файлов одного эпизода."""

    def __init__(self, parent, episode_number, files: list):
        super().__init__(parent)
        self.files = files
        self.checkboxes = []
        self.result_files = []

        num = episode_number if episode_number is not None else "?"
        self.setWindowTitle(f"Удалить файлы серии №{num}")
        self.setModal(True)
        self.resize(520, 320)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel(f"Удалить файлы серии №{num}?")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        root.addWidget(title)

        subtitle = QLabel("Отметьте, что удалить:")
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)

        # Список с чекбоксами (по умолчанию — пустые)
        for f in files:
            author = f["author"] or "?"
            quality = f["quality"] or "?"
            size = f["file_size"] or 0
            mb = size / (1024 * 1024)
            label = f"{author}  ·  {quality}  ·  {mb:.1f} МБ"

            cb = QCheckBox(label)
            cb.setProperty("file", f)
            self.checkboxes.append(cb)
            root.addWidget(cb)

        hint = QLabel("Прогресс просмотра сохранится.")
        hint.setObjectName("subtitle")
        root.addWidget(hint)

        root.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()

        cancel = QPushButton(i18n.tr("dialog.delete.cancel"))
        cancel.setObjectName("secondary")
        cancel.setFixedWidth(140)
        cancel.setFixedHeight(38)
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)

        delete_btn = QPushButton(i18n.tr("dialog.delete.confirm"))
        delete_btn.setFixedWidth(180)
        delete_btn.setFixedHeight(38)
        delete_btn.clicked.connect(self._on_accept)
        btns.addWidget(delete_btn)

        root.addLayout(btns)

    def _on_accept(self):
        self.result_files = [
            cb.property("file") for cb in self.checkboxes if cb.isChecked()
        ]
        if not self.result_files:
            return
        self.accept()

    def get_selected_files(self):
        return self.result_files


class DeleteAllDialog(QDialog):
    """Диалог удаления всех файлов тайтла."""

    def __init__(self, parent, series_title: str, files: list):
        super().__init__(parent)
        self.files = files
        self.result = False

        self.setWindowTitle("Очистить все скачанное")
        self.setModal(True)
        self.resize(600, 420)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel(f"Удалить все файлы «{series_title}»?")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setWordWrap(True)
        root.addWidget(title)

        total_size = sum((f["file_size"] or 0) for f in files)
        mb = total_size / (1024 * 1024)

        subtitle = QLabel(
            f"Будет удалено {len(files)} файлов ({mb:.1f} МБ):"
        )
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)

        # Список файлов
        list_frame = QFrame()
        list_frame.setStyleSheet(
            "background-color: rgba(30, 30, 30, 0.4);"
            "border-radius: 6px;"
        )
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.setSpacing(4)

        # Первые 10 файлов
        for f in files[:10]:
            ep_num = f["episode_number"]
            author = f["author"] or "?"
            quality = f["quality"] or "?"
            ep_str = f"{ep_num:.0f}" if ep_num and ep_num == int(ep_num) else str(ep_num)
            label = QLabel(f"Серия {ep_str:>3} — {author} · {quality}")
            label.setStyleSheet("font-size: 12px;")
            list_layout.addWidget(label)

        if len(files) > 10:
            more = QLabel(f"…и ещё {len(files) - 10} файлов")
            more.setObjectName("subtitle")
            list_layout.addWidget(more)

        root.addWidget(list_frame)

        hint = QLabel("Прогресс просмотра сохранится.")
        hint.setObjectName("subtitle")
        root.addWidget(hint)

        root.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()

        cancel = QPushButton("Отмена")
        cancel.setObjectName("secondary")
        cancel.setFixedWidth(140)
        cancel.setFixedHeight(38)
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)

        delete_btn = QPushButton(f"🗑 Удалить всё ({len(files)})")
        delete_btn.setFixedWidth(220)
        delete_btn.setFixedHeight(38)
        delete_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #a04040;"
            "  color: #ffffff;"
            "  border: none; border-radius: 6px;"
            "}"
            "QPushButton:hover { background-color: #b85050; }"
            "QPushButton:pressed { background-color: #8a3030; }"
        )
        delete_btn.clicked.connect(self._on_accept)
        btns.addWidget(delete_btn)

        root.addLayout(btns)

    def _on_accept(self):
        self.result = True
        self.accept()