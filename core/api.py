# -*- coding: utf-8 -*-
"""Обёртка над API Anime365."""

import json
import os
import requests

from core.constants import API_BASE_URL, TOKEN_PATH


DEFAULT_TIMEOUT = 15

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnimeLibrary/1.0",
}


class Anime365Error(Exception):
    """Ошибка API."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class Anime365API:
    """Клиент для API smotret-anime.app."""

    def __init__(self, token_path: str = TOKEN_PATH):
        self.token_path = token_path
        self.token = self._load_token()

    # ============================================================
    # Токен
    # ============================================================

    def _load_token(self) -> str | None:
        if not os.path.exists(self.token_path):
            return None
        try:
            with open(self.token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        if isinstance(data, str):
            return data.strip() or None
        for key in ("access_token", "token", "accessToken"):
            if isinstance(data, dict) and data.get(key):
                return str(data[key]).strip()
        return None

    def save_token(self, token: str):
        os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
        token = token.strip()
        with open(self.token_path, "w", encoding="utf-8") as f:
            json.dump({"access_token": token}, f, ensure_ascii=False, indent=2)
        self.token = token

    def has_token(self) -> bool:
        return bool(self.token)

    # ============================================================
    # Базовые запросы
    # ============================================================

    def _request(self, path: str, params: dict = None,
                 timeout: int = DEFAULT_TIMEOUT, retries: int = 3):
        """GET-запрос к API. Возвращает data или бросает исключение."""
        url = API_BASE_URL + path
        last_error = None

        for attempt in range(retries):
            try:
                r = requests.get(
                    url,
                    params=params,
                    headers=DEFAULT_HEADERS,
                    timeout=timeout,
                )
                r.raise_for_status()
                payload = r.json()
                if "error" in payload:
                    err = payload["error"]
                    raise Anime365Error(err.get("code"), err.get("message", ""))
                return payload.get("data")
            except requests.Timeout as e:
                last_error = e
                if attempt == retries - 1:
                    raise
            except requests.RequestException as e:
                last_error = e
                if attempt == retries - 1:
                    raise
        if last_error:
            raise last_error
        return None

    # ============================================================
    # Проверка токена и пользователь
    # ============================================================

    def check_token(self, token: str = None) -> tuple:
        """
        Проверяет валидность токена через /me.
        Возвращает (success: bool, error_message: str).
        error_message пустая строка, если всё ок.
        """
        t = (token or self.token or "").strip()

        # Отладка (видно в консоли)
        print(f"[check_token] длина={len(t)}, начало={t[:10]!r}, конец={t[-10:]!r}")

        if not t:
            return False, "Токен пуст"

        url = API_BASE_URL + "/me"
        try:
            r = requests.get(
                url,
                params={"access_token": t},
                headers=DEFAULT_HEADERS,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as e:
            print(f"[check_token] Сетевая ошибка: {e}")
            return False, f"Сеть: {e}"

        print(f"[check_token] HTTP статус: {r.status_code}")

        try:
            payload = r.json()
        except ValueError:
            print(f"[check_token] Не JSON: {r.text[:200]}")
            return False, "Ответ не JSON"

        print(f"[check_token] Ответ: {str(payload)[:200]}")

        if "error" in payload:
            err = payload["error"]
            msg = f"API {err.get('code')}: {err.get('message', '')}"
            print(f"[check_token] Ошибка API: {msg}")
            return False, msg

        data = payload.get("data")
        if isinstance(data, dict) and data.get("id"):
            return True, ""
        return False, f"Неверный ответ API: {str(payload)[:200]}"

    def get_me(self) -> dict | None:
        if not self.token:
            return None
        try:
            return self._request("/me", {"access_token": self.token})
        except (Anime365Error, requests.RequestException):
            return None

    # ============================================================
    # Сериалы
    # ============================================================

    def get_series(self, series_id: int) -> dict | None:
        try:
            return self._request(f"/series/{series_id}")
        except (Anime365Error, requests.RequestException):
            return None

    def get_episodes_paginated(self, series_id: int, limit: int = 100,
                               max_pages: int = 50) -> list:
        episodes = []
        last_id = 0
        for _ in range(max_pages):
            try:
                data = self._request(
                    "/episodes",
                    {"series_id": series_id, "afterId": last_id, "limit": limit},
                )
            except (Anime365Error, requests.RequestException):
                break
            if not isinstance(data, list) or not data:
                break
            episodes.extend(data)
            if len(data) < limit:
                break
            last_id = data[-1].get("id")
            if not last_id:
                break
        return episodes

    # ============================================================
    # Переводы
    # ============================================================

    def get_translations(self, episode_id: int) -> list:
        for params in (
            {"episodeId": episode_id},
            {"episode_id": episode_id},
        ):
            try:
                data = self._request("/translations", params)
                if isinstance(data, list) and data:
                    return data
            except (Anime365Error, requests.RequestException):
                continue
        return []

    # ============================================================
    # Embed
    # ============================================================

    def get_embed(self, translation_id: int) -> dict | None:
        if not self.token:
            return None
        try:
            return self._request(
                f"/translations/embed/{translation_id}",
                {"access_token": self.token},
            )
        except (Anime365Error, requests.RequestException):
            return None

    # ============================================================
    # Поиск
    # ============================================================

    def search_series(self, query: str, limit: int = 20) -> list:
        try:
            data = self._request("/series", {"search": query, "limit": limit})
            return data if isinstance(data, list) else []
        except (Anime365Error, requests.RequestException):
            return []


# ============================================================
# Утилиты для парсинга ответов
# ============================================================

def extract_subtitles_from_embed(embed_data: dict | None) -> str | None:
    if not isinstance(embed_data, dict):
        return None
    sub_url = embed_data.get("subtitlesUrl")
    if isinstance(sub_url, str) and sub_url:
        return sub_url
    return _find_subtitle_url(embed_data)


def _find_subtitle_url(data):
    if isinstance(data, str):
        low = data.lower()
        if any(ext in low for ext in (".ass", ".srt", ".vtt")):
            return data
        return None
    if isinstance(data, dict):
        for v in data.values():
            r = _find_subtitle_url(v)
            if r:
                return r
    elif isinstance(data, list):
        for item in data:
            r = _find_subtitle_url(item)
            if r:
                return r
    return None


def extract_video_urls(embed_data: dict | None) -> dict:
    """
    Извлекает ссылки на видео. Приоритет: stream > download.
    Stream-ссылки не требуют специальных заголовков и работают через requests.
    Возвращает {quality: url}.
    """
    if not isinstance(embed_data, dict):
        return {}

    result = {}

    # 1. Сначала stream (приоритет!)
    stream = embed_data.get("stream")
    if isinstance(stream, list):
        for item in stream:
            if isinstance(item, dict):
                urls_list = item.get("urls")
                if isinstance(urls_list, list) and urls_list:
                    height = item.get("height")
                    label = f"{height}p" if height else "stream"
                    result[label] = urls_list[0]

    # 2. download — только если для этого качества ещё нет ссылки
    download = embed_data.get("download")
    if isinstance(download, list):
        for item in download:
            if isinstance(item, dict):
                url = item.get("url")
                if url:
                    height = item.get("height")
                    label = f"{height}p" if height else "download"
                    if label not in result:
                        result[label] = url

    return result


def extract_qualities(embed_data: dict | None) -> list:
    return list(extract_video_urls(embed_data).keys())


# ============================================================
# Тест
# ============================================================

if __name__ == "__main__":
    print("=== Тест API ===")

    api = Anime365API()
    print("Токен найден:", api.has_token())

    print("\n--- Сериал 41893 ---")
    series = api.get_series(41893)
    if series:
        titles = series.get("titles") or {}
        print("Название:", series.get("title"))
        print("Год:", series.get("year"))
        print("Онгоинг:", series.get("isAiring"))

    print("\n--- Проверка токена ---")
    if api.has_token():
        ok, err = api.check_token()
        print(f"Валиден: {ok}, ошибка: {err!r}")
    else:
        print("Токен не найден")

    print("\nТест завершён.")