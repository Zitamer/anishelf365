# -*- coding: utf-8 -*-
"""Главный экран: библиотека с сеткой плиток (PySide6)."""

import os
import logging
import shutil
import threading
import time

from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QScrollArea, QGridLayout,
    QMenu, QDialog, QMessageBox,
)

from core.constants import (
    LIBRARY_TILE_W, LIBRARY_TILE_H,
    LIBRARY_COVER_W, LIBRARY_COVER_H,
)
from core import i18n
from core.api import Anime365API
from core.covers import cover_path


logger = logging.getLogger(__name__)


# ============================================================
# Плитка тайтла
# ============================================================

class SeriesTile(QFrame):
    """Плитка одного тайтла в сетке библиотеки."""

    def __init__(self, series_row, on_click=None, on_right_click=None):
        super().__init__()
        self.series_row = series_row
        self.series_id = series_row["series_id"]
        self.on_click = on_click
        self.on_right_click = on_right_click

        self.setFixedSize(LIBRARY_TILE_W, LIBRARY_TILE_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("seriesTile")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QFrame#seriesTile {"
            "  background-color: rgba(60, 60, 60, 0.25);"
            "  border-radius: 10px;"
            "}"
            "QFrame#seriesTile:hover {"
            "  background-color: rgba(80, 80, 80, 0.35);"
            "}"
        )

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        cover_label = QLabel()
        cover_label.setFixedSize(LIBRARY_COVER_W, LIBRARY_COVER_H)
        cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_label.setStyleSheet(
            "background-color: rgba(30, 30, 30, 0.5);"
            "border-radius: 6px;"
            "color: #888888;"
        )

        self._set_cover(cover_label)
        layout.addWidget(cover_label, alignment=Qt.AlignmentFlag.AlignCenter)

        title = self.series_row["title"] or f"ID {self.series_id}"
        title_label = QLabel(self._truncate(title, 30))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        title_label.setFixedHeight(32)
        layout.addWidget(title_label)

        episodes_count = self.series_row["episodes_count"] or 0
        info_label = QLabel(f"{i18n.tr('series.episodes')}: {episodes_count}")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(info_label)

        layout.addStretch()

        new_count = self.series_row["new_episodes_count"] or 0
        if new_count > 0:
            badge = QLabel(f"NEW +{new_count}", self)
            badge.setStyleSheet(
                "background-color: #2ea043;"
                "color: white;"
                "font-size: 10px;"
                "font-weight: bold;"
                "padding: 3px 8px;"
                "border-radius: 6px;"
            )
            badge.adjustSize()
            badge.move(self.width() - badge.width() - 8, 8)
            badge.raise_()

    def _set_cover(self, label: QLabel):
        path = cover_path(self.series_id)
        if os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                pix = pix.scaled(
                    LIBRARY_COVER_W, LIBRARY_COVER_H,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                label.setPixmap(pix)
                return

        title = self.series_row["title"] or f"ID {self.series_id}"
        label.setText(self._truncate(title, 40))
        label.setWordWrap(True)
        label.setStyleSheet(
            "background-color: rgba(30, 30, 30, 0.5);"
            "border-radius: 6px;"
            "color: #888888;"
            "padding: 10px;"
        )

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 1] + "…"

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.on_click:
            self.on_click(self.series_id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        if self.on_right_click:
            self.on_right_click(self.series_id, event.globalPos())


# ============================================================
# Сигналы для фоновых воркеров (скан / проверка обновлений)
# ============================================================

class WorkerSignals(QObject):
    progress = Signal(int, int, int)
    finished = Signal(dict)
    error = Signal(str)


# ============================================================
# Главный экран
# ============================================================

class LibraryView(QWidget):
    """Экран библиотеки: панели, фильтры, сетка плиток."""

    SORT_KEYS = ["title", "title_desc", "added", "year_new", "year_old"]
    FILTER_KEYS = ["all", "watching", "watched", "not_started", "has_new"]

    TOP_BAR_HEIGHT = 62
    FILTER_BAR_HEIGHT = 52
    BOTTOM_BAR_HEIGHT = 62

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.api = Anime365API()

        self.search_text = ""
        self.sort_key = app.settings.get("sort_key", "title")
        self.filter_key = app.settings.get("filter_key", "all")

        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)

        self._scan_signals = None
        self._is_scanning = False

        self._check_signals = None
        self._is_checking = False

        self._downloads_count = 0

        # Первый refresh() откладываем до showEvent — там у viewport уже
        # будет настоящая ширина. Иначе _calc_columns() вернёт дефолт и
        # плитки сначала отрисуются «в 2 колонки», а потом моргнут.
        self._first_refresh_done = False

        # Сколько колонок было при последнем refresh — чтобы не дёргать
        # перерисовку на каждый пиксель ресайза.
        self._last_cols = -1

        self._build_ui()

        # Счётчик очереди загрузок в 📥: подписываемся на сигнал менеджера.
        mgr = getattr(app, "download_manager", None)
        if mgr is not None:
            try:
                mgr.queue_changed.connect(self._on_queue_changed)
            except Exception:
                logger.exception("Не удалось подключиться к queue_changed")
            self._update_downloads_count()

    def showEvent(self, event):
        """Первый показ — отложенный refresh после того, как layout устоится."""
        super().showEvent(event)
        if not self._first_refresh_done:
            self._first_refresh_done = True
            QTimer.singleShot(0, self.refresh)
        # Счётчик очереди всегда синхронизируем при показе экрана.
        self._update_downloads_count()

    # ============================================================
    # Разметка
    # ============================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_top_bar())
        root.addWidget(self._make_filter_bar())
        root.addWidget(self._make_grid_area(), 1)
        root.addWidget(self._make_bottom_bar())

    def _make_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setFixedHeight(self.TOP_BAR_HEIGHT)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(8)

        title = QLabel("📺 " + i18n.tr("app.title"))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        layout.addStretch()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "🔍 " + i18n.tr("library.search_placeholder")
        )
        self.search_edit.setMinimumWidth(180)
        self.search_edit.setMaximumWidth(320)
        self.search_edit.setFixedHeight(38)
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit, 1)

        self.check_btn = QPushButton(i18n.tr("menu.check_new"))
        self.check_btn.setMinimumWidth(160)
        self.check_btn.setMaximumWidth(240)
        self.check_btn.setFixedHeight(42)
        self.check_btn.clicked.connect(self._on_check_new)
        layout.addWidget(self.check_btn)

        self.add_btn = QPushButton(i18n.tr("menu.add"))
        self.add_btn.setMinimumWidth(110)
        self.add_btn.setMaximumWidth(150)
        self.add_btn.setFixedHeight(42)
        self.add_btn.clicked.connect(self.app.show_add_series)
        layout.addWidget(self.add_btn)

        self.downloads_btn = QPushButton(self._format_downloads_text())
        self.downloads_btn.setFixedSize(56, 42)
        self.downloads_btn.setToolTip(i18n.tr("queue.title"))
        self.downloads_btn.clicked.connect(self._on_downloads_click)
        layout.addWidget(self.downloads_btn)

        self.ignored_btn = QPushButton(self._format_ignored_text())
        self.ignored_btn.setFixedSize(56, 42)
        self.ignored_btn.setToolTip(i18n.tr("ignored.tooltip"))
        self.ignored_btn.clicked.connect(self._on_ignored_click)
        layout.addWidget(self.ignored_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(46, 42)
        self.settings_btn.clicked.connect(self.app.show_settings)
        layout.addWidget(self.settings_btn)

        return bar

    def _format_downloads_text(self) -> str:
        if self._downloads_count > 0:
            return f"📥 {self._downloads_count}"
        return "📥"

    def _format_ignored_text(self) -> str:
        count = self.app.db.count_ignored()
        if count > 0:
            return f"🚫 {count}"
        return "🚫"

    def _make_filter_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("filterBar")
        bar.setFixedHeight(self.FILTER_BAR_HEIGHT)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(15, 6, 15, 6)
        layout.setSpacing(8)

        sort_label = QLabel(i18n.tr("library.sort.title") + ":")
        layout.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_labels = [
            i18n.tr("library.sort.title"),
            i18n.tr("library.sort.title_desc"),
            i18n.tr("library.sort.added"),
            i18n.tr("library.sort.year_new"),
            i18n.tr("library.sort.year_old"),
        ]
        self.sort_combo.addItems(self.sort_labels)
        self.sort_combo.setMinimumWidth(150)
        self.sort_combo.setMaximumWidth(220)
        self.sort_combo.setFixedHeight(38)
        self.sort_combo.setCurrentIndex(self._index_for_sort_key(self.sort_key))
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        layout.addWidget(self.sort_combo)

        layout.addSpacing(15)

        filter_label = QLabel(i18n.tr("library.filter.all") + ":")
        layout.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_labels = [
            i18n.tr("library.filter.all"),
            i18n.tr("library.filter.watching"),
            i18n.tr("library.filter.watched"),
            i18n.tr("library.filter.not_started"),
            i18n.tr("library.filter.has_new"),
        ]
        self.filter_combo.addItems(self.filter_labels)
        self.filter_combo.setMinimumWidth(140)
        self.filter_combo.setMaximumWidth(200)
        self.filter_combo.setFixedHeight(38)
        self.filter_combo.setCurrentIndex(
            self._index_for_filter_key(self.filter_key)
        )
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.filter_combo)

        layout.addStretch()

        self.found_label = QLabel()
        self.found_label.setObjectName("subtitle")
        layout.addWidget(self.found_label)

        return bar

    def _make_grid_area(self) -> QScrollArea:
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        self.grid.setContentsMargins(15, 15, 15, 15)
        self.grid.setSpacing(10)
        self.grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.scroll.setWidget(self.grid_container)

        # Ловим ресайз viewport — пересчёт колонок делаем мгновенно,
        # перерисовку — только если число колонок изменилось.
        self.scroll.viewport().installEventFilter(self)

        return self.scroll

    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport() and event.type() == event.Type.Resize:
            new_cols = self._calc_columns()
            if new_cols != self._last_cols:
                self.refresh()
        return super().eventFilter(obj, event)

    def _make_bottom_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("bottomBar")
        bar.setFixedHeight(self.BOTTOM_BAR_HEIGHT)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(10)

        self.status_label = QLabel()
        self.status_label.setObjectName("subtitle")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.scan_btn = QPushButton(i18n.tr("library.scan"))
        self.scan_btn.setFixedSize(260, 42)
        self.scan_btn.clicked.connect(self._on_scan)
        layout.addWidget(self.scan_btn)

        return bar

    # ============================================================
    # Сортировка/фильтры
    # ============================================================

    def _index_for_sort_key(self, key: str) -> int:
        try:
            return self.SORT_KEYS.index(key)
        except ValueError:
            return 0

    def _index_for_filter_key(self, key: str) -> int:
        try:
            return self.FILTER_KEYS.index(key)
        except ValueError:
            return 0

    # ============================================================
    # Данные
    # ============================================================

    def refresh(self):
        self._last_cols = self._calc_columns()
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.ignored_btn.setText(self._format_ignored_text())

        library_path = self.app.settings.library_path
        if not library_path:
            self._show_empty(i18n.tr("library.no_library_path"))
            self.found_label.setText("")
            return

        rows = self.app.db.list_series()
        rows = [dict(r) for r in rows]

        ignored_ids = {r["series_id"] for r in self.app.db.list_ignored()}
        if ignored_ids:
            rows = [r for r in rows if r["series_id"] not in ignored_ids]

        if self.search_text:
            needle = self.search_text.lower()
            rows = [r for r in rows if needle in (r["title"] or "").lower()]

        rows = self._apply_filter(rows)
        rows = self._apply_sort(rows)

        if not rows:
            total_count = len(self.app.db.list_series())
            ignored_count = len(ignored_ids)

            if total_count == 0:
                self._show_empty(i18n.tr("library.no_series"))
            elif ignored_count >= total_count:
                self._show_empty(
                    "Все тайтлы скрыты в игноре.\n"
                    "Нажмите 🚫 в верхней панели, чтобы вернуть."
                )
            else:
                self._show_empty("Ничего не найдено.")
            self.found_label.setText(i18n.tr("library.found", count=0))
            return

        cols = self._last_cols
        for i, row in enumerate(rows):
            r, c = divmod(i, cols)
            tile = SeriesTile(
                row,
                on_click=self._on_tile_click,
                on_right_click=self._on_tile_right_click,
            )
            self.grid.addWidget(tile, r, c)

        self.grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.found_label.setText(i18n.tr("library.found", count=len(rows)))

    def _apply_sort(self, rows):
        key = self.sort_key
        if key == "title":
            return sorted(rows, key=lambda r: (r["title"] or "").lower())
        if key == "title_desc":
            return sorted(rows, key=lambda r: (r["title"] or "").lower(),
                          reverse=True)
        if key == "added":
            return sorted(rows, key=lambda r: r.get("updated_at") or "",
                          reverse=True)
        if key == "year_new":
            return sorted(rows, key=lambda r: r.get("year") or 0, reverse=True)
        if key == "year_old":
            return sorted(rows, key=lambda r: r.get("year") or 0)
        return rows

    def _apply_filter(self, rows):
        key = self.filter_key
        if key == "all":
            return rows

        result = []
        for r in rows:
            sid = r["series_id"]
            total_eps = len(self.app.db.list_episodes(sid))
            watched = self.app.db.count_watched(sid)

            if key == "watching":
                if 0 < watched < total_eps:
                    result.append(r)
            elif key == "watched":
                if total_eps > 0 and watched >= total_eps:
                    result.append(r)
            elif key == "not_started":
                if watched == 0:
                    result.append(r)
            elif key == "has_new":
                if (r.get("new_episodes_count") or 0) > 0:
                    result.append(r)
        return result

    def _calc_columns(self) -> int:
        try:
            width = self.scroll.viewport().width()
        except Exception:
            width = 1200
        if width < 100:
            width = 1200

        # Точная формула: 2*15 (layout margins) + n*tile_w + (n-1)*10 <= width
        # ⟹ n <= (width - 20) / (tile_w + 10)
        margin = 20
        step = LIBRARY_TILE_W + 10
        cols = max(1, (width - margin) // step)
        return min(cols, 12)

    def _show_empty(self, text: str):
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "color: #888888;"
            "font-size: 14px;"
            "padding: 80px;"
        )
        self.grid.addWidget(label, 0, 0, 1, 6)

    # ============================================================
    # Обработчики UI
    # ============================================================

    def _on_search_changed(self, text: str):
        self._search_timer.start()

    def _do_search(self):
        self.search_text = self.search_edit.text().strip()
        self.refresh()

    def _on_sort_changed(self, index: int):
        if 0 <= index < len(self.SORT_KEYS):
            key = self.SORT_KEYS[index]
            if key != self.sort_key:
                self.sort_key = key
                self.app.settings.set("sort_key", key)
                self.refresh()

    def _on_filter_changed(self, index: int):
        if 0 <= index < len(self.FILTER_KEYS):
            key = self.FILTER_KEYS[index]
            if key != self.filter_key:
                self.filter_key = key
                self.app.settings.set("filter_key", key)
                self.refresh()

    def _on_tile_click(self, series_id: int):
        self.app.show_series(series_id)

    def _on_downloads_click(self):
        from ui_qt.dialogs.queue_dialog import QueueDialog
        dlg = QueueDialog(self, self.app.download_manager)
        dlg.exec()
        # На случай, если что-то отменили — синхронизируем счётчик.
        self._update_downloads_count()

    def _on_ignored_click(self):
        from ui_qt.dialogs.ignored_dialog import IgnoredSeriesDialog
        dlg = IgnoredSeriesDialog(self, self.app.db)
        dlg.exec()
        if dlg.changed:
            self.refresh()

    def _set_downloads_count(self, count: int):
        self._downloads_count = max(0, int(count))
        self.downloads_btn.setText(self._format_downloads_text())

    def _on_queue_changed(self):
        """Реакция на изменение очереди загрузок."""
        self._update_downloads_count()

    def _update_downloads_count(self):
        """Считывает состояние менеджера и обновляет текст кнопки 📥."""
        mgr = getattr(self.app, "download_manager", None)
        if mgr is None:
            return
        try:
            active, queued = mgr.get_queue_info()
        except Exception:
            logger.exception("get_queue_info() упал")
            return
        total = (1 if active is not None else 0) + int(queued or 0)
        self._set_downloads_count(total)

    def _on_tile_right_click(self, series_id: int, global_pos):
        menu = QMenu(self)

        act_open = QAction(i18n.tr("context_menu.open"), self)
        act_open.triggered.connect(lambda: self.app.show_series(series_id))
        menu.addAction(act_open)

        act_refresh = QAction(i18n.tr("context_menu.refresh"), self)
        act_refresh.triggered.connect(
            lambda: logger.info(f"Обновить метаданные {series_id}")
        )
        menu.addAction(act_refresh)

        act_open_folder = QAction(i18n.tr("context_menu.open_folder"), self)
        act_open_folder.triggered.connect(
            lambda: self._open_series_folder(series_id)
        )
        menu.addAction(act_open_folder)

        act_all_watched = QAction(
            i18n.tr("context_menu.mark_all_watched"), self
        )
        act_all_watched.triggered.connect(
            lambda: self._mark_all_watched(series_id)
        )
        menu.addAction(act_all_watched)

        act_site = QAction(i18n.tr("context_menu.open_on_site"), self)
        act_site.triggered.connect(lambda: self._open_on_site(series_id))
        menu.addAction(act_site)

        menu.addSeparator()

        if self.app.db.is_ignored(series_id):
            act_unignore = QAction(i18n.tr("context_menu.unignore"), self)
            act_unignore.triggered.connect(
                lambda: self._unignore_series(series_id)
            )
            menu.addAction(act_unignore)
        else:
            act_ignore = QAction(i18n.tr("context_menu.ignore"), self)
            act_ignore.triggered.connect(
                lambda: self._ignore_series(series_id)
            )
            menu.addAction(act_ignore)

        act_delete = QAction(i18n.tr("context_menu.delete"), self)
        act_delete.triggered.connect(
            lambda: self._delete_series(series_id)
        )
        menu.addAction(act_delete)

        menu.exec(global_pos)

    def _open_series_folder(self, series_id: int):
        lib = self.app.settings.library_path
        if not lib:
            return
        path = os.path.join(lib, str(series_id))
        if not os.path.isdir(path):
            QMessageBox.information(
                self, "Папка не найдена",
                f"Папка не существует:\n{path}",
            )
            return
        try:
            os.startfile(path)
        except AttributeError:
            import subprocess
            import sys
            if sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])

    def _mark_all_watched(self, series_id: int):
        self.app.db.set_all_watched(series_id, True)
        self.refresh()

    def _open_on_site(self, series_id: int):
        import webbrowser
        row = self.app.db.get_series(series_id)
        url = row["url"] if row and row["url"] else None
        if not url:
            data = self.api.get_series(series_id)
            if data and data.get("url"):
                url = data["url"]
        if url:
            webbrowser.open(url)

    def _ignore_series(self, series_id: int):
        from ui_qt.dialogs.delete_dialog import AddToIgnoreDialog

        row = self.app.db.get_series(series_id)
        title = (row["title"] if row else None) or f"ID {series_id}"

        dlg = AddToIgnoreDialog(self, title, series_id)
        if not dlg.exec():
            return
        if not dlg.confirmed():
            return

        self.app.db.add_ignored(series_id, title=title, reason="manual")
        logger.info(f"Тайтл {series_id} добавлен в игнор")
        self.refresh()

    def _unignore_series(self, series_id: int):
        from ui_qt.dialogs.delete_dialog import ask_yes_no

        row = self.app.db.get_series(series_id)
        title = (row["title"] if row else None) or f"ID {series_id}"

        if not ask_yes_no(
            self,
            i18n.tr("ignored.remove_confirm_title"),
            i18n.tr("ignored.confirm_text", title=title),
        ):
            return

        self.app.db.remove_ignored(series_id)
        logger.info(f"Тайтл {series_id} убран из игнора")
        self.refresh()

    def _delete_series(self, series_id: int):
        row = self.app.db.get_series(series_id)
        if not row:
            return

        title = row["title"] or f"ID {series_id}"

        files = self.app.db.list_local_files(series_id)
        files_count = len(files)
        total_size = sum((f["file_size"] or 0) for f in files)
        already_ignored = self.app.db.is_ignored(series_id)

        from ui_qt.dialogs.delete_dialog import DeleteSeriesDialog
        dlg = DeleteSeriesDialog(
            self, series_title=title, series_id=series_id,
            files_count=files_count, total_size=total_size,
            already_ignored=already_ignored,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        delete_files = dlg.should_delete_files()
        add_to_ignore = dlg.should_ignore()

        if delete_files:
            library_path = self.app.settings.library_path
            if library_path:
                series_dir = os.path.join(library_path, str(series_id))
                if os.path.isdir(series_dir):
                    try:
                        shutil.rmtree(series_dir)
                        logger.info(
                            i18n.tr("series_delete.folder_deleted",
                                    path=series_dir)
                        )
                    except OSError as e:
                        logger.error(
                            f"Не удалось удалить папку {series_dir}: {e}"
                        )
                        QMessageBox.warning(
                            self,
                            i18n.tr("common.error"),
                            i18n.tr("series_delete.folder_error",
                                    error=str(e)),
                        )

        try:
            self.app.db.delete_series(series_id)
            logger.info(
                i18n.tr("series_delete.success", series_id=series_id)
            )
        except Exception as e:
            logger.exception("Ошибка удаления из БД")
            QMessageBox.critical(
                self,
                i18n.tr("common.error"),
                i18n.tr("series_delete.db_error", error=str(e)),
            )
            return

        if add_to_ignore and not delete_files:
            self.app.db.add_ignored(
                series_id, title=title, reason="delete_keep_files"
            )
            logger.info(f"Тайтл {series_id} добавлен в игнор")

        self.refresh()

    # ============================================================
    # Сканирование
    # ============================================================

    def _on_scan(self):
        if self._is_scanning:
            return

        library_path = self.app.settings.library_path
        if not library_path or not os.path.isdir(library_path):
            self.status_label.setText(i18n.tr("library.no_library_path"))
            return

        self._is_scanning = True
        self.scan_btn.setEnabled(False)
        self.status_label.setText(
            i18n.tr("library.scanning", current=0, total=0)
        )

        self._scan_signals = WorkerSignals()
        self._scan_signals.progress.connect(self._on_scan_progress)
        self._scan_signals.finished.connect(self._on_scan_finished)
        self._scan_signals.error.connect(self._on_scan_error)

        def worker():
            from core.scanner import scan_library
            try:
                stats = scan_library(
                    self.app.db, self.api, library_path,
                    progress_cb=lambda c, t, sid: self._scan_signals.progress.emit(c, t, sid),
                )
                self._scan_signals.finished.emit(stats.to_dict())
            except Exception as e:
                self._scan_signals.error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_progress(self, current: int, total: int, sid: int):
        self.status_label.setText(
            i18n.tr("library.scanning", current=current, total=total)
        )

    def _on_scan_finished(self, stats: dict):
        self._is_scanning = False
        self.scan_btn.setEnabled(True)

        parts = [
            f"сериалов {stats['series_found']}",
            f"файлов {stats['files_found']}",
        ]
        skipped = stats.get("series_skipped_ignored", 0)
        if skipped:
            parts.append(f"пропущено {skipped} (игнор)")

        self.status_label.setText(
            "Сканирование завершено: " + ", ".join(parts)
        )
        self.refresh()

    def _on_scan_error(self, error: str):
        self._is_scanning = False
        self.scan_btn.setEnabled(True)
        self.status_label.setText(f"Ошибка: {error}")

    # ============================================================
    # Проверка новых серий (онгоинги)
    # ============================================================

    def _on_check_new(self):
        if self._is_checking:
            return

        total_series = len(self.app.db.list_series())
        if total_series == 0:
            self.status_label.setText(i18n.tr("library.check_no_series"))
            return

        self._is_checking = True
        self.check_btn.setEnabled(False)
        self.status_label.setText(
            i18n.tr("library.checking", current=0, total=total_series)
        )

        self._check_signals = WorkerSignals()
        self._check_signals.progress.connect(self._on_check_progress)
        self._check_signals.finished.connect(self._on_check_finished)
        self._check_signals.error.connect(self._on_check_error)

        def worker():
            from core.updater import check_for_updates
            try:
                stats = check_for_updates(
                    self.app.db, self.api,
                    progress_cb=lambda c, t, sid: self._check_signals.progress.emit(c, t, sid),
                )
                self._check_signals.finished.emit(stats.to_dict())
            except Exception as e:
                self._check_signals.error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_check_progress(self, current: int, total: int, sid: int):
        self.status_label.setText(
            i18n.tr("library.checking", current=current, total=total)
        )

    def _on_check_finished(self, stats: dict):
        self._is_checking = False
        self.check_btn.setEnabled(True)

        self.app.settings.last_check_time = time.time()

        new_total = stats.get("new_episodes_total", 0)
        series_with_new = stats.get("series_with_new", 0)
        failed = stats.get("series_failed", 0)

        if new_total > 0:
            self.status_label.setText(
                i18n.tr(
                    "library.check_done",
                    new=new_total,
                    series=series_with_new,
                )
            )
        else:
            self.status_label.setText(i18n.tr("library.check_no_new"))

        if failed:
            self.status_label.setText(
                self.status_label.text()
                + f"  ({failed} ошибок)"
            )

        logger.info(
            f"Проверка завершена: проверено {stats.get('series_checked', 0)}, "
            f"новых {new_total}, тайтлов с новыми {series_with_new}"
        )

        self.refresh()

    def _on_check_error(self, error: str):
        self._is_checking = False
        self.check_btn.setEnabled(True)
        self.status_label.setText(
            i18n.tr("library.check_error", error=error)
        )
        logger.error(f"Проверка новых серий упала: {error}")