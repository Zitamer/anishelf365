# -*- coding: utf-8 -*-
"""Удобная обёртка над таблицей settings с типизированными геттерами/сеттерами."""

from core.constants import (
    DEFAULT_LANGUAGE,
    DEFAULT_TRANSLATION_TYPE,
    DEFAULT_TRANSLATION_LANG,
)
from core.db import Database


class Settings:
    """Обёртка над Database для настроек приложения."""

    def __init__(self, db: Database):
        self.db = db

    # ---------- Общие ----------

    def get(self, key: str, default=None):
        return self.db.get_setting(key, default)

    def set(self, key: str, value):
        self.db.set_setting(key, value)

    # ---------- Библиотека ----------

    @property
    def library_path(self) -> str:
        return self.get("library_path", "")

    @library_path.setter
    def library_path(self, value: str):
        self.set("library_path", value)

    # ---------- VLC ----------

    @property
    def vlc_exe_path(self) -> str:
        return self.get("vlc_exe_path", "")

    @vlc_exe_path.setter
    def vlc_exe_path(self, value: str):
        self.set("vlc_exe_path", value)

    @property
    def libvlc_dir(self) -> str:
        return self.get("libvlc_dir", "")

    @libvlc_dir.setter
    def libvlc_dir(self, value: str):
        self.set("libvlc_dir", value)

    @property
    def player_mode(self) -> str:
        return self.get("player_mode", "embedded")

    @player_mode.setter
    def player_mode(self, value: str):
        self.set("player_mode", value)

    # ---------- Интерфейс ----------

    @property
    def language(self) -> str:
        return self.get("language", DEFAULT_LANGUAGE)

    @language.setter
    def language(self, value: str):
        self.set("language", value)

    @property
    def theme(self) -> str:
        return self.get("theme", "dark")

    @theme.setter
    def theme(self, value: str):
        self.set("theme", value)

    @property
    def episodes_view(self) -> str:
        return self.get("episodes_view", "tiles")

    @episodes_view.setter
    def episodes_view(self, value: str):
        self.set("episodes_view", value)

    # ---------- Тип перевода (sub/voice/raw) ----------

    @property
    def translation_type(self) -> str:
        """Глобальный тип перевода."""
        return self.get("translation_type", DEFAULT_TRANSLATION_TYPE)

    @translation_type.setter
    def translation_type(self, value: str):
        self.set("translation_type", value)

    # ---------- Язык перевода (ru/en/ja) ----------

    @property
    def translation_lang(self) -> str:
        """Глобальный язык перевода."""
        return self.get("translation_lang", DEFAULT_TRANSLATION_LANG)

    @translation_lang.setter
    def translation_lang(self, value: str):
        self.set("translation_lang", value)

    # ---------- Уведомления ----------

    @property
    def reminders_enabled(self) -> bool:
        return self.db.get_bool_setting("reminders_enabled", True)

    @reminders_enabled.setter
    def reminders_enabled(self, value: bool):
        self.set("reminders_enabled", "1" if value else "0")

    # ---------- Плеер ----------

    @property
    def volume(self) -> int:
        return self.db.get_int_setting("volume", 100)

    @volume.setter
    def volume(self, value: int):
        self.set("volume", max(0, min(100, int(value))))

    # ---------- Служебные ----------

    @property
    def last_check_time(self) -> float:
        return self.db.get_float_setting("last_check_time", 0.0)

    @last_check_time.setter
    def last_check_time(self, value: float):
        self.set("last_check_time", value)

    @property
    def last_full_update_all(self) -> float:
        return self.db.get_float_setting("last_full_update_all", 0.0)

    @last_full_update_all.setter
    def last_full_update_all(self, value: float):
        self.set("last_full_update_all", value)

    # ---------- Per-series overrides: тип перевода ----------

    def get_translation_type_for_series(self, series_id: int) -> str:
        val = self.get(f"translation_type_{series_id}")
        return val if val else self.translation_type

    def set_translation_type_for_series(self, series_id: int, value: str):
        self.set(f"translation_type_{series_id}", value)

    # ---------- Per-series overrides: язык перевода ----------

    def get_translation_lang_for_series(self, series_id: int) -> str:
        val = self.get(f"translation_lang_{series_id}")
        return val if val else self.translation_lang

    def set_translation_lang_for_series(self, series_id: int, value: str):
        self.set(f"translation_lang_{series_id}", value)

    # ---------- Последний перевод ----------

    def get_last_translation_for_series(self, series_id: int) -> int:
        return self.db.get_int_setting(f"last_translation_{series_id}", 0)

    def set_last_translation_for_series(self, series_id: int, translation_id: int):
        self.set(f"last_translation_{series_id}", translation_id)

    # ---------- Онбординг ----------

    @property
    def onboarding_completed(self) -> bool:
        return self.db.get_bool_setting("onboarding_completed", False)

    @onboarding_completed.setter
    def onboarding_completed(self, value: bool):
        self.set("onboarding_completed", "1" if value else "0")


if __name__ == "__main__":
    db = Database(":memory:")
    s = Settings(db)

    print("Тип перевода:", s.translation_type)
    print("Язык перевода:", s.translation_lang)

    s.set_translation_type_for_series(41893, "voice")
    s.set_translation_lang_for_series(41893, "en")
    print("Для 41893: type=", s.get_translation_type_for_series(41893),
          "lang=", s.get_translation_lang_for_series(41893))
    print("Для 12345: type=", s.get_translation_type_for_series(12345),
          "lang=", s.get_translation_lang_for_series(12345))

    db.close()