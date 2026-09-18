# -*- coding: utf-8 -*-
"""Общие фикстуры для тестов."""

import os
import sys
import pytest

# Чтобы pytest видел наш код (core, ui_qt, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.db import Database
from core.settings import Settings


@pytest.fixture
def db():
    """БД в памяти для каждого теста."""
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def settings(db):
    """Настройки поверх in-memory БД."""
    return Settings(db)


@pytest.fixture
def tmp_library(tmp_path):
    """Временная папка, имитирующая библиотеку."""
    lib = tmp_path / "library"
    lib.mkdir()
    return str(lib)


@pytest.fixture
def sample_series_data():
    """Мок ответа /series/{id} из API."""
    return {
        "id": 41893,
        "title": "Табакошка / Yani Neko",
        "titles": {
            "ru": "Табакошка",
            "romaji": "Yani Neko",
            "en": "Chainsmoker Cat",
        },
        "year": 2026,
        "season": "Лето 2026",
        "type": "tv",
        "isAiring": 1,
        "url": "https://smotret-anime.org/catalog/yani-neko-41893",
        "posterUrl": "https://example.com/poster.jpg",
        "genres": [{"title": "Комедия"}, {"title": "Сейнен"}],
        "descriptions": [{"value": "Описание..."}],
        "episodes": [
            {"id": 380000, "seriesId": 41893, "episodeInt": 1,
             "episodeType": "tv", "episodeTitle": "Пилот"},
            {"id": 380001, "seriesId": 41893, "episodeInt": 2,
             "episodeType": "tv", "episodeTitle": ""},
        ],
    }