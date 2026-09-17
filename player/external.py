# -*- coding: utf-8 -*-
"""Запуск внешнего VLC-плеера."""

import os
import subprocess
import logging
import sys

from core.vlc_finder import find_vlc_exe


logger = logging.getLogger(__name__)


class PlayerError(Exception):
    """Ошибка запуска плеера."""
    pass


def launch_vlc(
    video_path: str,
    subtitle_path: str = None,
    start_time: float = None,
    vlc_override: str = None,
    fullscreen: bool = False,
) -> subprocess.Popen:
    """
    Запускает внешний VLC-плеер.

    Параметры:
      video_path     — полный путь к видеофайлу
      subtitle_path  — полный путь к .ass/.srt (опционально)
      start_time     — секунда, с которой начать (опционально)
      vlc_override   — путь к vlc.exe (если в настройках указан)
      fullscreen     — запустить на весь экран

    Возвращает объект subprocess.Popen.
    """
    if not video_path or not os.path.isfile(video_path):
        raise PlayerError(f"Файл не найден: {video_path}")

    vlc_path = find_vlc_exe(vlc_override)
    if not vlc_path:
        raise PlayerError(
            "VLC не найден. Укажите путь к vlc.exe в настройках."
        )

    # Собираем аргументы
    args = [vlc_path, video_path]

    # Субтитры
    if subtitle_path and os.path.isfile(subtitle_path):
        args.append(f"--sub-file={subtitle_path}")
        logger.info(f"Подключены субтитры: {subtitle_path}")
    else:
        logger.info("Субтитры не подключены (файл не найден)")

    # Начало с позиции
    if start_time and start_time > 0:
        args.append(f"--start-time={start_time:.1f}")
        logger.info(f"Старт с позиции: {start_time:.1f} с")

    # Fullscreen
    if fullscreen:
        args.append("--fullscreen")

    # Чтобы окно VLC было поверх остальных окон
    args.append("--no-video-title-show")

    logger.info(f"Запуск VLC: {' '.join(args)}")

    # ---------- Запуск ----------
    try:
        if sys.platform.startswith("win"):
            # Скрываем консольное окно cmd у VLC
            creationflags = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(
                args,
                creationflags=creationflags,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )

        logger.info(f"VLC запущен, PID={proc.pid}")
        return proc

    except OSError as e:
        logger.exception("Ошибка запуска VLC")
        raise PlayerError(f"Не удалось запустить VLC: {e}")


def launch_vlc_external_fallback(video_path: str, subtitle_path: str = None):
    """
    Резервный запуск VLC через системный вызов.
    Используется, если стандартный find_vlc_exe не сработал.
    """
    if sys.platform.startswith("win"):
        os.startfile(video_path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", video_path])
    else:
        subprocess.Popen(["xdg-open", video_path])


def is_vlc_running(proc: subprocess.Popen) -> bool:
    """Проверяет, работает ли VLC-процесс."""
    if proc is None:
        return False
    return proc.poll() is None


def close_vlc(proc: subprocess.Popen):
    """Закрывает VLC-процесс."""
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
            logger.info("VLC закрыт")
    except OSError as e:
        logger.warning(f"Не удалось закрыть VLC: {e}")