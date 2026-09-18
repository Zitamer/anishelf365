# -*- coding: utf-8 -*-
"""Тесты работы с путями."""

import os
from core import paths as P


class TestRelPaths:
    def test_video_rel_path(self):
        assert P.video_rel_path(41893, 380000, 5931743) == \
               "41893/380000_5931743.mp4"

    def test_subtitle_rel_path(self):
        assert P.subtitle_rel_path(41893, 380000, 5931743) == \
               "41893/380000_5931743.ass"

    def test_series_rel_dir(self):
        assert P.series_rel_dir(41893) == "41893"


class TestAbsPaths:
    """
    Тесты платформонезависимые: собираем ожидаемый путь через os.path.join,
    а не хардкодим Windows-разделители. Иначе на Linux CI получаем
    'C:\\Anime/41893' vs 'C:\\Anime\\41893'.
    """

    def test_abs_series_dir(self, tmp_path):
        lib = str(tmp_path / "Anime")
        expected = os.path.join(lib, "41893")
        assert P.abs_series_dir(lib, 41893) == expected

    def test_abs_video_path(self, tmp_path):
        lib = str(tmp_path / "Anime")
        result = P.abs_video_path(lib, 41893, 380000, 5931743)
        expected = os.path.join(lib, "41893", "380000_5931743.mp4")
        assert os.path.normpath(result) == os.path.normpath(expected)


class TestParseFilename:
    def test_video(self):
        assert P.parse_filename("380000_5931743.mp4") == \
               (380000, 5931743, "mp4")

    def test_subtitle(self):
        assert P.parse_filename("380000_5931743.ass") == \
               (380000, 5931743, "ass")

    def test_srt(self):
        assert P.parse_filename("380000_5931743.srt") == \
               (380000, 5931743, "srt")

    def test_invalid_no_translation(self):
        assert P.parse_filename("380000.mp4") is None

    def test_invalid_random(self):
        assert P.parse_filename("abc_def.mp4") is None

    def test_invalid_extension(self):
        assert P.parse_filename("380000_5931743.txt") is None

    def test_empty(self):
        assert P.parse_filename("") is None


class TestParseSeriesDirname:
    def test_number(self):
        assert P.parse_series_dirname("41893") == 41893

    def test_non_number(self):
        assert P.parse_series_dirname("abc") is None

    def test_mixed(self):
        assert P.parse_series_dirname("123_456") is None


class TestSanitize:
    def test_removes_bad_chars(self):
        assert P.sanitize_filename('a/b\\c:d*e?f"g<h>i|j') == \
               "a_b_c_d_e_f_g_h_i_j"

    def test_normal_name(self):
        assert P.sanitize_filename("Табакошка") == "Табакошка"


class TestUtils:
    def test_is_video_file(self):
        assert P.is_video_file("a.mp4") is True
        assert P.is_video_file("a.ass") is False

    def test_is_subtitle_file(self):
        assert P.is_subtitle_file("a.ass") is True
        assert P.is_subtitle_file("a.srt") is True
        assert P.is_subtitle_file("a.vtt") is True
        assert P.is_subtitle_file("a.mp4") is False