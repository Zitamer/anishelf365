# -*- coding: utf-8 -*-
"""Парсинг ссылок Anime365 и извлечение ID."""

import re


# Ссылка на каталог: /catalog/<slug>-<series_id>
CATALOG_PATTERN = re.compile(
    r"/catalog/(?:[^/]+-)?(\d+)(?:/|$|\?)",
    re.IGNORECASE,
)

# Ссылка на эпизод: /catalog/<slug>-<series_id>/<N>-seriya-<episode_id>
EPISODE_PATTERN = re.compile(
    r"/catalog/[^/]+-(\d+)/\d+-seriya-(\d+)",
    re.IGNORECASE,
)

# Просто число
NUMBER_PATTERN = re.compile(r"^\d+$")


def parse_series_id(url_or_id: str) -> int | None:
    """
    Извлекает series_id из ссылки или числа.
    Поддерживает:
      - https://smotret-anime.org/catalog/yani-neko-41893
      - https://smotret-anime.org/catalog/yani-neko-41893/1-seriya-371562/...
      - https://smotret-anime.app/catalog/...
      - 41893
    """
    if not url_or_id:
        return None
    s = url_or_id.strip()

    # Просто число
    if NUMBER_PATTERN.match(s):
        return int(s)

    # Ссылка на каталог
    m = CATALOG_PATTERN.search(s)
    if m:
        return int(m.group(1))

    return None


def parse_episode_ids(url: str) -> tuple | None:
    """
    Извлекает (series_id, episode_id) из ссылки на эпизод.
    Возвращает None, если ссылка не на эпизод.
    """
    if not url:
        return None
    m = EPISODE_PATTERN.search(url)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def parse_translation_id(url: str) -> int | None:
    """
    Извлекает translation_id — последнее число в URL.
    Примеры:
      .../russkie-subtitry-5843348  → 5843348
    """
    if not url:
        return None
    matches = re.findall(r"-(\d+)(?=/|$|\?)", url)
    if not matches:
        return None
    return int(matches[-1])


# ============================================================
# Тест
# ============================================================

if __name__ == "__main__":
    print("=== Тест url_parser ===")

    test_cases = [
        ("https://smotret-anime.org/catalog/yani-neko-41893", 41893),
        ("https://smotret-anime.org/catalog/yani-neko-41893/1-seriya-371562/russkie-subtitry-5843348", 41893),
        ("https://smotret-anime.app/catalog/mushoku-tensei-iii-isekai-ittara-honki-dasu-36866", 36866),
        ("https://smotret-anime.org/catalog/isekai-nonbiri-nouka-2-40114/12-seriya-380593/russkie-subtitry-5827947", 40114),
        ("41893", 41893),
        ("https://smotret-anime.org/", None),
        ("not a url", None),
        ("", None),
    ]

    print("\n--- series_id ---")
    for url, expected in test_cases:
        result = parse_series_id(url)
        status = "✓" if result == expected else "✗"
        short = (url[:55] + "...") if len(url) > 55 else url
        print(f"{status} '{short}' → {result} (ожидали {expected})")

    print("\n--- episode_ids ---")
    ep_cases = [
        ("https://smotret-anime.org/catalog/yani-neko-41893/1-seriya-371562/russkie-subtitry-5843348",
         (41893, 371562)),
        ("https://smotret-anime.org/catalog/yani-neko-41893", None),
    ]
    for url, expected in ep_cases:
        result = parse_episode_ids(url)
        status = "✓" if result == expected else "✗"
        short = (url[:55] + "...") if len(url) > 55 else url
        print(f"{status} '{short}' → {result}")

    print("\n--- translation_id ---")
    tr_cases = [
        ("https://smotret-anime.org/catalog/yani-neko-41893/1-seriya-371562/russkie-subtitry-5843348",
         5843348),
        ("https://smotret-anime.org/catalog/isekai-nonbiri-nouka-2-40114/12-seriya-380593/russkie-subtitry-5827947",
         5827947),
    ]
    for url, expected in tr_cases:
        result = parse_translation_id(url)
        status = "✓" if result == expected else "✗"
        short = (url[:55] + "...") if len(url) > 55 else url
        print(f"{status} '{short}' → {result} (ожидали {expected})")