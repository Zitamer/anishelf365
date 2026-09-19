# -*- coding: utf-8 -*-
"""Окно очереди загрузок."""

import logging

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QProgressBar, QMenu,
)

from core import i18n


logger = logging.getLogger(__name__)


# ============================================================
# Геометрия строки
# ============================================================

ROW_HEIGHT = 96
ROW_SPACING = 8
ANIM_DURATION = 320  # мс — «переезд» одной строки


# ============================================================
# Стили
# ============================================================

ROW_BASE_STYLE = (
    "QFrame#queueRow {"
    "  background-color: rgba(60, 60, 60, 0.22);"
    "  border-radius: 6px;"
    "}"
)

NAV_BTN_ACTIVE = (
    "QPushButton {"
    "  font-size: 13px; font-weight: bold;"
    "  background-color: #3a3a3a; color: #e0e0e0;"
    "  border: 1px solid #4a4a4a;"
    "  border-radius: 6px;"
    "}"
    "QPushButton:hover {"
    "  background-color: #4a4a4a;"
    "  border-color: #5a5a5a;"
    "}"
    "QPushButton:pressed {"
    "  background-color: #2a2a2a;"
    "}"
)

NAV_BTN_BORDER = (
    "QPushButton, QPushButton:hover, QPushButton:pressed {"
    "  font-size: 13px; font-weight: bold;"
    "  background-color: transparent;"
    "  color: #606060;"
    "  border: none;"
    "  border-radius: 6px;"
    "}"
)


# ============================================================
# Строка задачи
# ============================================================

class QueueRow(QFrame):
    """Строка задачи: активная (с прогрессом) или ожидающая."""

    def __init__(self, task, active: bool, index: int = 0, total: int = 1,
                 on_cancel=None, on_move=None):
        super().__init__()
        self.task = task
        self.episode_id = task["episode_id"]
        self.active = active
        self.index = index
        self.total = total
        self.on_cancel = on_cancel
        self.on_move = on_move
        self._percent = task.get("percent", 0)
        self._stage = task.get("stage", "video")

        self.setObjectName("queueRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(ROW_BASE_STYLE)
        # Фиксируем высоту: она нужна для расчёта позиций.
        # Ширину устанавливает контейнер (см. QueueContainer._relayout).
        self.setFixedHeight(ROW_HEIGHT)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # --- Название + мета ---
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title = self.task.get("series_title") or f"ID {self.task.get('series_id')}"
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(54)   # ~3 строки
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

        # --- Прогресс-бар или метка «в очереди» ---
        if self.active:
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(self._percent))
            self.progress_bar.setFixedSize(200, 18)
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
            waiting_label.setFixedWidth(200)
            waiting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(waiting_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # --- Стрелки ↑ / ↓ ---
        if not self.active:
            at_top = self.index == 0
            at_bottom = self.index >= self.total - 1

            self.up_btn = QPushButton("↑")
            self.up_btn.setFixedSize(30, 28)
            self.up_btn.setStyleSheet(
                NAV_BTN_BORDER if at_top else NAV_BTN_ACTIVE
            )
            self.up_btn.clicked.connect(self._on_up_clicked)
            layout.addWidget(self.up_btn, 0, Qt.AlignmentFlag.AlignVCenter)

            self.down_btn = QPushButton("↓")
            self.down_btn.setFixedSize(30, 28)
            self.down_btn.setStyleSheet(
                NAV_BTN_BORDER if at_bottom else NAV_BTN_ACTIVE
            )
            self.down_btn.clicked.connect(self._on_down_clicked)
            layout.addWidget(self.down_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # --- Кнопка отмены ---
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

    # ---------- Клики по стрелкам ----------

    def _on_up_clicked(self):
        if self.index == 0:
            return
        if self.on_move:
            self.on_move(self.episode_id, "up")

    def _on_down_clicked(self):
        if self.index >= self.total - 1:
            return
        if self.on_move:
            self.on_move(self.episode_id, "down")

    # ---------- Прогресс ----------

    def set_progress(self, stage: str, percent: int):
        self._stage = stage
        self._percent = percent
        if self.active and hasattr(self, "progress_bar"):
            self.progress_bar.setValue(int(percent))

    # ---------- Контекстное меню ----------

    def contextMenuEvent(self, event):
        if self.on_move is None and self.on_cancel is None:
            super().contextMenuEvent(event)
            return

        menu = QMenu(self)

        if not self.active and self.on_move:
            at_top = self.index == 0
            at_bottom = self.index >= self.total - 1

            act_top = QAction("⏫ " + i18n.tr("queue.move_top"), self)
            act_top.setEnabled(not at_top)
            act_top.triggered.connect(
                lambda: self.on_move(self.episode_id, "top")
            )
            menu.addAction(act_top)

            act_up = QAction("↑ " + i18n.tr("queue.move_up"), self)
            act_up.setEnabled(not at_top)
            act_up.triggered.connect(
                lambda: self.on_move(self.episode_id, "up")
            )
            menu.addAction(act_up)

            act_down = QAction("↓ " + i18n.tr("queue.move_down"), self)
            act_down.setEnabled(not at_bottom)
            act_down.triggered.connect(
                lambda: self.on_move(self.episode_id, "down")
            )
            menu.addAction(act_down)

            act_bottom = QAction("⏬ " + i18n.tr("queue.move_bottom"), self)
            act_bottom.setEnabled(not at_bottom)
            act_bottom.triggered.connect(
                lambda: self.on_move(self.episode_id, "bottom")
            )
            menu.addAction(act_bottom)

            menu.addSeparator()

        if self.on_cancel:
            act_cancel = QAction("✕ " + i18n.tr("queue.cancel"), self)
            act_cancel.triggered.connect(
                lambda: self.on_cancel(self.episode_id)
            )
            menu.addAction(act_cancel)

        if menu.isEmpty():
            super().contextMenuEvent(event)
            return

        menu.exec(event.globalPos())
        event.accept()


# ============================================================
# Контейнер с ручным размещением строк (без layout)
# ============================================================

class QueueContainer(QWidget):
    """
    Контейнер для строк очереди.

    Управляет позициями и шириной строк вручную через setGeometry —
    так можно анимировать переезд через QPropertyAnimation. Обычный
    QVBoxLayout этого не даёт: он сам пересчитывает позиции мгновенно.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._anims = []
        self._placeholder = None

    def set_rows(self, rows, old_positions=None):
        """
        Установить новый список строк.

        rows — новые QueueRow в нужном порядке.
        old_positions — dict ep_id -> старый Y (для анимации).
        """
        self._clear_placeholder()

        new_ids = {r.episode_id for r in rows}
        for old in self._rows:
            if old.episode_id not in new_ids:
                old.setParent(None)
                old.deleteLater()

        for row in rows:
            if row.parent() is not self:
                row.setParent(self)
                row.show()

        self._rows = rows
        self._relayout(old_positions)

    def show_placeholder(self, text: str):
        """Показать заглушку «Очередь пуста» вместо списка."""
        for old in self._rows:
            old.setParent(None)
            old.deleteLater()
        self._rows = []

        self._clear_placeholder()

        lbl = QLabel(text, self)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            "color: #888888; font-size: 13px; padding: 40px;"
        )
        w = max(200, self.width())
        lbl.setGeometry(0, 0, w, 200)
        lbl.show()
        self._placeholder = lbl

        self.setMinimumHeight(200)

    def _clear_placeholder(self):
        if self._placeholder is not None:
            try:
                self._placeholder.setParent(None)
                self._placeholder.deleteLater()
            except RuntimeError:
                pass
            self._placeholder = None

    def _relayout(self, old_positions=None):
        width = self.width()
        y = 0
        for row in self._rows:
            # Важно: задаём ширину строки равной ширине контейнера.
            # Без этого QWidget без layout оставляет размер по sizeHint,
            # и строки выглядят разной ширины.
            row.resize(width, ROW_HEIGHT)

            target = QPoint(0, y)
            if old_positions and row.episode_id in old_positions:
                old_y = old_positions[row.episode_id]
                if old_y == y:
                    row.move(target)
                else:
                    row.move(QPoint(0, old_y))
                    self._animate_to(row, target)
            else:
                row.move(target)
            y += ROW_HEIGHT + ROW_SPACING

        self.setMinimumHeight(max(0, y))

    def _animate_to(self, row, target: QPoint):
        anim = QPropertyAnimation(row, b"pos", self)
        anim.setDuration(ANIM_DURATION)
        anim.setStartValue(row.pos())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anims.append(anim)
        anim.finished.connect(lambda a=anim: self._forget_anim(a))
        anim.start(QPropertyAnimation.DeletionPolicy.KeepWhenStopped)

    def _forget_anim(self, anim):
        try:
            self._anims.remove(anim)
        except ValueError:
            pass

    def resizeEvent(self, event):
        """При изменении ширины — обновить позиции и ширину строк."""
        super().resizeEvent(event)
        if self._placeholder is not None:
            w = max(200, self.width())
            self._placeholder.setGeometry(0, 0, w, 200)
        else:
            self._relayout(old_positions=None)


# ============================================================
# Диалог
# ============================================================

class QueueDialog(QDialog):
    """Окно очереди загрузок."""

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self._rows = {}

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
        # Стартовый размер — компактный, чтобы строки сразу влезали.
        # Минимум — чтобы помещался заголовок, одна строка и кнопка.
        self.resize(640, 420)
        self.setMinimumSize(520, 320)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel(i18n.tr("queue.title"))
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.container = QueueContainer()
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
        """Перестроить список, сохранив позицию скролла и координаты строк."""
        scroll_pos = self.scroll.verticalScrollBar().value()

        active = self.manager.get_active_task()
        pending = self.manager.get_pending()

        old_positions = {
            ep_id: row.y() for ep_id, row in self._rows.items()
        }

        tasks = []
        if active is not None:
            tasks.append((active, True, 0, 0))
        total_pending = len(pending)
        for idx, task in enumerate(pending):
            tasks.append((task, False, idx, total_pending))

        if not tasks:
            self.container.show_placeholder(i18n.tr("queue.empty"))
            self._rows = {}
            return

        new_rows = []
        new_rows_by_id = {}
        for task, is_active, idx, total in tasks:
            ep_id = task["episode_id"]
            old = self._rows.get(ep_id)
            if old is not None and old.active == is_active:
                old.index = idx
                old.total = total
                if not is_active:
                    if hasattr(old, "up_btn"):
                        old.up_btn.setStyleSheet(
                            NAV_BTN_BORDER if idx == 0 else NAV_BTN_ACTIVE
                        )
                    if hasattr(old, "down_btn"):
                        old.down_btn.setStyleSheet(
                            NAV_BTN_BORDER if idx >= total - 1
                            else NAV_BTN_ACTIVE
                        )
                new_rows.append(old)
                new_rows_by_id[ep_id] = old
            else:
                if old is not None:
                    old.setParent(None)
                    old.deleteLater()
                row = QueueRow(
                    task, active=is_active,
                    index=idx, total=total,
                    on_cancel=self._on_cancel,
                    on_move=None if is_active else self._on_move,
                )
                new_rows.append(row)
                new_rows_by_id[ep_id] = row

        self._rows = new_rows_by_id
        self.container.set_rows(new_rows, old_positions=old_positions)

        QTimer.singleShot(
            0,
            lambda p=scroll_pos: self.scroll.verticalScrollBar().setValue(p),
        )

    def _on_progress(self, episode_id, stage, percent):
        row = self._rows.get(episode_id)
        if row is not None and row.active:
            row.set_progress(stage, percent)

    def _on_move(self, episode_id, action: str):
        if action == "up":
            self.manager.move_up(episode_id)
        elif action == "down":
            self.manager.move_down(episode_id)
        elif action == "top":
            self.manager.move_to_top(episode_id)
        elif action == "bottom":
            self.manager.move_to_bottom(episode_id)

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
            self.refresh()