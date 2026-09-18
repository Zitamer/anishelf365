# -*- coding: utf-8 -*-
"""Тесты локализации."""

from core import i18n


class TestI18n:
    def test_available_languages(self):
        langs = i18n.available_languages()
        assert "ru" in langs
        assert "en" in langs

    def test_load_ru(self):
        i18n.load("ru")
        assert i18n.get_current_language() == "ru"

    def test_load_en(self):
        i18n.load("en")
        assert i18n.get_current_language() == "en"

    def test_tr_ru(self):
        i18n.load("ru")
        assert i18n.tr("common.yes") == "Да"
        assert i18n.tr("common.no") == "Нет"

    def test_tr_en(self):
        i18n.load("en")
        assert i18n.tr("common.yes") == "Yes"
        assert i18n.tr("common.no") == "No"

    def test_tr_with_params(self):
        i18n.load("ru")
        result = i18n.tr("library.found", count=5)
        assert "5" in result

    def test_missing_key_returns_key(self):
        i18n.load("ru")
        assert i18n.tr("nonexistent.key.xyz") == "nonexistent.key.xyz"