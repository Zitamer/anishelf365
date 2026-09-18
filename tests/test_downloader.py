# -*- coding: utf-8 -*-
"""Тесты скачивания."""

import os
import pytest

from core import downloader
from core.downloader import DownloadError, _headers_for


class TestHeadersFor:
    def test_smotret_anime_url(self):
        headers = _headers_for("https://smotret-anime.org/x")
        assert "Referer" in headers

    def test_app_domain(self):
        headers = _headers_for("https://smotret-anime.app/x")
        assert "Referer" in headers

    def test_external_cdn(self):
        headers = _headers_for("https://cdn.example.com/x")
        assert "Referer" not in headers


class TestDownloadEpisodeErrors:
    def test_no_embed(self, db, mock_api, tmp_library):
        mock_api.get_embed.return_value = None
        with pytest.raises(DownloadError):
            downloader.download_episode(
                api=mock_api, db=db, library_path=tmp_library,
                series_id=41893, episode_id=380000, episode_number=1,
                translation_id=5931743, quality_label="1080p",
            )

    def test_empty_video_urls(self, db, mock_api, tmp_library):
        mock_api.get_embed.return_value = {}
        with pytest.raises(DownloadError):
            downloader.download_episode(
                api=mock_api, db=db, library_path=tmp_library,
                series_id=41893, episode_id=380000, episode_number=1,
                translation_id=5931743, quality_label="1080p",
            )

    def test_unknown_quality(self, db, mock_api, tmp_library):
        mock_api.get_embed.return_value = {
            "stream": [{"height": 720, "urls": ["https://x"]}]
        }
        with pytest.raises(DownloadError):
            downloader.download_episode(
                api=mock_api, db=db, library_path=tmp_library,
                series_id=41893, episode_id=380000, episode_number=1,
                translation_id=5931743, quality_label="1080p",
            )


class TestDownloadSimple:
    """
    Тест простого скачивания (без параллельной загрузки).
    Подменяем размер файла на 1000 байт (< PARALLEL_MIN_SIZE).
    """
    def test_download_success(self, db, mock_api, sample_series_data,
                              tmp_library,
                              mock_requests_head, mock_requests_get_simple,
                              mocker):
        # Форсируем простой режим
        mocker.patch("core.downloader.PARALLEL_MIN_SIZE", 10**9)

        # Готовим БД: series + episode, иначе local_files упадёт по FK.
        db.upsert_series(sample_series_data)
        for ep in sample_series_data["episodes"]:
            db.upsert_episode(ep)

        mock_api.get_embed.return_value = {
            "stream": [{"height": 1080, "urls": ["https://cdn/stream.m3u8"]}]
        }

        progress_calls = []
        def on_progress(stage, percent, d, t):
            progress_calls.append((stage, percent))

        result = downloader.download_episode(
            api=mock_api, db=db, library_path=tmp_library,
            series_id=41893, episode_id=380000, episode_number=1,
            translation_id=5931743, quality_label="1080p",
            author="Sanae", translation_type="voice",  # чтобы .ass не качался
            translation_lang="ru",
            progress_cb=on_progress,
        )
        video_path, sub_path, size = result
        assert os.path.exists(video_path)
        assert os.path.getsize(video_path) == 1000
        assert size == 1000

        # Проверка прогресса
        assert any(stage == "video" for stage, _ in progress_calls)

        # Проверка записи в БД
        f = db.get_local_file(380000, 5931743)
        assert f is not None
        assert f["author"] == "Sanae"
        assert f["quality"] == "1080p"