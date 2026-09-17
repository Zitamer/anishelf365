# -*- coding: utf-8 -*-
"""Загрузка, кэширование и очистка обложек."""

import os
import time
import requests

from PIL import Image

from core.constants import COVERS_DIR, COVER_CACHE_DAYS


# Размер превью для плиток в библиотеке
COVER_SIZE = (200, 300)

# Заголовки для запроса (365 требует Referer)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnimeLibrary/1.0",
    "Referer": "https://smotret-anime.org/",
}

# Таймаут
TIMEOUT = 20


# ============================================================
# Пути
# ============================================================

def cover_path(series_id: int, covers_dir: str = COVERS_DIR) -> str:
    """Абсолютный путь к обложке '<series_id>.jpg'."""
    return os.path.join(covers_dir, f"{series_id}.jpg")


def cover_rel_path(series_id: int) -> str:
    """Относительный путь (для хранения в БД): '<series_id>.jpg'."""
    return f"{series_id}.jpg"


def has_cover(series_id: int, covers_dir: str = COVERS_DIR) -> bool:
    return os.path.isfile(cover_path(series_id, covers_dir))


# ============================================================
# Загрузка
# ============================================================

def download_cover(series_id: int, poster_url: str,
                   covers_dir: str = COVERS_DIR,
                   force: bool = False) -> str | None:
    """
    Скачивает обложку и сохраняет как JPEG.
    Возвращает абсолютный путь или None.
    Если файл уже есть и force=False — не перекачивает.
    """
    if not poster_url:
        return None

    os.makedirs(covers_dir, exist_ok=True)
    dest = cover_path(series_id, covers_dir)

    if os.path.exists(dest) and not force:
        return dest

    try:
        r = requests.get(poster_url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.content
    except requests.RequestException:
        return None

    # Сохраняем во временный файл, потом сжимаем
    tmp = dest + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
    except OSError:
        return None

    # Открываем, ресайзим, сохраняем
    try:
        with Image.open(tmp) as img:
            img = img.convert("RGB")
            # Сохраняем соотношение сторон
            img.thumbnail(COVER_SIZE, Image.LANCZOS)
            img.save(dest, "JPEG", quality=85)
        os.remove(tmp)
        return dest
    except Exception:
        # Если что-то пошло не так — пробуем сохранить как есть
        try:
            os.replace(tmp, dest)
            return dest
        except OSError:
            try:
                os.remove(tmp)
            except OSError:
                pass
            return None


def get_or_download(series_id: int, poster_url: str,
                    covers_dir: str = COVERS_DIR) -> str | None:
    """
    Возвращает путь к локальной обложке.
    Если нет — скачивает.
    """
    path = cover_path(series_id, covers_dir)
    if os.path.exists(path):
        return path
    return download_cover(series_id, poster_url, covers_dir)


def delete_cover(series_id: int, covers_dir: str = COVERS_DIR) -> bool:
    """Удаляет обложку. Возвращает True, если удалили."""
    path = cover_path(series_id, covers_dir)
    if os.path.exists(path):
        try:
            os.remove(path)
            return True
        except OSError:
            return False
    return False


# ============================================================
# Очистка кэша
# ============================================================

def cleanup_covers(db, covers_dir: str = COVERS_DIR,
                   cache_days: int = COVER_CACHE_DAYS) -> dict:
    """
    Удаляет обложки, которые:
      1. Не связаны ни с одним сериалом в БД.
      2. Старше `cache_days` дней.

    Возвращает {'deleted': N, 'kept': M, 'freed_bytes': B}.
    """
    if not os.path.isdir(covers_dir):
        return {"deleted": 0, "kept": 0, "freed_bytes": 0}

    # Все series_id из БД
    known_ids = set()
    rows = db.list_series()
    for row in rows:
        known_ids.add(row["series_id"])

    # Все локальные обложки
    now = time.time()
    threshold = cache_days * 24 * 3600

    deleted = 0
    kept = 0
    freed = 0

    for fname in os.listdir(covers_dir):
        if not fname.lower().endswith(".jpg"):
            continue
        path = os.path.join(covers_dir, fname)
        if not os.path.isfile(path):
            continue

        # Извлекаем series_id из имени файла
        name = os.path.splitext(fname)[0]
        if not name.isdigit():
            continue
        sid = int(name)

        # Проверяем: есть ли сериал в БД И старше ли файл 3 недели
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue

        age = now - mtime
        is_orphan = sid not in known_ids
        is_old = age > threshold

        # Удаляем только если И сирота, И старая (по договорённости)
        if is_orphan and is_old:
            try:
                size = os.path.getsize(path)
                os.remove(path)
                deleted += 1
                freed += size
            except OSError:
                kept += 1
        else:
            kept += 1

    return {
        "deleted": deleted,
        "kept": kept,
        "freed_bytes": freed,
    }


def get_cache_size(covers_dir: str = COVERS_DIR) -> int:
    """Размер кэша обложек в байтах."""
    if not os.path.isdir(covers_dir):
        return 0
    total = 0
    for fname in os.listdir(covers_dir):
        path = os.path.join(covers_dir, fname)
        if os.path.isfile(path):
            try:
                total += os.path.getsize(path)
            except OSError:
                pass
    return total


def human_size(num_bytes: int) -> str:
    """Читаемый размер: 1234567 → '1.2 МБ'."""
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} ТБ"


# ============================================================
# Тест
# ============================================================

if __name__ == "__main__":
    print("=== Тест covers ===\n")

    # Тестовый сериал (Табакошка)
    series_id = 41893
    poster_url = "https://smotret-anime.app/posters/41893.18946925934.jpg"

    print("Проверка наличия обложки до загрузки:", has_cover(series_id))

    print("\n--- Скачиваем обложку ---")
    path = get_or_download(series_id, poster_url)
    if path:
        print("Сохранена:", path)
        print("Размер файла:", human_size(os.path.getsize(path)))
        print("Файл существует:", os.path.exists(path))
    else:
        print("Не удалось скачать обложку")

    print("\n--- Размер кэша ---")
    size = get_cache_size()
    print("Всего в кэше:", human_size(size))

    print("\n--- Очистка кэша (без БД, для примера) ---")

    class FakeDB:
        def list_series(self):
            return []

    result = cleanup_covers(FakeDB())
    print("Удалено:", result["deleted"])
    print("Оставлено:", result["kept"])
    print("Освобождено:", human_size(result["freed_bytes"]))