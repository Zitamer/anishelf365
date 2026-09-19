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
from core import i18n


# ============================================================
# Autouse: гарантируем, что локализация загружена
# ============================================================

@pytest.fixture(autouse=True)
def _ensure_i18n_loaded():
    """
    Загружает язык перед каждым тестом.

    Без этого UI-тесты, запущенные в одиночку (например,
    `pytest tests/test_ui_dialogs.py`), получают от i18n.tr()
    сам ключ вместо перевода — потому что локаль подгружалась
    «побочным эффектом» от test_i18n.py при полном прогоне.
    """
    i18n.load("ru")
    yield


# ============================================================
# Базовые фикстуры
# ============================================================

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


# ============================================================
# Моки для API
# ============================================================

@pytest.fixture
def mock_api(mocker, sample_series_data):
    """Мок Anime365API."""
    api = mocker.MagicMock()
    api.get_series.return_value = sample_series_data
    api.get_translations.return_value = []
    api.get_embed.return_value = None
    api.has_token.return_value = True
    api.check_token.return_value = (True, "")
    return api


@pytest.fixture
def mock_requests_head(mocker):
    """Мок requests.head — возвращает размер файла 1000 байт."""
    def fake_head(url, **kwargs):
        resp = mocker.MagicMock()
        resp.status_code = 200
        resp.headers = {"content-length": "1000"}
        return resp
    return mocker.patch("requests.head", side_effect=fake_head)


@pytest.fixture
def mock_requests_get_simple(mocker):
    """
    Мок requests.get — отдаёт ровно 1000 байт и корректно работает
    как контекстный менеджер.
    """

    class FakeRaw:
        def __init__(self, total: int = 1000):
            self._remaining = total

        def read(self, size: int = -1) -> bytes:
            if self._remaining <= 0:
                return b""
            if size is None or size <= 0:
                n = self._remaining
            else:
                n = min(int(size), self._remaining)
            self._remaining -= n
            return b"x" * n

    class FakeResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {
                "content-length": "1000",
                "content-range": "bytes 0-999/1000",
            }
            self.raw = FakeRaw(1000)

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=8192):
            while True:
                chunk = self.raw.read(chunk_size)
                if not chunk:
                    return
                yield chunk

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_get(url, **kwargs):
        return FakeResponse()

    return mocker.patch("requests.get", side_effect=fake_get)


# ============================================================
# UI-фикстуры
# ============================================================

@pytest.fixture(scope="session")
def qapp_args():
    """Аргументы для QApplication — без реального окна."""
    return ["pytest"]


@pytest.fixture
def download_manager():
    """Настоящий DownloadManager (QObject со сигналами)."""
    from ui_qt.download_manager import DownloadManager
    mgr = DownloadManager()
    yield mgr
    try:
        mgr.shutdown(timeout_ms=500)
    except Exception:
        pass


@pytest.fixture
def mock_app_for_ui(mocker, db, settings, mock_api):
    """
    Минимальный мок AnimeLibraryApp для диалогов.
    Без download_manager — только db/settings/api.
    """
    app = mocker.MagicMock()
    app.db = db
    app.settings = settings
    app.api = mock_api
    app.logger = mocker.MagicMock()
    return app


@pytest.fixture
def mock_app_full(mocker, db, settings, mock_api, download_manager):
    """
    Более полный мок app для LibraryView / SeriesView.
    Содержит download_manager со сигналами и заглушки методов навигации.
    """
    app = mocker.MagicMock()
    app.db = db
    app.settings = settings
    app.api = mock_api
    app.logger = mocker.MagicMock()
    app.download_manager = download_manager

    # Навигационные методы — просто ничего не делают, но факт вызова ловим.
    app.show_library = mocker.MagicMock()
    app.show_series = mocker.MagicMock()
    app.show_settings = mocker.MagicMock()
    app.show_add_series = mocker.MagicMock()
    app.show_onboarding = mocker.MagicMock()
    return app


@pytest.fixture
def seeded_db(db, sample_series_data, settings, tmp_library):
    """
    БД с одним сериалом и двумя эпизодами + library_path в настройках.
    """
    db.upsert_series(sample_series_data)
    db.upsert_episodes(sample_series_data["episodes"])
    settings.library_path = tmp_library
    return db