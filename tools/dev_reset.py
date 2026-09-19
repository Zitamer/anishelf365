# -*- coding: utf-8 -*-
"""Dev-утилита: ручное вмешательство в БД для проверки онгоингов.

Запускать при ЗАКРЫТОМ основном приложении — иначе возможны блокировки SQLite.

Примеры:
    python tools/dev_reset.py list
    python tools/dev_reset.py show 41893
    python tools/dev_reset.py delete-last 41893
    python tools/dev_reset.py delete-episode 41893 380001
    python tools/dev_reset.py reset-new 41893
    python tools/dev_reset.py reset-all-new
"""

import sys
from pathlib import Path

# Чтобы core импортировался при запуске из любой папки
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.constants import DB_PATH
from core.db import Database


def cmd_list(db):
    rows = db.list_series()
    if not rows:
        print("БД пуста")
        return 0
    print(f"{'series_id':>10}  {'eps':>4}  {'new':>3}  title")
    print("-" * 60)
    for r in rows:
        eps = db.list_episodes(r["series_id"])
        new_cnt = r["new_episodes_count"] or 0
        print(f"{r['series_id']:>10}  {len(eps):>4}  {new_cnt:>3}  {r['title']}")
    return 0


def cmd_show(db, series_id: int):
    row = db.get_series(series_id)
    if not row:
        print(f"Тайтл {series_id} не найден в БД")
        return 1
    print(f"Тайтл: {row['title']} (id={series_id})")
    print(f"  is_airing: {row['is_airing']}")
    print(f"  new_episodes_count: {row['new_episodes_count'] or 0}")
    print(f"  last_full_update: {row['last_full_update']}")
    eps = db.list_episodes(series_id)
    print(f"  Эпизодов в БД: {len(eps)}")
    for ep in eps:
        print(
            f"    #{ep['number']:>5}  id={ep['episode_id']}  "
            f"type={ep['episode_type']}  title={ep['title']!r}"
        )
    return 0


def cmd_delete_last(db, series_id: int):
    """Удаляет последний по номеру эпизод. При следующей проверке API
    снова вернёт его как «новый»."""
    eps = db.list_episodes(series_id)
    if not eps:
        print(f"У {series_id} нет эпизодов")
        return 1
    last = eps[-1]
    print(
        f"Удаляю последний эпизод тайтла {series_id}: "
        f"#{last['number']} id={last['episode_id']}"
    )
    db.conn.execute(
        "DELETE FROM episodes_meta WHERE episode_id = ?",
        (last["episode_id"],),
    )
    db.conn.commit()
    print("OK. Нажми «Проверить новые серии» — он снова должен быть «новым».")
    return 0


def cmd_delete_episode(db, series_id: int, episode_id: int):
    ep = db.get_episode(episode_id)
    if not ep:
        print(f"Эпизод {episode_id} не найден")
        return 1
    print(
        f"Удаляю эпизод id={episode_id} (#{ep['number']}) тайтла {series_id}"
    )
    db.conn.execute(
        "DELETE FROM episodes_meta WHERE episode_id = ?",
        (episode_id,),
    )
    db.conn.commit()
    print("OK")
    return 0


def cmd_reset_new(db, series_id: int):
    db.reset_new_episodes_count(series_id)
    print(f"new_episodes_count сброшен для {series_id}")
    return 0


def cmd_reset_all_new(db):
    db.conn.execute("UPDATE series_meta SET new_episodes_count = 0")
    db.conn.commit()
    print("new_episodes_count сброшен у всех тайтлов")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    cmd = sys.argv[1]
    db = Database(DB_PATH)

    try:
        if cmd == "list":
            return cmd_list(db)
        if cmd == "show" and len(sys.argv) >= 3:
            return cmd_show(db, int(sys.argv[2]))
        if cmd == "delete-last" and len(sys.argv) >= 3:
            return cmd_delete_last(db, int(sys.argv[2]))
        if cmd == "delete-episode" and len(sys.argv) >= 4:
            return cmd_delete_episode(db, int(sys.argv[2]), int(sys.argv[3]))
        if cmd == "reset-new" and len(sys.argv) >= 3:
            return cmd_reset_new(db, int(sys.argv[2]))
        if cmd == "reset-all-new":
            return cmd_reset_all_new(db)
        print(__doc__)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())