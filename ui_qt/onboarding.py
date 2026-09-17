# -*- coding: utf-8 -*-
"""Онбординг: 5 шагов при первом запуске (PySide6)."""

import os
import logging
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QCheckBox, QFrame, QStackedWidget,
    QFileDialog, QMessageBox, QApplication,
)

from core.constants import (
    APP_NAME, AVAILABLE_LANGUAGES, VLC_DOWNLOAD_PAGE, CLIENTS_PAGE,
    DEFAULT_LANGUAGE,
)
from core import i18n
from core.vlc_finder import find_vlc_exe, find_libvlc_dir
from core.api import Anime365API
from ui_qt.styles.loader import apply_theme


logger = logging.getLogger(__name__)


LANGUAGE_NAMES = {
    "en": "English",
    "ru": "Русский",
}
LANGUAGE_CODES_BY_NAME = {v: k for k, v in LANGUAGE_NAMES.items()}


# ============================================================
# Плитка темы
# ============================================================

class ThemeTile(QFrame):
    """Плитка выбора темы. Прозрачный фон — цвет текста берётся из темы."""

    def __init__(self, theme_name: str, label: str, on_click):
        super().__init__()
        self.theme_name = theme_name
        self.on_click = on_click
        self.setFixedSize(200, 230)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        # Превью — цветной прямоугольник
        self.preview = QFrame()
        self.preview.setFixedSize(160, 150)
        if theme_name == "dark":
            self.preview.setStyleSheet(
                "background-color: #1a1a1a; border-radius: 6px;"
            )
        else:
            self.preview.setStyleSheet(
                "background-color: #ebebeb; border-radius: 6px;"
            )
        layout.addWidget(self.preview, alignment=Qt.AlignmentFlag.AlignCenter)

        # Подпись — без указания цвета, берёт цвет из общего QSS
        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 14px; background: transparent;")
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.set_selected(False)

    def set_selected(self, selected: bool):
        # Фон — прозрачный, чтобы текст наследовал цвет из темы
        if selected:
            self.setStyleSheet(
                "ThemeTile {"
                "  background-color: transparent;"
                "  border: 3px solid #1f6aa5;"
                "  border-radius: 10px;"
                "}"
            )
        else:
            self.setStyleSheet(
                "ThemeTile {"
                "  background-color: transparent;"
                "  border: 1px solid rgba(128, 128, 128, 0.4);"
                "  border-radius: 10px;"
                "}"
            )

    def mousePressEvent(self, event):
        if self.on_click:
            self.on_click(self.theme_name)
        super().mousePressEvent(event)


# ============================================================
# Онбординг
# ============================================================

class OnboardingWindow(QWidget):
    """Онбординг с 5 шагами."""

    TOTAL_STEPS = 5

    def __init__(self, app):
        super().__init__()
        self.app = app

        self.current_step = 1

        # Временные значения
        self.temp_language = app.settings.language or DEFAULT_LANGUAGE
        stored_theme = app.settings.theme or "dark"
        self.temp_use_system_theme = (stored_theme == "system")
        self.temp_theme = "dark" if self.temp_use_system_theme else stored_theme

        default_lib = os.path.join(os.path.expanduser("~"), "Anime")
        self.temp_library_path = app.settings.library_path or default_lib

        self.temp_vlc_path = find_vlc_exe() or ""
        self.temp_libvlc_dir = find_libvlc_dir() or ""

        self.temp_token = ""
        self.temp_token_valid = False
        self.temp_token_state = "idle"
        self.temp_token_error = ""

        self.api = Anime365API()

        self._build_ui()

        # Заполняем тексты до первого показа
        self._refresh_all_texts()

        # Показываем первый шаг
        self._show_step(1)

    # ============================================================
    # Разметка
    # ============================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------- Верхняя панель ----------
        self.header = QFrame()
        self.header.setObjectName("topBar")
        self.header.setFixedHeight(50)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        header_layout.addStretch()

        self.step_label = QLabel()
        self.step_label.setObjectName("subtitle")
        header_layout.addWidget(self.step_label)

        root.addWidget(self.header)

        # ---------- Стек шагов ----------
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.page_1 = self._make_page_1()
        self.page_2 = self._make_page_2()
        self.page_3 = self._make_page_3()
        self.page_4 = self._make_page_4()
        self.page_5 = self._make_page_5()

        self.stack.addWidget(self.page_1)
        self.stack.addWidget(self.page_2)
        self.stack.addWidget(self.page_3)
        self.stack.addWidget(self.page_4)
        self.stack.addWidget(self.page_5)

        # ---------- Нижняя панель ----------
        self.footer = QFrame()
        self.footer.setObjectName("bottomBar")
        self.footer.setFixedHeight(70)
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)

        self.back_btn = QPushButton()
        self.back_btn.setObjectName("secondary")
        self.back_btn.setFixedWidth(140)
        self.back_btn.clicked.connect(self._on_back)
        footer_layout.addWidget(self.back_btn)

        footer_layout.addStretch()

        self.next_btn = QPushButton()
        self.next_btn.setFixedWidth(160)
        self.next_btn.clicked.connect(self._on_next)
        footer_layout.addWidget(self.next_btn)

        root.addWidget(self.footer)

    # ============================================================
    # Страницы шагов
    # ============================================================

    def _make_page_1(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        self.title_1 = QLabel()
        self.title_1.setObjectName("title")
        self.title_1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_1)

        self.subtitle_1 = QLabel()
        self.subtitle_1.setObjectName("subtitle")
        self.subtitle_1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle_1)

        self.lang_combo = QComboBox()
        self.lang_combo.setFixedWidth(300)
        for code in AVAILABLE_LANGUAGES:
            if code in LANGUAGE_NAMES:
                self.lang_combo.addItem(LANGUAGE_NAMES[code], code)

        idx = self.lang_combo.findData(self.temp_language)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

        self.lang_combo.currentIndexChanged.connect(self._on_language_change)
        layout.addWidget(self.lang_combo, alignment=Qt.AlignmentFlag.AlignCenter)

        return page

    def _make_page_2(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(30)

        self.title_2 = QLabel()
        self.title_2.setObjectName("title")
        self.title_2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_2)

        tiles_row = QHBoxLayout()
        tiles_row.setSpacing(30)

        self.tile_dark = ThemeTile("dark", "", self._on_theme_click)
        self.tile_light = ThemeTile("light", "", self._on_theme_click)

        tiles_row.addStretch()
        tiles_row.addWidget(self.tile_dark)
        tiles_row.addWidget(self.tile_light)
        tiles_row.addStretch()

        layout.addLayout(tiles_row)

        self.system_check = QCheckBox()
        self.system_check.setChecked(self.temp_use_system_theme)
        self.system_check.stateChanged.connect(self._on_system_theme_toggle)
        layout.addWidget(self.system_check, alignment=Qt.AlignmentFlag.AlignCenter)

        return page

    def _make_page_3(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        self.title_3 = QLabel()
        self.title_3.setObjectName("title")
        self.title_3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_3)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()

        self.library_edit = QLineEdit()
        self.library_edit.setText(self.temp_library_path)
        self.library_edit.setFixedWidth(500)
        row.addWidget(self.library_edit)

        self.library_browse_btn = QPushButton()
        self.library_browse_btn.setFixedWidth(130)
        self.library_browse_btn.clicked.connect(self._browse_library)
        row.addWidget(self.library_browse_btn)

        row.addStretch()
        layout.addLayout(row)

        self.hint_3 = QLabel()
        self.hint_3.setObjectName("subtitle")
        self.hint_3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_3.setWordWrap(True)
        self.hint_3.setFixedWidth(600)
        layout.addWidget(self.hint_3, alignment=Qt.AlignmentFlag.AlignCenter)

        return page

    def _make_page_4(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        self.title_4 = QLabel()
        self.title_4.setObjectName("title")
        self.title_4.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_4)

        self.vlc_container = QWidget()
        self.vlc_container_layout = QVBoxLayout(self.vlc_container)
        self.vlc_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vlc_container_layout.setSpacing(12)
        layout.addWidget(self.vlc_container)

        return page

    def _make_page_5(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)

        self.title_5 = QLabel()
        self.title_5.setObjectName("title")
        self.title_5.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_5)

        self.step1_label = QLabel()
        self.step1_label.setObjectName("subtitle")
        self.step1_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.step1_label)

        self.clients_btn = QPushButton()
        self.clients_btn.setFixedWidth(300)
        self.clients_btn.clicked.connect(self._open_clients)
        layout.addWidget(self.clients_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.step2_label = QLabel()
        self.step2_label.setObjectName("subtitle")
        self.step2_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.step2_label)

        self.step3_label = QLabel()
        self.step3_label.setObjectName("subtitle")
        self.step3_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.step3_label)

        token_row = QHBoxLayout()
        token_row.setSpacing(10)
        token_row.addStretch()

        self.token_edit = QLineEdit()
        self.token_edit.setFixedWidth(500)
        token_row.addWidget(self.token_edit)

        self.paste_btn = QPushButton()
        self.paste_btn.setFixedWidth(180)
        self.paste_btn.clicked.connect(self._paste_token)
        token_row.addWidget(self.paste_btn)

        token_row.addStretch()
        layout.addLayout(token_row)

        check_row = QHBoxLayout()
        check_row.setSpacing(20)
        check_row.addStretch()

        self.check_btn = QPushButton()
        self.check_btn.setFixedWidth(160)
        self.check_btn.clicked.connect(self._check_token)
        check_row.addWidget(self.check_btn)

        self.token_status = QLabel()
        self.token_status.setObjectName("subtitle")
        self.token_status.setMinimumWidth(300)
        self.token_status.setWordWrap(True)
        check_row.addWidget(self.token_status)

        check_row.addStretch()
        layout.addLayout(check_row)

        return page

    # ============================================================
    # Обновление UI / локализация
    # ============================================================

    def _update_navigation(self):
        self.step_label.setText(
            i18n.tr("onboarding.step",
                    current=self.current_step,
                    total=self.TOTAL_STEPS)
        )

        self.back_btn.setText(i18n.tr("onboarding.back"))
        self.back_btn.setEnabled(self.current_step > 1)

        if self.current_step == self.TOTAL_STEPS:
            self.next_btn.setText(i18n.tr("onboarding.finish"))
            self.next_btn.setEnabled(self.temp_token_valid)
        else:
            self.next_btn.setText(i18n.tr("onboarding.next"))
            self.next_btn.setEnabled(True)

    def _refresh_all_texts(self):
        """Обновляет все тексты после смены языка или при первом показе."""
        # Шаг 1
        self.title_1.setText(i18n.tr("onboarding.language.title"))
        self.subtitle_1.setText(i18n.tr("onboarding.language.subtitle"))

        # Шаг 2
        self.title_2.setText(i18n.tr("onboarding.theme.title"))
        self.tile_dark.label.setText(i18n.tr("onboarding.theme.dark"))
        self.tile_light.label.setText(i18n.tr("onboarding.theme.light"))
        self.system_check.setText(i18n.tr("onboarding.theme.system"))
        self._update_theme_tiles()

        # Шаг 3
        self.title_3.setText(i18n.tr("onboarding.library.title"))
        self.library_browse_btn.setText(i18n.tr("onboarding.library.browse"))
        self.hint_3.setText(i18n.tr("onboarding.library.hint"))

        # Шаг 4
        self.title_4.setText(i18n.tr("onboarding.vlc.title"))
        self._populate_vlc_page()

        # Шаг 5
        self.title_5.setText(i18n.tr("onboarding.token.title"))
        self.step1_label.setText(i18n.tr("onboarding.token.step1"))
        self.step2_label.setText(i18n.tr("onboarding.token.step2"))
        self.step3_label.setText(i18n.tr("onboarding.token.step3"))
        self.clients_btn.setText(i18n.tr("onboarding.token.open_clients"))
        self.paste_btn.setText(i18n.tr("onboarding.token.paste"))
        self.check_btn.setText(i18n.tr("onboarding.token.check"))
        self._update_token_status()

    # ============================================================
    # Переключение шагов
    # ============================================================

    def _show_step(self, step_num: int):
        self.current_step = step_num
        self.stack.setCurrentIndex(step_num - 1)
        self._update_navigation()

        if step_num == 4:
            self._populate_vlc_page()
        if step_num == 5:
            self._update_token_status()

    # ============================================================
    # Шаг 1: Язык
    # ============================================================

    def _on_language_change(self, index: int):
        code = self.lang_combo.itemData(index)
        if not code or code == self.temp_language:
            return
        self.temp_language = code
        i18n.load(code)
        logger.info(f"Язык изменён на: {code}")
        self._refresh_all_texts()
        self._update_navigation()

    # ============================================================
    # Шаг 2: Тема
    # ============================================================

    def _on_theme_click(self, theme_name: str):
        if self.temp_use_system_theme:
            return
        self.temp_theme = theme_name
        self._update_theme_tiles()
        apply_theme(theme_name)

    def _update_theme_tiles(self):
        if self.temp_use_system_theme:
            self.tile_dark.set_selected(False)
            self.tile_light.set_selected(False)
        else:
            self.tile_dark.set_selected(self.temp_theme == "dark")
            self.tile_light.set_selected(self.temp_theme == "light")

    def _on_system_theme_toggle(self, state: int):
        self.temp_use_system_theme = bool(state)
        if self.temp_use_system_theme:
            apply_theme("system")
        else:
            apply_theme(self.temp_theme)
        self._update_theme_tiles()

    # ============================================================
    # Шаг 3: Папка библиотеки
    # ============================================================

    def _browse_library(self):
        d = QFileDialog.getExistingDirectory(
            self, i18n.tr("onboarding.library.title"),
            self.library_edit.text() or os.path.expanduser("~"),
        )
        if d:
            self.library_edit.setText(d)

    def _validate_library(self) -> bool:
        path = self.library_edit.text().strip()
        if not path:
            QMessageBox.warning(
                self, i18n.tr("common.error"),
                i18n.tr("library.no_library_path"),
            )
            return False

        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(
                    self, i18n.tr("common.error"),
                    f"Не удалось создать папку:\n{e}",
                )
                return False

        if not os.path.isdir(path):
            QMessageBox.critical(
                self, i18n.tr("common.error"),
                "Путь не является папкой.",
            )
            return False

        test_file = os.path.join(path, ".anime_library_test")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except OSError:
            QMessageBox.critical(
                self, i18n.tr("common.error"),
                "Нет прав на запись в эту папку.",
            )
            return False

        self.temp_library_path = path
        return True

    # ============================================================
    # Шаг 4: VLC
    # ============================================================

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _populate_vlc_page(self):
        self._clear_layout(self.vlc_container_layout)

        found = find_vlc_exe(self.temp_vlc_path) or find_vlc_exe()

        if found:
            self.temp_vlc_path = found

            found_label = QLabel(i18n.tr("onboarding.vlc.found"))
            found_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.vlc_container_layout.addWidget(found_label)

            path_label = QLabel(found)
            path_label.setObjectName("subtitle")
            path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            path_label.setWordWrap(True)
            path_label.setFixedWidth(700)
            self.vlc_container_layout.addWidget(path_label)

            browse_btn = QPushButton(i18n.tr("settings.browse"))
            browse_btn.setFixedWidth(220)
            browse_btn.clicked.connect(self._browse_vlc)
            self.vlc_container_layout.addWidget(
                browse_btn, alignment=Qt.AlignmentFlag.AlignCenter
            )
        else:
            not_found = QLabel(i18n.tr("onboarding.vlc.not_found"))
            not_found.setAlignment(Qt.AlignmentFlag.AlignCenter)
            not_found.setStyleSheet(
                "color: #d97a7a; font-size: 16px; font-weight: bold;"
            )
            self.vlc_container_layout.addWidget(not_found)

            explain = QLabel(i18n.tr("onboarding.vlc.explain"))
            explain.setObjectName("subtitle")
            explain.setAlignment(Qt.AlignmentFlag.AlignCenter)
            explain.setWordWrap(True)
            explain.setFixedWidth(600)
            self.vlc_container_layout.addWidget(explain)

            download_btn = QPushButton(i18n.tr("onboarding.vlc.download"))
            download_btn.setFixedWidth(220)
            download_btn.clicked.connect(self._open_vlc_download)
            self.vlc_container_layout.addWidget(
                download_btn, alignment=Qt.AlignmentFlag.AlignCenter
            )

            row = QHBoxLayout()
            row.setSpacing(10)
            row.addStretch()

            self.vlc_edit = QLineEdit()
            self.vlc_edit.setText(self.temp_vlc_path)
            self.vlc_edit.setFixedWidth(450)
            row.addWidget(self.vlc_edit)

            browse_btn = QPushButton(i18n.tr("settings.browse"))
            browse_btn.setFixedWidth(120)
            browse_btn.clicked.connect(self._browse_vlc)
            row.addWidget(browse_btn)

            row.addStretch()
            self.vlc_container_layout.addLayout(row)

            check_btn = QPushButton(i18n.tr("onboarding.vlc.check_again"))
            check_btn.setObjectName("secondary")
            check_btn.setFixedWidth(220)
            check_btn.clicked.connect(self._check_vlc_again)
            self.vlc_container_layout.addWidget(
                check_btn, alignment=Qt.AlignmentFlag.AlignCenter
            )

            skip_btn = QPushButton(i18n.tr("onboarding.skip"))
            skip_btn.setObjectName("secondary")
            skip_btn.setFixedWidth(220)
            skip_btn.clicked.connect(self._skip_vlc)
            self.vlc_container_layout.addWidget(
                skip_btn, alignment=Qt.AlignmentFlag.AlignCenter
            )

    def _browse_vlc(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "VLC executable",
            self.temp_vlc_path or "C:\\Program Files",
            "VLC (vlc.exe);;Executable (*.exe);;All files (*.*)",
        )
        if not f:
            return
        self.temp_vlc_path = f
        d = os.path.dirname(f)
        if os.path.isfile(os.path.join(d, "libvlc.dll")):
            self.temp_libvlc_dir = d
        self._populate_vlc_page()

    def _check_vlc_again(self):
        found = find_vlc_exe(self.temp_vlc_path) or find_vlc_exe()
        if found:
            self.temp_vlc_path = found
        self._populate_vlc_page()

    def _open_vlc_download(self):
        webbrowser.open(VLC_DOWNLOAD_PAGE)

    def _skip_vlc(self):
        answer = QMessageBox.question(
            self, i18n.tr("common.warning"),
            i18n.tr("onboarding.vlc.skip_warning"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.temp_vlc_path = ""
        self.temp_libvlc_dir = ""
        self._on_next()

    # ============================================================
    # Шаг 5: Токен
    # ============================================================

    def _open_clients(self):
        webbrowser.open(CLIENTS_PAGE)

    def _paste_token(self):
        text = QApplication.clipboard().text()
        if text:
            self.token_edit.setText(text.strip())

    def _check_token(self):
        token = self.token_edit.text().strip()

        if not token:
            self.temp_token_state = "invalid"
            self.temp_token_error = "Пустое поле"
            self.temp_token_valid = False
            self._update_token_status()
            self._update_navigation()
            return

        self.temp_token_state = "checking"
        self.temp_token_error = ""
        self._update_token_status()
        QApplication.processEvents()

        ok, error = self.api.check_token(token)

        self.temp_token = token
        if ok:
            self.temp_token_valid = True
            self.temp_token_state = "valid"
            self.temp_token_error = ""
        else:
            self.temp_token_valid = False
            self.temp_token_state = "invalid"
            self.temp_token_error = error

        self._update_token_status()
        self._update_navigation()

    def _update_token_status(self):
        if not hasattr(self, "token_status") or self.token_status is None:
            return

        if self.temp_token_state == "valid":
            self.token_status.setText(i18n.tr("onboarding.token.valid"))
            self.token_status.setStyleSheet("color: #7ac77a;")
        elif self.temp_token_state == "checking":
            self.token_status.setText("Проверка…")
            self.token_status.setStyleSheet("color: #888888;")
        elif self.temp_token_state == "invalid":
            base = i18n.tr("onboarding.token.invalid")
            text = f"{base}\n{self.temp_token_error}" if self.temp_token_error else base
            self.token_status.setText(text)
            self.token_status.setStyleSheet("color: #d97a7a;")
        else:
            self.token_status.setText(i18n.tr("onboarding.token.status_idle"))
            self.token_status.setStyleSheet("color: #888888;")

    # ============================================================
    # Навигация
    # ============================================================

    def _on_next(self):
        if self.current_step == 3:
            if not self._validate_library():
                return

        if self.current_step < self.TOTAL_STEPS:
            self._show_step(self.current_step + 1)
        else:
            self._finish()

    def _on_back(self):
        if self.current_step > 1:
            self._show_step(self.current_step - 1)

    # ============================================================
    # Завершение
    # ============================================================

    def _finish(self):
        s = self.app.settings
        s.language = self.temp_language
        s.theme = "system" if self.temp_use_system_theme else self.temp_theme
        s.library_path = self.temp_library_path
        s.vlc_exe_path = self.temp_vlc_path
        s.libvlc_dir = self.temp_libvlc_dir

        if self.temp_token:
            self.api.save_token(self.temp_token)

        s.onboarding_completed = True

        apply_theme(s.theme)

        logger.info("Онбординг завершён")
        self.app.show_library()