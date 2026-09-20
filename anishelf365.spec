# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec для AniShelf365 (onedir)."""

import os

from PyInstaller.utils.hooks import collect_submodules


# ---------- Корень проекта ----------
PROJECT_ROOT = os.path.abspath(os.path.dirname(SPEC))


# ---------- datas: локали, QSS, ассеты ----------
datas = []

# locales/*.json
locales_dir = os.path.join(PROJECT_ROOT, "locales")
if os.path.isdir(locales_dir):
    for fname in os.listdir(locales_dir):
        if fname.endswith(".json"):
            datas.append(
                (os.path.join(locales_dir, fname), "locales")
            )

# ui_qt/styles/*.qss
styles_dir = os.path.join(PROJECT_ROOT, "ui_qt", "styles")
if os.path.isdir(styles_dir):
    for fname in os.listdir(styles_dir):
        if fname.endswith(".qss"):
            datas.append(
                (os.path.join(styles_dir, fname), "ui_qt/styles")
            )

# assets/* (иконки, картинки и т.п.) — включаем, если папка есть
assets_dir = os.path.join(PROJECT_ROOT, "assets")
if os.path.isdir(assets_dir):
    for root, _dirs, files in os.walk(assets_dir):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(root, PROJECT_ROOT)
            datas.append((full, rel))


# ---------- hiddenimports ----------
hiddenimports = []
hiddenimports += collect_submodules("core")
hiddenimports += collect_submodules("ui_qt")
hiddenimports += collect_submodules("player")


# ---------- excludes: всё, что не нужно в exe ----------
excludes = [
    # Тесты и их плагины
    "tests",
    "pytest", "_pytest", "pytest_qt", "pytest_mock", "pytest_cov",
    # Тяжёлые научные пакеты
    "numpy", "matplotlib", "pandas", "scipy",
    # Jupyter / IPython
    "IPython", "jupyter", "notebook",
    # Tkinter
    "tkinter", "Tkinter",
    # PySide6 модули, которые мы не используем
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DExtras",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtNetworkAuth",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtStateMachine",
    "PySide6.QtTextToSpeech",
    # python-vlc — оставляем только если реально используется.
    # Если плеер запускается через subprocess (внешний VLC) — можно
    # раскомментировать следующую строку, чтобы не тащить libvlc.
    # "vlc",
]


# ---------- Analysis ----------
a = Analysis(
    ["main.py"],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)


# ---------- Сборка ----------
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AniShelf365",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,               # GUI-приложение, без чёрного окна
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, "assets", "icon.ico")
         if os.path.exists(os.path.join(PROJECT_ROOT, "assets", "icon.ico"))
         else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AniShelf365",
)