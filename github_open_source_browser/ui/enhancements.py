# -*- coding: utf-8 -*-
"""功能增强：图片内嵌、增量渲染、系统托盘、ZIP 下载。"""
from __future__ import annotations
from github_open_source_browser.i18n import tr

import os
import re
import time

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QListWidgetItem,
    QMenu,
    QSystemTrayIcon,
)

from github_open_source_browser.ui.main_window import MainWindow

# ---------------------------------------------------------------------------
# 保存原始方法引用
# ---------------------------------------------------------------------------

_ORIGINAL_SHOW_DETAIL = MainWindow._show_detail
_ORIGINAL_RENDER_DISCOVER = MainWindow._render_discover_items
_ORIGINAL_RENDER_TRENDING = MainWindow._render_trending_items
_ORIGINAL_DOWNLOAD_CURRENT = MainWindow._download_current
_ORIGINAL_INIT_UI = MainWindow._init_ui
_ORIGINAL_CLOSE_EVENT = MainWindow.closeEvent

# ---------------------------------------------------------------------------
# 1. README 图片内嵌
# ---------------------------------------------------------------------------


def _embed_readme_images(self, html_text, gen=None):
    """异步下载 README 中的图片并转为 base64 内嵌。gen 为捕获的详情翻译代数，
    切换项目后代数变化，任务即放弃，避免旧详情的图片嵌入覆盖新详情。"""
    img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
    urls = img_pattern.findall(html_text)
    if not urls:
        return

    def task():
        result = html_text
        deadline = time.monotonic() + 12  # 整体限时，避免关闭程序时长时间等待
        for url in urls:
            if time.monotonic() > deadline:
                break
            if gen is not None and self._translation_gen != gen:
                return None  # 已切换到其他项目，放弃嵌入
            if url.startswith("data:"):
                continue
            b64 = self.service.download_image_as_base64(url)
            if b64:
                result = result.replace(url, b64)
        return result

    def on_done(new_html):
        if gen is not None and self._translation_gen != gen:
            return  # 已切换到其他项目，放弃嵌入结果
        if new_html and new_html != html_text:
            self.readme_browser.setHtml(new_html)

    self._run_in_thread(task, on_done)


def _show_detail_with_images(self, repo):
    """详情页加载完成后嵌入图片。"""
    _ORIGINAL_SHOW_DETAIL(self, repo)
    # 延迟一下等渲染完成再提取 HTML 中的图片；捕获当前翻译代数，切换详情后放弃
    gen = self._translation_gen
    QTimer.singleShot(500, lambda: _embed_readme_images(self, self.readme_browser.toHtml(), gen))


MainWindow._embed_readme_images = _embed_readme_images
MainWindow._show_detail = _show_detail_with_images

# ---------------------------------------------------------------------------
# 2. 增量分批渲染（16 条/批）
# ---------------------------------------------------------------------------

_BATCH_SIZE = 16


def _render_discover_items_batched(self, repos):
    """分批渲染发现列表。"""
    self.repo_list.clear()
    self._display_repos = list(repos)
    self._discover_batch_queue = list(repos)
    self._discover_batch_index = 0
    self._discover_rendered = 0  # 与本页滚动加载计数对齐，渲染完成后由 _render_discover_batch 收尾
    self._render_discover_batch()
    self._update_list_summary()


def _render_discover_batch(self):
    queue = getattr(self, "_discover_batch_queue", [])
    idx = getattr(self, "_discover_batch_index", 0)
    end = min(len(queue), idx + _BATCH_SIZE)
    while idx < end:
        repo = queue[idx]
        brief = self._repo_list_brief(repo)
        language = repo.get("language", "")
        text = f"\u2b50{repo.get('stars', 0)}  {repo.get('full_name', '')}  {language}\n{brief}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, repo.get("full_name"))
        self.repo_list.addItem(item)
        idx += 1
    self._discover_batch_index = idx
    if idx < len(queue):
        QTimer.singleShot(16, self._render_discover_batch)
    else:
        # 本批全部渲染完成：同步已渲染计数，并自动触发这批项目的翻译
        self._discover_rendered = len(queue)
        self._translate_visible_batch(queue, self.repo_list, 0)


def _render_trending_items_batched(self, repos):
    """分批渲染热榜列表。"""
    self.trending_list.clear()
    self._display_trending_items = list(repos)
    self._trending_batch_queue = list(repos)
    self._trending_batch_index = 0
    self._trending_rendered = 0  # 与本页滚动加载计数对齐，渲染完成后由 _render_trending_batch 收尾
    self._render_trending_batch()
    self._update_list_summary()


def _render_trending_batch(self):
    queue = getattr(self, "_trending_batch_queue", [])
    idx = getattr(self, "_trending_batch_index", 0)
    end = min(len(queue), idx + _BATCH_SIZE)
    while idx < end:
        repo = queue[idx]
        rank_change = repo.get("rank_change", {})
        if rank_change.get("is_new"):
            prefix = "\U0001f195"
        elif rank_change.get("change", 0) > 0:
            prefix = f"\U0001f53a{rank_change['change']}"
        elif rank_change.get("change", 0) < 0:
            prefix = f"\U0001f53b{abs(rank_change['change'])}"
        else:
            prefix = "\u2796"
        stars_text = f"\u2b50{repo.get('period_stars', 0)}" if repo.get("period_stars") else ""
        brief = self._repo_list_brief(repo)
        language = repo.get("language", "")
        text = f"{prefix} #{repo.get('rank', '-')}  \u2b50{repo.get('stars', 0)} {stars_text}  {repo.get('full_name', '')}  {language}\n{brief}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, repo.get("full_name"))
        self.trending_list.addItem(item)
        idx += 1
    self._trending_batch_index = idx
    if idx < len(queue):
        QTimer.singleShot(16, self._render_trending_batch)
    else:
        # 本批全部渲染完成：同步已渲染计数，并自动触发这批项目的翻译
        self._trending_rendered = len(queue)
        self._translate_visible_batch(queue, self.trending_list, 0)


MainWindow._render_discover_items = _render_discover_items_batched
MainWindow._render_discover_batch = _render_discover_batch
MainWindow._render_trending_items = _render_trending_items_batched
MainWindow._render_trending_batch = _render_trending_batch

# ---------------------------------------------------------------------------
# 3. 系统托盘
# ---------------------------------------------------------------------------


def _init_tray(self):
    """初始化系统托盘。"""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        self._tray_icon = None
        return
    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.ico")
    icon = QIcon(icon_path) if os.path.exists(icon_path) else self.windowIcon()
    self._tray_icon = QSystemTrayIcon(icon, self)
    self._tray_icon.setToolTip("GitHub \u5f00\u6e90\u9879\u76ee\u6d4f\u89c8\u5668")
    menu = QMenu()
    show_action = QAction("\u663e\u793a\u4e3b\u7a97\u53e3", self)
    show_action.triggered.connect(lambda: (self.showNormal(), self.activateWindow()))
    menu.addAction(show_action)
    quit_action = QAction("\u9000\u51fa", self)
    quit_action.triggered.connect(lambda: (self._tray_icon.hide() if self._tray_icon else None, self.close()))
    menu.addAction(quit_action)
    self._tray_icon.setContextMenu(menu)
    self._tray_icon.activated.connect(
        lambda reason: (self.showNormal(), self.activateWindow())
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick
        else None
    )
    self._tray_icon.show()


def _init_ui_with_tray(self):
    _ORIGINAL_INIT_UI(self)
    _init_tray(self)


def _close_event_with_tray(self, event):
    if getattr(self, "_tray_icon", None):
        self._tray_icon.hide()
    # 安全关闭：先取消队列翻译，再等待两个线程池中运行中的 Worker 结束，
    # 最后清空主线程持有的 Worker 引用。否则退出时运行中的 QRunnable 被
    # Python GC 回收（C++ 对象在线程仍在运行时被删除）会导致 Qt fail-fast 闪退。
    self._batch_cancel = True
    self._translate_queue.clear()
    try:
        self._translate_anim_timer.stop()
    except Exception:
        pass
    try:
        self.translate_pool.clear()
        self.thread_pool.clear()
    except Exception:
        pass
    try:
        self.translate_pool.waitForDone()
        self.thread_pool.waitForDone()
    except Exception:
        pass
    self._active_workers.clear()
    _ORIGINAL_CLOSE_EVENT(self, event)


MainWindow._init_tray = _init_tray
MainWindow._init_ui = _init_ui_with_tray
MainWindow.closeEvent = _close_event_with_tray

# ---------------------------------------------------------------------------
# 4. ZIP 下载
# ---------------------------------------------------------------------------


def _download_current_zip(self):
    """下载项目 ZIP 包。"""
    repo = self._current_repo
    if not repo:
        return
    full_name = repo.get("full_name", "")
    if not full_name:
        return
    save_path, _ = QFileDialog.getSaveFileName(
        self, "\u4e0b\u8f7d\u9879\u76ee",
        f"{full_name.replace('/', '_')}.zip",
        "ZIP \u6587\u4ef6 (*.zip)",
    )
    if not save_path:
        return
    self.download_btn.setEnabled(False)
    self.status_label.setText(f"\u6b63\u5728\u4e0b\u8f7d {full_name}...")

    def task():
        default_branch = repo.get("default_branch", "main")
        zip_url = f"https://github.com/{full_name}/archive/refs/heads/{default_branch}.zip"
        mirror_url = self.service.http.get_mirror_url(zip_url)
        resp = self.service.http.get(mirror_url, timeout=60)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return save_path

    def on_done(path):
        self.download_btn.setEnabled(True)
        self.status_label.setText(f"\u5df2\u4e0b\u8f7d: {path}")
        self.service.history.add({
            "full_name": full_name,
            "url": repo.get("html_url", ""),
            "path": path,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self.service.save_config()

    def on_error(msg):
        self.download_btn.setEnabled(True)
        self.status_label.setText(f"\u4e0b\u8f7d\u5931\u8d25: {msg}")

    self._run_in_thread(task, on_done, on_error)


MainWindow._download_current = _download_current_zip
