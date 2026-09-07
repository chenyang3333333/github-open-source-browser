# -*- coding: utf-8 -*-
"""HTTP 客户端：统一代理、SSL、超时和请求管理。"""
from __future__ import annotations

import threading
import time
from typing import Any

import requests

from github_open_source_browser.config import (
    normalize_config,
    normalize_proxy_mode,
    normalize_proxy_value,
)


class HttpClient:
    """统一的 HTTP 客户端，管理代理、SSL、镜像和请求状态。"""

    def __init__(self, config: dict | None = None):
        self._config = normalize_config(config if isinstance(config, dict) else {})
        self._session = requests.Session()
        self._lock = threading.Lock()
        self._mirror_index = 0
        self._mirror_latency: dict[str, float] = {}
        self._active_request_count = 0
        self._apply_config()

    def update_config(self, config: dict) -> None:
        with self._lock:
            self._config = normalize_config(config)
            self._apply_config()

    def _apply_config(self) -> None:
        config = self._config
        mode = config.get("proxy_mode", "none")
        try:
            self._session.trust_env = mode == "system"
        except Exception:
            pass
        try:
            self._session.verify = config.get("ssl_verify", True)
        except Exception:
            pass
        # 清除旧代理
        self._session.proxies = {}
        if mode == "custom":
            proxy = normalize_proxy_value(config.get("proxy"))
            if proxy:
                self._session.proxies = {"http": proxy, "https": proxy}
        # 请求头
        token = str(config.get("github_token") or "").strip()
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Open-Source-Browser/2.0",
        }
        if token:
            headers["Authorization"] = f"token {token}"
        self._session.headers.update(headers)

    @property
    def config(self) -> dict:
        return self._config

    @property
    def session(self) -> requests.Session:
        return self._session

    def get(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", kwargs.pop("_timeout", 30))
        with self._lock:
            self._active_request_count += 1
        try:
            return self._session.get(url, **kwargs)
        finally:
            with self._lock:
                self._active_request_count -= 1

    def post(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", kwargs.pop("_timeout", 30))
        with self._lock:
            self._active_request_count += 1
        try:
            return self._session.post(url, **kwargs)
        finally:
            with self._lock:
                self._active_request_count -= 1

    def get_mirror_url(self, original_url: str) -> str:
        """根据镜像配置返回可能的镜像地址。"""
        config = self._config
        mode = config.get("mirror_mode", "auto")
        mirrors = config.get("mirrors", [])
        if mode == "none" or not mirrors:
            return original_url
        if mode == "auto":
            # 选择延迟最低的镜像
            best = None
            best_latency = float("inf")
            for mirror in mirrors:
                latency = self._mirror_latency.get(mirror, float("inf"))
                if latency < best_latency:
                    best_latency = latency
                    best = mirror
            if best:
                return self._apply_mirror(original_url, best)
            # 没有测速数据时按顺序选择
            if mirrors:
                idx = self._mirror_index % len(mirrors)
                return self._apply_mirror(original_url, mirrors[idx])
        return original_url

    def _apply_mirror(self, url: str, mirror: str) -> str:
        """将 GitHub 地址替换为镜像地址。"""
        if not mirror.endswith("/"):
            mirror += "/"
        if url.startswith("https://github.com/"):
            return mirror + url
        if url.startswith("https://raw.githubusercontent.com/"):
            return mirror + url
        return url

    def test_mirror_latency(self, mirror: str, timeout: float = 5.0) -> float | None:
        """测试镜像延迟，返回秒数或 None。"""
        test_url = mirror.rstrip("/") + "/https://github.com"
        try:
            start = time.monotonic()
            resp = self._session.get(test_url, timeout=timeout, allow_redirects=False)
            elapsed = time.monotonic() - start
            if resp.status_code in (200, 301, 302):
                self._mirror_latency[mirror] = elapsed
                return elapsed
        except Exception:
            pass
        return None

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass
