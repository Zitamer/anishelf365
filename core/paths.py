# -*- coding: utf-8 -*-
"""Работа с путями библиотеки. Всё по ID."""

import os
import re


# ============================================================
# Относительные пути (хранятся в БД, всегда с '/')
# ============================================================

def series_rel_dir(series_id: int) -> str:
    """Относительная папка сериала: '<series_id>'."""
    return str(series_id)


def video_rel_path(series_id: int, episode_id: int, translation_id: int) -> str:
    """'41893/380000_5931743.mp4'."""
    return f"{series_id}/{episode_id}_{translation_id}.mp4"


def subtitle_rel_path(series_id: int, episode_id: int, translation_id: int) -> str:
    """'41893/380000_5931743.ass'."""
    return f"{series_id}/{episode_id}_{translation_id}.ass"


def cover_rel_path(series_id: int) -> str:
    """'41893.jpg' (внутри COVERS_DIR)."""
    return f"{series_id}.jpg"


# ============================================================
# Абсолютные пути
# ============================================================

def _join(*parts) -> str:
    """Собирает путь и приводит к нативному виду."""
    return os.path.normpath(os.path.join(*[str(p) for p in parts]))


def abs_series_dir(library_path: str, series_id: int) -> str:
    """Абсолютный путь к папке сериала."""
    return _join(library_path, series_id)


def abs_video_path(library_path: str, series_id: int,
                   episode_id: int, translation_id: int) -> str:
    """Абсолютный путь к видео."""
    return _join(library_path, series_id, f"{episode_id}_{translation_id}.mp4")


def abs_subtitle_path(library_path: str, series_id: int,
                      episode_id: int, translation_id: int) -> str:
    """Абсолютный путь к субтитрам."""
    return _join(library_path, series_id, f"{episode_id}_{translation_id}.ass")


def abs_from_rel(library_path: str, rel_path: str) -> str:
    """Собирает абсолютный путь из library_path и относительного."""
    return os.path.normpath(os.path.join(library_path, rel_path))


# ============================================================
# Парсинг имён файлов
# ============================================================

FILE_PATTERN = re.compile(r"^(\d+)_(\d+)\.(mp4|ass|srt|vtt)$", re.IGNORECASE)


def parse_filename(filename: str) -> tuple | None:
    """
    Разбирает имя файла '<episode_id>_<translation_id>.<ext>'.
    Возвращает (episode_id, translation_id, ext) или None.
    """
    m = FILE_PATTERN.match(filename)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), m.group(3).lower()


def parse_series_dirname(dirname: str) -> int | None:
    """Имя папки — это series_id (число)."""
    return int(dirname) if dirname.isdigit() else None


# ============================================================
# Утилиты
# ============================================================

def sanitize_filename(name: str) -> str:
    """Убирает недопустимые символы из имени файла."""
    return re.sub(r'[\\/*?:"<>|]', "_", str(name))


def ensure_dir(path: str):
    """Создаёт директорию, если её нет."""
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def is_video_file(filename: str) -> bool:
    return filename.lower().endswith(".mp4")


def is_subtitle_file(filename: str) -> bool:
    return filename.lower().endswith((".ass", ".srt", ".vtt"))


def file_size(path: str) -> int:
    """Размер файла в байтах (0, если файл недоступен)."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0