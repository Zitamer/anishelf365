# -*- coding: utf-8 -*-
"""Диалоги удаления файлов и тайтлов."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame, QMessageBox,
)

from core import i18n


logger = logging.getLogger(__name__)


# ============================================================
# Вспомогательные функции
# ============================================================

def ask_yes_no(parent, title: str, text: str,
               yes_text: str = None, no_text: str = None) -> bool:
    """
    Модальный вопрос с локализованными кнопками.
    Возвращает True, если пользователь выбрал «Да».
    """
    if yes_text is None:
        yes_text = i18n.tr("common.yes")
    if no_text is None:
        no_text = i18n.tr("common.no")

    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Question)

    yes_btn = box.addButton(yes_text, QMessageBox.ButtonRole.YesRole)
    no_btn = box.addButton(no_text, QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(no_btn)

    box.exec()
    return box.clickedButton() is yes_btn


# ============================================================
# Диалоги удаления
# ============================================================

class DeleteEpisodeDialog(QDialog):
    """Диалог удаления файлов одного эпизода."""

    def __init__(self, parent, episode_number, files: list):
        super().__init__(parent)
        self.files = files
        self.checkboxes = []
        self.result_files = []

        num = episode_number if episode_number is not None else "?"
        self.setWindowTitle(i18n.tr("dialog.delete.title", number=num))
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

        for f in files:
            author = f["author"] or "?"
            quality = f["quality"] or "?"
            size = f["file_size"] or 0
            mb = size / (1024 * 1024)
            label = f"{author}  ·  {quality}  ·  {mb:.1f} МБ"

            cb = QCheckBox(label)
            cb.setProperty("file", dict(f))
            self.checkboxes.append(cb)
            root.addWidget(cb)

        hint = QLabel(i18n.tr("dialog.delete.progress_saved"))
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

        subtitle = QLabel(f"Будет удалено {len(files)} файлов ({mb:.1f} МБ):")
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)

        list_frame = QFrame()
        list_frame.setStyleSheet(
            "background-color: rgba(30, 30, 30, 0.4);"
            "border-radius: 6px;"
        )
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.setSpacing(4)

        for f in files[:10]:
            ep_num = f["episode_number"]
            author = f["author"] or "?"
            quality = f["quality"] or "?"
            try:
                ep_str = f"{int(ep_num):02d}" if ep_num is not None else "?"
            except (ValueError, TypeError):
                ep_str = str(ep_num)
            label = QLabel(f"Серия {ep_str:>3} — {author} · {quality}")
            label.setStyleSheet("font-size: 12px;")
            list_layout.addWidget(label)

        if len(files) > 10:
            more = QLabel(f"…и ещё {len(files) - 10} файлов")
            more.setObjectName("subtitle")
            list_layout.addWidget(more)

        root.addWidget(list_frame)

        hint = QLabel(i18n.tr("dialog.delete.progress_saved"))
        hint.setObjectName("subtitle")
        root.addWidget(hint)

        root.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()

        cancel = QPushButton(i18n.tr("common.cancel"))
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


class DeleteSeriesDialog(QDialog):
    """Диалог удаления тайтла из медиатеки."""

    def __init__(self, parent, series_title: str, series_id: int,
                 files_count: int, total_size: int,
                 already_ignored: bool = False):
        super().__init__(parent)
        self.result_delete_files = False
        self.result_ignore = False
        self.files_count = files_count

        self.setWindowTitle(i18n.tr("series_delete.title"))
        self.setModal(True)
        self.resize(600, 400)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel(i18n.tr("series_delete.question", title=series_title))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setWordWrap(True)
        root.addWidget(title)

        info = QLabel(i18n.tr("series_delete.explain"))
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        root.addWidget(info)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: rgba(120, 120, 120, 0.3);")
        root.addWidget(line)

        self.ignore_cb = None
        self.ignore_hint = None
        self.delete_files_cb = None

        if files_count > 0:
            mb = total_size / (1024 * 1024) if total_size else 0
            if mb >= 1:
                size_text = f"{mb:.1f} МБ"
            else:
                size_text = f"{total_size / 1024:.0f} КБ"

            self.delete_files_cb = QCheckBox(
                i18n.tr("series_delete.delete_files",
                        count=files_count, size=size_text)
            )
            self.delete_files_cb.setChecked(True)
            self.delete_files_cb.stateChanged.connect(self._on_files_cb_changed)
            root.addWidget(self.delete_files_cb)

            folder_hint = QLabel(
                i18n.tr("series_delete.folder_hint", series_id=series_id)
            )
            folder_hint.setWordWrap(True)
            folder_hint.setStyleSheet("font-size: 11px; color: #888888;")
            root.addWidget(folder_hint)

            self.ignore_cb = QCheckBox(i18n.tr("series_delete.ignore_cb"))
            self.ignore_cb.setChecked(False)
            self.ignore_cb.setStyleSheet("font-size: 12px;")
            root.addWidget(self.ignore_cb)

            self.ignore_hint = QLabel(i18n.tr("series_delete.ignore_hint"))
            self.ignore_hint.setWordWrap(True)
            self.ignore_hint.setStyleSheet(
                "font-size: 11px; color: #888888;"
            )
            root.addWidget(self.ignore_hint)

            self.ignore_cb.setVisible(False)
            self.ignore_hint.setVisible(False)

        else:
            empty = QLabel(i18n.tr("series_delete.no_files"))
            empty.setWordWrap(True)
            empty.setStyleSheet("font-size: 11px; color: #888888;")
            root.addWidget(empty)

        root.addStretch()

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch()

        cancel = QPushButton(i18n.tr("common.cancel"))
        cancel.setObjectName("secondary")
        cancel.setFixedWidth(140)
        cancel.setFixedHeight(38)
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)

        delete_btn = QPushButton(i18n.tr("series_delete.confirm_button"))
        delete_btn.setFixedWidth(180)
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

    def _on_files_cb_changed(self, state: int):
        if self.ignore_cb is None or self.ignore_hint is None:
            return

        delete_files = bool(state)

        if delete_files:
            self.ignore_cb.setVisible(False)
            self.ignore_cb.setChecked(False)
            self.ignore_hint.setVisible(False)
        else:
            self.ignore_cb.setVisible(True)
            self.ignore_hint.setVisible(True)

    def _on_accept(self):
        if self.delete_files_cb is not None:
            self.result_delete_files = self.delete_files_cb.isChecked()

        if self.ignore_cb is not None and self.ignore_cb.isVisible():
            self.result_ignore = self.ignore_cb.isChecked()

        self.accept()

    def should_delete_files(self) -> bool:
        return self.result_delete_files

    def should_ignore(self) -> bool:
        return self.result_ignore


class AddToIgnoreDialog(QDialog):
    """Простой диалог подтверждения добавления в игнор."""

    def __init__(self, parent, series_title: str, series_id: int):
        super().__init__(parent)
        self.result = False

        self.setWindowTitle(i18n.tr("ignored.add_title"))
        self.setModal(True)
        self.resize(520, 240)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel(
            f"Добавить «{series_title}» в список игнорирования?"
        )
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setWordWrap(True)
        root.addWidget(title)

        info = QLabel(i18n.tr("ignored.add_confirm_text"))
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        root.addWidget(info)

        root.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()

        cancel = QPushButton(i18n.tr("common.cancel"))
        cancel.setObjectName("secondary")
        cancel.setFixedWidth(140)
        cancel.setFixedHeight(38)
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)

        ok_btn = QPushButton(i18n.tr("ignored.add_button"))
        ok_btn.setFixedWidth(220)
        ok_btn.setFixedHeight(38)
        ok_btn.clicked.connect(self._on_accept)
        btns.addWidget(ok_btn)

        root.addLayout(btns)

    def _on_accept(self):
        self.result = True
        self.accept()

    def confirmed(self) -> bool:
        return self.result