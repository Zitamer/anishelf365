# -*- coding: utf-8 -*-
"""Проверка новых серий (онгоингов)."""

import logging

from core.api import Anime365API
from core.db import Database


logger = logging.getLogger(__name__)


class UpdateStats:
    """Результаты проверки обновлений."""

    def __init__(self):
        self.series_checked = 0       # всего проверено
        self.series_with_new = 0      # тайтлов с новыми сериями
        self.series_failed = 0        # тайтлов, где API упал
        self.series_no_new = 0        # без новых
        self.new_episodes_total = 0   # всего новых серий

    def to_dict(self):
        return {
            "series_checked": self.series_checked,
            "series_with_new": self.series_with_new,
            "series_failed": self.series_failed,
            "series_no_new": self.series_no_new,
            "new_episodes_total": self.new_episodes_total,
        }

    def __repr__(self):
        return f"UpdateStats({self.to_dict()})"


def check_for_updates(db: Database, api: Anime365API,
                      progress_cb=None, stop_flag=None) -> UpdateStats:
    """
    Проходит по всем тайтлам в БД (кроме игнорируемых), запрашивает у API
    список эпизодов и добавляет новые в БД.

    Счётчик new_episodes_count накапливается (не сбрасывается при проверке).
    Сбрасывается при открытии экрана тайтла — см. SeriesView.

    Возвращает UpdateStats.
    """
    stats = UpdateStats()

    all_series = db.list_series()
    if not all_series:
        return stats

    ignored = {r["series_id"] for r in db.list_ignored()}
    to_check = [s for s in all_series if s["series_id"] not in ignored]

    total = len(to_check)
    if total == 0:
        return stats

    for idx, series_row in enumerate(to_check, start=1):
        if stop_flag and stop_flag():
            break

        sid = series_row["series_id"]
        stats.series_checked += 1

        if progress_cb:
            progress_cb(idx, total, sid)

        try:
            data = api.get_series(sid)
        except Exception:
            logger.exception(f"Ошибка загрузки метаданных {sid}")
            stats.series_failed += 1
            continue

        if not data:
            logger.warning(f"API вернул пусто для {sid}")
            stats.series_failed += 1
            continue

        try:
            _update_one_series(db, series_row, data, stats)
        except Exception:
            logger.exception(f"Ошибка обновления {sid}")
            stats.series_failed += 1

    return stats


def _update_one_series(db: Database, series_row, data: dict,
                       stats: UpdateStats):
    """Обновляет метаданные и эпизоды одного сериала."""
    sid = series_row["series_id"]

    existing_ids = {ep["episode_id"] for ep in db.list_episodes(sid)}

    episodes = data.get("episodes") or []
    new_count = 0
    for ep in episodes:
        ep_id = ep.get("id")
        if ep_id and ep_id not in existing_ids:
            new_count += 1

    # Обновляем метаданные сериала (episodes_count, is_airing, poster_url и т.п.)
    db.upsert_series(data)

    # Обновляем/добавляем эпизоды (upsert по episode_id)
    if episodes:
        db.upsert_episodes(episodes)

    # Счётчик новых — накапливаем
    if new_count > 0:
        current = series_row["new_episodes_count"] or 0
        db.set_new_episodes_count(sid, current + new_count)
        stats.series_with_new += 1
        stats.new_episodes_total += new_count
        logger.info(f"[{sid}] новых серий: {new_count}")
    else:
        stats.series_no_new += 1

    db.set_full_update_time(sid)