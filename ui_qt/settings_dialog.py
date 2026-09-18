# -*- coding: utf-8 -*-
"""Диалог настроек приложения."""

import os
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QFrame, QScrollArea,
    QWidget, QFileDialog, QMessageBox, QApplication,
)

from core import i18n
from core.constants import (
    APP_NAME, APP_VERSION, LOG_PATH,
    AVAILABLE_LANGUAGES,
)
from core.vlc_finder import find_vlc_exe, find_libvlc_dir
from core.covers import human_size
from ui_qt.styles.loader import apply_theme


logger = logging.getLogger(__name__)


# Параметры, требующие перезапуска приложения
RESTART_REQUIRED_KEYS = {"language", "vlc_exe_path"}


class SettingsDialog(QDialog):
    """Модальное окно настроек."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.db = app.db
        self.settings = app.settings
        self.api = app.api

        self.need_restart = False
        self._initial = {}
        self._theme_at_open = None

        self._build_ui()
        self._load_values()

    # ============================================================
    # Разметка
    # ============================================================

    def _build_ui(self):
        self.setWindowTitle(i18n.tr("settings.title"))
        self.setModal(True)
        self.resize(720, 680)
        self.setMinimumSize(640, 540)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Заголовок
        header = QFrame()
        header.setObjectName("topBar")
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        title = QLabel(i18n.tr("settings.title"))
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        root.addWidget(header)

        # Область прокрутки
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(20)

        # Секции
        content_layout.addWidget(self._make_library_section())
        content_layout.addWidget(self._make_player_section())
        content_layout.addWidget(self._make_interface_section())

        # Уведомления временно скрыты (в разработке)
        # content_layout.addWidget(self._make_notifications_section())

        content_layout.addWidget(self._make_token_section())
        content_layout.addWidget(self._make_logs_section())
        content_layout.addWidget(self._make_about_section())
        content_layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # Кнопки
        footer = QFrame()
        footer.setObjectName("bottomBar")
        footer.setFixedHeight(72)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 12, 20, 12)
        footer_layout.addStretch()

        cancel_btn = QPushButton(i18n.tr("settings.cancel"))
        cancel_btn.setObjectName("secondary")
        cancel_btn.setFixedWidth(160)
        cancel_btn.setFixedHeight(44)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        save_btn = QPushButton(i18n.tr("settings.save"))
        save_btn.setFixedWidth(200)
        save_btn.setFixedHeight(44)
        save_btn.clicked.connect(self._on_save)
        footer_layout.addWidget(save_btn)

        root.addWidget(footer)

    # ---------- Секции ----------

    def _make_section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 15px; font-weight: bold;")
        return lbl

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: rgba(120, 120, 120, 0.3);")
        return line

    def _make_library_section(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._make_section_title(
            i18n.tr("settings.section.library")
        ))

        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(i18n.tr("settings.library.path"))
        lbl.setFixedWidth(140)
        row.addWidget(lbl)

        self.library_edit = QLineEdit()
        self.library_edit.setFixedHeight(38)
        row.addWidget(self.library_edit, 1)

        browse = QPushButton(i18n.tr("settings.browse"))
        browse.setFixedWidth(120)
        browse.setFixedHeight(38)
        browse.clicked.connect(self._browse_library)
        row.addWidget(browse)
        layout.addLayout(row)

        hint = QLabel(i18n.tr("settings.library.hint"))
        hint.setStyleSheet("font-size: 11px; color: #888888;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addWidget(self._make_divider())
        return frame

    def _make_player_section(self) -> QFrame:
        """
        Секция плеера.

        ПРИМЕЧАНИЕ:
        - Выбор режима (внешний / встроенный) и поле libvlc скрыты,
          так как встроенный плеер ещё не реализован. Сейчас всегда
          используется внешний VLC.
        - Когда встроенный плеер будет готов, верните контролы
          выбора режима и поля libvlc.
        """
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._make_section_title(
            i18n.tr("settings.section.player")
        ))

        # --- Пока скрыто: режим плеера ---
        # row = QHBoxLayout()
        # lbl = QLabel(i18n.tr("settings.player.mode"))
        # lbl.setFixedWidth(140)
        # row.addWidget(lbl)
        # self.player_mode_combo = QComboBox()
        # self.player_mode_combo.addItem(i18n.tr("settings.player.external"), "external")
        # self.player_mode_combo.addItem(i18n.tr("settings.player.embedded"), "embedded")
        # self.player_mode_combo.setFixedHeight(38)
        # self.player_mode_combo.setMaximumWidth(280)
        # row.addWidget(self.player_mode_combo)
        # row.addStretch()
        # layout.addLayout(row)

        # --- Путь к VLC (единственный контрол в этой секции) ---
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(i18n.tr("settings.player.vlc_path"))
        lbl.setFixedWidth(140)
        row.addWidget(lbl)

        self.vlc_edit = QLineEdit()
        self.vlc_edit.setFixedHeight(38)
        row.addWidget(self.vlc_edit, 1)

        find_btn = QPushButton(i18n.tr("settings.player.find_vlc"))
        find_btn.setFixedWidth(140)
        find_btn.setFixedHeight(38)
        find_btn.clicked.connect(self._auto_find_vlc)
        row.addWidget(find_btn)

        browse = QPushButton(i18n.tr("settings.browse"))
        browse.setFixedWidth(100)
        browse.setFixedHeight(38)
        browse.clicked.connect(self._browse_vlc)
        row.addWidget(browse)
        layout.addLayout(row)

        # Строка "обнаружено"
        self.vlc_detected_label = QLabel()
        self.vlc_detected_label.setStyleSheet(
            "font-size: 11px; color: #888888;"
        )
        layout.addWidget(self.vlc_detected_label)

        # --- Пока скрыто: папка libvlc ---
        # row = QHBoxLayout()
        # lbl = QLabel(i18n.tr("settings.player.libvlc_dir"))
        # lbl.setFixedWidth(140)
        # row.addWidget(lbl)
        # self.libvlc_edit = QLineEdit()
        # self.libvlc_edit.setFixedHeight(38)
        # row.addWidget(self.libvlc_edit, 1)
        # browse = QPushButton(i18n.tr("settings.browse"))
        # browse.setFixedWidth(100)
        # browse.setFixedHeight(38)
        # browse.clicked.connect(self._browse_libvlc)
        # row.addWidget(browse)
        # layout.addLayout(row)

        # --- Пока скрыто: предупреждение о внешнем режиме ---
        # self.player_warning = QLabel(i18n.tr("settings.player.external_warning"))
        # self.player_warning.setStyleSheet("font-size: 11px; color: #d9a56b;")
        # self.player_warning.setWordWrap(True)
        # layout.addWidget(self.player_warning)

        layout.addWidget(self._make_divider())
        return frame

    def _make_interface_section(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._make_section_title(
            i18n.tr("settings.section.interface")
        ))

        # Язык
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(i18n.tr("settings.interface.language"))
        lbl.setFixedWidth(140)
        row.addWidget(lbl)

        self.lang_combo = QComboBox()
        lang_names = {"en": "English", "ru": "Русский"}
        for code in AVAILABLE_LANGUAGES:
            self.lang_combo.addItem(lang_names.get(code, code), code)
        self.lang_combo.setFixedHeight(38)
        self.lang_combo.setMaximumWidth(280)
        row.addWidget(self.lang_combo)
        row.addStretch()
        layout.addLayout(row)

        # Тема
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(i18n.tr("settings.interface.theme"))
        lbl.setFixedWidth(140)
        row.addWidget(lbl)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem(
            i18n.tr("settings.interface.theme_dark"), "dark"
        )
        self.theme_combo.addItem(
            i18n.tr("settings.interface.theme_light"), "light"
        )
        self.theme_combo.addItem(
            i18n.tr("settings.interface.theme_system"), "system"
        )
        self.theme_combo.setFixedHeight(38)
        self.theme_combo.setMaximumWidth(280)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        row.addWidget(self.theme_combo)
        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(self._make_divider())
        return frame

    # ---- Секция уведомлений (временно отключена) ----
    # def _make_notifications_section(self) -> QFrame:
    #     frame = QFrame()
    #     layout = QVBoxLayout(frame)
    #     layout.setContentsMargins(0, 0, 0, 0)
    #     layout.setSpacing(8)
    #
    #     layout.addWidget(self._make_section_title(
    #         i18n.tr("settings.section.notifications")
    #     ))
    #
    #     self.reminders_cb = QCheckBox(
    #         i18n.tr("settings.notifications.reminders")
    #     )
    #     layout.addWidget(self.reminders_cb)
    #
    #     hint = QLabel(i18n.tr("settings.notifications.explain"))
    #     hint.setStyleSheet("font-size: 11px; color: #888888;")
    #     hint.setWordWrap(True)
    #     layout.addWidget(hint)
    #
    #     layout.addWidget(self._make_divider())
    #     return frame

    def _make_token_section(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._make_section_title(
            i18n.tr("settings.section.token")
        ))

        # Статус
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(i18n.tr("settings.token.status"))
        lbl.setFixedWidth(140)
        row.addWidget(lbl)

        self.token_status_label = QLabel()
        self.token_status_label.setStyleSheet("font-size: 12px;")
        row.addWidget(self.token_status_label)
        row.addStretch()
        layout.addLayout(row)

        # Поле ввода нового токена
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(i18n.tr("settings.token.enter"))
        lbl.setFixedWidth(140)
        row.addWidget(lbl)

        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText(
            i18n.tr("settings.token.placeholder")
        )
        self.token_edit.setFixedHeight(38)
        row.addWidget(self.token_edit, 1)
        layout.addLayout(row)

        # Кнопки
        row = QHBoxLayout()
        row.addSpacing(140)

        paste_btn = QPushButton(i18n.tr("settings.token.paste"))
        paste_btn.setFixedWidth(140)
        paste_btn.setFixedHeight(38)
        paste_btn.setObjectName("secondary")
        paste_btn.clicked.connect(self._paste_token)
        row.addWidget(paste_btn)

        check_btn = QPushButton(i18n.tr("settings.token.check"))
        check_btn.setFixedWidth(140)
        check_btn.setFixedHeight(38)
        check_btn.clicked.connect(self._check_token)
        row.addWidget(check_btn)

        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(self._make_divider())
        return frame

    def _make_logs_section(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._make_section_title(
            i18n.tr("settings.section.logs")
        ))

        row = QHBoxLayout()
        row.setSpacing(8)

        self.log_size_label = QLabel(
            i18n.tr("settings.logs.size", size="—")
        )
        self.log_size_label.setFixedWidth(140)
        row.addWidget(self.log_size_label)

        refresh_btn = QPushButton(i18n.tr("settings.logs.refresh"))
        refresh_btn.setFixedWidth(140)
        refresh_btn.setFixedHeight(38)
        refresh_btn.setObjectName("secondary")
        refresh_btn.clicked.connect(self._refresh_log_size)
        row.addWidget(refresh_btn)

        open_btn = QPushButton(i18n.tr("settings.logs.open_folder"))
        open_btn.setFixedWidth(160)
        open_btn.setFixedHeight(38)
        open_btn.setObjectName("secondary")
        open_btn.clicked.connect(self._open_logs_folder)
        row.addWidget(open_btn)

        clear_btn = QPushButton(i18n.tr("settings.logs.clear"))
        clear_btn.setFixedWidth(140)
        clear_btn.setFixedHeight(38)
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(self._clear_logs)
        row.addWidget(clear_btn)

        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(self._make_divider())
        return frame

    def _make_about_section(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._make_section_title(
            i18n.tr("settings.section.about")
        ))

        name = QLabel(f"{APP_NAME}")
        name.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(name)

        version = QLabel(
            i18n.tr("settings.about.version", version=APP_VERSION)
        )
        version.setStyleSheet("font-size: 12px; color: #888888;")
        layout.addWidget(version)

        desc = QLabel(i18n.tr("settings.about.description"))
        desc.setStyleSheet("font-size: 11px; color: #888888;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        return frame

    # ============================================================
    # Загрузка значений
    # ============================================================

    def _load_values(self):
        s = self.settings

        # Библиотека
        self.library_edit.setText(s.library_path or "")

        # Плеер: путь к VLC
        self.vlc_edit.setText(s.vlc_exe_path or "")

        detected_vlc = find_vlc_exe(s.vlc_exe_path)
        if detected_vlc:
            self.vlc_detected_label.setText(
                i18n.tr("settings.player.detected", path=detected_vlc)
            )
            self.vlc_detected_label.setStyleSheet(
                "font-size: 11px; color: #7ac77a;"
            )
        else:
            self.vlc_detected_label.setText(
                i18n.tr("settings.player.not_detected")
            )
            self.vlc_detected_label.setStyleSheet(
                "font-size: 11px; color: #d97a7a;"
            )

        # Интерфейс
        lang = s.language or "ru"
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == lang:
                self.lang_combo.setCurrentIndex(i)
                break

        theme = s.theme or "dark"
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == theme:
                self.theme_combo.setCurrentIndex(i)
                break

        # Токен
        self._refresh_token_status()

        # Логи
        self._refresh_log_size()

        # Сохраняем изначальные значения для сравнения
        self._initial = {
            "library_path": s.library_path,
            "vlc_exe_path": s.vlc_exe_path,
            "language": s.language,
            "theme": s.theme,
        }
        self._theme_at_open = s.theme

    # ============================================================
    # Обработчики UI
    # ============================================================

    def _browse_library(self):
        start = self.library_edit.text() or os.path.expanduser("~")
        d = QFileDialog.getExistingDirectory(
            self, i18n.tr("settings.library.path"), start
        )
        if d:
            self.library_edit.setText(d)

    def _browse_vlc(self):
        start = self.vlc_edit.text() or "C:\\Program Files"
        f, _ = QFileDialog.getOpenFileName(
            self, i18n.tr("settings.player.vlc_path"), start,
            "VLC (vlc.exe);;Executable (*.exe);;All files (*.*)",
        )
        if f:
            self.vlc_edit.setText(f)
            self._refresh_detected_label()

    def _auto_find_vlc(self):
        found = find_vlc_exe()
        if found:
            self.vlc_edit.setText(found)
            self._refresh_detected_label()
        else:
            QMessageBox.information(
                self,
                i18n.tr("settings.player.find_vlc"),
                i18n.tr("settings.player.not_detected"),
            )

    def _refresh_detected_label(self):
        detected_vlc = find_vlc_exe(self.vlc_edit.text().strip())
        if detected_vlc:
            self.vlc_detected_label.setText(
                i18n.tr("settings.player.detected", path=detected_vlc)
            )
            self.vlc_detected_label.setStyleSheet(
                "font-size: 11px; color: #7ac77a;"
            )
        else:
            self.vlc_detected_label.setText(
                i18n.tr("settings.player.not_detected")
            )
            self.vlc_detected_label.setStyleSheet(
                "font-size: 11px; color: #d97a7a;"
            )

    def _on_theme_changed(self):
        """Мгновенно применяет тему (preview)."""
        theme = self.theme_combo.currentData()
        apply_theme(theme)

    def _paste_token(self):
        text = QApplication.clipboard().text()
        if text:
            self.token_edit.setText(text.strip())

    def _check_token(self):
        token = self.token_edit.text().strip()
        if not token:
            return
        ok, error = self.api.check_token(token)
        if ok:
            self.token_status_label.setText(
                i18n.tr("settings.token.status_active")
            )
            self.token_status_label.setStyleSheet(
                "font-size: 12px; color: #7ac77a;"
            )
        else:
            self.token_status_label.setText(
                i18n.tr("settings.token.status_invalid")
            )
            self.token_status_label.setStyleSheet(
                "font-size: 12px; color: #d97a7a;"
            )

    def _refresh_token_status(self):
        if self.api.has_token():
            self.token_status_label.setText(
                i18n.tr("settings.token.status_active")
            )
            self.token_status_label.setStyleSheet(
                "font-size: 12px; color: #7ac77a;"
            )
        else:
            self.token_status_label.setText(
                i18n.tr("settings.token.status_invalid")
            )
            self.token_status_label.setStyleSheet(
                "font-size: 12px; color: #d97a7a;"
            )

    def _refresh_log_size(self):
        total = 0
        for suffix in ("", ".1", ".2", ".3"):
            p = LOG_PATH + suffix
            if os.path.exists(p):
                try:
                    total += os.path.getsize(p)
                except OSError:
                    pass
        self.log_size_label.setText(
            i18n.tr("settings.logs.size", size=human_size(total))
        )

    def _open_logs_folder(self):
        folder = os.path.dirname(LOG_PATH)
        try:
            os.startfile(folder)
        except AttributeError:
            import subprocess
            import sys as _sys
            if _sys.platform == "darwin":
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])

    def _clear_logs(self):
        from ui_qt.dialogs.delete_dialog import ask_yes_no

        if not ask_yes_no(
            self,
            i18n.tr("settings.logs.confirm_clear_title"),
            i18n.tr("settings.logs.confirm_clear_text"),
        ):
            return

        for suffix in ("", ".1", ".2", ".3"):
            p = LOG_PATH + suffix
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError as e:
                    logger.error(f"Не удалось удалить {p}: {e}")

        self._refresh_log_size()
        QMessageBox.information(
            self,
            i18n.tr("settings.title"),
            i18n.tr("settings.logs.cleared"),
        )

    # ============================================================
    # Сохранение / отмена
    # ============================================================

    def _collect_values(self) -> dict:
        return {
            "library_path": self.library_edit.text().strip(),
            "vlc_exe_path": self.vlc_edit.text().strip(),
            "language": self.lang_combo.currentData(),
            "theme": self.theme_combo.currentData(),
        }

    def _on_save(self):
        values = self._collect_values()

        # Валидация пути библиотеки
        lib = values["library_path"]
        if lib and not os.path.isdir(lib):
            try:
                os.makedirs(lib, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(
                    self,
                    i18n.tr("common.error"),
                    f"Не удалось создать папку:\n{e}",
                )
                return

        # Обновление токена (если введён)
        new_token = self.token_edit.text().strip()
        if new_token:
            self.api.save_token(new_token)
            logger.info("Токен обновлён через настройки")

        # Определяем, нужен ли перезапуск
        changed_keys = set()
        for key, new_val in values.items():
            old_val = self._initial.get(key)
            if str(old_val) != str(new_val):
                changed_keys.add(key)

        need_restart = bool(changed_keys & RESTART_REQUIRED_KEYS)

        # Сохраняем значения
        self.settings.library_path = values["library_path"]
        self.settings.vlc_exe_path = values["vlc_exe_path"]
        self.settings.language = values["language"]
        self.settings.theme = values["theme"]

        # player_mode пока всегда external (embedded в разработке)
        self.settings.player_mode = "external"

        logger.info(f"Настройки сохранены, изменено: {changed_keys}")

        if need_restart:
            from ui_qt.dialogs.delete_dialog import ask_yes_no
            if ask_yes_no(
                self,
                i18n.tr("settings.restart_title"),
                i18n.tr("settings.restart_text"),
                yes_text=i18n.tr("settings.restart_button"),
                no_text=i18n.tr("common.cancel"),
            ):
                self.need_restart = True
                self.accept()
                return

        self.accept()

    def reject(self):
        """При отмене — откатываем тему."""
        if self._theme_at_open is not None:
            apply_theme(self._theme_at_open)
        super().reject()