# -*- coding: utf-8 -*-
"""Тесты API-клиента."""

import json
import pytest

from core.api import (
    Anime365API,
    Anime365Error,
    extract_subtitles_from_embed,
    extract_video_urls,
    extract_qualities,
)


# ============================================================
# Извлечение ссылок из embed
# ============================================================

class TestExtractVideoUrls:
    def test_stream_only(self):
        embed = {
            "stream": [
                {"height": 1080, "urls": ["https://cdn/1080.m3u8"]},
                {"height": 720, "urls": ["https://cdn/720.m3u8"]},
            ]
        }
        urls = extract_video_urls(embed)
        assert urls["1080p"] == "https://cdn/1080.m3u8"
        assert urls["720p"] == "https://cdn/720.m3u8"

    def test_download_only(self):
        embed = {
            "download": [
                {"height": 1080, "url": "https://cdn/1080.mp4"},
                {"height": 720, "url": "https://cdn/720.mp4"},
            ]
        }
        urls = extract_video_urls(embed)
        assert urls["1080p"] == "https://cdn/1080.mp4"

    def test_stream_takes_priority(self):
        """stream имеет приоритет над download для одинакового качества."""
        embed = {
            "stream": [{"height": 1080, "urls": ["https://stream/1080"]}],
            "download": [{"height": 1080, "url": "https://download/1080.mp4"}],
        }
        urls = extract_video_urls(embed)
        assert urls["1080p"] == "https://stream/1080"

    def test_empty_dict(self):
        assert extract_video_urls({}) == {}

    def test_none(self):
        assert extract_video_urls(None) == {}

    def test_not_dict(self):
        assert extract_video_urls([]) == {}
        assert extract_video_urls("string") == {}


class TestExtractQualities:
    def test_list_of_qualities(self):
        embed = {
            "stream": [
                {"height": 1080, "urls": ["a"]},
                {"height": 720, "urls": ["b"]},
            ]
        }
        quals = extract_qualities(embed)
        assert "1080p" in quals
        assert "720p" in quals


class TestExtractSubtitlesFromEmbed:
    def test_direct_field(self):
        embed = {"subtitlesUrl": "https://subs/1.ass"}
        assert extract_subtitles_from_embed(embed) == "https://subs/1.ass"

    def test_recursive_find(self):
        embed = {"data": {"inner": {"file": "https://subs/2.srt"}}}
        assert extract_subtitles_from_embed(embed) == "https://subs/2.srt"

    def test_none_if_not_found(self):
        embed = {"url": "https://video.mp4"}
        assert extract_subtitles_from_embed(embed) is None

    def test_none_input(self):
        assert extract_subtitles_from_embed(None) is None


# ============================================================
# Anime365API — токен
# ============================================================

class TestTokenManagement:
    def test_load_no_file(self, tmp_path):
        api = Anime365API(str(tmp_path / "missing.json"))
        assert api.token is None
        assert api.has_token() is False

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "token.json")
        api = Anime365API(path)
        api.save_token("secret123")
        assert api.has_token() is True
        assert api.token == "secret123"

        # Перечитываем
        api2 = Anime365API(path)
        assert api2.token == "secret123"

    def test_load_plain_string(self, tmp_path):
        path = tmp_path / "token.json"
        path.write_text('"just-a-string"', encoding="utf-8")
        api = Anime365API(str(path))
        assert api.token == "just-a-string"

    def test_load_various_keys(self, tmp_path):
        for key in ("access_token", "token", "accessToken"):
            path = tmp_path / f"{key}.json"
            path.write_text(json.dumps({key: "xyz"}), encoding="utf-8")
            api = Anime365API(str(path))
            assert api.token == "xyz"