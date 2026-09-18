# -*- coding: utf-8 -*-
"""Тесты кэша обложек."""

import os
import pytest

from core import covers


class TestCoverPaths:
    def test_cover_path(self, tmp_path):
        p = covers.cover_path(41893, str(tmp_path))
        assert p.endswith("41893.jpg")

    def test_cover_rel_path(self):
        assert covers.cover_rel_path(41893) == "41893.jpg"

    def test_has_cover_false(self, tmp_path):
        assert covers.has_cover(41893, str(tmp_path)) is False

    def test_has_cover_true(self, tmp_path):
        path = covers.cover_path(41893, str(tmp_path))
        with open(path, "wb") as f:
            f.write(b"x")
        assert covers.has_cover(41893, str(tmp_path)) is True


class TestDeleteCover:
    def test_delete_existing(self, tmp_path):
        path = covers.cover_path(41893, str(tmp_path))
        with open(path, "wb") as f:
            f.write(b"x")
        assert covers.delete_cover(41893, str(tmp_path)) is True
        assert not os.path.exists(path)

    def test_delete_missing(self, tmp_path):
        assert covers.delete_cover(41893, str(tmp_path)) is False


class TestHumanSize:
    def test_bytes(self):
        assert "Б" in covers.human_size(500)

    def test_kilobytes(self):
        assert "КБ" in covers.human_size(2048)

    def test_megabytes(self):
        assert "МБ" in covers.human_size(5 * 1024 * 1024)

    def test_gigabytes(self):
        assert "ГБ" in covers.human_size(3 * 1024**3)


class TestCacheSize:
    def test_cache_size_empty(self, tmp_path):
        assert covers.get_cache_size(str(tmp_path)) == 0

    def test_cache_size_with_files(self, tmp_path):
        for i in range(3):
            with open(tmp_path / f"{i}.jpg", "wb") as f:
                f.write(b"x" * 100)
        assert covers.get_cache_size(str(tmp_path)) == 300