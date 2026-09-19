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
        # library_path по умолчанию пустой
        view = _make_view(qtbot, mock_app_full)
        assert _count_tiles(view) == 0

    def test_empty_library_shows_no_series(self, qtbot, mock_app_full, tmp_library):
        mock_app_full.settings.library_path = tmp_library
        view = _make_view(qtbot, mock_app_full)
        assert _count_tiles(view) == 0
        assert "library.found" not in view.found_label.text() or \
               "0" in view.found_label.text()


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

        # Ищем плитку и её дочерний QLabel с текстом "NEW +3"
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
        # _search_timer — 300 мс debounce
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
        # Добавим второй, но без new
        second = dict(sample_series_data)
        second["id"] = 11111
        second["title"] = "Без новых"
        second["titles"] = {"ru": "Без новых"}
        second["episodes"] = []
        seeded_db.upsert_series(second)

        # Первому — пометка
        seeded_db.set_new_episodes_count(41893, 1)

        mock_app_full.db = seeded_db
        view = _make_view(qtbot, mock_app_full)
        assert _count_tiles(view) == 2

        # has_new = индекс 4
        view.filter_combo.setCurrentIndex(4)
        qtbot.wait(20)
        assert _count_tiles(view) == 1

    def test_filter_not_started_shows_all(self, qtbot, mock_app_full, seeded_db):
        # Ничего не просмотрено — оба попадут в "not_started" (индекс 3)
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

        # sort_combo index 0 = title asc
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

        # Эмулируем клик по первой плитке
        for i in range(view.grid.count()):
            w = view.grid.itemAt(i).widget()
            if isinstance(w, SeriesTile):
                w.on_click(w.series_id)
                break

        mock_app_full.show_series.assert_called_once_with(41893)