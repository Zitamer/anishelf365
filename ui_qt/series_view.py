# -*- coding: utf-8 -*-
"""Экран тайтла: шапка, фильтры, список эпизодов (PySide6).

Режим плиток отключён — см. TILES_ENABLED.
"""

import os
import json
import logging
import threading

from PySide6.QtCore import Qt, QTimer, QObject, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QScrollArea, QMessageBox, QDialog,
    QLineEdit,
)

from core.constants import SERIES_COVER_W, SERIES_COVER_H
from core import i18n
from core.api import Anime365API
from core.covers import cover_path
from core import paths as P


logger = logging.getLogger(__name__)


TILES_ENABLED = False


# ============================================================
# Сигналы для фонового обновления метаданных
# ============================================================

class RefreshSignals(QObject):
    """Сигналы для безопасного апдейта UI из фонового потока."""
    done = Signal()
    error = Signal(str)


# ============================================================
# Утилиты
# ============================================================

def format_episode_number(num) -> str:
    if num is None:
        return "—"
    try:
        f = float(num)
        if f.is_integer():
            return f"{int(f):02d}"
        return f"{f:g}"
    except (ValueError, TypeError):
        return str(num)


def status_icon_and_color(progress) -> tuple:
    if progress and progress["watched"]:
        return "✓", "#7ac77a"
    if progress and progress["position"] > 0:
        return "▶", "#5b8cce"
    return "—", "#888888"


def describe_file(f) -> str:
    if not f:
        return ""
    author = (f["author"] or "?").strip() or "?"
    quality = (f["quality"] or "").strip()
    parts = [author]
    if quality:
        parts.append(quality)
    return " · ".join(parts)


# ============================================================
# Строка эпизода
# ============================================================

class EpisodeRow(QFrame):
    def __init__(self, episode_row, local_files, progress,
                 is_new: bool = False,
                 on_watch=None, on_download=None, on_delete=None,
                 on_unmark_new=None):
        super().__init__()
        self.episode_row = episode_row
        self.episode_id = episode_row["episode_id"]
        self.local_files = local_files or []
        self.progress = progress
        self.is_new = is_new
        self.on_watch = on_watch
        self.on_download = on_download
        self.on_delete = on_delete
        self.on_unmark_new = on_unmark_new
        self._downloading = False

        self.setObjectName("episodeRow")
        self.setFixedHeight(56)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QFrame#episodeRow {"
            "  background-color: rgba(60, 60, 60, 0.22);"
            "  border-radius: 6px;"
            "}"
            "QFrame#episodeRow:hover {"
            "  background-color: rgba(80, 80, 80, 0.30);"
            "}"
        )
        self._build_ui()

    def _build_ui(self):
        has_file = bool(self.local_files)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Бейдж NEW (если эпизод новый)
        if self.is_new:
            new_btn = QPushButton(i18n.tr("series.new_badge"))
            new_btn.setFixedHeight(22)
            new_btn.setMinimumWidth(52)
            new_btn.setToolTip(i18n.tr("series.new_badge_tooltip"))
            new_btn.setStyleSheet(
                "QPushButton {"
                "  font-size: 10px; font-weight: bold;"
                "  background-color: #2ea043; color: #ffffff;"
                "  border: none; border-radius: 10px;"
                "  padding: 2px 10px;"
                "}"
                "QPushButton:hover { background-color: #37bd51; }"
                "QPushButton:pressed { background-color: #248c36; }"
            )
            new_btn.clicked.connect(self._on_new_clicked)
            layout.addWidget(new_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        num_label = QLabel(format_episode_number(self.episode_row["number"]))
        num_label.setFixedWidth(40)
        num_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(num_label, 0, Qt.AlignmentFlag.AlignVCenter)

        icon, color = status_icon_and_color(self.progress)
        status_label = QLabel(icon)
        status_label.setFixedWidth(24)
        status_label.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: bold;"
        )
        layout.addWidget(status_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.info_label = QLabel()
        self._update_info_text(has_file)
        layout.addWidget(self.info_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self.watch_btn = QPushButton("▶")
        self.watch_btn.setFixedSize(50, 30)
        self.watch_btn.setStyleSheet(
            "QPushButton {"
            "  font-size: 13px; font-weight: bold;"
            "  background-color: #1f6aa5;"
            "  color: #ffffff;"
            "  border: none; border-radius: 6px;"
            "}"
            "QPushButton:hover { background-color: #2680c2; }"
            "QPushButton:pressed { background-color: #1a5a8e; }"
            "QPushButton:disabled {"
            "  background-color: #3a3a3a; color: #707070;"
            "}"
        )
        if has_file and self.on_watch:
            self.watch_btn.clicked.connect(
                lambda: self.on_watch(self.episode_id)
            )
        else:
            self.watch_btn.setEnabled(False)
        layout.addWidget(self.watch_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.download_btn = QPushButton("⬇")
        self.download_btn.setFixedSize(50, 30)
        self.download_btn.setStyleSheet(
            "QPushButton {"
            "  font-size: 13px; font-weight: bold;"
            "  background-color: #3a3a3a; color: #e0e0e0;"
            "  border: none; border-radius: 6px;"
            "}"
            "QPushButton:hover { background-color: #4a4a4a; }"
            "QPushButton:pressed { background-color: #2a2a2a; }"
            "QPushButton:disabled {"
            "  background-color: #2e2e2e; color: #707070;"
            "}"
        )
        if self.on_download:
            self.download_btn.clicked.connect(
                lambda: self.on_download(self.episode_id)
            )
        layout.addWidget(self.download_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setFixedSize(50, 30)
        if has_file and self.on_delete:
            self.delete_btn.setStyleSheet(
                "QPushButton {"
                "  font-size: 12px;"
                "  background-color: #3a3a3a; color: #e0e0e0;"
                "  border: none; border-radius: 6px;"
                "}"
                "QPushButton:hover { background-color: #a04040; }"
                "QPushButton:pressed { background-color: #8a3030; }"
            )
            self.delete_btn.clicked.connect(
                lambda: self.on_delete(self.episode_id)
            )
        else:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setStyleSheet(
                "QPushButton {"
                "  font-size: 12px;"
                "  background-color: #2e2e2e; color: #707070;"
                "  border: none; border-radius: 6px;"
                "}"
            )
        layout.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def _on_new_clicked(self):
        if self.on_unmark_new:
            self.on_unmark_new(self.episode_id)

    def _update_info_text(self, has_file):
        if self._downloading:
            return
        if has_file:
            info = describe_file(self.local_files[0])
            if len(self.local_files) > 1:
                info += f"  +{len(self.local_files) - 1}"
            self.info_label.setText(info)
            self.info_label.setStyleSheet("font-size: 12px;")
        else:
            self.info_label.setText(i18n.tr("episode.no_file", type="Sub"))
            self.info_label.setStyleSheet("font-size: 12px; color: #9b6b6b;")

    def set_download_progress(self, stage, percent, queued=False):
        self._downloading = True
        if queued:
            text = "В очереди…"
        elif stage == "video":
            text = f"Загрузка видео: {percent}%"
        elif stage == "subtitles":
            text = "Загрузка субтитров…"
        elif stage == "done":
            text = "Завершено"
        else:
            text = f"Загрузка: {percent}%"

        self.info_label.setText(text)
        self.info_label.setStyleSheet(
            "font-size: 12px; color: #5b8cce; font-weight: bold;"
        )
        self.download_btn.setEnabled(False)
        self.watch_btn.setEnabled(False)
        if self.delete_btn.isEnabled():
            self.delete_btn.setEnabled(False)

    def clear_download_progress(self):
        self._downloading = False


# ============================================================
# Экран тайтла
# ============================================================

class SeriesView(QWidget):
    TOP_BAR_HEIGHT = 50

    def __init__(self, app, series_id: int):
        super().__init__()
        self.app = app
        self.series_id = series_id
        # Используем общий API приложения — так тесты могут подменять
        # mock_app_full.api и влиять на поведение экрана.
        self.api = getattr(app, "api", None) or Anime365API()

        self.series_row = self.app.db.get_series(series_id)
        if not self.series_row:
            self._build_not_found()
            return

        # Счётчик новых серий НЕ сбрасываем сразу — покажем плашку в шапке
        # и метки «NEW» у эпизодов. Сброс: клик по плашке, клик по NEW
        # у эпизода или выход с экрана (disconnect_downloads).
        self._new_count_at_open = self.series_row["new_episodes_count"] or 0
        self._new_ids_at_open = set()
        self._new_banner = None
        # Флаг «при открытии счётчик был > 0». Нужен, чтобы сбросить БД
        # при выходе, даже если пользователь уже снял все NEW вручную.
        self._had_new_at_open = self._new_count_at_open > 0

        self.translation_type = self.app.settings.get_translation_type_for_series(series_id)
        self.translation_lang = self.app.settings.get_translation_lang_for_series(series_id)
        self.episodes_view = "list"
        self._description_expanded = False

        self._episodes = []
        self._files_by_ep = {}
        self._progress_by_ep = {}
        self._rows_by_ep = {}

        # Поиск по эпизодам
        self._search_text = ""
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_search)

        # Обновление данных
        self._is_refreshing = False
        self._refresh_signals = None

        # Ссылки на запущенные VLC-процессы: {episode_id: Popen}
        self._vlc_processes = {}

        self._manager = app.download_manager
        self._manager.progress.connect(self.on_download_progress)
        self._manager.finished.connect(self.on_download_finished)
        self._manager.error.connect(self.on_download_error)
        self._manager.queue_changed.connect(self._on_queue_changed)

        self._build_ui()
        self.refresh()

    def disconnect_downloads(self):
        # При выходе с экрана — сбрасываем счётчик новых серий, если он ещё >0.
        self._commit_new_reset()

        for signal, slot in (
            (self._manager.progress, self.on_download_progress),
            (self._manager.finished, self.on_download_finished),
            (self._manager.error, self.on_download_error),
            (self._manager.queue_changed, self._on_queue_changed),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    # ============================================================
    # Сброс счётчика новых серий
    # ============================================================

    def _commit_new_reset(self):
        """Зафиксировать сброс счётчика в БД (при выходе с экрана)."""
        if not self._had_new_at_open:
            return
        try:
            self.app.db.reset_new_episodes_count(self.series_id)
        except Exception:
            logger.exception("Не удалось сбросить new_episodes_count")
        self._new_count_at_open = 0
        self._new_ids_at_open = set()
        self._had_new_at_open = False

    def _on_reset_new_clicked(self):
        """Пользователь нажал на плашку «N новых серий» — сбрасываем всё."""
        logger.info(f"[{self.series_id}] Сброс счётчика новых серий (клик по плашке)")
        try:
            self.app.db.reset_new_episodes_count(self.series_id)
        except Exception:
            logger.exception("Не удалось сбросить new_episodes_count")

        self._new_count_at_open = 0
        self._new_ids_at_open = set()
        self._had_new_at_open = False

        self._update_new_banner()
        self.refresh()

    def _update_new_banner(self):
        """Обновить вид плашки без полного refresh()."""
        if self._new_banner is None:
            return
        if self._new_count_at_open > 0:
            self._new_banner.setText(
                i18n.tr(
                    "series.new_episodes_badge",
                    count=self._new_count_at_open,
                )
            )
            self._new_banner.show()
        else:
            try:
                self._new_banner.hide()
            except RuntimeError:
                pass

    def _on_unmark_new(self, episode_id: int):
        """Пользователь кликнул по NEW у эпизода — снимаем отметку."""
        if episode_id not in self._new_ids_at_open:
            return
        self._new_ids_at_open.discard(episode_id)
        if self._new_count_at_open > 0:
            self._new_count_at_open -= 1

        # Сразу пишем в БД: иначе при выходе с экрана _commit_new_reset
        # не увидит, что счётчик уже уменьшен, и оставит бейдж на главной.
        try:
            if self._new_count_at_open > 0:
                self.app.db.set_new_episodes_count(
                    self.series_id, self._new_count_at_open
                )
            else:
                self.app.db.reset_new_episodes_count(self.series_id)
                self._had_new_at_open = False
        except Exception:
            logger.exception("Не удалось обновить new_episodes_count")

        self._update_new_banner()
        self.refresh()

    # ============================================================
    # Экран "не найдено"
    # ============================================================

    def _build_not_found(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(f"Тайтл {self.series_id} не найден")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 16px;")
        layout.addWidget(label)
        btn = QPushButton(i18n.tr("series.back"))
        btn.setFixedWidth(180)
        btn.clicked.connect(self.app.show_library)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    # ============================================================
    # Разметка
    # ============================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._make_top_bar())
        root.addWidget(self._make_header())
        root.addWidget(self._make_progress())
        root.addWidget(self._make_episodes_control())
        root.addWidget(self._make_episodes_area(), 1)

    def _make_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setFixedHeight(self.TOP_BAR_HEIGHT)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(10)

        back_btn = QPushButton(i18n.tr("series.back"))
        back_btn.setObjectName("secondary")
        back_btn.setFixedWidth(150)
        back_btn.setFixedHeight(36)
        back_btn.clicked.connect(self.app.show_library)
        layout.addWidget(back_btn)

        layout.addStretch()

        self.clear_all_btn = QPushButton("🗑 Очистить скачанное")
        self.clear_all_btn.setObjectName("secondary")
        self.clear_all_btn.setFixedWidth(240)
        self.clear_all_btn.setFixedHeight(36)
        self.clear_all_btn.clicked.connect(self._on_clear_all_downloaded)
        layout.addWidget(self.clear_all_btn)

        refresh_btn = QPushButton(i18n.tr("series.refresh"))
        refresh_btn.setFixedWidth(240)
        refresh_btn.setFixedHeight(36)
        refresh_btn.clicked.connect(self._on_refresh_data)
        layout.addWidget(refresh_btn)

        return bar

    def _make_header(self) -> QFrame:
        header = QFrame()
        header.setContentsMargins(15, 15, 15, 15)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        cover_label = QLabel()
        cover_label.setFixedSize(SERIES_COVER_W, SERIES_COVER_H)
        cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_label.setStyleSheet(
            "background-color: rgba(30, 30, 30, 0.5);"
            "border-radius: 8px; color: #888888;"
        )
        self._set_cover(cover_label)
        layout.addWidget(cover_label, alignment=Qt.AlignmentFlag.AlignTop)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = self.series_row["title"] or f"ID {self.series_id}"

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        title_label.setWordWrap(True)
        title_row.addWidget(title_label, 0)

        # Плашка "N новых серий" — кликабельна, сбрасывает счётчик.
        if self._new_count_at_open > 0:
            self._new_banner = QPushButton(
                i18n.tr(
                    "series.new_episodes_badge",
                    count=self._new_count_at_open,
                )
            )
            self._new_banner.setFixedHeight(30)
            self._new_banner.setToolTip(
                i18n.tr("series.new_episodes_tooltip")
            )
            self._new_banner.setStyleSheet(
                "QPushButton {"
                "  font-size: 12px; font-weight: bold;"
                "  background-color: #2ea043; color: #ffffff;"
                "  border: none; border-radius: 15px;"
                "  padding: 2px 14px;"
                "}"
                "QPushButton:hover { background-color: #37bd51; }"
                "QPushButton:pressed { background-color: #248c36; }"
            )
            self._new_banner.clicked.connect(self._on_reset_new_clicked)
            title_row.addWidget(
                self._new_banner, 0, Qt.AlignmentFlag.AlignVCenter
            )

        title_row.addStretch()
        info_layout.addLayout(title_row)

        meta_parts = []
        if self.series_row["year"]:
            meta_parts.append(str(self.series_row["year"]))
        if self.series_row["season"]:
            meta_parts.append(self.series_row["season"])
        if self.series_row["type"]:
            meta_parts.append(self.series_row["type"].upper())
        if meta_parts:
            meta_label = QLabel(" · ".join(meta_parts))
            meta_label.setObjectName("subtitle")
            info_layout.addWidget(meta_label)

        genres = self._parse_genres(self.series_row["genres"])
        if genres:
            genres_label = QLabel("Жанры: " + ", ".join(genres))
            genres_label.setObjectName("subtitle")
            genres_label.setWordWrap(True)
            info_layout.addWidget(genres_label)

        description = self.series_row["description"] or ""
        if description:
            self.description_label = QLabel(self._truncate_description(description))
            self.description_label.setWordWrap(True)
            self.description_label.setStyleSheet("font-size: 12px;")
            info_layout.addWidget(self.description_label)

            if len(description) > 400:
                self.desc_btn = QPushButton(self._desc_btn_text())
                self.desc_btn.setObjectName("secondary")
                self.desc_btn.setFixedWidth(200)
                self.desc_btn.clicked.connect(self._toggle_description)
                info_layout.addWidget(self.desc_btn)

        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(10)

        first_unwatched = self.app.db.first_unwatched(self.series_id, "tv")
        num_text = "01"
        if first_unwatched:
            num_text = format_episode_number(first_unwatched["number"])

        self.continue_btn = QPushButton(i18n.tr("series.continue_from", number=num_text))
        self.continue_btn.setFixedWidth(280)
        self.continue_btn.setFixedHeight(40)
        self.continue_btn.clicked.connect(self._on_continue)
        btns_layout.addWidget(self.continue_btn)

        refresh_btn2 = QPushButton(i18n.tr("series.refresh"))
        refresh_btn2.setObjectName("secondary")
        refresh_btn2.setFixedWidth(220)
        refresh_btn2.setFixedHeight(40)
        refresh_btn2.clicked.connect(self._on_refresh_data)
        btns_layout.addWidget(refresh_btn2)

        btns_layout.addStretch()
        info_layout.addLayout(btns_layout)
        info_layout.addStretch()
        layout.addLayout(info_layout, 1)
        return header

    def _make_progress(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("progressCard")
        bar.setFixedHeight(46)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(15, 8, 15, 8)
        self.progress_label = QLabel()
        self.progress_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.progress_label)
        layout.addStretch()
        return bar

    def _make_episodes_control(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("filterBar")
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(15, 6, 15, 6)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Тип:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["sub", "voice", "raw"])
        self.type_combo.setFixedSize(110, 38)
        idx = self.type_combo.findText(self.translation_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentIndexChanged.connect(self._on_type_change)
        layout.addWidget(self.type_combo)

        layout.addSpacing(10)
        layout.addWidget(QLabel("Язык:"))

        self.lang_combo = QComboBox()
        self._lang_codes = ["ru", "en", "ja"]
        lang_display = {"ru": "Русский", "en": "English", "ja": "日本語"}
        for code in self._lang_codes:
            self.lang_combo.addItem(lang_display.get(code, code), code)
        self.lang_combo.setFixedSize(140, 38)
        for i, code in enumerate(self._lang_codes):
            if code == self.translation_lang:
                self.lang_combo.setCurrentIndex(i)
                break
        self.lang_combo.currentIndexChanged.connect(self._on_lang_change)
        layout.addWidget(self.lang_combo)

        layout.addSpacing(15)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            i18n.tr("series.search_placeholder")
        )
        self.search_edit.setFixedHeight(38)
        self.search_edit.setMinimumWidth(200)
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit, 1)

        return bar

    def _make_episodes_area(self) -> QScrollArea:
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.episodes_container = QWidget()
        self.episodes_layout = QVBoxLayout(self.episodes_container)
        self.episodes_layout.setContentsMargins(15, 10, 15, 15)
        self.episodes_layout.setSpacing(6)
        self.episodes_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.episodes_container)
        return self.scroll

    # ============================================================
    # Поиск
    # ============================================================

    def _on_search_changed(self, text: str):
        self._search_timer.start()

    def _apply_search(self):
        self._search_text = self.search_edit.text().strip()
        self.refresh()

    def _matches_search(self, ep) -> bool:
        if not self._search_text:
            return True
        needle = self._search_text.lower()

        # По номеру
        num = ep["number"]
        if num is not None:
            try:
                f = float(num)
                num_str = str(int(f)) if f.is_integer() else str(f)
            except (ValueError, TypeError):
                num_str = str(num)
            if needle in num_str:
                return True

        # По названию
        title = (ep["title"] or "").lower()
        if needle in title:
            return True

        return False

    # ============================================================
    # Данные
    # ============================================================

    def refresh(self):
        while self.episodes_layout.count():
            item = self.episodes_layout.takeAt(0)
            w = item.widget()
            if w:
                # Сначала отвязываем от родителя — виджет исчезает из
                # иерархии немедленно. Без этого deleteLater() откладывает
                # удаление до следующей итерации event loop, и при частых
                # refresh новый layout накладывался поверх старого.
                w.setParent(None)
                w.deleteLater()
        self._rows_by_ep = {}

        all_episodes = self.app.db.list_episodes_by_type(self.series_id, "tv")

        # Определяем «новые» эпизоды при первом refresh — последние N по номеру.
        if not self._new_ids_at_open and self._new_count_at_open > 0:
            tail = all_episodes[-self._new_count_at_open:]
            self._new_ids_at_open = {e["episode_id"] for e in tail}

        # Применяем поиск
        self._episodes = [e for e in all_episodes if self._matches_search(e)]

        all_files = self.app.db.list_local_files(self.series_id)
        self._files_by_ep = {}
        for f in all_files:
            self._files_by_ep.setdefault(f["episode_id"], []).append(f)

        self._progress_by_ep = {}
        for ep in self._episodes:
            self._progress_by_ep[ep["episode_id"]] = self.app.db.get_progress(
                ep["episode_id"]
            )

        total_eps = len(all_episodes)
        watched_count = self.app.db.count_watched(self.series_id)

        downloaded = 0
        for ep in all_episodes:
            files = self._files_by_ep.get(ep["episode_id"], [])
            if any(
                (f["translation_type"] or "sub") == self.translation_type
                and (f["translation_lang"] or "ru") == self.translation_lang
                for f in files
            ):
                downloaded += 1

        self.progress_label.setText(
            f"{i18n.tr('series.watched_progress', watched=watched_count, total=total_eps)}"
            f"   ·   "
            f"{i18n.tr('series.downloaded_progress', downloaded=downloaded, total=total_eps)}"
        )

        if not all_episodes:
            empty = QLabel("Нет серий")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #888888; font-size: 14px; padding: 60px;")
            self.episodes_layout.addWidget(empty)
            return

        if not self._episodes:
            # Поиск не нашёл — показываем сообщение
            empty = QLabel(
                i18n.tr("series.search_empty", query=self._search_text)
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #888888; font-size: 14px; padding: 60px;")
            self.episodes_layout.addWidget(empty)
            return

        active_id, _ = self._manager.get_queue_info()

        for ep in self._episodes:
            ep_id = ep["episode_id"]
            is_new = ep_id in self._new_ids_at_open
            row = EpisodeRow(
                ep,
                self._files_by_ep.get(ep_id, []),
                self._progress_by_ep.get(ep_id),
                is_new=is_new,
                on_watch=self._on_watch_episode,
                on_download=self._on_download_episode,
                on_delete=self._on_delete_episode,
                on_unmark_new=self._on_unmark_new,
            )
            self.episodes_layout.addWidget(row)
            self._rows_by_ep[ep_id] = row

            if ep_id == active_id:
                state = self._manager.get_state(ep_id)
                if state:
                    row.set_download_progress(state[0], state[1])
            elif self._manager.is_downloading(ep_id):
                row.set_download_progress("video", 0, queued=True)

        self.episodes_layout.addStretch()

    # ============================================================
    # Вспомогательные
    # ============================================================

    def _set_cover(self, label):
        path = cover_path(self.series_id)
        if os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                pix = pix.scaled(
                    SERIES_COVER_W, SERIES_COVER_H,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                label.setPixmap(pix)
                return
        title = self.series_row["title"] or f"ID {self.series_id}"
        label.setText(title[:40])
        label.setWordWrap(True)

    def _parse_genres(self, genres_json) -> list:
        if not genres_json:
            return []
        try:
            return json.loads(genres_json) or []
        except (json.JSONDecodeError, TypeError):
            return []

    def _truncate_description(self, text: str) -> str:
        if self._description_expanded or len(text) <= 400:
            return text
        return text[:400].rstrip() + "…"

    def _desc_btn_text(self) -> str:
        if self._description_expanded:
            return "Свернуть"
        return "Показать полностью"

    def _toggle_description(self):
        self._description_expanded = not self._description_expanded
        description = self.series_row["description"] or ""
        self.description_label.setText(self._truncate_description(description))
        self.desc_btn.setText(self._desc_btn_text())

    # ============================================================
    # Воспроизведение
    # ============================================================

    def _on_watch_episode(self, episode_id: int):
        files = self.app.db.list_files_for_episode(episode_id)
        if not files:
            QMessageBox.information(
                self, "Нет файла",
                "Для этого эпизода нет скачанных файлов.",
            )
            return

        chosen = self._pick_file(files)
        if not chosen:
            return

        library_path = self.app.settings.library_path
        if not library_path:
            QMessageBox.warning(self, "Ошибка", "Не указан путь к библиотеке.")
            return

        video_abs = P.abs_from_rel(library_path, chosen["relative_path"])
        subtitle_abs = None
        if chosen["subtitle_path"]:
            subtitle_abs = P.abs_from_rel(library_path, chosen["subtitle_path"])

        if not os.path.isfile(video_abs):
            QMessageBox.warning(
                self, "Файл не найден",
                f"Файл отсутствует на диске:\n{video_abs}\n\n"
                f"Возможно, он был перемещён или удалён.",
            )
            return

        try:
            from player.external import launch_vlc, PlayerError

            vlc_override = self.app.settings.vlc_exe_path or None

            proc = launch_vlc(
                video_path=video_abs,
                subtitle_path=subtitle_abs,
                vlc_override=vlc_override,
            )

            self._vlc_processes[episode_id] = proc
            logger.info(
                f"[{episode_id}] VLC запущен для {os.path.basename(video_abs)}"
            )

            self.app.db.set_watched(episode_id, True)
            QTimer.singleShot(300, self.refresh)

        except PlayerError as e:
            QMessageBox.critical(self, "Ошибка плеера", str(e))
        except Exception as e:
            logger.exception("Неожиданная ошибка запуска VLC")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось запустить плеер:\n{e}",
            )

    def _pick_file(self, files: list):
        if not files:
            return None

        if len(files) == 1:
            return files[0]

        matching = [
            f for f in files
            if (f["translation_type"] or "sub") == self.translation_type
            and (f["translation_lang"] or "ru") == self.translation_lang
        ]
        if matching:
            if len(matching) == 1:
                return matching[0]
            return self._ask_which_file(matching)

        return self._ask_which_file(files)

    def _ask_which_file(self, files: list):
        from PySide6.QtWidgets import QInputDialog

        items = []
        for f in files:
            author = f["author"] or "?"
            quality = f["quality"] or "?"
            lang = (f["translation_lang"] or "?").upper()
            kind = (f["translation_type"] or "sub").upper()
            items.append(f"{author} · {kind} [{lang}] · {quality}")

        choice, ok = QInputDialog.getItem(
            self,
            "Выбор перевода",
            "Найдено несколько файлов. Выберите:",
            items, 0, False,
        )
        if not ok:
            return None

        idx = items.index(choice)
        return files[idx]

    # ============================================================
    # Скачивание
    # ============================================================

    def _on_download_episode(self, episode_id: int):
        if self._manager.is_downloading(episode_id):
            logger.info(f"[{episode_id}] Уже в очереди")
            return

        ep_row = self.app.db.get_episode(episode_id)
        ep_number = ep_row["number"] if ep_row else None

        from ui_qt.dialogs.download_dialog import DownloadDialog
        dialog = DownloadDialog(
            self, api=self.api, episode_id=episode_id,
            episode_number=ep_number,
            preferred_lang=self.translation_lang,
            preferred_type=self.translation_type,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.get_result()
        if not result:
            return

        # Снимаем метку NEW только после подтверждения диалога. Если
        # пользователь отменил — ничего не теряем. Без refresh() —
        # иначе строка пересоздастся прямо во время старта загрузки.
        if episode_id in self._new_ids_at_open:
            self._on_unmark_new(episode_id)

        self._manager.start(
            api=self.api, db=self.app.db,
            library_path=self.app.settings.library_path,
            series_id=self.series_id, episode_id=episode_id,
            episode_number=ep_number,
            translation_id=result["translation_id"],
            quality=result["quality"], author=result["author"],
            translation_type=result["translation_type"],
            translation_lang=self.translation_lang,
            series_title=self.series_row["title"],
        )

    def on_download_progress(self, episode_id, stage, percent):
        if episode_id not in self._rows_by_ep:
            return
        row = self._rows_by_ep.get(episode_id)
        if row:
            row.set_download_progress(stage, percent)

    def on_download_finished(self, episode_id):
        if episode_id not in self._rows_by_ep:
            return
        logger.info(f"[{episode_id}] Готово")
        QTimer.singleShot(0, self.refresh)

    def on_download_error(self, episode_id, error):
        if episode_id not in self._rows_by_ep:
            return
        logger.error(f"[{episode_id}] Ошибка: {error}")
        QTimer.singleShot(0, self.refresh)
        QTimer.singleShot(100, lambda: QMessageBox.warning(
            self, "Ошибка скачивания", f"Не удалось скачать эпизод:\n{error}"
        ))

    def _on_queue_changed(self):
        QTimer.singleShot(0, self._update_download_indicators)

    def _update_download_indicators(self):
        active_id, _ = self._manager.get_queue_info()
        for ep_id, row in self._rows_by_ep.items():
            if ep_id == active_id:
                state = self._manager.get_state(ep_id)
                if state:
                    row.set_download_progress(state[0], state[1])
            elif self._manager.is_downloading(ep_id):
                row.set_download_progress("video", 0, queued=True)

    # ============================================================
    # Удаление
    # ============================================================

    def _on_delete_episode(self, episode_id: int):
        files = self.app.db.list_files_for_episode(episode_id)
        if not files:
            return

        ep_row = self.app.db.get_episode(episode_id)
        ep_number = ep_row["number"] if ep_row else None

        from ui_qt.dialogs.delete_dialog import DeleteEpisodeDialog
        dialog = DeleteEpisodeDialog(self, ep_number, files)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = dialog.get_selected_files()
        if not selected:
            return

        library_path = self.app.settings.library_path
        deleted_count = 0
        for f in selected:
            try:
                for rel in (f["relative_path"], f["subtitle_path"]):
                    if rel:
                        abs_path = P.abs_from_rel(library_path, rel)
                        if os.path.exists(abs_path):
                            os.remove(abs_path)
                            logger.info(f"Удалён файл: {abs_path}")
                self.app.db.delete_local_file(f["episode_id"], f["translation_id"])
                deleted_count += 1
            except OSError as e:
                logger.error(f"Ошибка удаления {f}: {e}")
                QMessageBox.warning(
                    self, "Ошибка удаления",
                    f"Не удалось удалить файл:\n{e}",
                )

        logger.info(f"Удалено файлов: {deleted_count}")
        self.refresh()

    def _on_clear_all_downloaded(self):
        files = self.app.db.list_local_files(self.series_id)
        if not files:
            QMessageBox.information(
                self, "Нечего удалять",
                "В этом тайтле нет скачанных файлов.",
            )
            return

        from ui_qt.dialogs.delete_dialog import DeleteAllDialog
        title = self.series_row["title"] or f"ID {self.series_id}"
        dialog = DeleteAllDialog(self, title, files)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        library_path = self.app.settings.library_path
        deleted = 0
        errors = 0
        for f in files:
            try:
                for rel in (f["relative_path"], f["subtitle_path"]):
                    if rel:
                        abs_path = P.abs_from_rel(library_path, rel)
                        if os.path.exists(abs_path):
                            os.remove(abs_path)
                deleted += 1
            except OSError as e:
                logger.error(f"Ошибка удаления {f['relative_path']}: {e}")
                errors += 1

        self.app.db.delete_files_for_series(self.series_id)

        logger.info(f"Очищено файлов: {deleted}, ошибок: {errors}")
        QMessageBox.information(
            self, "Готово",
            f"Удалено {deleted} файлов." + (f"\nОшибок: {errors}" if errors else ""),
        )
        self.refresh()

    # ============================================================
    # Прочее
    # ============================================================

    def _on_continue(self):
        first = self.app.db.first_unwatched(self.series_id, "tv")
        if first:
            self._on_watch_episode(first["episode_id"])

    def _on_type_change(self, index: int):
        value = self.type_combo.currentText()
        if value != self.translation_type:
            self.translation_type = value
            self.app.settings.set_translation_type_for_series(self.series_id, value)
            self.refresh()

    def _on_lang_change(self, index: int):
        value = self.lang_combo.currentData()
        if value and value != self.translation_lang:
            self.translation_lang = value
            self.app.settings.set_translation_lang_for_series(self.series_id, value)
            self.refresh()

    # ============================================================
    # Обновление данных тайтла
    # ============================================================

    def _on_refresh_data(self):
        if self._is_refreshing:
            return

        self._is_refreshing = True

        # Статус в progress_label
        self.progress_label.setText(i18n.tr("series.refreshing"))

        self._refresh_signals = RefreshSignals()
        self._refresh_signals.done.connect(self._on_refresh_done)
        self._refresh_signals.error.connect(self._on_refresh_error)

        def worker():
            try:
                data = self.api.get_series(self.series_id)
                if not data or not data.get("id"):
                    raise RuntimeError("API вернул пустой ответ")

                self.app.db.upsert_series(data)
                episodes = data.get("episodes") or []
                if episodes:
                    self.app.db.upsert_episodes(episodes)

                logger.info(
                    f"Обновлено {self.series_id}: "
                    f"{len(episodes)} эпизодов из API"
                )
                self._refresh_signals.done.emit()
            except Exception as e:
                logger.exception("Ошибка обновления данных")
                self._refresh_signals.error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_refresh_done(self):
        self._is_refreshing = False
        # Перечитываем series_row — мог поменяться title/описание/episodes_count.
        self.series_row = self.app.db.get_series(self.series_id)
        # Если после обновления появились новые серии — обновляем счётчик
        # и показываем плашку. Раньше счётчик сбрасывался при открытии,
        # но тут мы уже внутри — новые серии не теряем.
        self.refresh()
        self.progress_label.setText(i18n.tr("series.refresh_done"))
        QTimer.singleShot(2500, self._restore_progress_label)

    def _on_refresh_error(self, error: str):
        self._is_refreshing = False
        self.progress_label.setText(
            i18n.tr("series.refresh_error", error=error)
        )
        QTimer.singleShot(4000, self._restore_progress_label)

    def _restore_progress_label(self):
        """Вернуть progress_label к обычному содержимому."""
        try:
            total_eps = len(self.app.db.list_episodes_by_type(self.series_id, "tv"))
            watched_count = self.app.db.count_watched(self.series_id)

            downloaded = 0
            files_by_ep = {}
            for f in self.app.db.list_local_files(self.series_id):
                files_by_ep.setdefault(f["episode_id"], []).append(f)
            for ep in self.app.db.list_episodes_by_type(self.series_id, "tv"):
                files = files_by_ep.get(ep["episode_id"], [])
                if any(
                    (f["translation_type"] or "sub") == self.translation_type
                    and (f["translation_lang"] or "ru") == self.translation_lang
                    for f in files
                ):
                    downloaded += 1

            self.progress_label.setText(
                f"{i18n.tr('series.watched_progress', watched=watched_count, total=total_eps)}"
                f"   ·   "
                f"{i18n.tr('series.downloaded_progress', downloaded=downloaded, total=total_eps)}"
            )
        except Exception:
            logger.exception("Не удалось восстановить progress_label")