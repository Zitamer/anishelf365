# -*- coding: utf-8 -*-
"""Тесты парсинга ссылок."""

from core.url_parser import parse_series_id, parse_episode_ids, parse_translation_id


class TestParseSeriesId:
    def test_full_url(self):
        url = "https://smotret-anime.org/catalog/yani-neko-41893"
        assert parse_series_id(url) == 41893

    def test_url_with_episode(self):
        url = ("https://smotret-anime.org/catalog/yani-neko-41893/"
               "1-seriya-371562/russkie-subtitry-5843348")
        assert parse_series_id(url) == 41893

    def test_app_domain(self):
        url = ("https://smotret-anime.app/catalog/"
               "mushoku-tensei-iii-isekai-ittara-honki-dasu-36866")
        assert parse_series_id(url) == 36866

    def test_plain_number(self):
        assert parse_series_id("41893") == 41893

    def test_plain_number_with_spaces(self):
        assert parse_series_id("  41893  ") == 41893

    def test_empty(self):
        assert parse_series_id("") is None

    def test_none(self):
        assert parse_series_id(None) is None

    def test_no_id_in_url(self):
        assert parse_series_id("https://smotret-anime.org/") is None

    def test_garbage(self):
        assert parse_series_id("not a url") is None


class TestParseEpisodeIds:
    def test_episode_url(self):
        url = ("https://smotret-anime.org/catalog/yani-neko-41893/"
               "1-seriya-371562/russkie-subtitry-5843348")
        assert parse_episode_ids(url) == (41893, 371562)

    def test_series_url_without_episode(self):
        url = "https://smotret-anime.org/catalog/yani-neko-41893"
        assert parse_episode_ids(url) is None

    def test_empty(self):
        assert parse_episode_ids("") is None


class TestParseTranslationId:
    def test_russian_subs(self):
        url = ("https://smotret-anime.org/catalog/yani-neko-41893/"
               "1-seriya-371562/russkie-subtitry-5843348")
        assert parse_translation_id(url) == 5843348

    def test_another_url(self):
        url = ("https://smotret-anime.org/catalog/isekai-nonbiri-nouka-2-40114/"
               "12-seriya-380593/russkie-subtitry-5827947")
        assert parse_translation_id(url) == 5827947

    def test_empty(self):
        assert parse_translation_id("") is None