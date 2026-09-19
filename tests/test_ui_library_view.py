# -*- coding: utf-8 -*-
"""UI-тесты главного экрана (LibraryView)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from ui_qt.library_view import LibraryView, SeriesTile


def _make_view(qtbot, mock_app_full):
    view = LibraryView(mock_app_full)
    qtbot.addWidget(view)
    view.show()
    # showEvent запускает refresh через QTimer.singleShot(0) — даём ему шанс.
    qtbot.wait(20)
    return view


def _count_tiles(view) -> int:
    return sum(
        1 for i in range(view.grid.count())
        if isinstance(view.grid.itemAt(i).widget(), SeriesTile)
    )


class TestLibraryViewEmpty:
    def test_creates_without_error(self, qtbot, mock_app_full):
        view = _make_view(qtbot, mock_app_full)
        assert view is not None

    def test_no_library_path_shows_placeholder(self, qtbot, mock_app_full):
        view = _make_view(qtbot, mock_app_full)
        assert _count_tiles(view) == 0

    def test_empty_library_shows_no_series(self, qtbot, mock_app_full, tmp_library):
        mock_app_full.settings.library_path = tmp_library
        view = _make_view(qtbot, mock_app_full)
        assert _count_tiles(view) == 0


class TestLibraryViewWithData:
    def test_one_series_one_tile(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert _count_tiles(view) == 1

    def test_two_series_two_tiles(self, qtbot, mock_app_full, seeded_db,
                                  sample_series_data):
        second = dict(sample_series_data)
        second["id"] = 11111
        second["title"] = "Другой тайтл"
        second["titles"] = {"ru": "Другой тайтл"}
        second["episodes"] = []
        seeded_db.upsert_series(second)

        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert _count_tiles(view) == 2

    def test_new_badge_visible(self, qtbot, mock_app_full, seeded_db):
        seeded_db.set_new_episodes_count(41893, 3)
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        for i in range(view.grid.count()):
            w = view.grid.itemAt(i).widget()
            if isinstance(w, SeriesTile):
                labels = w.findChildren(QLabel)
                texts = [lbl.text() for lbl in labels]
                assert any("NEW +3" in t for t in texts)
                return
        pytest.fail("Плитка не найдена")


class TestLibraryViewSearch:
    def test_search_filters_out(self, qtbot, mock_app_full, seeded_db,
                                sample_series_data):
        second = dict(sample_series_data)
        second["id"] = 11111
        second["title"] = "Власть книжного червя"
        second["titles"] = {"ru": "Власть книжного червя"}
        second["episodes"] = []
        seeded_db.upsert_series(second)
        mock_app_full.db = seeded_db

        view = _make_view(qtbot, mock_app_full)
        assert _count_tiles(view) == 2

        view.search_edit.setText("Власть")
        qtbot.wait(350)
        assert _count_tiles(view) == 1

    def test_search_no_match_shows_empty(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        view.search_edit.setText("xyzqwerty")
        qtbot.wait(350)
        assert _count_tiles(view) == 0


class TestLibraryViewFilter:
    def test_filter_has_new_shows_only_new(self, qtbot, mock_app_full,
                                           seeded_db, sample_series_data):
        second = dict(sample_series_data)
        second["id"] = 11111
        second["title"] = "Без новых"
        second["titles"] = {"ru": "Без новых"}
        second["episodes"] = []
        seeded_db.upsert_series(second)

        seeded_db.set_new_episodes_count(41893, 1)

        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert _count_tiles(view) == 2

        # has_new = индекс 4
        view.filter_combo.setCurrentIndex(4)
        qtbot.wait(20)
        assert _count_tiles(view) == 1

    def test_filter_not_started_shows_all(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        view.filter_combo.setCurrentIndex(3)
        qtbot.wait(20)
        assert _count_tiles(view) == 1


class TestLibraryViewSort:
    def test_sort_by_title_asc(self, qtbot, mock_app_full, seeded_db,
                               sample_series_data):
        second = dict(sample_series_data)
        second["id"] = 11111
        second["title"] = "ААА первый по алфавиту"
        second["titles"] = {"ru": "ААА первый по алфавиту"}
        second["episodes"] = []
        seeded_db.upsert_series(second)

        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        view.sort_combo.setCurrentIndex(0)
        qtbot.wait(20)

        titles = []
        for i in range(view.grid.count()):
            w = view.grid.itemAt(i).widget()
            if isinstance(w, SeriesTile):
                titles.append(w.series_row["title"])

        assert titles == sorted(titles, key=lambda s: s.lower())


class TestLibraryViewNavigation:
    def test_tile_click_calls_show_series(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        for i in range(view.grid.count()):
            w = view.grid.itemAt(i).widget()
            if isinstance(w, SeriesTile):
                w.on_click(w.series_id)
                break

        mock_app_full.show_series.assert_called_once_with(41893)


# ============================================================
# Счётчик очереди загрузок в 📥
# ============================================================

class TestLibraryViewDownloadsCounter:
    def test_initial_counter_empty(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        # Пока очередь пуста — просто "📥"
        assert view.downloads_btn.text() == "📥"

    def test_counter_updates_on_queue_changed(self, qtbot, mock_app_full,
                                              seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        # Эмулируем: 1 активная + 2 в очереди = 3
        mock_app_full.download_manager.get_queue_info = lambda: (100, 2)
        mock_app_full.download_manager.queue_changed.emit()
        qtbot.wait(20)

        assert view.downloads_btn.text() == "📥 3"

    def test_counter_back_to_zero(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        # Активная + 1 в очереди
        mock_app_full.download_manager.get_queue_info = lambda: (100, 1)
        mock_app_full.download_manager.queue_changed.emit()
        qtbot.wait(20)
        assert view.downloads_btn.text() == "📥 2"

        # Очередь очистилась
        mock_app_full.download_manager.get_queue_info = lambda: (None, 0)
        mock_app_full.download_manager.queue_changed.emit()
        qtbot.wait(20)
        assert view.downloads_btn.text() == "📥"

    def test_counter_only_queued(self, qtbot, mock_app_full, seeded_db):
        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)

        mock_app_full.download_manager.get_queue_info = lambda: (None, 5)
        mock_app_full.download_manager.queue_changed.emit()
        qtbot.wait(20)

        assert view.downloads_btn.text() == "📥 5"

    def test_counter_on_show_event(self, qtbot, mock_app_full, seeded_db):
        """При показе экрана счётчик синхронизируется с менеджером."""
        mock_app_full.db = seeded_db

        # Менеджер уже занят, но view ещё не создан.
        mock_app_full.download_manager.get_queue_info = lambda: (100, 3)

        view = LibraryView(mock_app_full)
        qtbot.addWidget(view)
        view.show()
        qtbot.wait(20)

        # В __init__ и в showEvent счётчик считывается — должен быть "📥 4"
        assert view.downloads_btn.text() == "📥 4"