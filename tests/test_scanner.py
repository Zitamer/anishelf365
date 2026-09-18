# -*- coding: utf-8 -*-
"""Тесты сканера библиотеки."""

import os
import pytest

from core.scanner import scan_library, scan_series_files, ScanStats


# ============================================================
# scan_library
# ============================================================

class TestScanLibrary:
    def test_empty_library(self, db, mock_api, tmp_path):
        lib = str(tmp_path / "empty")
        os.makedirs(lib)
        stats = scan_library(db, mock_api, lib)
        assert stats.series_found == 0

    def test_nonexistent_path(self, db, mock_api, tmp_path):
        lib = str(tmp_path / "nonexistent")
        stats = scan_library(db, mock_api, lib)
        assert stats.series_found == 0

    def test_one_series_no_files(self, db, mock_api, tmp_library):
        os.makedirs(os.path.join(tmp_library, "41893"))
        stats = scan_library(db, mock_api, tmp_library)
        assert stats.series_found == 1
        assert stats.series_new == 1
        assert stats.files_found == 0
        assert db.get_series(41893) is not None

    def test_one_series_with_files(self, db, mock_api, tmp_library):
        series_dir = os.path.join(tmp_library, "41893")
        os.makedirs(series_dir)
        with open(os.path.join(series_dir, "380000_5931743.mp4"), "wb") as f:
            f.write(b"x" * 1000)
        with open(os.path.join(series_dir, "380000_5931743.ass"), "w") as f:
            f.write("subtitle")

        stats = scan_library(db, mock_api, tmp_library)
        assert stats.files_found == 1
        assert stats.files_new == 1
        files = db.list_local_files(41893)
        assert len(files) == 1
        assert files[0]["relative_path"] == "41893/380000_5931743.mp4"

    def test_ignored_series_skipped(self, db, mock_api, tmp_library):
        os.makedirs(os.path.join(tmp_library, "41893"))
        db.add_ignored(41893, title="Test")

        stats = scan_library(db, mock_api, tmp_library)
        assert stats.series_skipped_ignored == 1
        assert stats.series_found == 0
        assert db.get_series(41893) is None

    def test_non_numeric_dirname_skipped(self, db, mock_api, tmp_library):
        os.makedirs(os.path.join(tmp_library, "not-a-number"))
        stats = scan_library(db, mock_api, tmp_library)
        assert stats.series_found == 0


# ============================================================
# scan_series_files
# ============================================================

class TestScanSeriesFiles:
    def test_scan_new_series(self, db, sample_series_data, tmp_library):
        """
        Скан серии, у которой уже есть метаданные в БД.

        scan_series_files — низкоуровневая функция: она только сопоставляет
        файлы на диске с записями в БД. Метаданные сериала и эпизодов должен
        подготовить вызывающий (в проде это делает scan_library через API).
        """
        db.upsert_series(sample_series_data)
        for ep in sample_series_data["episodes"]:
            db.upsert_episode(ep)

        series_dir = os.path.join(tmp_library, "41893")
        os.makedirs(series_dir)
        with open(os.path.join(series_dir, "380000_5931743.mp4"), "wb") as f:
            f.write(b"x" * 500)

        found = scan_series_files(db, 41893, tmp_library)
        assert found == 1
        files = db.list_local_files(41893)
        assert len(files) == 1
        assert files[0]["relative_path"] == "41893/380000_5931743.mp4"

    def test_scan_nonexistent_dir(self, db, tmp_library):
        found = scan_series_files(db, 99999, tmp_library)
        assert found == 0

    def test_scan_ignored_series(self, db, tmp_library):
        os.makedirs(os.path.join(tmp_library, "41893"))
        db.add_ignored(41893)
        found = scan_series_files(db, 41893, tmp_library)
        assert found == 0

    def test_scan_empty_dir(self, db, tmp_library):
        os.makedirs(os.path.join(tmp_library, "41893"))
        found = scan_series_files(db, 41893, tmp_library)
        assert found == 0


# ============================================================
# ScanStats
# ============================================================

class TestScanStats:
    def test_to_dict(self):
        stats = ScanStats()
        stats.series_found = 5
        stats.files_found = 10
        d = stats.to_dict()
        assert d["series_found"] == 5
        assert d["files_found"] == 10
        assert "series_skipped_ignored" in d

    def test_default_zero(self):
        stats = ScanStats()
        assert stats.series_found == 0
        assert stats.files_found == 0