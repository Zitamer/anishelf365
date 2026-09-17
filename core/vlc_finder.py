# -*- coding: utf-8 -*-
"""Поиск VLC и настройка python-vlc."""

import os
import shutil
import sys

from core.constants import VLC_STANDARD_PATHS, LIBVLC_STANDARD_DIRS


# ============================================================
# Поиск vlc.exe
# ============================================================

def find_vlc_exe(override: str = None) -> str | None:
    """
    Ищет vlc.exe (или vlc на *nix).
    Приоритет:
      1. override (путь из настроек)
      2. PATH
      3. Стандартные пути
    """
    if override and os.path.isfile(override):
        return override

    exe_name = "vlc.exe" if sys.platform.startswith("win") else "vlc"
    found = shutil.which(exe_name)
    if found:
        return found

    for path in VLC_STANDARD_PATHS:
        if os.path.isfile(path):
            return path

    return None


# ============================================================
# Поиск папки libvlc
# ============================================================

def find_libvlc_dir(override: str = None) -> str | None:
    """
    Ищет папку, содержащую libvlc.dll (.so / .dylib).
    Приоритет:
      1. override
      2. Стандартные папки
    """
    if override and os.path.isdir(override):
        return override

    for d in LIBVLC_STANDARD_DIRS:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.lower().startswith("libvlc"):
                return d

    return None


# ============================================================
# Настройка python-vlc
# ============================================================

_libvlc_configured = False
_libvlc_dir_used = None


def configure_libvlc(libvlc_dir: str = None) -> bool:
    """
    Настраивает окружение для python-vlc.
    Возвращает True, если libvlc найден и загружается.

    Порядок:
      1. Если уже настроено — вернуть True.
      2. Попробовать импортировать vlc без настройки (вдруг уже работает).
      3. Найти папку libvlc, добавить в PATH и os.add_dll_directory.
      4. Импортировать vlc и создать Instance.
    """
    global _libvlc_configured, _libvlc_dir_used

    if _libvlc_configured:
        return True

    # 1. Пробуем как есть
    try:
        import vlc
        vlc.Instance("--quiet")
        _libvlc_configured = True
        return True
    except Exception:
        pass

    # 2. Ищем папку
    dll_dir = find_libvlc_dir(libvlc_dir)
    if not dll_dir:
        return False

    # 3. Настраиваем окружение под Windows
    if sys.platform.startswith("win"):
        try:
            os.add_dll_directory(dll_dir)
        except (AttributeError, OSError):
            pass
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
    else:
        ld = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = dll_dir + os.pathsep + ld

    # 4. Пробуем снова
    try:
        import vlc
        vlc.Instance("--quiet")
        _libvlc_configured = True
        _libvlc_dir_used = dll_dir
        return True
    except Exception:
        return False


def get_libvlc_version() -> str | None:
    """Возвращает версию libvlc, если он работает."""
    if not _libvlc_configured:
        if not configure_libvlc():
            return None
    try:
        import vlc
        return vlc.libvlc_get_version().decode()
    except Exception:
        return None


# ============================================================
# Проверка версии VLC (без запуска vlc.exe)
# ============================================================

def check_vlc_version(vlc_exe: str, timeout: int = 5) -> str | None:
    """
    Возвращает версию VLC через libvlc (без запуска vlc.exe).
    Не запускает GUI-приложение, чтобы не открывались окна.
    """
    return get_libvlc_version()


def is_valid_vlc(vlc_exe: str) -> bool:
    """
    Проверяет, что vlc.exe существует и libvlc доступен.
    Работает без запуска vlc.exe.
    """
    if not vlc_exe or not os.path.isfile(vlc_exe):
        return False

    # Если libvlc уже работает — VLC точно валиден
    if _libvlc_configured or configure_libvlc():
        return True

    # Fallback: рядом с vlc.exe должен быть libvlc.dll
    dll_dir = os.path.dirname(vlc_exe)
    dll_name = "libvlc.dll" if sys.platform.startswith("win") else "libvlc.so"
    if os.path.isfile(os.path.join(dll_dir, dll_name)):
        return True

    return False


# ============================================================
# Высокоуровневая проверка окружения
# ============================================================

def check_vlc_environment(settings) -> dict:
    """
    Проверяет наличие VLC и libvlc с учётом настроек.
    Возвращает словарь:
      {
        'vlc_exe': str | None,
        'vlc_version': str | None,
        'vlc_valid': bool,
        'libvlc_dir': str | None,
        'libvlc_version': str | None,
        'embedded_available': bool,
        'external_available': bool,
      }
    """
    vlc_exe = find_vlc_exe(getattr(settings, "vlc_exe_path", "") or "")

    # Настраиваем libvlc
    libvlc_dir = find_libvlc_dir(getattr(settings, "libvlc_dir", "") or "")
    embedded = configure_libvlc(libvlc_dir)

    # Проверяем VLC (без запуска exe)
    valid = is_valid_vlc(vlc_exe) if vlc_exe else False
    vlc_version = check_vlc_version(vlc_exe) if vlc_exe else None
    libvlc_version = get_libvlc_version() if embedded else None

    return {
        "vlc_exe": vlc_exe,
        "vlc_version": vlc_version,
        "vlc_valid": valid,
        "libvlc_dir": libvlc_dir,
        "libvlc_version": libvlc_version,
        "embedded_available": embedded,
        "external_available": valid,
    }


# ============================================================
# Тест
# ============================================================

if __name__ == "__main__":
    print("=== Тест vlc_finder ===\n")

    # 1. Поиск vlc.exe
    print("--- Поиск VLC ---")
    exe = find_vlc_exe()
    print("Найден vlc.exe:", exe)
    if exe:
        version = check_vlc_version(exe)
        print("Версия:", version)
        print("Валиден:", is_valid_vlc(exe))

    # 2. Поиск libvlc
    print("\n--- Поиск libvlc ---")
    dll_dir = find_libvlc_dir()
    print("Папка libvlc:", dll_dir)

    # 3. Настройка python-vlc
    print("\n--- Настройка python-vlc ---")
    ok = configure_libvlc(dll_dir)
    print("Настроен:", ok)
    if ok:
        print("Версия libvlc:", get_libvlc_version())

    # 4. Полная проверка окружения (с фиктивным settings)
    print("\n--- Полная проверка окружения ---")

    class FakeSettings:
        vlc_exe_path = ""
        libvlc_dir = ""

    result = check_vlc_environment(FakeSettings())
    for k, v in result.items():
        print(f"  {k}: {v}")