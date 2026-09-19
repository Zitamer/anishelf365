# -*- coding: utf-8 -*-
"""Тесты проверки онгоингов."""

import pytest

from core.updater import check_for_updates, UpdateStats


def _make_series_data(series_id, episode_ids):
    return {
        "id": series_id,
        "title": f"Series {series_id}",
        "titles": {"ru": f"Series {series_id}"},
        "year": 2026,
        "type": "tv",
        "isAiring": 1,
        "episodes": [
            {
                "id": ep_id,
                "seriesId": series_id,
                "episodeInt": i + 1,
                "episodeType": "tv",
                "episodeTitle": "",
            }
            for i, ep_id in enumerate(episode_ids)
        ],
    }


class TestCheckForUpdates:
    def test_no_series(self, db, mock_api):
        stats = check_for_updates(db, mock_api)
        assert stats.series_checked == 0
        assert stats.new_episodes_total == 0

    def test_no_new_episodes(self, db, mock_api, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episodes(sample_series_data["episodes"])

        mock_api.get_series.return_value = sample_series_data

        stats = check_for_updates(db, mock_api)
        assert stats.series_checked == 1
        assert stats.series_no_new == 1
        assert stats.new_episodes_total == 0
        assert db.get_series(41893)["new_episodes_count"] == 0

    def test_new_episode_detected(self, db, mock_api, sample_series_data):
        # В БД только 1 эпизод
        db.upsert_series(sample_series_data)
        db.upsert_episodes([sample_series_data["episodes"][0]])

        # API возвращает 2 эпизода (второй — новый)
        mock_api.get_series.return_value = sample_series_data

        stats = check_for_updates(db, mock_api)
        assert stats.series_with_new == 1
        assert stats.new_episodes_total == 1
        assert db.get_series(41893)["new_episodes_count"] == 1
        # Оба эпизода в БД
        assert len(db.list_episodes(41893)) == 2

    def test_counter_accumulates(self, db, mock_api, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episodes([sample_series_data["episodes"][0]])
        mock_api.get_series.return_value = sample_series_data

        # Первый прогон — +1
        check_for_updates(db, mock_api)
        assert db.get_series(41893)["new_episodes_count"] == 1

        # Второй прогон с ещё одним новым
        extended = _make_series_data(41893, [380000, 380001, 380002])
        mock_api.get_series.return_value = extended
        check_for_updates(db, mock_api)

        # Накопилось 2 (380001 из первого прогона + 380002 из второго)
        assert db.get_series(41893)["new_episodes_count"] == 2

    def test_ignored_series_skipped(self, db, mock_api, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episodes(sample_series_data["episodes"])
        db.add_ignored(41893, title="Test")

        stats = check_for_updates(db, mock_api)
        assert stats.series_checked == 0

    def test_api_failure_counted(self, db, mock_api, sample_series_data):
        db.upsert_series(sample_series_data)
        mock_api.get_series.return_value = None  # как будто API упал

        stats = check_for_updates(db, mock_api)
        assert stats.series_failed == 1
        assert stats.series_with_new == 0

    def test_progress_callback(self, db, mock_api, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episodes(sample_series_data["episodes"])
        mock_api.get_series.return_value = sample_series_data

        calls = []
        check_for_updates(
            db, mock_api,
            progress_cb=lambda c, t, sid: calls.append((c, t, sid)),
        )
        assert calls == [(1, 1, 41893)]


class TestUpdateStats:
    def test_to_dict_keys(self):
        s = UpdateStats()
        d = s.to_dict()
        for key in ("series_checked", "series_with_new", "series_failed",
                    "series_no_new", "new_episodes_total"):
            assert key in d