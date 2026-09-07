# -*- coding: utf-8 -*-
"""主窗口：项目列表、热榜、收藏、详情页、翻译。"""
from __future__ import annotations
from github_open_source_browser.i18n import tr, set_language, get_language, on_language_changed, AVAILABLE_LANGUAGES, init as i18n_init

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from PyQt6.QtCore import QEvent, QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QGridLayout,
    QStackedWidget,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from github_open_source_browser.config import (
    DEFAULT_CONFIG,
    TARGET_LANGUAGE_DISPLAY_OPTIONS,
    normalize_config,
    normalize_target_language,
)
from github_open_source_browser.services.github_service import (
    REPOSITORY_PAGE_SIZE,
    TRENDING_PAGE_SIZE,
    filter_repos_by_category,
    CATEGORY_LANGUAGES,
)
from github_open_source_browser.ui.theme import apply_theme
from github_open_source_browser.ui.loading import LoadingIndicator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

CATEGORY_DISPLAY_LABELS = {
    '': tr('cat.all'),
    'all': tr('cat.all'),
    'ai': tr('cat.ai'),
    'frontend': tr('cat.frontend'),
    'backend': tr('cat.backend'),
    'mobile': tr('cat.mobile'),
    'devops': tr('cat.devops'),
    'database': tr('cat.database'),
    'security': tr('cat.security'),
    'game': tr('cat.game'),
    'tool': tr('cat.tool'),
}

CATEGORY_DISPLAY_DESCRIPTIONS = {
    '': tr('catdesc.all'),
    'all': tr('catdesc.all'),
    'ai': tr('catdesc.ai'),
    'frontend': tr('catdesc.frontend'),
    'backend': tr('catdesc.backend'),
    'mobile': tr('catdesc.mobile'),
    'devops': tr('catdesc.devops'),
    'database': tr('catdesc.database'),
    'security': tr('catdesc.security'),
    'game': tr('catdesc.game'),
    'tool': tr('catdesc.tool'),
}

VIEW_DISPLAY_LABELS = {
    'discover': tr('view.discover'),
    'trending': tr('view.trending'),
    'favorites': tr('view.favorites'),
    'history': tr('view.history'),
}


# ---------------------------------------------------------------------------
# 后台任务 Worker
# ---------------------------------------------------------------------------


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)


class Worker(QRunnable):
    """QRunnable 兼容的后台任务 Worker。"""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)
        # QRunnable needs its own signals object since it is not a QObject

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """GitHub 开源项目浏览器主窗口。"""

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.config = service.config
        self.thread_pool = QThreadPool.globalInstance()
        # 翻译专用线程池：与搜索/详情/图片下载隔离，避免长翻译任务挤占全局池导致卡死
        self.translate_pool = QThreadPool(self)
        self.translate_pool.setMaxThreadCount(max(1, int(self.config.get("concurrent_limit", 3))))
        # 详情翻译专用单线程池：README 长任务（最长60s）不占用列表翻译线程，互不阻塞
        self.detail_translate_pool = QThreadPool(self)
        self.detail_translate_pool.setMaxThreadCount(1)
        # 主线程持有进行中的 Worker 引用：防止 QRunnable 自动删除时
        # 其 signals(QObject) 在 worker 线程被 Python GC 销毁而崩溃
        self._active_workers = []
        self._busy_count = 0
        self._current_repo = None
        self._repos: list[dict] = []
        self._display_repos: list[dict] = []
        self._trending_items: list[dict] = []
        self._display_trending_items: list[dict] = []
        self._favorite_items: list[dict] = []
        self._current_category = ""
        self._dark_mode = self.config.get("dark_mode", False)
        self._translation_language_generation = 0
        self._translation_gen = 0  # 详情翻译代数：切换项目时递增以取消旧翻译
        self._current_readme = ""
        self._batch_cancel = False
        self._loading_more = False
        self._translate_queue = []
        self._active_translations = 0  # 在途列表翻译任务数
        self._batch_translate_total = 0  # 本次批量翻译总数
        self._batch_translate_done = 0  # 已完成数（含失败）
        self._translate_anim_timer = QTimer(self)
        self._translate_anim_timer.setInterval(500)
        self._translate_anim_timer.timeout.connect(self._on_translate_anim_tick)
        self._translate_anim_dots = 0
        self._page_size = 10
        self._discover_rendered = 0
        self._trending_rendered = 0
        self._discover_page = 1  # 发现页已加载的 API 页码
        self._discover_api_loading = False  # 是否正在请求下一页
        self._discover_no_more = False  # API 已无更多数据
        self._discover_fetch_gen = 0  # 分页请求代数：刷新时递增，丢弃过期分页结果

        # 热榜无限滚动：后续周期扩展抓取状态
        self._trending_no_more = False  # 已无更多周期内容
        self._trending_periods: list[str] = []  # 待抓取的后续周期队列
        self._trending_fetch_gen = 0  # 扩展抓取代数：刷新时递增，丢弃过期结果

        self._init_ui()
        self._connect_signals()
        self._apply_theme()
        on_language_changed(self._retranslate_ui)

        # 延迟加载（启动后加载趋势热榜）
        if self.config.get("startup_auto_load", True):
            QTimer.singleShot(0, self.refresh_trending)

        # Release notification check
        if self.config.get("release_notify", True):
            QTimer.singleShot(3000, self._check_new_release)

    # ------------------------------------------------------------------
    # UI 初始化
    # ------------------------------------------------------------------

    def _init_ui(self):
        self.setWindowTitle(tr("app.title"))
        self.setMinimumSize(1200, 700)
        self.resize(1400, 850)

        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- 顶部工具栏 ----
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(8)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchEdit")
        self.search_edit.setPlaceholderText(tr("search.placeholder"))
        toolbar_layout.addWidget(self.search_edit, 1)

        # Loading indicator
        self._loading = LoadingIndicator()
        toolbar_layout.addWidget(self._loading)

        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("languageCombo")
        self.lang_combo.addItem(tr("search.all_lang"), "")
        for lang in ("Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "C++", "C#", "Swift", "Kotlin"):
            self.lang_combo.addItem(lang, lang.lower())
        toolbar_layout.addWidget(self.lang_combo)

        self.ui_lang_combo = QComboBox()
        self.ui_lang_combo.setObjectName("uiLangCombo")
        for label, value in AVAILABLE_LANGUAGES:
            self.ui_lang_combo.addItem(label, value)
        saved_lang = self.config.get("ui_language", "")
        cur_lang = saved_lang if saved_lang else get_language()
        idx = self.ui_lang_combo.findData(cur_lang)
        if idx >= 0:
            self.ui_lang_combo.setCurrentIndex(idx)
        toolbar_layout.addWidget(self.ui_lang_combo)

        toolbar_layout.addStretch()

        self.refresh_btn = QPushButton(tr("btn.refresh"))
        # 不使用 primaryButton 高亮样式（蓝色强调），保持普通按钮外观
        self.refresh_btn.setFixedHeight(32)
        toolbar_layout.addWidget(self.refresh_btn)

        self.settings_btn = QPushButton(tr("btn.settings"))
        self.settings_btn.setFixedHeight(32)
        toolbar_layout.addWidget(self.settings_btn)

        self.theme_btn = QPushButton("\u2600")
        self.theme_btn.setToolTip(tr("theme.to_dark"))
        self.theme_btn.setFixedSize(38, 30)
        toolbar_layout.addWidget(self.theme_btn)

        main_layout.addWidget(toolbar)

        # ---- 主内容区 ----
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("mainSplitter")

        # ---- 左侧面板 ----
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        left_panel.setMinimumWidth(500)
        left_panel.setMaximumWidth(700)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(6)

        self.statusLabel = QLabel(tr("app.ready"))
        self.statusLabel.setObjectName("statusLabel")
        left_layout.addWidget(self.statusLabel)

        self.mirrorLabel = QLabel("")
        self.mirrorLabel.setObjectName("mirrorLabel")
        left_layout.addWidget(self.mirrorLabel)

        self.listSummary = QLabel("")
        self.listSummary.setObjectName("listSummary")
        left_layout.addWidget(self.listSummary)

        # 分类按钮 3列
        self._category_buttons = []
        cat_grid = QGridLayout()
        cat_grid.setSpacing(4)
        row, col = 0, 0
        for key, label in CATEGORY_DISPLAY_LABELS.items():
            if key == "all":
                continue
            btn = QPushButton(label)
            btn.setProperty("cat_value", key)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setToolTip(CATEGORY_DISPLAY_DESCRIPTIONS.get(key, ""))
            btn.clicked.connect(lambda checked, k=key: self._on_category_clicked(k))
            cat_grid.addWidget(btn, row, col)
            self._category_buttons.append(btn)
            col += 1
            if col >= 5:
                col = 0
                row += 1
        for btn in self._category_buttons:
            if btn.property("cat_value") == "":
                btn.setChecked(True)
                break
        left_layout.addLayout(cat_grid)

        # 视图切换
        self.view_combo = QComboBox()
        self.view_combo.setObjectName("viewCombo")
        # 主界面视图：趋势热榜 / 我的收藏 / 历史（已移除“发现项目”，
        # 搜索结果复用 discover 页作为查询结果容器，不占用视图下拉项）
        for value in ("trending", "favorites", "history"):
            self.view_combo.addItem(VIEW_DISPLAY_LABELS[value], value)
        left_layout.addWidget(self.view_combo)

        # QStackedWidget
        self._view_stack = QStackedWidget()
        self._discover_page = QWidget()
        dl = QVBoxLayout(self._discover_page)
        dl.setContentsMargins(0, 0, 0, 0)
        self.repo_list = QListWidget()
        self.repo_list.setObjectName("repoList")
        self.repo_list.setWordWrap(True)
        self.repo_list.setSpacing(2)
        self.repo_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.repo_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        dl.addWidget(self.repo_list)
        self._view_stack.addWidget(self._discover_page)

        self._trending_page = QWidget()
        tl = QVBoxLayout(self._trending_page)
        tl.setContentsMargins(0, 0, 0, 0)
        self.trending_list = QListWidget()
        self.trending_list.setObjectName("trendingList")
        self.trending_list.setWordWrap(True)
        self.trending_list.setSpacing(2)
        self.trending_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.trending_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        tl.addWidget(self.trending_list)
        self._view_stack.addWidget(self._trending_page)

        self._favorites_page = QWidget()
        fl = QVBoxLayout(self._favorites_page)
        fl.setContentsMargins(0, 0, 0, 0)
        self.fav_list = QListWidget()
        self.fav_list.setObjectName("favList")
        self.fav_list.setWordWrap(True)
        self.fav_list.setSpacing(2)
        self.fav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.fav_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        fl.addWidget(self.fav_list)
        self._view_stack.addWidget(self._favorites_page)

        self._history_page = QWidget()
        hl = QVBoxLayout(self._history_page)
        hl.setContentsMargins(0, 0, 0, 0)
        self.history_list = QListWidget()
        self.history_list.setObjectName("historyList")
        self.history_list.setWordWrap(True)
        self.history_list.setSpacing(2)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        hl.addWidget(self.history_list)
        self._view_stack.addWidget(self._history_page)

        self._dashboard_page = QWidget()
        bl = QVBoxLayout(self._dashboard_page)
        bl.setContentsMargins(0, 0, 0, 0)
        self.dashboard_list = QListWidget()
        self.dashboard_list.setObjectName("dashboardList")
        self.dashboard_list.setWordWrap(True)
        self.dashboard_list.setSpacing(2)
        self.dashboard_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dashboard_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        bl.addWidget(self.dashboard_list)
        self._view_stack.addWidget(self._dashboard_page)

        left_layout.addWidget(self._view_stack, 1)
        self._view_stack.setCurrentIndex(1)  # 默认显示趋势热榜页

        self.list_summary_label = QLabel("")
        self.list_summary_label.setObjectName("descLabel")
        left_layout.addWidget(self.list_summary_label)

        splitter.addWidget(left_panel)

        # ---- 右侧详情面板 ----
        detail_panel = QWidget()
        detail_panel.setObjectName("detailPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(8)

        # 标题行 + 翻译按钮
        title_row = QHBoxLayout()
        self.detail_title = QLabel(tr("window.select_project"))
        self.detail_title.setObjectName("detailTitle")
        self.detail_title.setFixedHeight(32)
        title_row.addWidget(self.detail_title, 1)
        self.translate_btn = QPushButton(tr("btn.translate"))
        self.translate_btn.setFixedHeight(32)
        title_row.addWidget(self.translate_btn)
        detail_layout.addLayout(title_row)

        # Hidden attributes for compatibility
        self.detail_stats = QLabel("")
        self.detail_status = QLabel("")
        self.desc_label = QLabel("")

        readme_section = QLabel("README")
        readme_section.setObjectName("sectionTitle")
        readme_section.setFixedHeight(16)
        detail_layout.addWidget(readme_section)

        self.readme_browser = QTextBrowser()
        self.readme_browser.setObjectName("readmeBrowser")
        self.readme_browser.setOpenExternalLinks(True)
        detail_layout.addWidget(self.readme_browser, 1)

        # 操作按钮行1: HTTPS/SSH/网页/收藏
        action_row1 = QHBoxLayout()
        action_row1.setSpacing(4)
        self.copy_https_btn = QPushButton("\U0001f4cb HTTPS\u514b\u9686")
        self.copy_https_btn.setFixedHeight(32)
        action_row1.addWidget(self.copy_https_btn)
        self.copy_ssh_btn = QPushButton("\U0001f511 SSH\u514b\u9686")
        self.copy_ssh_btn.setFixedHeight(32)
        action_row1.addWidget(self.copy_ssh_btn)
        self.web_btn = QPushButton("\U0001f310 网页")
        self.web_btn.setFixedHeight(32)
        action_row1.addWidget(self.web_btn)
        self.fav_btn = QPushButton("\u2b50 收藏")
        self.fav_btn.setFixedHeight(32)
        action_row1.addWidget(self.fav_btn)
        detail_layout.addLayout(action_row1)

        # 操作按钮行2: MD/HTML/对比/批量收藏
        action_row2 = QHBoxLayout()
        action_row2.setSpacing(4)
        self.download_btn = QPushButton("\U0001f4e5 \u4e0b\u8f7dZIP")
        self.download_btn.setFixedHeight(32)
        action_row2.addWidget(self.download_btn)
        self.copy_link_btn = QPushButton("\U0001f517 \u590d\u5236\u94fe\u63a5")
        self.copy_link_btn.setFixedHeight(32)
        action_row2.addWidget(self.copy_link_btn)
        self.compare_btn = QPushButton("\u2696 对比")
        self.compare_btn.setFixedHeight(32)
        action_row2.addWidget(self.compare_btn)
        self.batch_fav_btn = QPushButton("\u2b50 批量收藏")
        self.batch_fav_btn.setFixedHeight(32)
        action_row2.addWidget(self.batch_fav_btn)
        detail_layout.addLayout(action_row2)

        # 下载资源
        download_section = QLabel(tr("view.download_resources"))
        download_section.setObjectName("sectionTitle")
        download_section.setFixedHeight(16)
        detail_layout.addWidget(download_section)

        self.download_list = QListWidget()
        self.download_list.setObjectName("downloadList")
        self.download_list.setFixedHeight(100)
        self.download_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.download_list.setWordWrap(True)
        detail_layout.addWidget(self.download_list)

        download_hint = QLabel(tr("view.download_hint"))
        download_hint.setObjectName("downloadHint")
        download_hint.setFixedHeight(16)
        detail_layout.addWidget(download_hint)

        # status_label for detail loading status
        self.status_label = QLabel("")
        self.status_label.setObjectName("descLabel")

        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, 36)
        splitter.setStretchFactor(1, 64)

        main_layout.addWidget(splitter, 1)
        self.statusBar().showMessage(tr("app.ready"))

    def _connect_signals(self):
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        self.search_edit.returnPressed.connect(self.refresh_repos)
        self.refresh_btn.clicked.connect(self.refresh_repos)
        if hasattr(self, "web_btn"):
            self.web_btn.clicked.connect(self._open_in_browser)
        self.settings_btn.clicked.connect(self._open_settings)
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.repo_list.currentRowChanged.connect(self._on_repo_selected)
        self.trending_list.currentRowChanged.connect(self._on_trending_selected)
        self.fav_list.currentRowChanged.connect(self._on_fav_selected)
        self.history_list.currentRowChanged.connect(self._on_history_selected)
        self.dashboard_list.currentRowChanged.connect(self._on_dashboard_selected)
        self.fav_btn.clicked.connect(self._toggle_favorite)
        self.translate_btn.clicked.connect(self._translate_current_detail)
        self.download_btn.clicked.connect(self._download_current)
        if hasattr(self, "download_list"):
            self.download_list.itemDoubleClicked.connect(self._on_download_item_clicked)
        if hasattr(self, "copy_https_btn"):
            self.copy_https_btn.clicked.connect(self._copy_https_clone)
        if hasattr(self, "copy_ssh_btn"):
            self.copy_ssh_btn.clicked.connect(self._copy_ssh_clone)
        if hasattr(self, "compare_btn"):
            self.compare_btn.clicked.connect(self._compare_versions)
        if hasattr(self, "batch_fav_btn"):
            self.batch_fav_btn.clicked.connect(self._batch_favorite)
        if hasattr(self, "copy_link_btn"):
            self.copy_link_btn.clicked.connect(self._copy_link)
        self.ui_lang_combo.currentIndexChanged.connect(self._on_ui_language_changed)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_filter_changed)
        # 滚动到底自动加载下一页
        self.repo_list.verticalScrollBar().valueChanged.connect(self._on_discover_scroll)
        self.trending_list.verticalScrollBar().valueChanged.connect(self._on_trending_scroll)

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------

    def _apply_theme(self):
        apply_theme(QApplication.instance(), self._dark_mode)
        self.theme_btn.setText("☀️" if self._dark_mode else "🌙")
        self.theme_btn.setToolTip(tr("theme.to_light") if self._dark_mode else tr("theme.to_dark"))

    def _toggle_theme(self):
        self._dark_mode = not self._dark_mode
        self.config["dark_mode"] = self._dark_mode
        self._apply_theme()
        
        self.service.save_config()

    # ------------------------------------------------------------------
    # 视图切换
    # ------------------------------------------------------------------

    def _on_view_changed(self, index):
        self._batch_cancel = True
        self._translate_queue.clear()
        self._translate_anim_timer.stop()
        self._batch_translate_total = 0
        self._batch_translate_done = 0
        # 递增翻译代数：中断旧视图的详情/README 加载与翻译，把线程池资源留给新视图
        self._translation_gen += 1
        view = self.view_combo.currentData()
        page_map = {"trending": 1, "favorites": 2, "history": 3, "dashboard": 4}
        self._view_stack.setCurrentIndex(page_map.get(view, 0))
        self._update_list_summary()
        if view == "history":
            self._load_history()
        if view == "dashboard":
            self._load_dashboard()
        if view == "trending":
            # 切换到趋势热榜时拉取最新数据（on_done 中 setCurrentIndex(1)
            # 在索引未变化时不触发本方法，无递归风险）
            self.refresh_trending(category_languages=self._current_category_languages())

    def _current_category_languages(self) -> list[str] | None:
        """返回当前分类的语言集合（list）；无语言映射（security/空分类）返回 None。"""
        cat = self._current_category
        if not cat:
            return None
        langs = CATEGORY_LANGUAGES.get(str(cat).strip().casefold(), set())
        return sorted(langs) if langs else None

    def _on_category_clicked(self, category):
        self._current_category = category
        for btn in self._category_buttons:
            btn.setChecked(btn.property("cat_value") == category)
        # 搜索词优先级最高：搜索词存在时列表保持搜索结果，分类仅在无词时切换热榜领域
        if self.search_edit.text().strip():
            return
        self.refresh_trending(category_languages=self._current_category_languages())

    # ------------------------------------------------------------------
    # 列表渲染
    # ------------------------------------------------------------------

    def _render_discover_items(self, repos):
        self._display_repos = list(repos)
        self.repo_list.clear()
        self._discover_rendered = 0
        self._load_more_discover()
        self._update_list_summary()

    def _load_more_discover(self):
        """加载下一批发现项目并翻译；本地数据渲染完后从 API 加载下一页。"""
        self._loading_more = True
        repos = self._display_repos
        start = self._discover_rendered
        end = min(start + self._page_size, len(repos))
        if start >= end:
            self._loading_more = False
            self._fetch_next_discover_page()
            return
        batch = repos[start:end]
        for repo in batch:
            brief = self._repo_list_brief(repo)
            language = repo.get("language", "")
            name_part = repo.get("_translated_name") or repo.get("full_name", "")
            text = f"⭐{repo.get('stars', 0)}  {name_part}  {language}\n{brief}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, repo.get("full_name"))
            self.repo_list.addItem(item)
        self._discover_rendered = end
        self._update_list_summary()
        self._loading_more = False
        # 翻译这批项目
        self._translate_visible_batch(batch, self.repo_list, start)

    def _fetch_next_discover_page(self):
        """请求 GitHub Search API 下一页并追加到发现列表，保持 stars 排序衔接。"""
        if self._discover_api_loading or self._discover_no_more:
            return
        self._discover_api_loading = True
        keyword = self.search_edit.text().strip()
        if keyword:
            # 搜索词优先级最高：搜索场景下一页不再叠加分类，保证结果不受分类影响
            category_languages = None
        else:
            category_languages = self._current_category_languages()
        next_page = self._discover_page + 1
        fetch_gen = self._discover_fetch_gen

        def task():
            return self.service.search_repos(
                keyword,
                page=next_page,
                per_page=REPOSITORY_PAGE_SIZE,
                languages=category_languages,
                sort="stars",
            )

        def on_done(repos):
            self._discover_api_loading = False
            # 刷新已重置列表，丢弃过期分页结果
            if fetch_gen != self._discover_fetch_gen:
                return
            if not repos:
                self._discover_no_more = True
                self.statusBar().showMessage(tr("status.all_loaded"), 2000)
                return
            if not keyword and category_languages is None and self._current_category:
                # 非搜索场景、无语言映射的分类（如 security）：对追加数据本地过滤兜底
                repos = filter_repos_by_category(repos, self._current_category)
            self._discover_page = next_page
            if not repos:
                # 该页无匹配项目：不停止，继续尝试下一页（API 返回空时才停止）
                return
            self._repos.extend(repos)
            self._display_repos.extend(repos)
            # 从已渲染位置继续渲染新数据，不重绘已有行避免滚动跳变
            self._load_more_discover()

        def on_error(msg):
            self._discover_api_loading = False
            self._discover_no_more = True
            self.statusBar().showMessage(tr("status.search_failed", msg=msg), 3000)

        self._run_in_thread(task, on_done, on_error)

    def _render_trending_items(self, repos):
        self._display_trending_items = list(repos)
        self.trending_list.clear()
        self._trending_rendered = 0
        self._load_more_trending()
        self._update_list_summary()

    def _trending_item_text(self, repo: dict) -> str:
        """构造热榜列表项文本（含排名与涨跌前缀）。"""
        rank_change = repo.get("rank_change", {})
        if rank_change.get("is_new"):
            prefix = "🆕"
        elif rank_change.get("change", 0) > 0:
            prefix = f"🔺{rank_change['change']}"
        elif rank_change.get("change", 0) < 0:
            prefix = f"🔻{abs(rank_change['change'])}"
        else:
            prefix = "➖"
        stars_text = f"⭐{repo.get('period_stars', 0)}" if repo.get("period_stars") else ""
        brief = self._repo_list_brief(repo)
        language = repo.get("language", "")
        name_part = repo.get("_translated_name") or repo.get("full_name", "")
        return f"{prefix} #{repo.get('rank', '-')}  ⭐{repo.get('stars', 0)} {stars_text}  {name_part}  {language}\n{brief}"

    def _load_more_trending(self):
        """加载下一批热榜项目并翻译；本地缓存渲染完后抓取后续周期继续滚动。"""
        repos = self._display_trending_items
        start = self._trending_rendered
        end = min(start + self._page_size, len(repos))
        if start >= end:
            # 本地缓存已渲染完：尝试从后续周期抓取更多热榜
            self._fetch_more_trending()
            return
        self._loading_more = True
        batch = repos[start:end]
        for repo in batch:
            text = self._trending_item_text(repo)
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, repo.get("full_name"))
            self.trending_list.addItem(item)
        self._trending_rendered = end
        self._update_list_summary()
        self._loading_more = False
        # 翻译这批项目（含第一个项目，逐一翻译并保留官方排名）
        self._translate_visible_batch(batch, self.trending_list, start)

    def _fetch_more_trending(self):
        """滚动到底时从后续周期抓取更多热榜，去重后连续排名并渲染翻译。"""
        if self._loading_more or self._trending_no_more:
            return
        if not self._trending_periods:
            # 已无后续周期：标记耗尽并提示
            self._trending_no_more = True
            self.statusBar().showMessage(tr("status.all_loaded"), 2000)
            return
        self._loading_more = True
        since = self._trending_periods.pop(0)
        lang = self.config.get("trending_language", "")
        category_languages = self._current_category_languages()
        fetch_gen = self._trending_fetch_gen

        def task():
            fetched = []
            if category_languages:
                # 分类场景：按分类语言分别抓取并合并
                for clang in category_languages:
                    url_lang = str(clang).strip().replace(" ", "-")
                    try:
                        fetched.extend(self.service.scrape_trending(since, url_lang))
                    except Exception:
                        pass
            else:
                fetched.extend(self.service.scrape_trending(since, lang))
            return fetched

        def on_done(repos):
            self._loading_more = False
            if fetch_gen != self._trending_fetch_gen:
                return  # 刷新已重置，丢弃过期扩展结果
            # 分类（无语言映射）本地过滤兜底，保持连续排名
            if self._current_category and not category_languages:
                repos = filter_repos_by_category(repos, self._current_category)
            existing = {r.get("full_name") for r in self._display_trending_items if r.get("full_name")}
            new_repos = [r for r in repos or [] if r.get("full_name") and r["full_name"] not in existing]
            if not new_repos:
                # 该周期无去重后新内容：继续尝试下一周期
                self._fetch_more_trending()
                return
            # 连续排名：从当前总数继续编号，不再重置为 1
            next_rank = len(self._display_trending_items) + 1
            for r in new_repos:
                r["rank"] = next_rank
                next_rank += 1
            self._trending_items.extend(new_repos)
            self._display_trending_items.extend(new_repos)
            self.statusBar().showMessage(tr("status.loaded_trending", count=len(new_repos)))
            # 从已渲染位置继续渲染本批，并自动触发该批次项目的翻译
            self._load_more_trending()

        def on_error(msg):
            self._loading_more = False
            if fetch_gen != self._trending_fetch_gen:
                return
            self.statusBar().showMessage(tr("status.trending_failed", msg=msg), 3000)

        self._run_in_thread(task, on_done, on_error)

    def _on_discover_scroll(self, value):
        if self._loading_more:
            return
        sb = self.repo_list.verticalScrollBar()
        if value >= sb.maximum() - 2:
            self._load_more_discover()

    def _on_trending_scroll(self, value):
        if self._loading_more:
            return
        sb = self.trending_list.verticalScrollBar()
        if value >= sb.maximum() - 2:
            self._load_more_trending()

    def _translate_visible_batch(self, repos, list_widget, start_index):
        """并发翻译当前页项目简介与名称，逐条翻译逐条更新。"""
        # 设置中关闭自动翻译时跳过
        if not self.config.get("auto_translate_desc", True):
            return
        target = self.config.get("target_language", "zh-CN")
        if target in ("en", "en-US"):
            return
        normalized = target.lower().replace("-", "_")
        cache_key = f"_translated_{normalized}"
        for i, repo in enumerate(repos):
            if str(repo.get(cache_key) or "").strip():
                continue
            original = str(repo.get("description") or "").strip()
            if not original:
                continue
            self._translate_queue.append((start_index + i, repo, original, cache_key, list_widget))
            self._batch_translate_total += 1
        # 启动队列翻译（水位式补充，幂等：已有在途任务时不重复出队）
        if len(self._translate_queue) > 0:
            self._batch_cancel = False
            self._translate_pump()

    def _translate_pump(self):
        """水位式补充翻译任务：并发 = min(列表上限, 剩余队列)，由完成回调持续补位。"""
        if self._batch_cancel:
            self._translate_queue.clear()
            self._translate_anim_timer.stop()
            return
        if not self._translate_queue:
            self._translate_anim_timer.stop()
            return
        # 列表翻译用满并发；详情翻译已有独立专用线程池（detail_translate_pool），
        # 互不阻塞，无需再为它让出并发，避免滚动加载的新行长时间排不到翻译
        limit = max(1, int(self.config.get("concurrent_limit", 3)))
        # 同步线程池上限，使“并发翻译数”设置在运行中调大后立即生效
        if self.translate_pool.maxThreadCount() != limit:
            self.translate_pool.setMaxThreadCount(limit)
        target = self.config.get("target_language", "zh-CN")
        while self._active_translations < limit and self._translate_queue:
            idx, repo, original, cache_key, list_widget = self._translate_queue.pop(0)
            self._active_translations += 1

            def task(idx=idx, repo=repo, original=original, cache_key=cache_key, list_widget=list_widget):
                # 视图已切换时放弃翻译，快速释放翻译池线程
                if self._batch_cancel:
                    return None
                try:
                    # translate_description 返回 str；翻译失败时内部回退原文
                    translated = self.service.translate_description(original, target, deadline=time.monotonic() + 15)
                    ok = bool(translated) and translated != original
                    # 名称翻译优先本地词典：本地无法产出有意义译文（如 user/repo 标识符）时
                    # 保留原文，避免每个项目额外一次代理请求拖慢整批翻译
                    full_name = repo.get("full_name", "")
                    translated_name = ""
                    if full_name:
                        try:
                            from github_open_source_browser.translator import local_translate as _lt_name
                            translated_name = _lt_name(full_name, target) or ""
                        except Exception:
                            translated_name = ""
                        if not translated_name or translated_name == full_name:
                            translated_name = ""
                    return (idx, repo, translated, translated_name, cache_key, list_widget) if ok else None
                except Exception as e:
                    logger.warning("列表翻译任务异常: %s", e)
                    return None

            def on_done(result, cache_key=cache_key, list_widget=list_widget):
                try:
                    self._active_translations = max(0, self._active_translations - 1)
                    self._batch_translate_done += 1
                    if result:
                        idx, repo, translated, translated_name, cache_key, list_widget = result
                        repo[cache_key] = translated
                        if translated_name and translated_name != repo.get("full_name", ""):
                            repo["_translated_name"] = translated_name
                        item = list_widget.item(idx)
                        if item:
                            lang = repo.get("language", "")
                            name_part = repo.get("_translated_name") or repo.get("full_name", "")
                            if list_widget is self.trending_list:
                                # 热榜行保留排名与涨跌前缀（brief 从 repo 缓存字段读取翻译）
                                text = self._trending_item_text(repo)
                            else:
                                brief = translated[:77] + "…" if len(translated) > 80 else translated
                                text = f"⭐{repo.get('stars', 0)}  {name_part}  {lang}\n{brief}"
                            item.setText(text)
                    if not self._batch_cancel:
                        self._show_batch_progress()
                finally:
                    # 无论结果如何都补位下一个任务，防止异常导致翻译队列停摆
                    if not self._batch_cancel:
                        interval = max(0, int(self.config.get("request_interval_ms", 200)))
                        QTimer.singleShot(interval, self._translate_pump)

            def on_error(msg, cache_key=cache_key, list_widget=list_widget):
                try:
                    self._active_translations = max(0, self._active_translations - 1)
                    self._batch_translate_done += 1
                    if not self._batch_cancel:
                        self._show_batch_progress()
                finally:
                    # 跳过失败的，继续补位
                    if not self._batch_cancel:
                        interval = max(0, int(self.config.get("request_interval_ms", 200)))
                        QTimer.singleShot(interval, self._translate_pump)

            self._run_translate_in_thread(task, on_done, on_error)

    def _show_batch_progress(self):
        """状态栏显示批量翻译进度，完成后短暂提示。"""
        total = self._batch_translate_total
        done = min(self._batch_translate_done, total)
        if total > 0 and done < total:
            self.statusBar().showMessage(tr("status.translate_progress", done=done, total=total))
        elif total > 0:
            self.statusBar().showMessage(tr("status.translated"), 2000)

    def _render_favorite_items(self, repos):
        self.fav_list.clear()
        self._favorite_items = list(repos)
        for repo in repos:
            brief = self._repo_list_brief(repo)
            language = repo.get("language", "")
            text = f"⭐{repo.get('stars', 0)}  {repo.get('full_name', '')}  {language}\n{brief}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, repo.get("full_name"))
            self.fav_list.addItem(item)
        self._update_list_summary()

    def _repo_list_brief(self, repo: dict) -> str:
        desc = self._repo_description_for_target(repo)
        if len(desc) > 80:
            desc = desc[:77] + "…"
        return desc or tr("window.no_brief")

    def _repo_description_for_target(self, repo: dict) -> str:
        target = self.config.get("target_language", "zh-CN")
        # 优先使用已翻译字段
        if target.startswith("zh"):
            for field in ("description_zh", "description_zh_cn"):
                val = str(repo.get(field) or "").strip()
                if val:
                    return val
        normalized = target.lower().replace("-", "_")
        field = f"description_{normalized}"
        val = str(repo.get(field) or "").strip()
        if val:
            return val
        # 如果没有翻译过，尝试翻译并缓存到 repo 字典
        original = str(repo.get("description") or "").strip()
        if not original:
            return ""
        # 只翻译英文内容到非英文目标
        if target in ("en", "en-US"):
            return original
        cache_key = f"_translated_{normalized}"
        cached = str(repo.get(cache_key) or "").strip()
        if cached:
            return cached
        # 后台批量翻译会填充缓存，这里只返回原文
        return original

    # ------------------------------------------------------------------
    # 列表摘要
    # ------------------------------------------------------------------

    def _update_list_summary(self):
        view = self.view_combo.currentData()
        if view == "discover":
            total = len(self._repos)
            shown = len(self._display_repos)
            cat = self._current_category
            cat_label = CATEGORY_DISPLAY_LABELS.get(cat, tr("cat.all"))
            text = tr("summary.discover", cat_label=cat_label, shown=shown, total=total)
        elif view == "trending":
            total = len(self._trending_items)
            shown = len(self._display_trending_items)
            text = tr("summary.trending", shown=shown, total=total)
        elif view == "favorites":
            total = len(self._favorite_items)
            text = tr("summary.favorites", total=total)
        else:
            text = ""
        self.list_summary_label.setText(text)
        if hasattr(self, "listSummary"):
            self.listSummary.setText(text)

    # ------------------------------------------------------------------
    # 刷新项目
    # ------------------------------------------------------------------

    def _sort_repos(self, repos: list[dict]) -> list[dict]:
        """发现页排序：星星降序，无星星（或相同）按最近更新时间降序。"""
        # 先按更新时间降序（稳定排序），再按星星降序：星星相同保持时间序
        return sorted(
            sorted(
                repos,
                key=lambda r: str(r.get("pushed_at") or r.get("updated_at") or ""),
                reverse=True,
            ),
            key=lambda r: -(r.get("stars", 0) or 0),
        )

    def refresh_repos(self, category_languages: list[str] | None = None):
        keyword = self.search_edit.text().strip()
        if not keyword:
            # 无搜索词：回到趋势热榜（按当前分类领域），搜索词优先级最高时不受分类影响
            idx = self.view_combo.findData("trending")
            if idx >= 0:
                self.view_combo.setCurrentIndex(idx)
            self.refresh_trending(category_languages=self._current_category_languages())
            return
        lang = self.lang_combo.currentData() or ""
        old_lang = self.config.get("language", "")
        if lang != old_lang:
            self.config["language"] = lang
        self.statusBar().showMessage(tr("status.searching"))
        if hasattr(self, "refresh_btn"): self.refresh_btn.setEnabled(False)
        if hasattr(self, "_loading"): self._loading.show_loading(tr("status.searching"))
        # 重置分页计数，开始新的加载序列
        self._discover_page = 1
        self._discover_api_loading = False
        self._discover_fetch_gen += 1

        def task():
            return self.service.search_repos(
                keyword,
                page=1,
                per_page=REPOSITORY_PAGE_SIZE,
                languages=category_languages,
                sort="stars",
            )

        def on_done(repos):
            if hasattr(self, "refresh_btn"): self.refresh_btn.setEnabled(True)
            if hasattr(self, "_loading"): self._loading.hide_loading()
            # 项目按星级从高到低排序展示（无星星按最近更新时间）
            repos = self._sort_repos(repos)
            self._repos = repos
            self._display_repos = list(repos)
            self._render_discover_items(repos)
            self._view_stack.setCurrentIndex(0)  # 主列表切换为搜索结果容器
            self.statusBar().showMessage(tr("status.loaded_projects", count=len(repos)))

        def on_error(msg):
            if hasattr(self, "refresh_btn"): self.refresh_btn.setEnabled(True)
            if hasattr(self, "_loading"): self._loading.hide_loading()
            self.statusBar().showMessage(tr("status.search_failed", msg=msg))

        self._run_in_thread(task, on_done, on_error)

    def refresh_trending(self, category_languages: list[str] | None = None):
        since = self.config.get("trending_since", "daily")
        lang = self.config.get("trending_language", "")
        self.statusBar().showMessage(tr("status.loading_trending"))
        if hasattr(self, "trending_btn"): self.trending_btn.setEnabled(False)
        if hasattr(self, "_loading"): self._loading.show_loading(tr("status.loading_trending"))

        def task():
            if category_languages:
                # 按分类语言抓取各语言热榜并合并去重，按今日新增星星降序重排
                merged = []
                seen = set()
                for clang in category_languages:
                    # Trending URL 语言用连字符（jupyter notebook -> jupyter-notebook）
                    url_lang = str(clang).strip().replace(" ", "-")
                    for repo in self.service.scrape_trending(since, url_lang):
                        if repo["full_name"] in seen:
                            continue
                        seen.add(repo["full_name"])
                        merged.append(repo)
                merged.sort(key=lambda r: r.get("period_stars", 0) or 0, reverse=True)
                for i, repo in enumerate(merged):
                    repo["rank"] = i + 1
                return merged
            repos = self.service.scrape_trending(since, lang, page=1, per_page=TRENDING_PAGE_SIZE)
            # 添加排名信息
            for i, repo in enumerate(repos):
                repo["rank"] = i + 1
            return repos

        def on_done(repos):
            if hasattr(self, "trending_btn"): self.trending_btn.setEnabled(True)
            if hasattr(self, "_loading"): self._loading.hide_loading()
            # 无语言映射的分类（security）或分类为空时的本地过滤兜底，保持排名顺序
            if self._current_category and not category_languages:
                repos = filter_repos_by_category(repos, self._current_category)
            self._trending_items = repos
            self._display_trending_items = list(repos)
            # 刷新后重置无限滚动状态：记录后续待抓取周期，递增代数丢弃在途扩展结果
            self._trending_no_more = False
            self._trending_periods = self.service.trending_periods_after(since)
            self._trending_fetch_gen += 1
            self._loading_more = False
            self._render_trending_items(repos)
            # 切到热榜视图（combo 项已移除“发现项目”，用 data 定位而非固定索引）
            idx = self.view_combo.findData("trending")
            if idx >= 0:
                self.view_combo.setCurrentIndex(idx)
            self.statusBar().showMessage(tr("status.loaded_trending", count=len(repos)))

        def on_error(msg):
            if hasattr(self, "trending_btn"): self.trending_btn.setEnabled(True)
            if hasattr(self, "_loading"): self._loading.hide_loading()
            self.statusBar().showMessage(tr("status.trending_failed", msg=msg))

        self._run_in_thread(task, on_done, on_error)

    def _load_favorites(self):
        favs = self.service.favorites.all()
        self._favorite_items = favs
        self._render_favorite_items(favs)

    # ------------------------------------------------------------------
    # 项目选择与详情
    # ------------------------------------------------------------------

    def _on_repo_selected(self, row):
        if row < 0 or row >= len(self._display_repos):
            return
        repo = self._display_repos[row]
        self._show_detail(repo)

    def _on_trending_selected(self, row):
        if row < 0 or row >= len(self._display_trending_items):
            return
        repo = self._display_trending_items[row]
        self._show_detail(repo)

    def _on_fav_selected(self, row):
        if row < 0 or row >= len(self._favorite_items):
            return
        repo = self._favorite_items[row]
        self._show_detail(repo)

    def _show_detail(self, repo):
        # 递增翻译代数，取消之前所有进行中的详情翻译（README 加载/翻译、图片嵌入）。
        # 注意：这里不设置 _batch_cancel、不清空 _translate_queue——列表批量翻译在
        # 独立 translate_pool 运行，详情翻译走 detail_translate_pool，互不争抢线程；
        # 若在此清空列表翻译队列，已渲染批次中尚未出队的项目会永久丢失翻译
        # （只有下一批 _translate_visible_batch 才会恢复补位，最后一批则永不翻译）。
        self._translation_gen += 1
        self._translate_anim_timer.stop()
        self._batch_translate_total = 0
        self._batch_translate_done = 0
        current_gen = self._translation_gen
        self._current_repo = repo
        full_name = repo.get("full_name", "")
        self.detail_title.setText(full_name)
        stars = repo.get("stars", 0)
        lang = repo.get("language", "")
        forks = repo.get("forks", 0)
        stats_parts = []
        if stars: stats_parts.append(f"⭐ {stars:,}")
        if lang: stats_parts.append(lang)
        if forks: stats_parts.append(f"🍴 {forks:,}")
        self.detail_stats.setText(" | ".join(stats_parts))
        self.desc_label.setText(self._repo_description_for_target(repo) or tr("window.no_desc"))
        self.status_label.setText(tr("status.loading_detail"))
        self.readme_browser.setHtml(f"<p style='color:gray'>{tr('status.loading_readme')}</p>")

        # 填充下载链接（同步，立即显示）
        self._populate_download_list(repo)

        # 更新收藏按钮状态
        is_fav = self.service.favorites.contains(full_name)
        self.fav_btn.setText(tr("btn.favorited") if is_fav else tr("btn.favorite"))

        # 异步加载 README（代际变化时放弃，释放线程池给新任务）
        def task():
            if self._translation_gen != current_gen:
                return None
            readme = self.service.get_readme(full_name)
            if self._translation_gen != current_gen:
                return None
            release = self.service.get_release(full_name)
            return {"readme": readme, "release": release}

        def on_done(result):
            try:
                if not result:
                    return  # 已切换项目/视图，任务被取消，放弃更新
                print("ON_DONE_ENTER", type(result).__name__, flush=True)
                readme = result.get("readme", "")
                release = result.get("release")
                if readme:
                    self._current_readme = readme
                    self._render_readme(readme)
                else:
                    self._current_readme = ""
                    self.readme_browser.setHtml(f"<p style='color:gray'>{tr('status.no_readme')}</p>")
                status_parts = [tr("status.detail_loaded")]
                if release:
                    status_parts.append(tr("status.latest_ver", ver=release.get("tag_name", "")))
                self.status_label.setText(" | ".join(status_parts))
                self._populate_download_list(repo, release)
                # 自动翻译：如果设置了自动翻译 README，加载完后自动触发
                if self.config.get("auto_translate_readme") and current_gen == self._translation_gen:
                    self._auto_translate_detail(repo, current_gen)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print("ON_DONE_EXC", type(e).__name__, e, flush=True)

        def on_error(msg):
            self.status_label.setText(tr("status.detail_failed", msg=msg))
            self.readme_browser.setHtml(
                f'<p style="color:#d32f2f">{tr("status.detail_failed", msg=msg)}</p>'
            )

        self._run_in_thread(task, on_done, on_error)

    def _populate_download_list(self, repo, release=None):
        """填充下载资源列表。"""
        self.download_list.clear()
        full_name = repo.get("full_name", "")
        if not full_name:
            return
        # ZIP download
        default_branch = repo.get("default_branch", "main")
        zip_url = f"https://github.com/{full_name}/archive/refs/heads/{default_branch}.zip"
        item = QListWidgetItem(f"📦 ZIP: {full_name} ({default_branch})")
        item.setData(Qt.ItemDataRole.UserRole, zip_url)
        self.download_list.addItem(item)
        # TAR.GZ download
        tar_url = f"https://github.com/{full_name}/archive/refs/heads/{default_branch}.tar.gz"
        item = QListWidgetItem(f"📦 TAR.GZ: {full_name} ({default_branch})")
        item.setData(Qt.ItemDataRole.UserRole, tar_url)
        self.download_list.addItem(item)
        # Release assets
        if release:
            tag = release.get("tag_name", "")
            release_url = release.get("html_url", "")
            if release_url:
                item = QListWidgetItem(f"🏷 Release {tag}")
                item.setData(Qt.ItemDataRole.UserRole, release_url)
                self.download_list.addItem(item)
        # GitHub page link
        html_url = repo.get("html_url", f"https://github.com/{full_name}")
        item = QListWidgetItem(f"🌐 GitHub 页面: {html_url}")
        item.setData(Qt.ItemDataRole.UserRole, html_url)
        self.download_list.addItem(item)

    def _render_readme(self, markdown_text):
        """将 Markdown 渲染为 HTML 并显示。"""
        try:
            import markdown
            html = markdown.markdown(
                markdown_text,
                extensions=["tables", "fenced_code", "codehilite", "toc"],
            )
            # 包装为完整 HTML
            full_html = f"""
            <html><head><style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.6; color: #e6edf3; background-color: #0d1117; padding: 16px; }}
            a {{ color: #58a6ff; }}
            code {{ background-color: #161b22; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
            pre {{ background-color: #161b22; padding: 12px; border-radius: 6px; overflow-x: auto; }}
            pre code {{ background: none; padding: 0; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #30363d; padding: 8px; text-align: left; }}
            th {{ background-color: #161b22; }}
            img {{ max-width: 100%; }}
            blockquote {{ border-left: 4px solid #30363d; padding-left: 12px; color: #8b949e; }}
            h1, h2, h3, h4 {{ border-bottom: 1px solid #21262d; padding-bottom: 8px; }}
            </style></head><body>{html}</body></html>
            """
            self.readme_browser.setHtml(full_html)
        except Exception:
            self.readme_browser.setPlainText(markdown_text)

    # ------------------------------------------------------------------
    # 翻译
    # ------------------------------------------------------------------

    def _translate_current_detail(self):
        repo = self._current_repo
        if not repo:
            return
        # 只递增详情翻译代数取消旧详情任务；不设置 _batch_cancel、不清空列表翻译队列，
        # 详情翻译走 detail_translate_pool，与列表批量翻译互不干扰
        self._translation_gen += 1
        self._batch_translate_total = 0
        self._batch_translate_done = 0
        current_gen = self._translation_gen
        target = self.config.get("target_language", "zh-CN")
        self.translate_btn.setEnabled(False)
        self.translate_btn.setText(tr("status.translating_btn"))
        self.status_label.setText(tr("status.translating"))
        self._translate_anim_dots = 0
        self._translate_anim_timer.start()
        if hasattr(self, '_loading'):
            self._loading.show_loading(tr("status.translating"))

        # 描述翻译与 README 翻译拆成两个独立 Worker，互不阻塞、各带总时长上限。
        # README 未加载完成时由 task_readme 内部补加载，保证翻译按钮始终产出译文。
        pending = {"n": 2}

        def finish():
            pending["n"] -= 1
            if pending["n"] > 0:
                return
            if current_gen != self._translation_gen:
                return  # 项目已切换，按钮由新翻译管理
            self._translate_anim_timer.stop()
            self.translate_btn.setEnabled(True)
            self.translate_btn.setText(tr("btn.translate"))
            self.status_label.setText(tr("status.translated"))
            if hasattr(self, '_loading'):
                self._loading.hide_loading()

        def task_desc():
            if self._translation_gen != current_gen:
                return None
            desc = repo.get("description", "")
            return self.service.translate_description(desc, target, deadline=time.monotonic() + 15)

        def task_readme():
            if self._translation_gen != current_gen:
                return None
            cached_readme = self._current_readme or ""
            if cached_readme:
                return self.service.translate_readme(cached_readme, target, deadline=time.monotonic() + 60)
            # README 尚未加载完成：先补加载再翻译，保证翻译按钮始终能产出 README 译文
            if self._translation_gen != current_gen:
                return None
            readme = self.service.get_readme(repo.get("full_name", ""))
            if self._translation_gen != current_gen:
                return None
            self._current_readme = readme or ""
            return self.service.translate_readme(self._current_readme, target, deadline=time.monotonic() + 60) if self._current_readme else ""

        def on_desc(result):
            if current_gen == self._translation_gen and result:
                self.desc_label.setText(result)
            finish()

        def on_readme(result):
            if current_gen == self._translation_gen and result:
                self._render_readme(result)
            finish()

        self._run_translate_in_thread(task_desc, on_desc, lambda msg: finish(), pool=self.detail_translate_pool)
        # 无条件启动 README 翻译：cached_readme 为空时 task_readme 内部会补加载再翻译
        self._run_translate_in_thread(task_readme, on_readme, lambda msg: finish(), pool=self.detail_translate_pool)

    def _on_translate_anim_tick(self):
        """翻译动画：状态栏文字循环显示 翻译中. / 翻译中.. / 翻译中..."""
        self._translate_anim_dots = (self._translate_anim_dots % 3) + 1
        dots = "." * self._translate_anim_dots
        base = tr("status.translating").rstrip(".")
        self.status_label.setText(base + dots)

    def _auto_translate_detail(self, repo, gen):
        """自动翻译当前项目（由设置触发），翻译前先取消之前的翻译。"""
        self._translate_anim_dots = 0
        self._translate_anim_timer.start()
        target = self.config.get("target_language", "zh-CN")
        self.translate_btn.setEnabled(False)
        self.translate_btn.setText(tr("status.translating_btn"))
        self.status_label.setText(tr("status.translating"))

        # 描述与 README 翻译拆两个独立 Worker，互不阻塞、各带总时长上限
        pending = {"n": 2 if self._current_readme else 1}

        def finish():
            pending["n"] -= 1
            if pending["n"] > 0:
                return
            if gen != self._translation_gen:
                return
            self._translate_anim_timer.stop()
            self.translate_btn.setEnabled(True)
            self.translate_btn.setText(tr("btn.translate"))
            self.status_label.setText(tr("status.translated"))

        def task_desc():
            if self._translation_gen != gen:
                return None
            desc = repo.get("description", "")
            return self.service.translate_description(desc, target, deadline=time.monotonic() + 15)

        def task_readme():
            if self._translation_gen != gen:
                return None
            cached_readme = self._current_readme or ""
            return self.service.translate_readme(cached_readme, target, deadline=time.monotonic() + 60) if cached_readme else ""

        def on_desc(result):
            if gen == self._translation_gen and result:
                self.desc_label.setText(result)
            finish()

        def on_readme(result):
            if gen == self._translation_gen and result:
                self._render_readme(result)
            finish()

        self._run_translate_in_thread(task_desc, on_desc, lambda msg: finish(), pool=self.detail_translate_pool)
        if self._current_readme:
            self._run_translate_in_thread(task_readme, on_readme, lambda msg: finish(), pool=self.detail_translate_pool)

    # ------------------------------------------------------------------
    # 收藏
    # ------------------------------------------------------------------

    def _toggle_favorite(self):
        repo = self._current_repo
        if not repo:
            return
        full_name = repo.get("full_name", "")
        if self.service.favorites.contains(full_name):
            self.service.favorites.remove(full_name)
            self.fav_btn.setText(tr("btn.favorite"))
            self.statusBar().showMessage(tr("status.unfavorited", full_name=full_name))
        else:
            self.service.favorites.add(repo)
            self.fav_btn.setText(tr("btn.favorited"))
            self.statusBar().showMessage(tr("status.favorited", full_name=full_name))
        self.service.save_config()
        # 刷新收藏列表
        self._load_favorites()

    # ------------------------------------------------------------------
    # 下载
    # ------------------------------------------------------------------

    def _download_current(self):
        repo = self._current_repo
        if not repo:
            return
        full_name = repo.get("full_name", "")
        url = repo.get("html_url", "")
        if not url:
            return
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))
        self.service.history.add({
            "full_name": full_name,
            "url": url,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self.service.save_config()
        self.statusBar().showMessage(tr("status.opened_in_browser", full_name=full_name))

    def _copy_link(self):
        repo = self._current_repo
        if not repo:
            return
        url = repo.get("html_url", "")
        if url:
            QApplication.clipboard().setText(url)
            self.statusBar().showMessage(tr("status.link_copied"))

    def _open_in_browser(self):
        repo = self._current_repo
        if repo:
            url = repo.get("html_url", "")
            if url:
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(url))

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------

    def _open_settings(self):
        from github_open_source_browser.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.service, self)
        if dialog.exec():
            # 设置已保存，刷新配置
            self.config = self.service.config
            self._apply_theme()
        

    # ------------------------------------------------------------------
    # 语言切换
    # ------------------------------------------------------------------

    def _on_ui_language_changed(self, index):
        lang = self.ui_lang_combo.currentData()
        if not lang:
            return
        self.config["ui_language"] = lang
        self.config["target_language"] = lang.replace("_", "-") if "_" in lang else lang
        self.service.save_config()
        set_language(lang)
        self._retranslate_ui()
        # Refresh list items to follow new language
        view = self.view_combo.currentData()
        if view == "discover":
            self._render_discover_items(self._display_repos)
        elif view == "trending":
            self._render_trending_items(self._display_trending_items)
        elif view == "favorites":
            self._render_favorite_items(self._favorite_items)
        elif view == "history":
            self._render_history_items()

    def _on_lang_filter_changed(self, index):
        lang = self.lang_combo.currentData() or ""
        self.config["language"] = lang

    def _retranslate_ui(self):
        """刷新所有 UI 控件的文字为当前语言。"""
        self.setWindowTitle(tr("app.title"))
        self.search_edit.setPlaceholderText(tr("search.placeholder"))
        self.lang_combo.setItemText(0, tr("search.all_lang"))
        self.refresh_btn.setText(tr("btn.refresh"))
        if hasattr(self, "trending_btn"): self.trending_btn.setText(tr("btn.trending"))
        self.web_btn.setText(tr("btn.web"))
        self.settings_btn.setText(tr("btn.settings"))
        is_dark = self._dark_mode
        self.theme_btn.setToolTip(tr("theme.to_light") if is_dark else tr("theme.to_dark"))
        fn = self._current_repo.get("full_name", "") if self._current_repo else ""
        self.fav_btn.setText(tr("btn.favorited") if self.service.favorites.contains(fn) else tr("btn.favorite"))
        if hasattr(self, "copy_https_btn"): self.copy_https_btn.setText("\U0001f4cb HTTPS\u514b\u9686")
        if hasattr(self, "copy_ssh_btn"): self.copy_ssh_btn.setText("\U0001f511 SSH\u514b\u9686")
        if hasattr(self, "download_btn"): self.download_btn.setText("\U0001f4e5 \u4e0b\u8f7dZIP")
        if hasattr(self, "copy_link_btn"): self.copy_link_btn.setText("\U0001f517 \u590d\u5236\u94fe\u63a5")
        if hasattr(self, "compare_btn"): self.compare_btn.setText("\u2696 \u5bf9\u6bd4")
        if hasattr(self, "batch_fav_btn"): self.batch_fav_btn.setText("\u2b50 \u6279\u91cf\u6536\u85cf")
        self.translate_btn.setText(tr("btn.translate"))
        self.download_btn.setText(tr("btn.download"))
        self.copy_link_btn.setText(tr("btn.copy_link"))
        vl = {"discover": "view.discover", "trending": "view.trending",
              "favorites": "view.favorites", "history": "view.history", "dashboard": "view.dashboard"}
        for i in range(self.view_combo.count()):
            v = self.view_combo.itemData(i)
            if v in vl:
                self.view_combo.setItemText(i, tr(vl[v]))
        ck = {"": "cat.all", "ai": "cat.ai", "frontend": "cat.frontend",
              "backend": "cat.backend", "mobile": "cat.mobile", "devops": "cat.devops",
              "database": "cat.database", "security": "cat.security", "game": "cat.game", "tool": "cat.tool"}
        cd = {"": "catdesc.all", "ai": "catdesc.ai", "frontend": "catdesc.frontend",
              "backend": "catdesc.backend", "mobile": "catdesc.mobile", "devops": "catdesc.devops",
              "database": "catdesc.database", "security": "catdesc.security", "game": "catdesc.game", "tool": "catdesc.tool"}
        for btn in self._category_buttons:
            k = btn.property("cat_value")
            if k in ck:
                btn.setText(tr(ck[k]))
                btn.setToolTip(tr(cd.get(k, "")))
        if self._current_repo:
            self.detail_title.setText(self._current_repo.get("full_name", ""))
            self.desc_label.setText(self._repo_description_for_target(self._current_repo) or tr("window.no_desc"))
        else:
            self.detail_title.setText(tr("window.select_project"))
            self.desc_label.setText("")
        self.status_label.setText("")
        if hasattr(self, "statusLabel"): self.statusLabel.setText(tr("app.ready"))
        if hasattr(self, "mirrorLabel"): self.mirrorLabel.setText("")
        if hasattr(self, "listSummary"): self.listSummary.setText("")
        self.statusBar().showMessage(tr("app.ready"))
        self._update_list_summary()

    # ------------------------------------------------------------------
    # 后台任务
    # ------------------------------------------------------------------

    def _run_in_thread(self, fn, on_done=None, on_error=None):
        """提交后台任务。"""
        self._busy_count += 1
        self.statusBar().showMessage(tr("app.loading"))

        def task_wrapper():
            try:
                result = fn()
                return result
            except Exception as e:
                raise e

        worker = Worker(task_wrapper)
        # 关闭 autoDelete：worker 与 signals(QObject) 由主线程持有引用并统一回收，
        # 避免 signals 在 worker 线程被 GC 销毁导致 Qt fail-fast 崩溃
        worker.setAutoDelete(False)
        self._active_workers.append(worker)

        def handle_result(result):
            self._busy_count = max(0, self._busy_count - 1)
            if on_done:
                on_done(result)

        def handle_error(msg):
            self._busy_count = max(0, self._busy_count - 1)
            if on_error:
                on_error(msg)

        def cleanup():
            # finished 信号在主线程处理，此处释放 worker 引用，让 QObject 在主线程回收
            if worker in self._active_workers:
                self._active_workers.remove(worker)

        worker.signals.result.connect(handle_result)
        worker.signals.error.connect(handle_error)
        worker.signals.finished.connect(cleanup)
        self.thread_pool.start(worker)

    def _run_translate_in_thread(self, fn, on_done=None, on_error=None, pool=None):
        """提交翻译后台任务，走翻译专用线程池，避免长翻译挤占全局池。
        pool 为 None 时使用列表翻译池（translate_pool）。"""
        self._busy_count += 1
        target_pool = pool if pool is not None else self.translate_pool

        def task_wrapper():
            return fn()

        worker = Worker(task_wrapper)
        # 与 _run_in_thread 相同：关闭 autoDelete，主线程持有并统一回收，
        # 避免 signals(QObject) 在 worker 线程被 GC 销毁导致崩溃
        worker.setAutoDelete(False)
        self._active_workers.append(worker)

        def handle_result(result):
            self._busy_count = max(0, self._busy_count - 1)
            if on_done:
                on_done(result)

        def handle_error(msg):
            self._busy_count = max(0, self._busy_count - 1)
            if on_error:
                on_error(msg)

        def cleanup():
            if worker in self._active_workers:
                self._active_workers.remove(worker)

        worker.signals.result.connect(handle_result)
        worker.signals.error.connect(handle_error)
        worker.signals.finished.connect(cleanup)
        target_pool.start(worker)

    # ------------------------------------------------------------------
    # 窗口事件
    # ------------------------------------------------------------------

    def _on_history_selected(self, row):
        history = self.service.history.all()
        if row < 0 or row >= len(history):
            return
        entry = history[row]
        full_name = entry.get("full_name", "")
        repo = None
        for r in self._repos + self._trending_items + self._favorite_items:
            if r.get("full_name") == full_name:
                repo = r
                break
        if repo:
            self._show_detail(repo)
        else:
            self.detail_title.setText(full_name)
            self.desc_label.setText(entry.get("url", ""))

    def _render_history_items(self):
        self.history_list.clear()
        for entry in self.service.history.all():
            text = entry.get("full_name", "") + "  " + entry.get("time", "")
            item = QListWidgetItem(text)
            self.history_list.addItem(item)
        self._update_list_summary()

    def _load_history(self):
        self._render_history_items()

    def _on_dashboard_selected(self, row):
        repos = getattr(self, "_dashboard_repos", [])
        if row < 0 or row >= len(repos):
            return
        self._show_detail(repos[row])

    def _render_dashboard_items(self, repos):
        self.dashboard_list.clear()
        self._dashboard_repos = list(repos)
        for repo in sorted(repos, key=lambda r: r.get("stars", 0), reverse=True):
            text = f"\u2b50{repo.get('stars', 0)}  {repo.get('full_name', '')}  {repo.get('language', '')}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, repo.get("full_name"))
            self.dashboard_list.addItem(item)
        self._update_list_summary()

    def _load_dashboard(self):
        all_repos = self._repos + self._trending_items + self._favorite_items
        seen = set()
        unique = []
        for r in all_repos:
            fn = r.get("full_name", "")
            if fn and fn not in seen:
                seen.add(fn)
                unique.append(r)
        self._render_dashboard_items(unique)

    def _check_new_release(self):
        """Check for new releases of the app itself."""
        def task():
            try:
                resp = self.service.http.get("https://api.github.com/repos/nicekwell/github-open-source-browser/releases/latest", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    tag = data.get("tag_name", "")
                    body = data.get("body", "")[:200]
                    return {"tag": tag, "body": body, "url": data.get("html_url", "")}
            except Exception:
                pass
            return None

        def on_done(result):
            if result and result.get("tag"):
                from github_open_source_browser import __version__
                tag = result["tag"].lstrip("v")
                if tag != __version__:
                    self.statusBar().showMessage(f"\u65b0\u7248\u672c {result['tag']} \u5df2\u53d1\u5e03\uff0c\u8bf7\u67e5\u770b", 10000)

        self._run_in_thread(task, on_done)

    def _on_download_item_clicked(self, item):
        """点击下载项打开链接。"""
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            if url:
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(url))

    def _copy_https_clone(self):
        """复制 HTTPS 克隆地址。"""
        repo = self._current_repo
        if not repo:
            return
        full_name = repo.get("full_name", "")
        if full_name:
            url = f"https://github.com/{full_name}.git"
            QApplication.clipboard().setText(url)
            self.statusBar().showMessage(f"HTTPS: {url}")

    def _copy_ssh_clone(self):
        """复制 SSH 克隆地址。"""
        repo = self._current_repo
        if not repo:
            return
        full_name = repo.get("full_name", "")
        if full_name:
            url = f"git@github.com:{full_name}.git"
            QApplication.clipboard().setText(url)
            self.statusBar().showMessage(f"SSH: {url}")

    def _compare_versions(self):
        """打开 GitHub 比较页面。"""
        repo = self._current_repo
        if not repo:
            return
        url = repo.get("html_url", "")
        if url:
            compare_url = f"{url}/compare"
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(compare_url))

    def _batch_favorite(self):
        """批量收藏当前显示的项目。"""
        view = self.view_combo.currentData()
        if view == "discover":
            repos = self._display_repos
        elif view == "trending":
            repos = self._display_trending_items
        else:
            repos = []
        count = 0
        for repo in repos:
            if not self.service.favorites.contains(repo.get("full_name", "")):
                self.service.favorites.add(repo)
                count += 1
        if count > 0:
            self.service.save_config()
            self._load_favorites()
            self.statusBar().showMessage(f"批量收藏 {count} 个项目")
        else:
            self.statusBar().showMessage("所有项目已收藏")

    def closeEvent(self, event):
        self.service.save_config()
        super().closeEvent(event)
