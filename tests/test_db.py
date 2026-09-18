# -*- coding: utf-8 -*-
"""Тесты базы данных."""


class TestSettings:
    def test_set_get(self, db):
        db.set_setting("foo", "bar")
        assert db.get_setting("foo") == "bar"

    def test_default(self, db):
        assert db.get_setting("missing", "default") == "default"

    def test_int_setting(self, db):
        db.set_setting("num", "42")
        assert db.get_int_setting("num") == 42

    def test_bool_setting(self, db):
        db.set_setting("flag", "1")
        assert db.get_bool_setting("flag") is True
        db.set_setting("flag", "0")
        assert db.get_bool_setting("flag") is False

    def test_update(self, db):
        db.set_setting("key", "v1")
        db.set_setting("key", "v2")
        assert db.get_setting("key") == "v2"


class TestSeries:
    def test_upsert_and_get(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        row = db.get_series(41893)
        assert row is not None
        assert row["title"] == "Табакошка / Yani Neko"
        assert row["year"] == 2026
        assert row["is_airing"] == 1

    def test_upsert_updates(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        sample_series_data["year"] = 2027
        db.upsert_series(sample_series_data)
        assert db.get_series(41893)["year"] == 2027

    def test_delete_cascade(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        for ep in sample_series_data["episodes"]:
            db.upsert_episode(ep)
        db.add_local_file(
            series_id=41893, episode_id=380000, episode_number=1,
            translation_id=5931743, relative_path="41893/x.mp4",
        )
        db.set_watched(380000, True)

        db.delete_series(41893)

        assert db.get_series(41893) is None
        assert len(db.list_episodes(41893)) == 0
        assert len(db.list_local_files(41893)) == 0
        assert db.get_progress(380000) is None


class TestEpisodes:
    def test_upsert_episode(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episode({
            "id": 380000, "seriesId": 41893,
            "episodeInt": 1, "episodeType": "tv",
            "episodeTitle": "Пилот",
        })
        ep = db.get_episode(380000)
        assert ep["number"] == 1
        assert ep["title"] == "Пилот"

    def test_upsert_episodes_bulk(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episodes(sample_series_data["episodes"])
        assert len(db.list_episodes(41893)) == 2

    def test_fractional_number(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episode({
            "id": 380099, "seriesId": 41893,
            "episodeInt": 1.5, "episodeType": "tv",
        })
        assert db.get_episode(380099)["number"] == 1.5


class TestLocalFiles:
    def test_add_and_get(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episode(sample_series_data["episodes"][0])
        db.add_local_file(
            series_id=41893, episode_id=380000, episode_number=1,
            translation_id=5931743,
            relative_path="41893/380000_5931743.mp4",
            author="Sanae", translation_type="sub",
            translation_lang="ru", quality="1080p",
            file_size=1_234_567,
        )
        row = db.get_local_file(380000, 5931743)
        assert row["author"] == "Sanae"
        assert row["quality"] == "1080p"

    def test_upsert_replaces(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episode(sample_series_data["episodes"][0])
        db.add_local_file(
            series_id=41893, episode_id=380000, episode_number=1,
            translation_id=5931743, relative_path="old.mp4",
        )
        db.add_local_file(
            series_id=41893, episode_id=380000, episode_number=1,
            translation_id=5931743, relative_path="new.mp4",
        )
        assert db.get_local_file(380000, 5931743)["relative_path"] == "new.mp4"

    def test_delete(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episode(sample_series_data["episodes"][0])
        db.add_local_file(
            series_id=41893, episode_id=380000, episode_number=1,
            translation_id=5931743, relative_path="x.mp4",
        )
        db.delete_local_file(380000, 5931743)
        assert db.get_local_file(380000, 5931743) is None


class TestWatchProgress:
    def test_set_get_progress(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episode(sample_series_data["episodes"][0])
        db.set_progress(380000, position=500.0, duration=1440.0)
        p = db.get_progress(380000)
        assert p["position"] == 500.0
        assert p["duration"] == 1440.0
        assert p["watched"] == 0

    def test_set_watched(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        db.upsert_episode(sample_series_data["episodes"][0])
        db.set_watched(380000, True)
        assert db.get_progress(380000)["watched"] == 1

    def test_count_watched(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        for ep in sample_series_data["episodes"]:
            db.upsert_episode(ep)
        db.set_watched(380000, True)
        assert db.count_watched(41893) == 1

    def test_first_unwatched(self, db, sample_series_data):
        db.upsert_series(sample_series_data)
        for ep in sample_series_data["episodes"]:
            db.upsert_episode(ep)
        db.set_watched(380000, True)
        first = db.first_unwatched(41893)
        assert first["episode_id"] == 380001


class TestIgnored:
    def test_add_and_check(self, db):
        assert db.is_ignored(41893) is False
        db.add_ignored(41893, title="Test")
        assert db.is_ignored(41893) is True

    def test_list(self, db):
        db.add_ignored(41893, title="A")
        db.add_ignored(11111, title="B")
        assert len(db.list_ignored()) == 2

    def test_remove(self, db):
        db.add_ignored(41893, title="Test")
        db.remove_ignored(41893)
        assert db.is_ignored(41893) is False

    def test_count(self, db):
        assert db.count_ignored() == 0
        db.add_ignored(41893)
        db.add_ignored(11111)
        assert db.count_ignored() == 2

    def test_upsert(self, db):
        db.add_ignored(41893, title="Old")
        db.add_ignored(41893, title="New")
        items = db.list_ignored()
        assert len(items) == 1
        assert items[0]["title"] == "New"