# -*- coding: utf-8 -*-
"""Тесты обёртки настроек."""


class TestSettings:
    def test_library_path(self, settings):
        assert settings.library_path == ""
        settings.library_path = "C:/Anime"
        assert settings.library_path == "C:/Anime"

    def test_default_values(self, settings):
        assert settings.theme == "dark"
        assert settings.player_mode == "embedded"
        assert settings.reminders_enabled is True

    def test_volume_clamped(self, settings):
        settings.volume = 150
        assert settings.volume == 100
        settings.volume = -50
        assert settings.volume == 0
        settings.volume = 75
        assert settings.volume == 75

    def test_theme(self, settings):
        settings.theme = "light"
        assert settings.theme == "light"

    def test_translation_type_default(self, settings):
        assert settings.translation_type == "sub"

    def test_translation_type_per_series(self, settings):
        settings.set_translation_type_for_series(41893, "voice")
        assert settings.get_translation_type_for_series(41893) == "voice"
        assert settings.get_translation_type_for_series(11111) == "sub"

    def test_translation_lang_per_series(self, settings):
        settings.set_translation_lang_for_series(41893, "en")
        assert settings.get_translation_lang_for_series(41893) == "en"
        assert settings.get_translation_lang_for_series(11111) == "ru"

    def test_last_translation(self, settings):
        assert settings.get_last_translation_for_series(41893) == 0
        settings.set_last_translation_for_series(41893, 5931743)
        assert settings.get_last_translation_for_series(41893) == 5931743

    def test_onboarding_flag(self, settings):
        assert settings.onboarding_completed is False
        settings.onboarding_completed = True
        assert settings.onboarding_completed is True

    def test_reminders_flag(self, settings):
        settings.reminders_enabled = False
        assert settings.reminders_enabled is False