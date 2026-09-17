# -*- coding: utf-8 -*-
"""Anime Library — точка входа приложения (PySide6)."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


# ---------- Определение корня проекта ----------
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


# ---------- Логирование ----------
def setup_logging():
    from core.constants import DATA_DIR, LOG_PATH, LOG_MAX_BYTES, LOG_BACKUP_COUNT

    os.makedirs(DATA_DIR, exist_ok=True)

    handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    if not getattr(sys, "frozen", False):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        root.addHandler(console)


# ---------- Запуск ----------
def main():
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("Запуск Anime Library (PySide6)")

    try:
        from PySide6.QtWidgets import QApplication
        from ui_qt.app import AnimeLibraryApp

        # Fusion-стиль лучше реагирует на QSS, чем native Windows
        QApplication.setStyle("Fusion")

        app = QApplication(sys.argv)
        app.setApplicationName("Anime Library")
        app.setOrganizationName("AnimeLibrary")

        window = AnimeLibraryApp()
        window.show()

        code = app.exec()
        logger.info(f"Выход с кодом {code}")
        sys.exit(code)
    except Exception:
        logger.exception("Критическая ошибка")
        raise


if __name__ == "__main__":
    main()