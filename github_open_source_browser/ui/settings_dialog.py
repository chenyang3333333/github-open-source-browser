# -*- coding: utf-8 -*-
"""设置对话框：翻译、网络、其他设置。"""
from __future__ import annotations
from github_open_source_browser.i18n import tr

import time
from typing import Any

from PyQt6.QtCore import QThreadPool, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QDialog,
    QScrollArea,
    QWidget,
)

from github_open_source_browser.config import (
    DEFAULT_CONFIG,
    TARGET_LANGUAGE_DISPLAY_OPTIONS,
    _TRANSLATION_PROVIDER_OPTIONS,
    normalize_config,
    normalize_target_language,
    normalize_translation_provider,
)

class SettingsDialog(QDialog):
    """设置对话框。"""

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.config = dict(service.config)
        self.setWindowTitle(tr("settings.title"))
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setMinimumSize(800, 700)
        self.resize(850, 750)
        self._init_ui()
        self._load_config()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标签页
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # 账号与搜索页
        account_tab = QWidget()
        account_layout = QFormLayout(account_tab)
        account_layout.setSpacing(8)

        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText(tr("placeholder.token"))
        account_layout.addRow(tr("settings.github_token"), self.token_edit)

        token_row = QHBoxLayout()
        self.token_show_btn = QPushButton(tr("btn.show"))
        self.token_show_btn.clicked.connect(lambda: self.token_edit.setEchoMode(QLineEdit.EchoMode.Normal))
        token_row.addWidget(self.token_show_btn)
        self.token_hide_btn = QPushButton(tr("btn.hide"))
        self.token_hide_btn.clicked.connect(lambda: self.token_edit.setEchoMode(QLineEdit.EchoMode.Password))
        token_row.addWidget(self.token_hide_btn)
        self.token_clear_btn = QPushButton(tr("btn.clear_key"))
        self.token_clear_btn.clicked.connect(lambda: self.token_edit.clear())
        token_row.addWidget(self.token_clear_btn)
        token_row.addStretch()
        account_layout.addRow("", token_row)

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("stars:>500")
        account_layout.addRow(tr("settings.default_query"), self.query_edit)

        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(1, 120)
        self.interval_spin.setMinimumWidth(120)
        self.interval_spin.setDecimals(0)
        self.interval_spin.setSuffix(tr("settings.minutes"))
        account_layout.addRow(tr("settings.auto_refresh"), self.interval_spin)

        tabs.addTab(account_tab, tr("settings.tab_account"))

        # 翻译设置页 (with scroll)
        translation_scroll = QScrollArea()
        translation_scroll.setWidgetResizable(True)
        translation_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        translation_tab = QWidget()
        translation_layout = QFormLayout(translation_tab)
        translation_layout.setSpacing(8)
        translation_layout.setContentsMargins(8, 8, 8, 8)
        translation_scroll.setWidget(translation_tab)

        # 翻译供应商
        self.translation_provider_combo = QComboBox()
        for label, value in _TRANSLATION_PROVIDER_OPTIONS:
            self.translation_provider_combo.addItem(label, value)
        translation_layout.addRow(tr("settings.trans_service"), self.translation_provider_combo)

        # 翻译语言
        self.target_lang_combo = QComboBox()
        for label, value in TARGET_LANGUAGE_DISPLAY_OPTIONS:
            self.target_lang_combo.addItem(label, value)
        translation_layout.addRow(tr("settings.trans_lang"), self.target_lang_combo)

        # API 设置
        self.translation_api_url_edit = QLineEdit()
        self.translation_api_url_edit.setPlaceholderText(tr("placeholder.api_url"))
        translation_layout.addRow(tr("settings.api_url"), self.translation_api_url_edit)

        self.translation_api_key_edit = QLineEdit()
        self.translation_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.translation_api_key_edit.setPlaceholderText(tr("settings.api_key"))
        translation_layout.addRow(tr("settings.api_key"), self.translation_api_key_edit)

        self.translation_model_edit = QComboBox()
        self.translation_model_edit.setEditable(False)
        self.translation_model_edit.setPlaceholderText(tr("placeholder.model"))
        self.translation_model_edit.setMinimumWidth(200)
        self._model_label = QLabel(tr("settings.model"))
        model_row = QHBoxLayout()
        model_row.addWidget(self.translation_model_edit, 1)
        self.fetch_models_btn = QPushButton(tr("settings.fetch_models"))
        self.fetch_models_btn.setFixedWidth(80)
        self.fetch_models_btn.clicked.connect(self._fetch_models)
        model_row.addWidget(self.fetch_models_btn)
        translation_layout.addRow(self._model_label, model_row)

        # 腾讯云

        # 超时和重试
        self.translation_timeout_spin = QDoubleSpinBox()
        self.translation_timeout_spin.setRange(1.0, 60.0)
        self.translation_timeout_spin.setMinimumWidth(120)
        self.translation_timeout_spin.setDecimals(1)
        self.translation_timeout_spin.setSuffix(tr("settings.seconds"))
        translation_layout.addRow(tr("settings.trans_timeout"), self.translation_timeout_spin)

        self.translation_retry_spin = QSpinBox()
        self.translation_retry_spin.setRange(0, 3)
        self.translation_retry_spin.setMinimumWidth(120)
        translation_layout.addRow(tr("settings.retry_count"), self.translation_retry_spin)

        # 缓存
        self.translation_cache_checkbox = QCheckBox(tr("settings.cache_enabled"))
        translation_layout.addRow(tr("settings.cache"), self.translation_cache_checkbox)

        # 缓存统计
        self.translation_cache_stats = QLabel("0 条，0 B")
        translation_layout.addRow(tr("settings.cache_stats"), self.translation_cache_stats)

        cache_row = QHBoxLayout()
        self.clear_cache_btn = QPushButton(tr("settings.clear_cache"))
        self.clear_cache_btn
        self.clear_cache_btn.clicked.connect(self._clear_translation_cache)
        cache_row.addWidget(self.clear_cache_btn)
        cache_row.addStretch()
        translation_layout.addRow("", cache_row)

        # Translation scope
        scope_label = QLabel(tr("settings.translate_scope"))
        scope_label.setObjectName("sectionTitle")
        translation_layout.addRow(scope_label)

        self.auto_translate_desc_cb = QCheckBox(tr("settings.auto_translate_desc"))
        self.auto_translate_desc_cb.setToolTip(tr("settings.translate_desc_hint"))
        translation_layout.addRow("", self.auto_translate_desc_cb)

        self.auto_translate_readme_cb = QCheckBox(tr("settings.auto_translate_readme"))
        self.auto_translate_readme_cb.setToolTip(tr("settings.translate_readme_hint"))
        translation_layout.addRow("", self.auto_translate_readme_cb)

        # Request interval
        self.request_interval_spin = QSpinBox()
        self.request_interval_spin.setRange(0, 5000)
        self.request_interval_spin.setSingleStep(50)
        self.request_interval_spin.setMinimumWidth(120)
        self.request_interval_spin.setSuffix(" ms")
        translation_layout.addRow(tr("settings.request_interval"), self.request_interval_spin)

        # Concurrent limit
        self.concurrent_limit_spin = QSpinBox()
        self.concurrent_limit_spin.setRange(1, 10)
        self.concurrent_limit_spin.setMinimumWidth(120)
        translation_layout.addRow(tr("settings.concurrent_limit"), self.concurrent_limit_spin)

        # 密钥操作
        key_row = QHBoxLayout()
        self.key_show_btn = QPushButton(tr("btn.show"))
        self.key_show_btn.clicked.connect(lambda: self.translation_api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal))
        key_row.addWidget(self.key_show_btn)
        self.key_hide_btn = QPushButton(tr("btn.hide"))
        self.key_hide_btn.clicked.connect(lambda: self.translation_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password))
        key_row.addWidget(self.key_hide_btn)
        self.key_clear_btn = QPushButton(tr("btn.clear_key"))
        self.key_clear_btn.clicked.connect(lambda: self.translation_api_key_edit.clear())
        key_row.addWidget(self.key_clear_btn)
        key_row.addStretch()
        translation_layout.addRow(tr("settings.key_management"), key_row)

        # 测试按钮
        self.translation_test_button = QPushButton(tr("btn.test_translation"))
        self.translation_test_button.clicked.connect(self._test_translation)
        translation_layout.addRow(tr("settings.service_test"), self.translation_test_button)

        self.translation_test_status = QLabel(tr("settings.not_tested"))
        translation_layout.addRow(tr("settings.status"), self.translation_test_status)

        tabs.addTab(translation_scroll, tr("settings.translation"))

        # 镜像加速页
        mirror_tab = QWidget()
        mirror_layout = QFormLayout(mirror_tab)
        mirror_layout.setSpacing(8)

        self.mirrors_edit = QPlainTextEdit()
        self.mirrors_edit.setPlaceholderText(tr("settings.mirrors_hint"))
        self.mirrors_edit.setMaximumHeight(100)
        mirror_layout.addRow(tr("settings.mirror_pool"), self.mirrors_edit)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(tr("settings.mirror_auto"), "auto")
        self.mode_combo.addItem(tr("settings.mirror_none"), "none")
        mirror_layout.addRow(tr("settings.mirror_strategy"), self.mode_combo)

        self.retest_spin = QDoubleSpinBox()
        self.retest_spin.setRange(1, 120)
        self.retest_spin.setMinimumWidth(120)
        self.retest_spin.setDecimals(0)
        self.retest_spin.setSuffix(tr("settings.minutes"))
        mirror_layout.addRow(tr("settings.retest_interval"), self.retest_spin)

        self.mirror_checkbox = QCheckBox(tr("settings.use_mirror_download"))
        mirror_layout.addRow(tr("settings.download"), self.mirror_checkbox)

        self.test_btn = QPushButton(tr("settings.test_mirror"))
        self.test_btn.clicked.connect(self._test_mirror_speed)
        mirror_layout.addRow("", self.test_btn)

        self.mirror_status = QLabel(tr("settings.not_tested"))
        mirror_layout.addRow(tr("settings.status"), self.mirror_status)

        tabs.addTab(mirror_tab, tr("settings.tab_mirror"))

        # 网络设置页
        network_tab = QWidget()
        network_layout = QFormLayout(network_tab)
        network_layout.setSpacing(8)

        # 代理模式
        self.proxy_mode_combo = QComboBox()
        self.proxy_mode_combo.addItem(tr("settings.proxy_none"), "none")
        self.proxy_mode_combo.addItem(tr("settings.proxy_system"), "system")
        self.proxy_mode_combo.addItem(tr("settings.proxy_custom"), "custom")
        network_layout.addRow(tr("settings.proxy_mode"), self.proxy_mode_combo)

        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText(tr("placeholder.proxy"))
        network_layout.addRow(tr("settings.proxy_addr"), self.proxy_edit)

        self.proxy_mode_help = QLabel("")
        self.proxy_mode_help.setWordWrap(True)
        network_layout.addRow(tr("settings.proxy_help"), self.proxy_mode_help)

        # SSL
        self.ssl_checkbox = QCheckBox(tr("settings.ssl_verify"))
        network_layout.addRow("SSL", self.ssl_checkbox)

        # GitHub Token
        self.github_token_edit = QLineEdit()
        self.github_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_token_edit.setPlaceholderText(tr("settings.token_hint"))
        network_layout.addRow(tr("settings.github_token"), self.github_token_edit)
        self.oauth_btn = QPushButton(tr("btn.oauth_login"))
        self.oauth_btn.clicked.connect(self._start_oauth)
        network_layout.addRow("", self.oauth_btn)

        tabs.addTab(network_tab, tr("settings.network"))

        # 其他设置页 (with scroll)
        other_scroll = QScrollArea()
        other_scroll.setWidgetResizable(True)
        other_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        other_tab = QWidget()
        other_layout = QFormLayout(other_tab)
        other_layout.setSpacing(8)
        other_layout.setContentsMargins(8, 8, 8, 8)
        other_scroll.setWidget(other_tab)

        self.startup_auto_load_checkbox = QCheckBox(tr("settings.startup_load"))
        other_layout.addRow(tr("settings.startup_behavior"), self.startup_auto_load_checkbox)

        self.readme_image_checkbox = QCheckBox(tr("settings.load_images"))
        other_layout.addRow(tr("settings.readme_image"), self.readme_image_checkbox)

        self.readme_image_timeout_spin = QDoubleSpinBox()
        self.readme_image_timeout_spin.setRange(0.75, 10.0)
        self.readme_image_timeout_spin.setDecimals(2)
        self.readme_image_timeout_spin.setSingleStep(0.25)
        self.readme_image_timeout_spin.setSuffix(tr("settings.seconds"))
        other_layout.addRow(tr("settings.image_timeout"), self.readme_image_timeout_spin)

        self.autostart_checkbox = QCheckBox(tr("settings.autostart"))
        other_layout.addRow(tr("settings.autostart"), self.autostart_checkbox)

        self.minimize_to_tray_checkbox = QCheckBox(tr("settings.minimize_tray"))
        other_layout.addRow(tr("settings.tray"), self.minimize_to_tray_checkbox)

        self.release_notify_checkbox = QCheckBox(tr("settings.release_notify"))
        other_layout.addRow(tr("settings.notify"), self.release_notify_checkbox)

        tabs.addTab(other_scroll, tr("settings.other"))

        # 插件管理页
        plugin_tab = QWidget()
        plugin_layout = QVBoxLayout(plugin_tab)
        plugin_layout.setSpacing(8)
        plugin_hint = QLabel(tr("settings.plugin_hint"))
        plugin_hint.setWordWrap(True)
        plugin_layout.addWidget(plugin_hint)
        open_plugin_btn = QPushButton(tr("settings.open_plugin_dir"))
        open_plugin_btn.clicked.connect(self._open_plugin_dir)
        plugin_layout.addWidget(open_plugin_btn)
        plugin_layout.addStretch()
        tabs.addTab(plugin_tab, tr("settings.tab_plugins"))

        # 诊断信息
        diag_tab = QWidget()
        diag_layout = QVBoxLayout(diag_tab)
        diag_layout.setSpacing(8)
        self._diag_text = QPlainTextEdit()
        self._diag_text.setReadOnly(True)
        self._diag_text.setMaximumHeight(200)
        diag_layout.addWidget(self._diag_text)
        copy_diag_btn = QPushButton("\u590d\u5236\u8bca\u65ad\u4fe1\u606f")
        copy_diag_btn.clicked.connect(lambda: QApplication.clipboard().setText(self._diag_text.toPlainText()))
        diag_layout.addWidget(copy_diag_btn)
        diag_layout.addStretch()
        tabs.addTab(diag_tab, "\u8bca\u65ad")

        # 底部按钮
        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        restore_btn = QPushButton(tr("btn.restore_default"))
        restore_btn.clicked.connect(self._restore_defaults)
        button_row.addWidget(restore_btn)

        import_btn = QPushButton(tr("dialog.import_title"))
        import_btn.clicked.connect(self._import_settings)
        button_row.addWidget(import_btn)

        export_btn = QPushButton(tr("dialog.export_title"))
        export_btn.clicked.connect(self._export_settings)
        button_row.addWidget(export_btn)

        button_row.addStretch()

        save_btn = QPushButton(tr("btn.save"))
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        button_row.addWidget(save_btn)

        cancel_btn = QPushButton(tr("btn.cancel"))
        cancel_btn.clicked.connect(self.close)
        button_row.addWidget(cancel_btn)

        layout.addLayout(button_row)

        # 状态
        self.status_label = QLabel("")
        self.status_label.setObjectName("descLabel")
        layout.addWidget(self.status_label)

        # 信号
        self.proxy_mode_combo.currentIndexChanged.connect(self._refresh_proxy_visibility)
        self.translation_provider_combo.currentIndexChanged.connect(self._refresh_translation_visibility)

    def _load_config(self):
        config = self.config
        # 翻译
        provider = normalize_translation_provider(config.get("translation_provider", "auto"))
        idx = self.translation_provider_combo.findData(provider)
        if idx >= 0:
            self.translation_provider_combo.setCurrentIndex(idx)
        lang = normalize_target_language(config.get("target_language", "zh-CN"))
        idx = self.target_lang_combo.findData(lang)
        if idx >= 0:
            self.target_lang_combo.setCurrentIndex(idx)
        self.translation_api_url_edit.setText(str(config.get("translation_api_url", "")))
        self.translation_api_key_edit.setText(str(config.get("translation_api_key", "")))
        model_val = str(config.get("translation_model", ""))
        if model_val:
            idx = self.translation_model_edit.findText(model_val)
            if idx >= 0:
                self.translation_model_edit.setCurrentIndex(idx)
            else:
                self.translation_model_edit.addItem(model_val)
                self.translation_model_edit.setCurrentIndex(self.translation_model_edit.count() - 1)
        else:
            self.translation_model_edit.setCurrentIndex(-1)

        self.translation_timeout_spin.setValue(config.get("translation_timeout_seconds", 12.0))
        self.translation_retry_spin.setValue(config.get("translation_retry_count", 1))
        self.translation_cache_checkbox.setChecked(config.get("translation_cache_enabled", True))
        # 网络
        proxy_mode = config.get("proxy_mode", "none")
        idx = self.proxy_mode_combo.findData(proxy_mode)
        if idx >= 0:
            self.proxy_mode_combo.setCurrentIndex(idx)
        self.proxy_edit.setText(str(config.get("proxy", "")))
        self.ssl_checkbox.setChecked(config.get("ssl_verify", True))
        self.github_token_edit.setText(str(config.get("github_token", "")))
        # 其他
        self.startup_auto_load_checkbox.setChecked(config.get("startup_auto_load", True))
        self.readme_image_checkbox.setChecked(config.get("readme_image_enabled", True))
        self.readme_image_timeout_spin.setValue(config.get("readme_image_timeout", 2.5))
        self.autostart_checkbox.setChecked(config.get("autostart", False))
        self.minimize_to_tray_checkbox.setChecked(config.get("minimize_to_tray", True))
        self.release_notify_checkbox.setChecked(config.get("release_notify", True))
        # 账号与搜索
        if hasattr(self, 'token_edit'):
            self.token_edit.setText(str(config.get("github_token", "")))
        if hasattr(self, 'query_edit'):
            self.query_edit.setText(str(config.get("query", "stars:>500")))
        if hasattr(self, 'interval_spin'):
            self.interval_spin.setValue(config.get("interval_minutes", 30))
        # 镜像
        if hasattr(self, 'mirrors_edit'):
            mirrors = config.get("mirrors", [])
            self.mirrors_edit.setPlainText("\n".join(mirrors) if isinstance(mirrors, list) else str(mirrors))
        if hasattr(self, 'mode_combo'):
            idx = self.mode_combo.findData(config.get("mirror_mode", "auto"))
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
        if hasattr(self, 'retest_spin'):
            self.retest_spin.setValue(config.get("mirror_retest_minutes", 30))
        if hasattr(self, 'mirror_checkbox'):
            self.mirror_checkbox.setChecked(config.get("use_mirror_download", True))
        # Translation scope
        if hasattr(self, 'auto_translate_desc_cb'):
            self.auto_translate_desc_cb.setChecked(config.get("auto_translate_desc", True))
        if hasattr(self, 'auto_translate_readme_cb'):
            self.auto_translate_readme_cb.setChecked(config.get("auto_translate_readme", False))
        if hasattr(self, 'request_interval_spin'):
            self.request_interval_spin.setValue(config.get("request_interval_ms", 200))
        if hasattr(self, 'concurrent_limit_spin'):
            self.concurrent_limit_spin.setValue(config.get("concurrent_limit", 3))
        self._refresh_proxy_visibility()
        self._refresh_translation_visibility()
        self._load_diagnostics()
        # Deselect all spinbox text after loading
        self._deselect_spinboxes()

    def _deselect_spinboxes(self):
        """Deselect text in all spinboxes to avoid unwanted selection."""
        from PyQt6.QtWidgets import QSpinBox, QDoubleSpinBox, QPushButton
        for spin in self.findChildren((QSpinBox, QDoubleSpinBox)):
            le = spin.lineEdit()
            if le:
                le.deselect()
        # Prevent buttons from stealing focus from spinboxes
        for btn in self.findChildren(QPushButton):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _load_diagnostics(self):
        import platform
        import sys
        lines = []
        lines.append("Python: " + sys.version.split()[0])
        try:
            from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
            lines.append("Qt: " + QT_VERSION_STR)
            lines.append("PyQt6: " + PYQT_VERSION_STR)
        except Exception:
            pass
        lines.append("Platform: " + platform.platform())
        service = getattr(self, 'service', None)
        if service:
            lines.append("Config: " + str(getattr(service, 'config_path', 'N/A')))
            lines.append("Translation: " + str(self.config.get('translation_provider', 'auto')))
            lines.append("Language: " + str(self.config.get('target_language', 'zh-CN')))
            lines.append("Proxy: " + str(self.config.get('proxy_mode', 'none')))
            lines.append("Cache: " + str(self.config.get('translation_cache_enabled', True)))
        self._diag_text.setPlainText("\n".join(lines))

    def _test_mirror_speed(self):
        self.mirror_status.setText(tr("settings.testing_mirror"))
        service = getattr(self, 'service', None)
        if not service:
            self.mirror_status.setText(tr("settings.no_service"))
            return
        mirrors_text = self.mirrors_edit.toPlainText().strip()
        mirrors = [m.strip() for m in mirrors_text.split('\n') if m.strip()]
        if not mirrors:
            self.mirror_status.setText(tr("settings.no_mirrors"))
            return
        from PyQt6.QtCore import QThreadPool
        def task():
            results = []
            for mirror in mirrors:
                latency = service.http.test_mirror_latency(mirror)
                if latency is not None:
                    results.append((mirror, latency))
            return results
        def on_done(results):
            if results:
                results.sort(key=lambda x: x[1])
                best = results[0]
                self.mirror_status.setText(f"{best[0]} ({best[1]*1000:.0f}ms)")
            else:
                self.mirror_status.setText(tr("settings.all_mirrors_failed"))
        from github_open_source_browser.ui.main_window import Worker
        worker = Worker(task)
        worker.signals.result.connect(on_done)
        QThreadPool.globalInstance().start(worker)

    def _clear_translation_cache(self):
        service = getattr(self, 'service', None)
        if service and hasattr(service, 'db'):
            try:
                service.db.clear_cache()
                self.translation_cache_stats.setText("0 条，0 B")
                self.status_label.setText(tr("settings.cache_cleared"))
            except Exception:
                self.status_label.setText(tr("settings.cache_clear_failed"))

    def _open_plugin_dir(self):
        import os, subprocess
        plugin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'user_plugins')
        os.makedirs(plugin_dir, exist_ok=True)
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', plugin_dir])
        else:
            subprocess.Popen(['xdg-open', plugin_dir])

    def _save(self):
        config = self.config
        config["translation_provider"] = normalize_translation_provider(self.translation_provider_combo.currentData())
        config["target_language"] = normalize_target_language(self.target_lang_combo.currentData())
        config["translation_api_url"] = self.translation_api_url_edit.text().strip()
        config["translation_api_key"] = self.translation_api_key_edit.text().strip()
        config["translation_model"] = self.translation_model_edit.currentText().strip()

        config["translation_timeout_seconds"] = self.translation_timeout_spin.value()
        config["translation_retry_count"] = self.translation_retry_spin.value()
        config["translation_cache_enabled"] = self.translation_cache_checkbox.isChecked()
        config["proxy_mode"] = self.proxy_mode_combo.currentData() or "none"
        config["proxy"] = self.proxy_edit.text().strip()
        config["ssl_verify"] = self.ssl_checkbox.isChecked()
        config["github_token"] = self.github_token_edit.text().strip()
        config["startup_auto_load"] = self.startup_auto_load_checkbox.isChecked()
        config["readme_image_enabled"] = self.readme_image_checkbox.isChecked()
        config["readme_image_timeout"] = self.readme_image_timeout_spin.value()
        config["autostart"] = self.autostart_checkbox.isChecked()
        config["minimize_to_tray"] = self.minimize_to_tray_checkbox.isChecked()
        config["release_notify"] = self.release_notify_checkbox.isChecked()
        # 账号与搜索
        if hasattr(self, 'token_edit'):
            config["github_token"] = self.token_edit.text().strip()
        if hasattr(self, 'query_edit'):
            config["query"] = self.query_edit.text().strip() or "stars:>500"
        if hasattr(self, 'interval_spin'):
            config["interval_minutes"] = int(self.interval_spin.value())
        # 镜像
        if hasattr(self, 'mirrors_edit'):
            mirrors_text = self.mirrors_edit.toPlainText().strip()
            config["mirrors"] = [m.strip() for m in mirrors_text.split('\n') if m.strip()]
        if hasattr(self, 'mode_combo'):
            config["mirror_mode"] = self.mode_combo.currentData() or "auto"
        if hasattr(self, 'retest_spin'):
            config["mirror_retest_minutes"] = int(self.retest_spin.value())
        if hasattr(self, 'mirror_checkbox'):
            config["use_mirror_download"] = self.mirror_checkbox.isChecked()
        # Translation scope
        if hasattr(self, 'auto_translate_desc_cb'):
            config["auto_translate_desc"] = self.auto_translate_desc_cb.isChecked()
        if hasattr(self, 'auto_translate_readme_cb'):
            config["auto_translate_readme"] = self.auto_translate_readme_cb.isChecked()
        if hasattr(self, 'request_interval_spin'):
            config["request_interval_ms"] = self.request_interval_spin.value()
        if hasattr(self, 'concurrent_limit_spin'):
            config["concurrent_limit"] = self.concurrent_limit_spin.value()
        config = normalize_config(config)
        self.service.config = config
        self.service.save_config()
        self.service.http.update_config(config)
        # 开机自启动
        try:
            _set_autostart(config.get("autostart", False))
        except Exception:
            pass
        self.status_label.setText(tr("status.settings_saved"))
        self.close()

    def _start_oauth(self):
        service = getattr(self, 'service', None)
        if not service:
            return
        url = service.get_oauth_url()
        if not url:
            self.status_label.setText(tr("oauth.need_client_id"))
            return
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(url))
        self.status_label.setText(tr("oauth.browser_auth"))

    def _set_autostart(enabled):
        import sys
        if sys.platform != "win32":
            return
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            app_name = "GitHubOpenSourceBrowser"
            if enabled:
                import os
                exe = sys.executable
                if getattr(sys, 'frozen', False):
                    exe = sys.executable
                else:
                    exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'run_app.py')
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe}"')
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass

    # Known default models for providers that don't have a /models endpoint
    _KNOWN_MODELS = {
        "claude": [
            "claude-sonnet-4-20250514",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-5-sonnet-20241022",
        ],
        "gemini": [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-2.0-flash-exp",
            "gemini-pro",
        ],
        "mimo": [
            "mimo-v2.5",
            "mimo-v2.5-pro",
            "mimo-v2.5-asr",
            "mimo-v2.5-tts",
            "mimo-v2.5-tts-voiceclone",
            "mimo-v2.5-tts-voicedesign",
        ],
        "openai_compatible": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "deepseek-chat",
            "deepseek-reasoner",
            "qwen-plus",
            "qwen-turbo",
            "glm-4",
        ],
    }

    _PROVIDER_DEFAULT_URLS = {
        "openai_compatible": "https://api.openai.com/v1",
        "claude": "https://api.anthropic.com",
        "gemini": "https://generativelanguage.googleapis.com",
        "mimo": "https://api.xiaomimimo.com/v1",
    }

    def _fetch_models(self):
        """Fetch available models from API or use built-in list."""
        provider = self.translation_provider_combo.currentData() or "auto"
        api_url = self.translation_api_url_edit.text().strip()
        api_key = self.translation_api_key_edit.text().strip()

        # Use default URL if empty
        if not api_url:
            api_url = self._PROVIDER_DEFAULT_URLS.get(provider, "")

        # For providers without API or without key, show known models directly
        if not api_url or not api_key:
            known = self._KNOWN_MODELS.get(provider, [])
            if known:
                self._apply_model_list(known)
                self.status_label.setText(tr("settings.models_found", count=len(known)) + " (builtin)")
            else:
                self.status_label.setText(tr("settings.need_api_url"))
            return

        self.fetch_models_btn.setEnabled(False)
        self.status_label.setText(tr("settings.fetching_models"))

        def task():
            import requests as req
            models = []
            if provider == "claude":
                models = list(self._KNOWN_MODELS.get("claude", []))
            elif provider == "gemini":
                resp = req.get(
                    f"{api_url.rstrip('/')}/v1beta/models",
                    params={"key": api_key},
                    timeout=10,
                )
                resp.raise_for_status()
                for m in resp.json().get("models", []):
                    name = m.get("name", "").split("/")[-1]
                    if name:
                        models.append(name)
            else:
                # OpenAI-compatible (covers openai, deepseek, qwen, mimo, etc.)
                resp = req.get(
                    f"{api_url.rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
                resp.raise_for_status()
                for m in resp.json().get("data", []):
                    mid = m.get("id", "")
                    if mid:
                        models.append(mid)
            return models

        def on_done(models):
            self.fetch_models_btn.setEnabled(True)
            if models:
                self._apply_model_list(models)
                self.status_label.setText(tr("settings.models_found", count=len(models)))
            else:
                # Fallback to known models
                known = self._KNOWN_MODELS.get(provider, [])
                if known:
                    self._apply_model_list(known)
                    self.status_label.setText(tr("settings.models_found", count=len(known)) + " (builtin)")
                else:
                    self.status_label.setText(tr("settings.no_models"))

        def on_error(msg):
            self.fetch_models_btn.setEnabled(True)
            # Fallback to known models on error
            known = self._KNOWN_MODELS.get(provider, [])
            if known:
                self._apply_model_list(known)
                self.status_label.setText(tr("settings.models_found", count=len(known)) + " (builtin)")
            else:
                self.status_label.setText(tr("settings.fetch_models_failed", msg=str(msg)))

        from github_open_source_browser.ui.main_window import Worker
        worker = Worker(task)
        worker.signals.result.connect(on_done)
        worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)

    def _apply_model_list(self, models):
        """Apply model list to combo box."""
        current = self.translation_model_edit.currentText().strip()
        self.translation_model_edit.clear()
        for m in models[:50]:
            self.translation_model_edit.addItem(m)
        if current:
            idx = self.translation_model_edit.findText(current)
            if idx >= 0:
                self.translation_model_edit.setCurrentIndex(idx)
            else:
                self.translation_model_edit.addItem(current)
                self.translation_model_edit.setCurrentIndex(self.translation_model_edit.count() - 1)
        elif models:
            self.translation_model_edit.setCurrentIndex(0)
        self.status_label.setText(tr("settings.models_found", count=len(models)))

    def _restore_defaults(self):
        protected_keys = {"github_token", "oauth_client_id", "translation_api_key", "favorites", "download_history"}
        current = dict(self.config)
        import copy
        defaults = copy.deepcopy(DEFAULT_CONFIG)
        for key in protected_keys:
            if key in current:
                defaults[key] = current[key]
        self.config = defaults
        self._load_config()
        self.status_label.setText(tr("status.settings_restored"))

    def _import_settings(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("dialog.import_title"), "", tr("dialog.json_files"))
        if not path:
            return
        try:
            import json
            from pathlib import Path
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            imported = data.get("settings", data)
            if not isinstance(imported, dict):
                raise ValueError(tr("settings.file_format_error"))
            protected = {"github_token", "oauth_client_id", "translation_api_key", "favorites", "download_history"}
            for key, value in imported.items():
                if key not in protected:
                    self.config[key] = value
            self.config = normalize_config(self.config)
            self._load_config()
            self.status_label.setText(tr("status.settings_imported"))
        except Exception as e:
            self.status_label.setText(tr("status.import_failed", msg=str(e)))

    def _export_settings(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("dialog.export_title"), "settings.json", tr("dialog.json_files"))
        if not path:
            return
        try:
            import json
            import copy
            from pathlib import Path
            secret_keys = {"github_token", "oauth_client_id", "translation_api_key", "favorites", "download_history"}
            payload = {k: copy.deepcopy(v) for k, v in self.config.items() if k not in secret_keys}
            Path(path).write_text(
                json.dumps({"format": "github-open-source-browser-settings", "version": 1, "settings": payload}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.status_label.setText(tr("status.exported", path=str(path)))
        except Exception as e:
            self.status_label.setText(tr("status.export_failed", msg=str(e)))

    def _test_translation(self):
        self.translation_test_button.setEnabled(False)
        self.status_label.setText(tr("status.testing_translation"))
        test_config = dict(self.config)
        test_config["translation_provider"] = normalize_translation_provider(self.translation_provider_combo.currentData())
        test_config["target_language"] = normalize_target_language(self.target_lang_combo.currentData())

        def task():
            from github_open_source_browser.services.translation_service import translate_text
            target = test_config.get("target_language", "zh-CN")
            result, used_external = translate_text("Hello GitHub", "en", target, test_config)
            provider = test_config.get("translation_provider", "auto")
            if result and result != "Hello GitHub":
                return {"success": True, "result": result, "provider": provider, "external": used_external}
            return {"success": False, "result": result, "provider": provider, "external": used_external}

        def on_done(result):
            self.translation_test_button.setEnabled(True)
            if isinstance(result, dict) and result.get("success"):
                provider_name = result.get("provider", "unknown")
                ext = " (external)" if result.get("external") else " (local)"
                self.status_label.setText(tr("test.success", result=f"{result['result']}{ext}"))
            else:
                self.status_label.setText(tr("test.fail"))

        def on_error(msg):
            self.translation_test_button.setEnabled(True)
            self.status_label.setText(tr("test.fail_msg", msg=str(msg)))

        from github_open_source_browser.ui.main_window import Worker
        worker = Worker(task)
        worker.signals.result.connect(on_done)
        worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)

    def _refresh_proxy_visibility(self):
        mode = self.proxy_mode_combo.currentData() or "none"
        self.proxy_edit.setEnabled(mode == "custom")
        help_text = {
            "system": tr("proxy.help_system"),
            "none": tr("proxy.help_none"),
            "custom": tr("proxy.help_custom"),
        }
        self.proxy_mode_help.setText(help_text.get(mode, ""))

    def _refresh_translation_visibility(self):
        provider = self.translation_provider_combo.currentData() or "auto"
        show_api = provider not in ("auto", "local")
        self.translation_api_url_edit.setVisible(show_api)
        self.translation_api_key_edit.setVisible(show_api)
        show_model = provider in ("openai_compatible", "claude", "gemini", "mimo")
        # Show/hide model row by hiding the combo and button individually
        # Show/hide model row
        model_label = getattr(self, '_model_label', None)
        if model_label:
            model_label.setVisible(show_model)
        self.translation_model_edit.setVisible(show_model)
        if hasattr(self, 'fetch_models_btn'):
            self.fetch_models_btn.setVisible(show_model)
        if hasattr(self, "fetch_models_btn"):
            self.fetch_models_btn.setVisible(show_model)
        # Update API key placeholder based on provider
        if provider == "tencent":
            self.translation_api_key_edit.setPlaceholderText("SecretId:SecretKey")
            self.translation_api_url_edit.setPlaceholderText(tr("settings.tencent_url_hint"))
        else:
            self.translation_api_key_edit.setPlaceholderText(tr("placeholder.api_key"))
            self.translation_api_url_edit.setPlaceholderText(tr("placeholder.api_url"))

