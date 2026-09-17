# -*- coding: utf-8 -*-
"""Скачивание эпизодов (видео + .ass субтитры)."""

import os
import time
import logging
import threading
import requests

from concurrent.futures import ThreadPoolExecutor, as_completed

from urllib3.exceptions import ProtocolError, IncompleteRead

from core.api import Anime365API, extract_video_urls
from core.constants import ASS_DOWNLOAD_URL
from core import paths as P


logger = logging.getLogger(__name__)


PROGRESS_UPDATE_INTERVAL = 0.2
PARALLEL_THREADS = 4
PARALLEL_MIN_SIZE = 5 * 1024 * 1024
CHUNK_SIZE = 65536
MAX_RETRIES_SIMPLE = 30
MAX_RETRIES_PART = 100


DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://smotret-anime.org/",
    "Origin": "https://smotret-anime.org",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

CDN_HEADERS = {
    "User-Agent": DOWNLOAD_HEADERS["User-Agent"],
    "Accept": "*/*",
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
}


class DownloadError(Exception):
    pass


class DownloadCancelled(Exception):
    pass


# ============================================================
# Утилиты
# ============================================================

def _headers_for(url: str) -> dict:
    if "smotret-anime.org" in url or "smotret-anime.app" in url:
        return dict(DOWNLOAD_HEADERS)
    return dict(CDN_HEADERS)


def _cleanup(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _cleanup_any(tmp: str):
    """Удаляет tmp и все tmp.N."""
    _cleanup(tmp)
    for i in range(PARALLEL_THREADS):
        _cleanup(f"{tmp}.{i}")


# ============================================================
# Основная функция
# ============================================================

def download_episode(
    api, db, library_path, series_id, episode_id, episode_number,
    translation_id, quality_label, author=None, translation_type="sub",
    translation_lang=None, progress_cb=None, cancel_check=None,
):
    t_start = time.time()
    logger.info(f"[{episode_id}] download_episode: перевод {translation_id}, "
                f"номер серии {episode_number}")

    embed = api.get_embed(translation_id)
    if not embed:
        raise DownloadError("Не удалось получить embed")

    video_urls = extract_video_urls(embed)
    if not video_urls:
        raise DownloadError("В embed нет ссылок на видео")
    if quality_label not in video_urls:
        raise DownloadError(
            f"Качество '{quality_label}' недоступно. "
            f"Доступно: {', '.join(video_urls.keys())}"
        )

    video_url = video_urls[quality_label]

    # ---- Имя файла: <series_id>/<episode_id>_<translation_id>.mp4 ----
    video_path = P.abs_video_path(
        library_path, series_id, episode_id, translation_id,
    )
    P.ensure_dir(os.path.dirname(video_path))

    logger.info(f"[{episode_id}] Скачивание видео → {video_path}")
    video_size = _download_file(
        video_url, video_path, "video", episode_id,
        progress_cb, cancel_check,
    )

    subtitle_path = None
    rel_sub = None

    if translation_type == "sub":
        subtitle_url = ASS_DOWNLOAD_URL.format(translation_id=translation_id)
        subtitle_abs = P.abs_subtitle_path(
            library_path, series_id, episode_id, translation_id,
        )
        try:
            _download_file(
                subtitle_url, subtitle_abs, "subtitles", episode_id,
                progress_cb, cancel_check,
            )
            subtitle_path = subtitle_abs
            rel_sub = P.subtitle_rel_path(series_id, episode_id, translation_id)
            logger.info(f"[{episode_id}] Субтитры скачаны")
        except DownloadError as e:
            logger.warning(f"[{episode_id}] Субтитры недоступны: {e}")

    rel_video = P.video_rel_path(series_id, episode_id, translation_id)
    db.add_local_file(
        series_id=series_id, episode_id=episode_id,
        episode_number=episode_number, translation_id=translation_id,
        relative_path=rel_video, subtitle_path=rel_sub,
        author=author, translation_type=translation_type,
        translation_lang=translation_lang, quality=quality_label,
        file_size=video_size,
    )

    if progress_cb:
        progress_cb("done", 100, video_size, video_size)

    logger.info(f"[{episode_id}] Успех за {time.time() - t_start:.1f} с")
    return video_path, subtitle_path, video_size


# ============================================================
# Диспетчер
# ============================================================

def _download_file(url, dest, stage, episode_id=None,
                   progress_cb=None, cancel_check=None) -> int:
    tmp = dest + ".part"
    P.ensure_dir(os.path.dirname(dest))
    tag = f"[{episode_id}]" if episode_id else "[?]"

    total = _probe_total_size(url)
    logger.info(f"{tag} {stage}: total={total} байт")

    try:
        if total and total >= PARALLEL_MIN_SIZE:
            try:
                _download_parallel(
                    url, tmp, total, stage, episode_id,
                    progress_cb, cancel_check,
                )
            except DownloadError as e:
                logger.warning(f"{tag} {stage}: параллельная не удалась ({e}), "
                               f"простой режим")
                _cleanup_any(tmp)
                _download_simple(
                    url, tmp, stage, episode_id,
                    progress_cb, cancel_check,
                )
        else:
            _download_simple(
                url, tmp, stage, episode_id,
                progress_cb, cancel_check,
            )

        # Проверка размера
        actual = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        if total and actual < total:
            raise DownloadError(
                f"Размер файла меньше ожидаемого: {actual} из {total} байт"
            )

        if os.path.exists(dest):
            os.remove(dest)
        os.replace(tmp, dest)

        if progress_cb:
            progress_cb(stage, 100, actual, actual)

        return actual

    except Exception:
        _cleanup_any(tmp)
        raise


def _probe_total_size(url: str) -> int:
    headers = _headers_for(url)
    try:
        r = requests.head(url, headers=headers, timeout=15, allow_redirects=True)
        if r.status_code == 200:
            size = int(r.headers.get("content-length", 0))
            if size:
                return size
    except requests.RequestException:
        pass

    try:
        h = dict(headers)
        h["Range"] = "bytes=0-0"
        r = requests.get(url, headers=h, timeout=15, stream=True)
        cr = r.headers.get("content-range")
        cl = int(r.headers.get("content-length", 0))
        r.close()
        if cr:
            try:
                return int(cr.split("/")[-1])
            except (ValueError, IndexError):
                pass
        return cl
    except (requests.RequestException, ValueError):
        return 0


# ============================================================
# Параллельная загрузка
# ============================================================

def _download_parallel(url, tmp, total, stage, episode_id,
                       progress_cb, cancel_check):
    tag = f"[{episode_id}]" if episode_id else "[?]"
    n = PARALLEL_THREADS
    part_size = total // n
    ranges = []
    for i in range(n):
        start = i * part_size
        end = (start + part_size - 1) if i < n - 1 else (total - 1)
        ranges.append((i, start, end))

    logger.info(f"{tag} {stage}: параллельная загрузка, {n} потоков, "
                f"~{part_size // 1024} КБ часть")

    progress_lock = threading.Lock()
    last_update = {"t": 0.0}
    aborted = {"v": False}
    part_paths = {i: f"{tmp}.{i}" for i, _, _ in ranges}

    def report_progress(force=False):
        if not progress_cb or not total:
            return
        now = time.time()
        with progress_lock:
            if not force and now - last_update["t"] < PROGRESS_UPDATE_INTERVAL:
                return
            last_update["t"] = now

        size = 0
        for p in part_paths.values():
            try:
                size += os.path.getsize(p)
            except OSError:
                pass
        percent = min(99, int(size / total * 100))
        progress_cb(stage, percent, size, total)

    def download_part(index: int, start: int, end: int):
        expected = end - start + 1
        part_tmp = part_paths[index]
        downloaded = os.path.getsize(part_tmp) if os.path.exists(part_tmp) else 0
        attempt = 0

        while downloaded < expected:
            if cancel_check and cancel_check():
                aborted["v"] = True
                return
            if aborted["v"]:
                return

            attempt += 1
            if attempt > MAX_RETRIES_PART:
                logger.warning(
                    f"{tag} {stage}: part {index} не докачана "
                    f"({downloaded}/{expected}) после {MAX_RETRIES_PART} попыток"
                )
                return

            cur_start = start + downloaded
            headers = _headers_for(url)
            headers["Range"] = f"bytes={cur_start}-{end}"

            try:
                with requests.get(url, headers=headers, stream=True,
                                  timeout=(10, 30)) as r:
                    if r.status_code not in (200, 206):
                        raise DownloadError(f"HTTP {r.status_code}")

                    mode = "ab" if downloaded > 0 else "wb"
                    with open(part_tmp, mode) as f:
                        raw = r.raw
                        while True:
                            if cancel_check and cancel_check():
                                aborted["v"] = True
                                return
                            try:
                                chunk = raw.read(CHUNK_SIZE)
                            except (IncompleteRead, ProtocolError):
                                break
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            report_progress()
                            if downloaded >= expected:
                                break

            except DownloadCancelled:
                aborted["v"] = True
                return
            except (requests.RequestException, DownloadError):
                time.sleep(0.3)
                continue

        actual = os.path.getsize(part_tmp) if os.path.exists(part_tmp) else 0
        if actual != expected:
            logger.warning(
                f"{tag} {stage}: part {index} итог {actual} из {expected}"
            )

    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [
            pool.submit(download_part, i, start, end)
            for i, start, end in ranges
        ]
        for _ in as_completed(futures):
            pass

    if aborted["v"]:
        raise DownloadCancelled("Отменено")

    errors = []
    for i, start, end in ranges:
        expected = end - start + 1
        p = part_paths[i]
        actual = os.path.getsize(p) if os.path.exists(p) else 0
        if actual != expected:
            errors.append(f"part {i}: {actual} из {expected}")

    if errors:
        raise DownloadError("; ".join(errors))

    logger.info(f"{tag} {stage}: сборка частей…")
    with open(tmp, "wb") as out:
        for i, _, _ in ranges:
            p = part_paths[i]
            with open(p, "rb") as part:
                while True:
                    buf = part.read(CHUNK_SIZE * 16)
                    if not buf:
                        break
                    out.write(buf)
            os.remove(p)

    final_size = os.path.getsize(tmp)
    if final_size != total:
        raise DownloadError(
            f"Итоговый файл {final_size} ≠ ожидаемому {total}"
        )

    logger.info(f"{tag} {stage}: параллельная загрузка завершена")


# ============================================================
# Простая загрузка
# ============================================================

def _download_simple(url, tmp, stage, episode_id,
                     progress_cb, cancel_check):
    tag = f"[{episode_id}]" if episode_id else "[?]"
    t_start = time.time()
    downloaded = 0
    total = 0
    last_update = 0.0
    last_error = None

    for attempt in range(1, MAX_RETRIES_SIMPLE + 1):
        if os.path.exists(tmp):
            downloaded = os.path.getsize(tmp)

        headers = _headers_for(url)
        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"

        logger.info(f"{tag} {stage}: попытка {attempt}/{MAX_RETRIES_SIMPLE}, "
                    f"start={downloaded}")

        try:
            with requests.get(url, stream=True, timeout=(10, 30),
                               headers=headers) as r:
                if downloaded > 0 and r.status_code == 200:
                    logger.info(f"{tag} {stage}: сервер не поддерживает Range")
                    downloaded = 0
                    with open(tmp, "wb"):
                        pass

                r.raise_for_status()

                cl = int(r.headers.get("content-length", 0))
                cr = r.headers.get("content-range")
                if cr:
                    try:
                        total = int(cr.split("/")[-1])
                    except (ValueError, IndexError):
                        total = downloaded + cl
                else:
                    total = downloaded + cl

                mode = "ab" if downloaded > 0 else "wb"
                with open(tmp, mode) as f:
                    raw = r.raw
                    while True:
                        if cancel_check and cancel_check():
                            raise DownloadCancelled("Отменено")
                        try:
                            chunk = raw.read(CHUNK_SIZE)
                        except (IncompleteRead, ProtocolError) as e:
                            logger.debug(
                                f"{tag} {stage}: обрыв на {downloaded} "
                                f"({type(e).__name__})"
                            )
                            break
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total:
                            now = time.time()
                            if now - last_update >= PROGRESS_UPDATE_INTERVAL:
                                percent = int(downloaded / total * 100)
                                progress_cb(stage, percent, downloaded, total)
                                last_update = now

            if total and downloaded < total:
                raise DownloadError(f"Частично: {downloaded}/{total}")

            elapsed = time.time() - t_start
            mb = downloaded / (1024 * 1024)
            logger.info(f"{tag} {stage}: скачано {mb:.1f} МБ за {elapsed:.1f} с")
            return downloaded

        except DownloadCancelled:
            raise

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            last_error = e
            if isinstance(status, int) and 400 <= status < 500 and status not in (408, 429):
                raise DownloadError(f"HTTP {status}. Ссылка устарела.")
            time.sleep(min(1.5 ** attempt, 8))

        except DownloadError as e:
            last_error = e
            time.sleep(0.3)

        except (requests.ConnectionError, requests.Timeout,
                requests.exceptions.ChunkedEncodingError,
                IncompleteRead, ProtocolError) as e:
            last_error = e
            time.sleep(min(1.2 ** attempt, 5))

        except requests.RequestException as e:
            last_error = e
            time.sleep(min(1.5 ** attempt, 8))

        except OSError as e:
            raise DownloadError(f"Ошибка записи: {e}")

    raise DownloadError(
        f"Не удалось скачать после {MAX_RETRIES_SIMPLE} попыток. "
        f"Последняя ошибка: {last_error}"
    )