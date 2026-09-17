# -*- coding: utf-8 -*-
"""Локализация: загрузка JSON-файлов и функция tr()."""

import json
import os

from core.constants import LOCALES_DIR, DEFAULT_LANGUAGE


_current_lang = DEFAULT_LANGUAGE
_strings: dict = {}
_fallback_strings: dict = {}


def available_languages() -> list:
    """Список доступных языков (по файлам в locales/)."""
    if not os.path.isdir(LOCALES_DIR):
        return [DEFAULT_LANGUAGE]
    langs = []
    for f in os.listdir(LOCALES_DIR):
        if f.endswith(".json"):
            langs.append(f[:-5])
    return sorted(langs) or [DEFAULT_LANGUAGE]


def load(lang: str) -> bool:
    """Загружает строки для указанного языка. Fallback — английский."""
    global _current_lang, _strings, _fallback_strings

    _fallback_strings = _load_file(DEFAULT_LANGUAGE) or {}

    if lang == DEFAULT_LANGUAGE:
        _strings = _fallback_strings
        _current_lang = lang
        return True

    loaded = _load_file(lang)
    if loaded is None:
        _strings = _fallback_strings
        _current_lang = DEFAULT_LANGUAGE
        return False

    _strings = loaded
    _current_lang = lang
    return True


def _load_file(lang: str) -> dict | None:
    path = os.path.join(LOCALES_DIR, f"{lang}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_current_language() -> str:
    return _current_lang


def tr(key: str, **kwargs) -> str:
    """Возвращает строку по ключу. Поддерживает подстановку."""
    s = _strings.get(key)
    if s is None:
        s = _fallback_strings.get(key)
    if s is None:
        return key

    if kwargs:
        try:
            return s.format(**kwargs)
        except (KeyError, IndexError):
            return s
    return s


if __name__ == "__main__":
    print("Доступные языки:", available_languages())

    print("\n--- Английский (по умолчанию) ---")
    load("en")
    print(tr("app.title"))
    print(tr("library.found", count=12))
    print(tr("series.continue_from", number=4))

    print("\n--- Русский ---")
    load("ru")
    print(tr("app.title"))
    print(tr("library.found", count=12))
    print(tr("series.continue_from", number=4))

    print("\n--- Несуществующий ключ ---")
    print(tr("nonexistent.key"))