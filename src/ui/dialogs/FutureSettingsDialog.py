# --- Standard Library Imports ---
import os
import json
import sys

# --- PyQt5 Imports ---
from PyQt5.QtCore import Qt, QStandardPaths
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
    QGroupBox, QComboBox, QMessageBox, QGridLayout, QCheckBox
)

# --- Local Application Imports ---
from ...i18n.translator import get_translation
from ...utils.resolution import get_dark_theme
from ..main_window import get_app_icon_object
from ...config.constants import (
    THEME_KEY, LANGUAGE_KEY, DOWNLOAD_LOCATION_KEY,
    RESOLUTION_KEY, UI_SCALE_KEY, SAVE_CREATOR_JSON_KEY,
    COOKIE_TEXT_KEY, USE_COOKIE_KEY,
    FETCH_FIRST_KEY
)
from ...services.updater import UpdateChecker, UpdateDownloader

class FutureSettingsDialog(QDialog):
    """
    A dialog for managing application-wide settings like theme, language,
    and display options, with an organized layout.
    """
    def __init__(self, parent_app_ref, parent=None):
        super().__init__(parent)
        self.parent_app = parent_app_ref
        self.setModal(True)
        self.update_downloader_thread = None # To keep a reference

        app_icon = get_app_icon_object()
        if app_icon and not app_icon.isNull():
            self.setWindowIcon(app_icon)

        screen_height = QApplication.primaryScreen().availableGeometry().height() if QApplication.primaryScreen() else 800
        scale_factor = screen_height / 800.0
        base_min_w, base_min_h = 420, 480 # Increased height for update section
        scaled_min_w = int(base_min_w * scale_factor)
        scaled_min_h = int(base_min_h * scale_factor)
        self.setMinimumSize(scaled_min_w, scaled_min_h)

        self._init_ui()
        self._retranslate_ui()
        self._apply_theme()

    def _init_ui(self):
        """Initializes all UI components and layouts for the dialog."""
        main_layout = QVBoxLayout(self)

        self.interface_group_box = QGroupBox()
        interface_layout = QGridLayout(self.interface_group_box)

        # Theme, UI Scale, Language (unchanged)...
        self.theme_label = QLabel()
        self.theme_toggle_button = QPushButton()
        self.theme_toggle_button.clicked.connect(self._toggle_theme)
        interface_layout.addWidget(self.theme_label, 0, 0)
        interface_layout.addWidget(self.theme_toggle_button, 0, 1)

        self.ui_scale_label = QLabel()
        self.ui_scale_combo_box = QComboBox()
        self.ui_scale_combo_box.currentIndexChanged.connect(self._display_setting_changed)
        interface_layout.addWidget(self.ui_scale_label, 1, 0)
        interface_layout.addWidget(self.ui_scale_combo_box, 1, 1)

        self.language_label = QLabel()
        self.language_combo_box = QComboBox()
        self.language_combo_box.currentIndexChanged.connect(self._language_selection_changed)
        interface_layout.addWidget(self.language_label, 2, 0)
        interface_layout.addWidget(self.language_combo_box, 2, 1)

        main_layout.addWidget(self.interface_group_box)

        self.download_window_group_box = QGroupBox()
        download_window_layout = QGridLayout(self.download_window_group_box)
        
        self.window_size_label = QLabel()
        self.resolution_combo_box = QComboBox()
        self.resolution_combo_box.currentIndexChanged.connect(self._display_setting_changed)
        download_window_layout.addWidget(self.window_size_label, 0, 0)
        download_window_layout.addWidget(self.resolution_combo_box, 0, 1)

        self.default_path_label = QLabel()
        self.save_path_button = QPushButton()
        self.save_path_button.clicked.connect(self._save_cookie_and_path)
        download_window_layout.addWidget(self.default_path_label, 1, 0)
        download_window_layout.addWidget(self.save_path_button, 1, 1)

        self.save_creator_json_checkbox = QCheckBox()
        self.save_creator_json_checkbox.stateChanged.connect(self._creator_json_setting_changed)
        download_window_layout.addWidget(self.save_creator_json_checkbox, 2, 0, 1, 2)
        
        self.fetch_first_checkbox = QCheckBox()
        self.fetch_first_checkbox.stateChanged.connect(self._fetch_first_setting_changed)
        download_window_layout.addWidget(self.fetch_first_checkbox, 3, 0, 1, 2)

        main_layout.addWidget(self.download_window_group_box)

        # --- NEW: Update Section ---
        self.update_group_box = QGroupBox()
        update_layout = QGridLayout(self.update_group_box)
        self.version_label = QLabel()
        self.update_status_label = QLabel()
        self.check_update_button = QPushButton()
        self.check_update_button.clicked.connect(self._check_for_updates)
        update_layout.addWidget(self.version_label, 0, 0)
        update_layout.addWidget(self.update_status_label, 0, 1)
        update_layout.addWidget(self.check_update_button, 1, 0, 1, 2)
        main_layout.addWidget(self.update_group_box)
        # --- END: New Section ---

        main_layout.addStretch(1)

        self.ok_button = QPushButton()
        self.ok_button.clicked.connect(self.accept)
        main_layout.addWidget(self.ok_button, 0, Qt.AlignRight | Qt.AlignBottom)

    def _retranslate_ui(self):
        self.setWindowTitle(self._tr("settings_dialog_title", "Settings"))
        self.interface_group_box.setTitle(self._tr("interface_group_title", "Interface Settings"))
        self.download_window_group_box.setTitle(self._tr("download_window_group_title", "Download & Window Settings"))
        self.theme_label.setText(self._tr("theme_label", "Theme:"))
        self.ui_scale_label.setText(self._tr("ui_scale_label", "UI Scale:"))
        self.language_label.setText(self._tr("language_label", "Language:"))
        self.window_size_label.setText(self._tr("window_size_label", "Window Size:"))
        self.default_path_label.setText(self._tr("default_path_label", "Default Path:"))
        self.save_creator_json_checkbox.setText(self._tr("save_creator_json_label", "Save Creator.json file"))
        self.fetch_first_checkbox.setText(self._tr("fetch_first_label", "Fetch First (Download after all pages are found)"))
        self.fetch_first_checkbox.setToolTip(self._tr("fetch_first_tooltip", "If checked, the downloader will find all posts from a creator first before starting any downloads.\nThis can be slower to start but provides a more accurate progress bar."))
        self._update_theme_toggle_button_text()
        self.save_path_button.setText(self._tr("settings_save_cookie_path_button", "Save Cookie + Download Path"))
        self.save_path_button.setToolTip(self._tr("settings_save_cookie_path_tooltip", "Save the current 'Download Location' and Cookie settings for future sessions."))
        self.ok_button.setText(self._tr("ok_button", "OK"))

        # --- NEW: Translations for Update Section ---
        self.update_group_box.setTitle(self._tr("update_group_title", "Application Updates"))
        current_version = self.parent_app.windowTitle().split(' v')[-1]
        self.version_label.setText(self._tr("current_version_label", f"Current Version: v{current_version}"))
        self.update_status_label.setText(self._tr("update_status_ready", "Ready to check."))
        self.check_update_button.setText(self._tr("check_for_updates_button", "Check for Updates"))
        # --- END: New Translations ---

        self._populate_display_combo_boxes()
        self._populate_language_combo_box()
        self._load_checkbox_states()

    def _check_for_updates(self):
        """Starts the update check thread."""
        self.check_update_button.setEnabled(False)
        self.update_status_label.setText(self._tr("update_status_checking", "Checking..."))
        current_version = self.parent_app.windowTitle().split(' v')[-1]
        
        self.update_checker_thread = UpdateChecker(current_version)
        self.update_checker_thread.update_available.connect(self._on_update_available)
        self.update_checker_thread.up_to_date.connect(self._on_up_to_date)
        self.update_checker_thread.update_error.connect(self._on_update_error)
        self.update_checker_thread.start()

    def _on_update_available(self, new_version, download_url):
        self.update_status_label.setText(self._tr("update_status_found", f"Update found: v{new_version}"))
        self.check_update_button.setEnabled(True)
        
        reply = QMessageBox.question(self, self._tr("update_available_title", "Update Available"),
                                     self._tr("update_available_message", f"A new version (v{new_version}) is available.\nWould you like to download and install it now?"),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            self.ok_button.setEnabled(False)
            self.check_update_button.setEnabled(False)
            self.update_status_label.setText(self._tr("update_status_downloading", "Downloading update..."))
            self.update_downloader_thread = UpdateDownloader(download_url, self.parent_app)
            self.update_downloader_thread.download_finished.connect(self._on_download_finished)
            self.update_downloader_thread.download_error.connect(self._on_update_error)
            self.update_downloader_thread.start()

    def _on_download_finished(self):
        QApplication.instance().quit()
    
    def _on_up_to_date(self, message):
        self.update_status_label.setText(self._tr("update_status_latest", message))
        self.check_update_button.setEnabled(True)
    
    def _on_update_error(self, message):
        self.update_status_label.setText(self._tr("update_status_error", f"Error: {message}"))
        self.check_update_button.setEnabled(True)
        self.ok_button.setEnabled(True)

    # --- (The rest of the file remains unchanged from your provided code) ---
    def _load_checkbox_states(self):
        self.save_creator_json_checkbox.blockSignals(True)
        should_save = self.parent_app.settings.value(SAVE_CREATOR_JSON_KEY, True, type=bool)
        self.save_creator_json_checkbox.setChecked(should_save)
        self.save_creator_json_checkbox.blockSignals(False)

        self.fetch_first_checkbox.blockSignals(True)
        should_fetch_first = self.parent_app.settings.value(FETCH_FIRST_KEY, False, type=bool)
        self.fetch_first_checkbox.setChecked(should_fetch_first)
        self.fetch_first_checkbox.blockSignals(False)

    def _creator_json_setting_changed(self, state):
        is_checked = state == Qt.Checked
        self.parent_app.settings.setValue(SAVE_CREATOR_JSON_KEY, is_checked)
        self.parent_app.settings.sync()

    def _fetch_first_setting_changed(self, state):
        is_checked = state == Qt.Checked
        self.parent_app.settings.setValue(FETCH_FIRST_KEY, is_checked)
        self.parent_app.settings.sync()

    def _tr(self, key, default_text=""):
        if callable(get_translation) and self.parent_app:
            return get_translation(self.parent_app.current_selected_language, key, default_text)
        return default_text

    def _apply_theme(self):
        if self.parent_app and self.parent_app.current_theme == "dark":
            scale = getattr(self.parent_app, 'scale_factor', 1)
            self.setStyleSheet(get_dark_theme(scale))
        else:
            self.setStyleSheet("")

    def _update_theme_toggle_button_text(self):
        if self.parent_app.current_theme == "dark":
            self.theme_toggle_button.setText(self._tr("theme_toggle_light", "Switch to Light Mode"))
        else:
            self.theme_toggle_button.setText(self._tr("theme_toggle_dark", "Switch to Dark Mode"))

    def _toggle_theme(self):
        new_theme = "light" if self.parent_app.current_theme == "dark" else "dark"
        self.parent_app.settings.setValue(THEME_KEY, new_theme)
        self.parent_app.settings.sync()
        self.parent_app.current_theme = new_theme
        self._apply_theme()
        if hasattr(self.parent_app, '_apply_theme_and_restart_prompt'):
            self.parent_app._apply_theme_and_restart_prompt()

    def _populate_display_combo_boxes(self):
        self.resolution_combo_box.blockSignals(True)
        self.resolution_combo_box.clear()
        resolutions = [("Auto", "Auto"), ("1280x720", "1280x720"), ("1600x900", "1600x900"), ("1920x1080", "1920x1080")]
        current_res = self.parent_app.settings.value(RESOLUTION_KEY, "Auto")
        for res_key, res_name in resolutions:
            self.resolution_combo_box.addItem(res_name, res_key)
            if current_res == res_key:
                self.resolution_combo_box.setCurrentIndex(self.resolution_combo_box.count() - 1)
        self.resolution_combo_box.blockSignals(False)

        self.ui_scale_combo_box.blockSignals(True)
        self.ui_scale_combo_box.clear()
        scales = [
            (0.5, "50%"),
            (0.7, "70%"),
            (0.9, "90%"),
            (1.0, "100% (Default)"),
            (1.25, "125%"),
            (1.50, "150%"),
            (1.75, "175%"),
            (2.0, "200%")
            ]
        current_scale = self.parent_app.settings.value(UI_SCALE_KEY, 1.0)
        for scale_val, scale_name in scales:
            self.ui_scale_combo_box.addItem(scale_name, scale_val)
            if abs(float(current_scale) - scale_val) < 0.01:
                self.ui_scale_combo_box.setCurrentIndex(self.ui_scale_combo_box.count() - 1)
        self.ui_scale_combo_box.blockSignals(False)

    def _display_setting_changed(self):
        selected_res = self.resolution_combo_box.currentData()
        selected_scale = self.ui_scale_combo_box.currentData()
        self.parent_app.settings.setValue(RESOLUTION_KEY, selected_res)
        self.parent_app.settings.setValue(UI_SCALE_KEY, selected_scale)
        self.parent_app.settings.sync()
        QMessageBox.information(self, self._tr("display_change_title", "Display Settings Changed"),
                                self._tr("language_change_message", "A restart is required..."))

    def _populate_language_combo_box(self):
        self.language_combo_box.blockSignals(True)
        self.language_combo_box.clear()
        languages = [
            ("en", "English"), ("ja", "日本語 (Japanese)"), ("fr", "Français (French)"),
            ("de", "Deutsch (German)"), ("es", "Español (Spanish)"), ("pt", "Português (Portuguese)"),
            ("ru", "Русский (Russian)"), ("zh_CN", "简体中文 (Simplified Chinese)"),
            ("zh_TW", "繁體中文 (Traditional Chinese)"), ("ko", "한국어 (Korean)")
            ]
        current_lang = self.parent_app.current_selected_language
        for lang_code, lang_name in languages:
            self.language_combo_box.addItem(lang_name, lang_code)
            if current_lang == lang_code:
                self.language_combo_box.setCurrentIndex(self.language_combo_box.count() - 1)
        self.language_combo_box.blockSignals(False)

    def _language_selection_changed(self, index):
        selected_lang_code = self.language_combo_box.itemData(index)
        if selected_lang_code and selected_lang_code != self.parent_app.current_selected_language:
            self.parent_app.settings.setValue(LANGUAGE_KEY, selected_lang_code)
            self.parent_app.settings.sync()
            self.parent_app.current_selected_language = selected_lang_code
            self._retranslate_ui()
            if hasattr(self.parent_app, '_retranslate_main_ui'):
                self.parent_app._retranslate_main_ui()
            QMessageBox.information(self, self._tr("language_change_title", "Language Changed"),
                                    self._tr("language_change_message", "A restart is required..."))

    def _save_cookie_and_path(self):
        path_saved = False
        cookie_saved = False
        if hasattr(self.parent_app, 'dir_input') and self.parent_app.dir_input:
            current_path = self.parent_app.dir_input.text().strip()
            if current_path and os.path.isdir(current_path):
                self.parent_app.settings.setValue(DOWNLOAD_LOCATION_KEY, current_path)
                path_saved = True
        if hasattr(self.parent_app, 'use_cookie_checkbox'):
            use_cookie = self.parent_app.use_cookie_checkbox.isChecked()
            cookie_content = self.parent_app.cookie_text_input.text().strip()
            if use_cookie and cookie_content:
                self.parent_app.settings.setValue(USE_COOKIE_KEY, True)
                self.parent_app.settings.setValue(COOKIE_TEXT_KEY, cookie_content)
                cookie_saved = True
            else:
                self.parent_app.settings.setValue(USE_COOKIE_KEY, False)
                self.parent_app.settings.setValue(COOKIE_TEXT_KEY, "")
        self.parent_app.settings.sync()
        if path_saved or cookie_saved:
            QMessageBox.information(self, "Settings Saved", "Settings have been saved.")
        else:
            QMessageBox.warning(self, "Nothing to Save", "No valid settings to save.")