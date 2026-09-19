# -*- coding: utf-8 -*-
"""UI-тесты экрана тайтла (SeriesView)."""

import pytest
from PySide6.QtWidgets import QLabel, QPushButton

from ui_qt.series_view import SeriesView, EpisodeRow, format_episode_number


def _make_view(qtbot, mock_app_full, series_id=41893):
    view = SeriesView(mock_app_full, series_id)
    qtbot.addWidget(view)
    view.show()
    qtbot.wait(20)
    return view


def _count_rows(view) -> int:
    return sum(
        1 for i in range(view.episodes_layout.count())
        if isinstance(view.episodes_layout.itemAt(i).widget(), EpisodeRow)
    )


# ============================================================
# Утилиты
# ============================================================

class TestFormatEpisodeNumber:
    def test_int(self):
        assert format_episode_number(1) == "01"
        assert format_episode_number(12) == "12"

    def test_float_integer(self):
        assert format_episode_number(1.0) == "01"

    def test_float_fractional(self):
        assert format_episode_number(1.5) == "1.5"

    def test_none(self):
        assert format_episode_number(None) == "—"


# ============================================================
# Создание и базовые проверки
# ============================================================

class TestSeriesViewInit:
    def test_creates_without_error(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert view is not None
        assert view.series_id == 41893

    def test_shows_two_episodes(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert _count_rows(view) == 2

    def test_not_found_when_missing(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full, series_id=99999)
        assert view.series_id == 99999
        # Должна быть кнопка "назад" на экране not-found
        btns = view.findChildren(QPushButton)
        assert any(b.text() for b in btns)


class TestSeriesViewResetNewCounter:
    def test_resets_new_counter_on_open(self, qtbot, mock_app_full, seeded_db):
        seeded_db.set_new_episodes_count(41893, 5)
        assert seeded_db.get_series(41893)["new_episodes_count"] == 5

        mock_app_full.db = seeded_db
        _make_view(qtbot, mock_app_full)

        # Счётчик должен сброситься при открытии экрана
        assert seeded_db.get_series(41893)["new_episodes_count"] == 0

    def test_no_reset_when_already_zero(self, qtbot, mock_app_full, seeded_db):
        # Счётчик уже 0 — проверим, что ничего не падает
        mock_app_full.db = seeded_db
        _make_view(qtbot, mock_app_full)
        assert seeded_db.get_series(41893)["new_episodes_count"] == 0


# ============================================================
# Фильтры
# ============================================================

class TestSeriesViewFilters:
    def test_type_combo_has_options(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert view.type_combo.count() >= 3
        items = [view.type_combo.itemText(i) for i in range(view.type_combo.count())]
        assert "sub" in items
        assert "voice" in items

    def test_lang_combo_has_options(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert view.lang_combo.count() >= 3
        codes = [view.lang_combo.itemData(i) for i in range(view.lang_combo.count())]
        assert "ru" in codes
        assert "en" in codes

    def test_changing_type_updates_setting(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        idx = view.type_combo.findText("voice")
        view.type_combo.setCurrentIndex(idx)
        qtbot.wait(20)

        assert mock_app_full.settings.get_translation_type_for_series(41893) == "voice"

    def test_changing_lang_updates_setting(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        idx = view.lang_combo.findData("en")
        view.lang_combo.setCurrentIndex(idx)
        qtbot.wait(20)

        assert mock_app_full.settings.get_translation_lang_for_series(41893) == "en"


# ============================================================
# Навигация
# ============================================================

class TestSeriesViewNavigation:
    def test_back_button_calls_show_library(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        # Первая кнопка "Назад" — в верхней панели
        for btn in view.findChildren(QPushButton):
            if btn.text() and "Назад" in btn.text():
                btn.click()
                break

        mock_app_full.show_library.assert_called()