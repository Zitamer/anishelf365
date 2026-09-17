# -*- coding: utf-8 -*-
"""Сканирование библиотеки: наполнение БД метаданными и файлами."""

import os

from core import paths as P
from core.api import Anime365API
from core.covers import get_or_download, cover_path
from core.db import Database


# ============================================================
# Результат сканирования
# ============================================================

class ScanStats:
    def __init__(self):
        self.series_found = 0        # всего папок с series_id
        self.series_new = 0          # новых сериалов добавлено
        self.series_updated = 0      # обновлено метаданных
        self.series_failed = 0       # не удалось получить из API
        self.episodes_found = 0      # найдено эпизодов в API
        self.files_found = 0         # найдено локальных mp4
        self.files_new = 0           # новых файлов добавлено в БД
        self.files_updated = 0       # файлов обновлено

    def to_dict(self):
        return {
            "series_found": self.series_found,
            "series_new": self.series_new,
            "series_updated": self.series_updated,
            "series_failed": self.series_failed,
            "episodes_found": self.episodes_found,
            "files_found": self.files_found,
            "files_new": self.files_new,
            "files_updated": self.files_updated,
        }

    def __repr__(self):
        return f"ScanStats({self.to_dict()})"


# ============================================================
# Основная функция: сканирование всей библиотеки
# ============================================================

def scan_library(db: Database, api: Anime365API, library_path: str,
                 progress_cb=None, stop_flag=None) -> ScanStats:
    """
    Сканирует библиотеку.

    Параметры:
      db           — Database
      api          — Anime365API
      library_path — корень библиотеки
      progress_cb  — функция(current, total, series_id) для прогресса
      stop_flag    — функция, возвращающая True для прерывания

    Возвращает ScanStats.
    """
    stats = ScanStats()

    if not library_path or not os.path.isdir(library_path):
        return stats

    # Собираем список папок с числовыми именами
    subdirs = []
    for name in sorted(os.listdir(library_path)):
        full = os.path.join(library_path, name)
        if not os.path.isdir(full):
            continue
        sid = P.parse_series_dirname(name)
        if sid is not None:
            subdirs.append((sid, full))

    total = len(subdirs)
    if total == 0:
        return stats

    for idx, (series_id, series_dir) in enumerate(subdirs, start=1):
        if stop_flag and stop_flag():
            break

        if progress_cb:
            progress_cb(idx, total, series_id)

        stats.series_found += 1

        # ---- 1. Метаданные сериала ----
        row = db.get_series(series_id)
        if row is None:
            if not _load_series_from_api(db, api, series_id, stats):
                stats.series_failed += 1
                continue
            stats.series_new += 1
            row = db.get_series(series_id)

        # ---- 2. Эпизоды ----
        episodes = db.list_episodes(series_id)
        if not episodes:
            data = api.get_series(series_id)
            if data:
                eps = data.get("episodes") or []
                if eps:
                    db.upsert_episodes(eps)
                    stats.episodes_found += len(eps)
                    episodes = db.list_episodes(series_id)

        # ---- 3. Локальные файлы ----
        _scan_files_in_dir(db, series_id, series_dir, library_path, stats)

    return stats


# ============================================================
# Сканирование одного сериала
# ============================================================

def scan_series_files(db: Database, series_id: int, library_path: str) -> int:
    """
    Сканирует файлы одного сериала и добавляет их в БД.
    Возвращает количество найденных .mp4.

    Используется, например, после добавления тайтла через диалог,
    когда метаданные уже загружены и нужно найти локальные файлы.
    """
    if not library_path:
        return 0
    series_dir = os.path.join(library_path, str(series_id))
    if not os.path.isdir(series_dir):
        return 0

    stats = ScanStats()
    _scan_files_in_dir(db, series_id, series_dir, library_path, stats)
    return stats.files_found


# ============================================================
# Загрузка метаданных сериала
# ============================================================

def _load_series_from_api(db: Database, api: Anime365API,
                          series_id: int, stats: ScanStats) -> bool:
    """Загружает метаданные сериала из API и сохраняет в БД."""
    data = api.get_series(series_id)
    if not data:
        return False

    db.upsert_series(data)

    episodes = data.get("episodes") or []
    if episodes:
        db.upsert_episodes(episodes)
        stats.episodes_found += len(episodes)

    # Обложка
    poster_url = data.get("posterUrl")
    if poster_url:
        local = get_or_download(series_id, poster_url)
        if local:
            db.set_local_poster(series_id, local)

    return True


# ============================================================
# Сканирование файлов в папке сериала
# ============================================================

def _scan_files_in_dir(db: Database, series_id: int, series_dir: str,
                       library_path: str, stats: ScanStats):
    """
    Ищет в папке файлы <episode_id>_<translation_id>.mp4 и .ass.
    Добавляет их в local_files.
    """
    try:
        entries = os.listdir(series_dir)
    except OSError:
        return

    # Индексируем .ass-файлы по (episode_id, translation_id)
    subtitle_index = {}
    video_files = []

    for fname in entries:
        full = os.path.join(series_dir, fname)
        if not os.path.isfile(full):
            continue
        parsed = P.parse_filename(fname)
        if not parsed:
            continue
        episode_id, translation_id, ext = parsed
        if ext == "mp4":
            video_files.append((episode_id, translation_id, full))
        elif ext in ("ass", "srt", "vtt"):
            subtitle_index[(episode_id, translation_id)] = full

    # Обрабатываем видео
    for episode_id, translation_id, video_abs in video_files:
        stats.files_found += 1

        rel_video = P.video_rel_path(series_id, episode_id, translation_id)
        sub_abs = subtitle_index.get((episode_id, translation_id))
        rel_sub = None
        if sub_abs:
            rel_sub = P.subtitle_rel_path(series_id, episode_id, translation_id)
            # Если расширение не .ass — сохраняем корректно
            ext = os.path.splitext(sub_abs)[1].lstrip(".").lower()
            if ext != "ass":
                rel_sub = rel_sub.rsplit(".", 1)[0] + f".{ext}"

        # Проверяем, есть ли уже в БД
        existing = db.get_local_file(episode_id, translation_id)

        # Ищем эпизод в БД (для number)
        ep_row = db.get_episode(episode_id)
        ep_number = ep_row["number"] if ep_row else None

        size = P.file_size(video_abs)

        db.add_local_file(
            series_id=series_id,
            episode_id=episode_id,
            episode_number=ep_number,
            translation_id=translation_id,
            relative_path=rel_video,
            subtitle_path=rel_sub,
            author=None,           # неизвестно из имени файла
            translation_type=None,
            translation_lang=None,
            quality=None,
            file_size=size,
        )

        if existing:
            stats.files_updated += 1
        else:
            stats.files_new += 1


# ============================================================
# Быстрая проверка: есть ли в папке файлы
# ============================================================

def has_any_files(library_path: str, series_id: int) -> bool:
    """Есть ли в папке сериала хоть один .mp4."""
    series_dir = P.abs_series_dir(library_path, series_id)
    if not os.path.isdir(series_dir):
        return False
    for fname in os.listdir(series_dir):
        if P.is_video_file(fname):
            return True
    return False


# ============================================================
# Тест
# ============================================================

if __name__ == "__main__":
    import sys
    from core.constants import DB_PATH, COVERS_DIR
    from core.covers import human_size

    TEST_LIBRARY = os.path.join(os.path.dirname(DB_PATH), "test_library")

    print("=== Тест scanner ===")
    print(f"Библиотека: {TEST_LIBRARY}")

    if not os.path.isdir(TEST_LIBRARY):
        print("\nПапки нет. Создайте тестовую структуру.")
        sys.exit(0)

    db = Database(":memory:")
    api = Anime365API()

    def progress(current, total, sid):
        print(f"  [{current}/{total}] Обработка сериала {sid}...")

    stats = scan_library(db, api, TEST_LIBRARY, progress_cb=progress)

    print("\n--- Результаты ---")
    print(f"Найдено папок:      {stats.series_found}")
    print(f"Новых сериалов:     {stats.series_new}")
    print(f"Ошибок API:         {stats.series_failed}")
    print(f"Эпизодов из API:    {stats.episodes_found}")
    print(f"Локальных mp4:      {stats.files_found}")
    print(f"Новых файлов в БД:  {stats.files_new}")

    print("\n--- Сериалы в БД ---")
    for row in db.list_series():
        print(f"  id={row['series_id']} title={row['title']!r}")
        eps = db.list_episodes(row['series_id'])
        print(f"    эпизодов: {len(eps)}")
        files = db.list_local_files(row['series_id'])
        print(f"    файлов:   {len(files)}")

    # Тест scan_series_files
    if db.list_series():
        sid = db.list_series()[0]["series_id"]
        print(f"\n--- scan_series_files({sid}) ---")
        found = scan_series_files(db, sid, TEST_LIBRARY)
        print(f"Найдено файлов: {found}")

    db.close()
    print("\nТест завершён.")