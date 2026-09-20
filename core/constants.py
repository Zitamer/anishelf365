# -*- coding: utf-8 -*-
"""Глобальные константы проекта."""

import os
import sys

# ---------- Версия ----------
APP_VERSION = "0.1.0"
APP_NAME = "AniShelf365"

# ---------- Пороги и тайминги ----------
WATCHED_THRESHOLD = 0.9
CHECK_COOLDOWN_MINUTES = 5
DAILY_CHECK_HOURS = 24
BANNER_SNOOZE_MINUTES = 60
BANNER_TIMER_MINUTES = 60
FULL_UPDATE_DAYS = 21
COVER_CACHE_DAYS = 21
MASS_DOWNLOAD_MIN_COVERAGE = 0.5
PROGRESS_SAVE_INTERVAL = 5
TOAST_TIMEOUT_MS = 10_000
FULLSCREEN_PANEL_HIDE_MS = 3000

# ---------- API ----------
API_BASE_URL = "https://smotret-anime.app/api"
SITE_BASE_URL = "https://smotret-anime.org"
ASS_DOWNLOAD_URL = SITE_BASE_URL + "/translations/ass/{translation_id}?download=1"
CLIENTS_PAGE = SITE_BASE_URL + "/api/clients"
VLC_DOWNLOAD_PAGE = "https://www.videolan.org/vlc/"

# ---------- Пути ----------
if getattr(sys, "frozen", False):
    # Запущены из собранного .exe (PyInstaller).
    #   sys._MEIPASS — папка со встроенными ресурсами
    #                  (dist/AniShelf365/_internal для onedir)
    #   sys.executable — путь к .exe, рядом с ним лежит data/
    BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    BASE_DIR = BUNDLE_DIR

# Данные пишутся рядом с .exe (в из исходников — в корне проекта).
DATA_DIR = os.path.join(BASE_DIR, "data")
COVERS_DIR = os.path.join(DATA_DIR, "covers")

# Ресурсы читаются из bundle (в .exe они упакованы в _internal).
LOCALES_DIR = os.path.join(BUNDLE_DIR, "locales")
ASSETS_DIR = os.path.join(BUNDLE_DIR, "assets")

DB_PATH = os.path.join(DATA_DIR, "library.db")
TOKEN_PATH = os.path.join(DATA_DIR, "token.json")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
LOG_PATH = os.path.join(DATA_DIR, "app.log")

# ---------- Логирование ----------
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3

# ---------- VLC ----------
VLC_STANDARD_PATHS = [
    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    r"D:\Program Files\VideoLAN\VLC\vlc.exe",
    r"D:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    "/usr/bin/vlc",
    "/usr/local/bin/vlc",
    "/Applications/VLC.app/Contents/MacOS/VLC",
]

LIBVLC_STANDARD_DIRS = [
    r"C:\Program Files\VideoLAN\VLC",
    r"C:\Program Files (x86)\VideoLAN\VLC",
    r"D:\Program Files\VideoLAN\VLC",
    r"D:\Program Files (x86)\VideoLAN\VLC",
    "/usr/lib/x86_64-linux-gnu",
    "/usr/lib",
    "/Applications/VLC.app/Contents/MacOS/lib",
]

# ---------- Языки интерфейса ----------
DEFAULT_LANGUAGE = "en"
AVAILABLE_LANGUAGES = ["en", "ru"]

# ---------- Типы переводов ----------
# Порядок в выпадающем списке
TRANSLATION_TYPES = ["sub", "voice", "raw"]
DEFAULT_TRANSLATION_TYPE = "sub"

# ---------- Языки переводов ----------
# Порядок в выпадающем списке
TRANSLATION_LANGS = ["ru", "en", "ja"]
DEFAULT_TRANSLATION_LANG = "ru"

# Человекочитаемые названия языков переводов
TRANSLATION_LANG_NAMES = {
    "ru": "Русский",
    "en": "English",
    "ja": "日本語",
}

# ---------- Размеры UI ----------
LIBRARY_TILE_W = 220
LIBRARY_TILE_H = 360
LIBRARY_COVER_W = 200
LIBRARY_COVER_H = 300

SERIES_COVER_W = 300
SERIES_COVER_H = 430