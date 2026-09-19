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
        btns = view.findChildren(QPushButton)
        assert any(b.text() for b in btns)


# ============================================================
# Сброс счётчика новых серий
# ============================================================

class TestSeriesViewResetNewCounter:
    def test_does_not_reset_on_open(self, qtbot, mock_app_full, seeded_db):
        """Счётчик новых серий НЕ сбрасывается при открытии — плашка видна."""
        seeded_db.set_new_episodes_count(41893, 5)
        mock_app_full.db = seeded_db

        view = _make_view(qtbot, mock_app_full)

        assert seeded_db.get_series(41893)["new_episodes_count"] == 5
        assert view._new_count_at_open == 5

    def test_resets_on_disconnect(self, qtbot, mock_app_full, seeded_db):
        """Счётчик сбрасывается при выходе с экрана (disconnect_downloads)."""
        seeded_db.set_new_episodes_count(41893, 5)
        mock_app_full.db = seeded_db

        view = _make_view(qtbot, mock_app_full)
        view.disconnect_downloads()

        assert seeded_db.get_series(41893)["new_episodes_count"] == 0

    def test_no_reset_when_already_zero(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        view.disconnect_downloads()
        assert seeded_db.get_series(41893)["new_episodes_count"] == 0


# ============================================================
# Фильтры
# ============================================================

class TestSeriesViewFilters:
    def test_type_combo_has_options(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert view.type_combo.count() >= 3
        items = [view.type_combo.itemText(i)
                 for i in range(view.type_combo.count())]
        assert "sub" in items
        assert "voice" in items

    def test_lang_combo_has_options(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert view.lang_combo.count() >= 3
        codes = [view.lang_combo.itemData(i)
                 for i in range(view.lang_combo.count())]
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

        for btn in view.findChildren(QPushButton):
            if btn.text() and "Назад" in btn.text():
                btn.click()
                break

        mock_app_full.show_library.assert_called()


# ============================================================
# Плашка и метки "новых серий"
# ============================================================

class TestSeriesViewNewEpisodesBadge:
    def test_badge_shown_when_new_count_positive(self, qtbot, mock_app_full,
                                                 seeded_db):
        seeded_db.set_new_episodes_count(41893, 3)
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        assert view._new_count_at_open == 3
        assert view._new_banner is not None
        assert "3" in view._new_banner.text()

    def test_badge_hidden_when_zero(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert view._new_banner is None

    def test_counter_resets_on_banner_click(self, qtbot, mock_app_full,
                                            seeded_db):
        seeded_db.set_new_episodes_count(41893, 2)
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        view._on_reset_new_clicked()

        assert seeded_db.get_series(41893)["new_episodes_count"] == 0
        assert view._new_count_at_open == 0

    def test_counter_resets_on_disconnect(self, qtbot, mock_app_full,
                                          seeded_db):
        seeded_db.set_new_episodes_count(41893, 2)
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        view.disconnect_downloads()

        assert seeded_db.get_series(41893)["new_episodes_count"] == 0

    def test_new_episodes_are_marked_in_list(self, qtbot, mock_app_full,
                                             seeded_db):
        seeded_db.set_new_episodes_count(41893, 1)
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        assert len(view._new_ids_at_open) == 1
        for row in view._rows_by_ep.values():
            if row.episode_id in view._new_ids_at_open:
                assert row.is_new is True
            else:
                assert row.is_new is False

    def test_unmark_single_new(self, qtbot, mock_app_full, seeded_db):
        seeded_db.set_new_episodes_count(41893, 2)
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        target = next(iter(view._new_ids_at_open))
        view._on_unmark_new(target)

        assert target not in view._new_ids_at_open
        assert view._new_count_at_open == 1


# ============================================================
# Поиск по эпизодам
# ============================================================

class TestSeriesViewSearch:
    def test_search_by_number(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        assert len(view._episodes) == 2

        view.search_edit.setText("1")
        qtbot.wait(250)  # debounce 200 мс
        assert len(view._episodes) == 1
        assert view._episodes[0]["number"] == 1

    def test_search_no_match(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        view.search_edit.setText("9999")
        qtbot.wait(250)
        assert len(view._episodes) == 0

    def test_search_cleared_shows_all(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        view.search_edit.setText("1")
        qtbot.wait(250)
        assert len(view._episodes) == 1

        view.search_edit.setText("")
        qtbot.wait(250)
        assert len(view._episodes) == 2


# ============================================================
# Обновление данных
# ============================================================

class TestSeriesViewRefreshData:
    def test_refresh_calls_api(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db

        extended = {
            "id": 41893,
            "title": "Табакошка (обновлено)",
            "titles": {"ru": "Табакошка"},
            "year": 2026,
            "type": "tv",
            "episodes": [
                {"id": 380000, "seriesId": 41893, "episodeInt": 1,
                 "episodeType": "tv", "episodeTitle": ""},
                {"id": 380001, "seriesId": 41893, "episodeInt": 2,
                 "episodeType": "tv", "episodeTitle": ""},
                {"id": 380002, "seriesId": 41893, "episodeInt": 3,
                 "episodeType": "tv", "episodeTitle": ""},
            ],
        }
        mock_app_full.api.get_series.return_value = extended
        view = _make_view(qtbot, mock_app_full)

        view._on_refresh_data()
        # Воркер в отдельном потоке — ждём завершения
        qtbot.waitUntil(
            lambda: not view._is_refreshing,
            timeout=3000,
        )

        mock_app_full.api.get_series.assert_called_with(41893)
        assert len(mock_app_full.db.list_episodes(41893)) == 3

    def test_refresh_error_shown(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        mock_app_full.api.get_series.side_effect = Exception("boom")
        view = _make_view(qtbot, mock_app_full)

        view._on_refresh_data()
        qtbot.waitUntil(
            lambda: not view._is_refreshing,
            timeout=3000,
        )

        text = view.progress_label.text()
        assert "Ошибка" in text or "boom" in text