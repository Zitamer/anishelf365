# -*- coding: utf-8 -*-
"""SQLite: схема и методы работы с БД."""

import json
import os
import sqlite3
from datetime import datetime

from core.constants import DB_PATH


def _now() -> str:
    """Текущая дата-время в формате для SQLite (ISO-совместимо)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


SCHEMA = """
PRAGMA foreign_keys = ON;

-- ============================================================
-- Метаданные сериалов
-- ============================================================
CREATE TABLE IF NOT EXISTS series_meta (
    series_id           INTEGER PRIMARY KEY,
    title               TEXT,
    title_original      TEXT,
    title_en            TEXT,
    description         TEXT,
    year                INTEGER,
    season              TEXT,
    type                TEXT,
    genres              TEXT,
    url                 TEXT,
    poster_url          TEXT,
    poster_local        TEXT,
    episodes_count      INTEGER DEFAULT 0,
    is_airing           INTEGER DEFAULT 0,
    new_episodes_count  INTEGER DEFAULT 0,
    updated_at          DATETIME,
    last_full_update    DATETIME
);

-- ============================================================
-- Метаданные эпизодов
-- ============================================================
CREATE TABLE IF NOT EXISTS episodes_meta (
    episode_id      INTEGER PRIMARY KEY,
    series_id       INTEGER NOT NULL,
    number          REAL,
    title           TEXT,
    episode_type    TEXT,
    duration        INTEGER,
    air_date        TEXT,
    updated_at      DATETIME,
    FOREIGN KEY (series_id) REFERENCES series_meta(series_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_episodes_series ON episodes_meta(series_id);
CREATE INDEX IF NOT EXISTS idx_episodes_number ON episodes_meta(series_id, number);

-- ============================================================
-- Локальные файлы
-- ============================================================
CREATE TABLE IF NOT EXISTS local_files (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id        INTEGER NOT NULL,
    episode_id       INTEGER NOT NULL,
    episode_number   REAL,
    translation_id   INTEGER NOT NULL,
    relative_path    TEXT NOT NULL,
    subtitle_path    TEXT,
    author           TEXT,
    translation_type TEXT,
    translation_lang TEXT,
    quality          TEXT,
    file_size        INTEGER DEFAULT 0,
    downloaded_at    DATETIME,
    FOREIGN KEY (series_id) REFERENCES series_meta(series_id) ON DELETE CASCADE,
    FOREIGN KEY (episode_id) REFERENCES episodes_meta(episode_id) ON DELETE CASCADE,
    UNIQUE (episode_id, translation_id)
);

CREATE INDEX IF NOT EXISTS idx_files_series ON local_files(series_id);
CREATE INDEX IF NOT EXISTS idx_files_episode ON local_files(episode_id);
CREATE INDEX IF NOT EXISTS idx_files_type ON local_files(translation_type);

-- ============================================================
-- Прогресс просмотра
-- ============================================================
CREATE TABLE IF NOT EXISTS watch_progress (
    episode_id      INTEGER PRIMARY KEY,
    position        REAL DEFAULT 0,
    duration        REAL DEFAULT 0,
    watched         INTEGER DEFAULT 0,
    last_watched    DATETIME,
    FOREIGN KEY (episode_id) REFERENCES episodes_meta(episode_id) ON DELETE CASCADE
);

-- ============================================================
-- Настройки (key-value)
-- ============================================================
CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT
);

-- ============================================================
-- Игнорируемые сериалы
-- ============================================================
CREATE TABLE IF NOT EXISTS ignored_series (
    series_id   INTEGER PRIMARY KEY,
    title       TEXT,
    reason      TEXT,
    added_at    DATETIME
);
"""


class Database:
    """Обёртка над SQLite с методами для всех таблиц."""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        # Для :memory: или имени файла без директории — не создаём папку
        if path != ":memory:":
            dir_name = os.path.dirname(path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Включаем каскадное удаление (per-connection)
        self.conn.execute("PRAGMA foreign_keys = ON")

        self.conn.executescript(SCHEMA)

        # executescript может сбросить PRAGMA — устанавливаем ещё раз
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.commit()

        # Миграции
        self._migrate()

    def _migrate(self):
        """Добавляет новые колонки в существующие таблицы."""
        # translation_lang в local_files
        cur = self.conn.execute("PRAGMA table_info(local_files)")
        cols = {row["name"] for row in cur.fetchall()}
        if "translation_lang" not in cols:
            self.conn.execute(
                "ALTER TABLE local_files ADD COLUMN translation_lang TEXT"
            )
            self.conn.commit()

    # ============================================================
    # Settings
    # ============================================================

    def get_setting(self, key: str, default=None):
        cur = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value):
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    def get_int_setting(self, key: str, default: int = 0) -> int:
        val = self.get_setting(key)
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def get_float_setting(self, key: str, default: float = 0.0) -> float:
        val = self.get_setting(key)
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def get_bool_setting(self, key: str, default: bool = False) -> bool:
        val = self.get_setting(key)
        if val is None:
            return default
        return str(val).lower() in ("1", "true", "yes", "on")

    # ============================================================
    # Series
    # ============================================================

    def upsert_series(self, data: dict):
        """UPSERT сериала из ответа /series/{id}."""
        titles = data.get("titles") or {}
        genres = data.get("genres") or []
        genres_json = json.dumps(
            [g.get("title") for g in genres if g.get("title")],
            ensure_ascii=False,
        )
        descriptions = data.get("descriptions") or []
        description = descriptions[0].get("value", "") if descriptions else ""

        self.conn.execute(
            """
            INSERT INTO series_meta
                (series_id, title, title_original, title_en, description,
                 year, season, type, genres, url, poster_url,
                 episodes_count, is_airing, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(series_id) DO UPDATE SET
                title = excluded.title,
                title_original = excluded.title_original,
                title_en = excluded.title_en,
                description = excluded.description,
                year = excluded.year,
                season = excluded.season,
                type = excluded.type,
                genres = excluded.genres,
                url = excluded.url,
                poster_url = excluded.poster_url,
                episodes_count = excluded.episodes_count,
                is_airing = excluded.is_airing,
                updated_at = excluded.updated_at
            """,
            (
                data.get("id"),
                data.get("title") or titles.get("ru") or titles.get("romaji"),
                titles.get("romaji"),
                titles.get("en"),
                description,
                data.get("year"),
                data.get("season"),
                data.get("type"),
                genres_json,
                data.get("url"),
                data.get("posterUrl"),
                len(data.get("episodes") or []),
                1 if data.get("isAiring") else 0,
                _now(),
            ),
        )
        self.conn.commit()

    def get_series(self, series_id: int):
        cur = self.conn.execute(
            "SELECT * FROM series_meta WHERE series_id = ?", (series_id,)
        )
        return cur.fetchone()

    def list_series(self):
        cur = self.conn.execute(
            "SELECT * FROM series_meta ORDER BY title COLLATE NOCASE"
        )
        return cur.fetchall()

    def list_airing_series(self):
        cur = self.conn.execute(
            "SELECT * FROM series_meta WHERE is_airing = 1 "
            "ORDER BY title COLLATE NOCASE"
        )
        return cur.fetchall()

    def set_local_poster(self, series_id: int, path: str):
        self.conn.execute(
            "UPDATE series_meta SET poster_local = ? WHERE series_id = ?",
            (path, series_id),
        )
        self.conn.commit()

    def set_new_episodes_count(self, series_id: int, count: int):
        self.conn.execute(
            "UPDATE series_meta SET new_episodes_count = ? WHERE series_id = ?",
            (count, series_id),
        )
        self.conn.commit()

    def reset_new_episodes_count(self, series_id: int):
        self.conn.execute(
            "UPDATE series_meta SET new_episodes_count = 0 WHERE series_id = ?",
            (series_id,),
        )
        self.conn.commit()

    def delete_series(self, series_id: int):
        """Удаляет сериал и все связанные данные (каскадно)."""
        self.conn.execute("DELETE FROM series_meta WHERE series_id = ?", (series_id,))
        self.conn.commit()

    def set_full_update_time(self, series_id: int, dt: str = None):
        dt = dt or _now()
        self.conn.execute(
            "UPDATE series_meta SET last_full_update = ? WHERE series_id = ?",
            (dt, series_id),
        )
        self.conn.commit()

    # ============================================================
    # Episodes
    # ============================================================

    def upsert_episode(self, ep: dict):
        self.conn.execute(
            """
            INSERT INTO episodes_meta
                (episode_id, series_id, number, title, episode_type,
                 duration, air_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(episode_id) DO UPDATE SET
                series_id = excluded.series_id,
                number = excluded.number,
                title = excluded.title,
                episode_type = excluded.episode_type,
                duration = excluded.duration,
                air_date = excluded.air_date,
                updated_at = excluded.updated_at
            """,
            (
                ep.get("id"),
                ep.get("seriesId"),
                ep.get("episodeInt") if ep.get("episodeInt") is not None else ep.get("episode_number"),
                ep.get("episodeTitle") or "",
                ep.get("episodeType"),
                ep.get("duration"),
                ep.get("firstUploadedDateTime"),
                _now(),
            ),
        )
        self.conn.commit()

    def upsert_episodes(self, episodes: list):
        """Массовый UPSERT эпизодов (в одной транзакции)."""
        now = _now()
        rows = []
        for ep in episodes:
            rows.append((
                ep.get("id"),
                ep.get("seriesId"),
                ep.get("episodeInt") if ep.get("episodeInt") is not None else ep.get("episode_number"),
                ep.get("episodeTitle") or "",
                ep.get("episodeType"),
                ep.get("duration"),
                ep.get("firstUploadedDateTime"),
                now,
            ))
        self.conn.executemany(
            """
            INSERT INTO episodes_meta
                (episode_id, series_id, number, title, episode_type,
                 duration, air_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(episode_id) DO UPDATE SET
                series_id = excluded.series_id,
                number = excluded.number,
                title = excluded.title,
                episode_type = excluded.episode_type,
                duration = excluded.duration,
                air_date = excluded.air_date,
                updated_at = excluded.updated_at
            """,
            rows,
        )
        self.conn.commit()

    def get_episode(self, episode_id: int):
        cur = self.conn.execute(
            "SELECT * FROM episodes_meta WHERE episode_id = ?", (episode_id,)
        )
        return cur.fetchone()

    def list_episodes(self, series_id: int):
        cur = self.conn.execute(
            "SELECT * FROM episodes_meta WHERE series_id = ? ORDER BY number",
            (series_id,),
        )
        return cur.fetchall()

    def list_episodes_by_type(self, series_id: int, episode_type: str):
        cur = self.conn.execute(
            "SELECT * FROM episodes_meta "
            "WHERE series_id = ? AND episode_type = ? ORDER BY number",
            (series_id, episode_type),
        )
        return cur.fetchall()

    # ============================================================
    # Local files
    # ============================================================

    def add_local_file(
        self,
        series_id: int,
        episode_id: int,
        episode_number,
        translation_id: int,
        relative_path: str,
        subtitle_path: str = None,
        author: str = None,
        translation_type: str = None,
        translation_lang: str = None,
        quality: str = None,
        file_size: int = 0,
    ):
        self.conn.execute(
            """
            INSERT INTO local_files
                (series_id, episode_id, episode_number, translation_id,
                 relative_path, subtitle_path, author, translation_type,
                 translation_lang, quality, file_size, downloaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(episode_id, translation_id) DO UPDATE SET
                relative_path = excluded.relative_path,
                subtitle_path = excluded.subtitle_path,
                author = excluded.author,
                translation_type = excluded.translation_type,
                translation_lang = excluded.translation_lang,
                quality = excluded.quality,
                file_size = excluded.file_size,
                downloaded_at = excluded.downloaded_at
            """,
            (
                series_id, episode_id, episode_number, translation_id,
                relative_path, subtitle_path, author, translation_type,
                translation_lang, quality, file_size, _now(),
            ),
        )
        self.conn.commit()

    def get_local_file(self, episode_id: int, translation_id: int):
        cur = self.conn.execute(
            "SELECT * FROM local_files WHERE episode_id = ? AND translation_id = ?",
            (episode_id, translation_id),
        )
        return cur.fetchone()

    def list_local_files(self, series_id: int):
        cur = self.conn.execute(
            "SELECT * FROM local_files WHERE series_id = ? ORDER BY episode_number",
            (series_id,),
        )
        return cur.fetchall()

    def list_files_for_episode(self, episode_id: int):
        cur = self.conn.execute(
            "SELECT * FROM local_files WHERE episode_id = ?",
            (episode_id,),
        )
        return cur.fetchall()

    def delete_local_file(self, episode_id: int, translation_id: int):
        self.conn.execute(
            "DELETE FROM local_files WHERE episode_id = ? AND translation_id = ?",
            (episode_id, translation_id),
        )
        self.conn.commit()

    def delete_files_for_episode(self, episode_id: int):
        self.conn.execute("DELETE FROM local_files WHERE episode_id = ?", (episode_id,))
        self.conn.commit()

    def delete_files_for_series(self, series_id: int):
        self.conn.execute("DELETE FROM local_files WHERE series_id = ?", (series_id,))
        self.conn.commit()

    def get_downloaded_episode_numbers(self, series_id: int) -> set:
        cur = self.conn.execute(
            "SELECT DISTINCT episode_number FROM local_files "
            "WHERE series_id = ? AND episode_number IS NOT NULL",
            (series_id,),
        )
        return {row["episode_number"] for row in cur.fetchall()}

    def get_downloaded_authors(self, series_id: int):
        cur = self.conn.execute(
            "SELECT DISTINCT author FROM local_files "
            "WHERE series_id = ? AND author IS NOT NULL ORDER BY author",
            (series_id,),
        )
        return [row["author"] for row in cur.fetchall()]

    # ============================================================
    # Watch progress
    # ============================================================

    def set_progress(self, episode_id: int, position: float, duration: float,
                     watched: bool = None):
        existing = self.get_progress(episode_id)
        watched_val = existing["watched"] if existing else 0
        if watched is not None:
            watched_val = 1 if watched else 0

        self.conn.execute(
            """
            INSERT INTO watch_progress
                (episode_id, position, duration, watched, last_watched)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(episode_id) DO UPDATE SET
                position = excluded.position,
                duration = excluded.duration,
                watched = excluded.watched,
                last_watched = excluded.last_watched
            """,
            (episode_id, position, duration, watched_val, _now()),
        )
        self.conn.commit()

    def get_progress(self, episode_id: int):
        cur = self.conn.execute(
            "SELECT * FROM watch_progress WHERE episode_id = ?", (episode_id,)
        )
        return cur.fetchone()

    def set_watched(self, episode_id: int, watched: bool):
        existing = self.get_progress(episode_id)
        if existing:
            self.conn.execute(
                "UPDATE watch_progress SET watched = ?, last_watched = ? "
                "WHERE episode_id = ?",
                (1 if watched else 0, _now(), episode_id),
            )
        else:
            self.conn.execute(
                "INSERT INTO watch_progress "
                "(episode_id, position, duration, watched, last_watched) "
                "VALUES (?, 0, 0, ?, ?)",
                (episode_id, 1 if watched else 0, _now()),
            )
        self.conn.commit()

    def set_all_watched(self, series_id: int, watched: bool = True):
        episodes = self.list_episodes(series_id)
        for ep in episodes:
            self.set_watched(ep["episode_id"], watched)

    def count_watched(self, series_id: int) -> int:
        cur = self.conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM watch_progress wp
            JOIN episodes_meta em ON em.episode_id = wp.episode_id
            WHERE em.series_id = ? AND wp.watched = 1
            """,
            (series_id,),
        )
        return cur.fetchone()["cnt"]

    def first_unwatched(self, series_id: int, episode_type: str = "tv"):
        cur = self.conn.execute(
            """
            SELECT em.* FROM episodes_meta em
            LEFT JOIN watch_progress wp ON wp.episode_id = em.episode_id
            WHERE em.series_id = ? AND em.episode_type = ?
              AND COALESCE(wp.watched, 0) = 0
            ORDER BY em.number
            LIMIT 1
            """,
            (series_id, episode_type),
        )
        return cur.fetchone()

    # ============================================================
    # Ignored series
    # ============================================================

    def add_ignored(self, series_id: int, title: str = None, reason: str = None):
        """Добавляет сериал в список игнорирования."""
        self.conn.execute(
            """
            INSERT INTO ignored_series(series_id, title, reason, added_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(series_id) DO UPDATE SET
                title = excluded.title,
                reason = excluded.reason,
                added_at = excluded.added_at
            """,
            (series_id, title, reason, _now()),
        )
        self.conn.commit()

    def remove_ignored(self, series_id: int):
        """Убирает сериал из списка игнорирования."""
        self.conn.execute(
            "DELETE FROM ignored_series WHERE series_id = ?", (series_id,)
        )
        self.conn.commit()

    def is_ignored(self, series_id: int) -> bool:
        """Проверяет, находится ли сериал в списке игнорирования."""
        cur = self.conn.execute(
            "SELECT 1 FROM ignored_series WHERE series_id = ? LIMIT 1",
            (series_id,),
        )
        return cur.fetchone() is not None

    def list_ignored(self):
        """Возвращает список игнорируемых сериалов."""
        cur = self.conn.execute(
            "SELECT * FROM ignored_series ORDER BY added_at DESC"
        )
        return cur.fetchall()

    def count_ignored(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) AS cnt FROM ignored_series")
        return cur.fetchone()["cnt"]

    # ============================================================
    # Служебное
    # ============================================================

    def close(self):
        self.conn.close()