# -*- coding: utf-8 -*-
"""Диалог управления списком игнорируемых сериалов."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFrame,
)

from core import i18n


logger = logging.getLogger(__name__)


class IgnoredSeriesDialog(QDialog):
    """Диалог со списком игнорируемых тайтлов."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.changed = False

        self.setWindowTitle(i18n.tr("ignored.list_title"))
        self.setModal(True)
        self.resize(700, 480)
        self.setMinimumSize(600, 400)

        self._build_ui()
        self._reload()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel(i18n.tr("ignored.list_title"))
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        info = QLabel(i18n.tr("ignored.list_hint"))
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        root.addWidget(info)

        self.count_label = QLabel("")
        self.count_label.setObjectName("subtitle")
        root.addWidget(self.count_label)

        list_frame = QFrame()
        list_frame.setStyleSheet(
            "QFrame {"
            "  background-color: rgba(30, 30, 30, 0.4);"
            "  border-radius: 6px;"
            "}"
        )
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(8, 8, 8, 8)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("font-size: 13px;")
        self.list_widget.itemSelectionChanged.connect(
            self._on_selection_changed
        )
        list_layout.addWidget(self.list_widget)
        root.addWidget(list_frame, 1)

        btns = QHBoxLayout()
        btns.setSpacing(10)

        self.remove_btn = QPushButton(i18n.tr("ignored.remove_button"))
        self.remove_btn.setFixedWidth(240)
        self.remove_btn.setFixedHeight(38)
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        btns.addWidget(self.remove_btn)

        btns.addStretch()

        close_btn = QPushButton(i18n.tr("common.close"))
        close_btn.setObjectName("secondary")
        close_btn.setFixedWidth(140)
        close_btn.setFixedHeight(38)
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)

        root.addLayout(btns)

    def _reload(self):
        self.list_widget.clear()

        items = self.db.list_ignored()
        self.count_label.setText(i18n.tr("ignored.count", count=len(items)))

        if not items:
            placeholder = QListWidgetItem(i18n.tr("ignored.empty"))
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(Qt.GlobalColor.gray)
            self.list_widget.addItem(placeholder)
            self.remove_btn.setEnabled(False)
            return

        for row in items:
            sid = row["series_id"]
            title = row["title"] or f"ID {sid}"
            reason = row["reason"] or ""
            added = row["added_at"] or ""

            text = f"{title}  (ID: {sid})"
            if reason:
                text += "\n   " + i18n.tr("ignored.reason_label", reason=reason)
            if added:
                text += "\n   " + i18n.tr("ignored.added_label", date=added)

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, sid)
            self.list_widget.addItem(item)

    def _on_selection_changed(self):
        has_selection = len(self.list_widget.selectedItems()) > 0
        if has_selection:
            item = self.list_widget.selectedItems()[0]
            sid = item.data(Qt.ItemDataRole.UserRole)
            self.remove_btn.setEnabled(sid is not None)
        else:
            self.remove_btn.setEnabled(False)

    def _on_remove_clicked(self):
        selected = self.list_widget.selectedItems()
        if not selected:
            return

        item = selected[0]
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid is None:
            return

        row = self.db.get_series(sid)
        title = row["title"] if row else f"ID {sid}"

        from ui_qt.dialogs.delete_dialog import ask_yes_no
        if not ask_yes_no(
            self,
            i18n.tr("ignored.remove_confirm_title"),
            i18n.tr("ignored.confirm_text", title=title),
        ):
            return

        self.db.remove_ignored(sid)
        logger.info(f"Тайтл {sid} убран из игнора")
        self.changed = True
        self._reload()