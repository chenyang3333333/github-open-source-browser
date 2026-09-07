# -*- coding: utf-8 -*-
"""GitHub 服务：API 调用、热榜抓取、收藏管理、下载历史。"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from github_open_source_browser.config import (
    DEFAULT_CONFIG,
    load_config_file,
    normalize_config,
    save_config_file,
)
from github_open_source_browser.database import Database
from github_open_source_browser.services.http_client import HttpClient
from github_open_source_browser.translator import (
    local_translate,
    protect_glossary_terms,
    protect_markdown_blocks,
    restore_glossary_terms,
    restore_markdown_blocks,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 翻译缓存
# ---------------------------------------------------------------------------


class TranslationCache:
    """基于 SQLite 的翻译缓存。"""

    def __init__(self, db: Database):
        self._db = db
        self._lock = threading.Lock()

    def get(self, key: str, source: str) -> str | None:
        with self._lock:
            try:
                # 只传 key，使用默认 30 天 TTL；source（语言标识）不是 ttl_seconds，
                # 误传会导致条件变为 updated_at >= now 而永远查不到缓存
                return self._db.get_translation(key)
            except Exception:
                return None

    def set(self, key: str, value: str) -> None:
        with self._lock:
            try:
                self._db.set_translation(key, value)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 收藏管理
# ---------------------------------------------------------------------------


class FavoritesStore:
    """管理收藏列表，基于配置文件持久化。"""

    def __init__(self, config: dict):
        self._config = config

    def all(self) -> list[dict]:
        return list(self._config.get("favorites", []) or [])

    def add(self, repo: dict) -> bool:
        favorites = self._config.setdefault("favorites", [])
        full_name = repo.get("full_name", "")
        if any(f.get("full_name") == full_name for f in favorites):
            return False
        favorites.insert(0, {
            "full_name": full_name,
            "html_url": repo.get("html_url", ""),
            "description": repo.get("description", ""),
            "language": repo.get("language", ""),
            "stars": repo.get("stars", 0),
        })
        return True

    def remove(self, full_name: str) -> bool:
        favorites = self._config.get("favorites", [])
        before = len(favorites)
        self._config["favorites"] = [f for f in favorites if f.get("full_name") != full_name]
        return len(self._config["favorites"]) < before

    def contains(self, full_name: str) -> bool:
        return any(f.get("full_name") == full_name for f in self.all())

    def count(self) -> int:
        return len(self.all())


# ---------------------------------------------------------------------------
# 下载历史
# ---------------------------------------------------------------------------


class DownloadHistoryStore:
    """管理下载历史记录。"""

    def __init__(self, config: dict):
        self._config = config

    def all(self) -> list[dict]:
        return list(self._config.get("download_history", []) or [])

    def add(self, entry: dict) -> None:
        history = self._config.setdefault("download_history", [])
        history.insert(0, entry)
        # 限制历史记录数量
        if len(history) > 500:
            self._config["download_history"] = history[:500]

    def clear(self) -> None:
        self._config["download_history"] = []


# ---------------------------------------------------------------------------
# 排行历史
# ---------------------------------------------------------------------------


class RankingHistoryStore:
    """记录热榜排名变化。"""

    def __init__(self, db: Database):
        self._db = db

    def get_previous_rankings(self, since: str) -> dict[str, int]:
        try:
            return self._db.get_ranking_history(since)
        except Exception:
            return {}

    def save_rankings(self, since: str, rankings: dict[str, int]) -> None:
        try:
            self._db.save_ranking_history(since, rankings)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 分类系统
# ---------------------------------------------------------------------------

CATEGORY_LANGUAGES = {
    "ai": {"python", "jupyter notebook"},
    "frontend": {"javascript", "typescript", "html", "css"},
    "backend": {"go", "rust", "java", "c#"},
    "mobile": {"swift", "kotlin", "dart"},
    "devops": {"shell", "dockerfile"},
    "database": {"sql", "plsql"},
    "security": set(),
    "game": {"c#", "gdscript", "lua"},
    "tool": {"shell", "python", "go", "rust"},
}

CATEGORY_KEYWORDS = {
    "ai": {
        "artificial intelligence", "generative ai", "genai", "machine learning",
        "deep learning", "large language model", "llm", "gpt", "transformer",
        "neural network", "computer vision", "natural language processing", "nlp",
        "pytorch", "tensorflow", "huggingface", "llama", "diffusion",
        "stable diffusion", "rag", "retrieval augmented generation", "embedding",
        "multimodal", "openai", "ollama", "ai agent", "agent framework",
        "speech recognition", "optical character recognition", "ocr",
    },
    "frontend": {"react", "vue", "angular", "svelte", "tailwind", "frontend", "front-end"},
    "backend": {"api", "server", "rest", "graphql", "microservice", "backend", "back-end"},
    "mobile": {"android", "ios", "flutter", "react native", "react-native"},
    "devops": {"docker", "kubernetes", "ci/cd", "deploy", "terraform", "devops"},
    "database": {"database", "sql", "postgres", "mysql", "mongo", "redis", "mongodb"},
    "security": {"security", "vulnerability", "cve", "firewall", "encryption", "cybersecurity"},
    "game": {"game", "unity", "unreal", "godot", "game engine"},
    "tool": {"cli", "terminal", "tool", "utility", "scraper", "downloader", "command line"},
}

CATEGORY_TOPICS = {
    "ai": {
        "ai", "artificial-intelligence", "machine-learning", "deep-learning",
        "large-language-model", "llm", "generative-ai", "computer-vision",
        "natural-language-processing", "nlp", "neural-network", "pytorch",
        "tensorflow", "huggingface", "transformers", "llama", "diffusion",
        "stable-diffusion", "retrieval-augmented-generation", "rag", "embedding",
        "multimodal", "openai", "ollama", "ai-agent", "agents", "speech-recognition", "ocr",
    },
    "frontend": {"frontend", "front-end", "web", "react", "vue", "angular", "svelte", "tailwind"},
    "backend": {"backend", "back-end", "api", "server", "rest-api", "graphql", "microservices"},
    "mobile": {"android", "ios", "flutter", "react-native", "swift", "kotlin"},
    "devops": {"devops", "docker", "kubernetes", "ci-cd", "deployment", "terraform"},
    "database": {"database", "sql", "postgresql", "mysql", "mongodb", "redis"},
    "security": {"security", "cybersecurity", "vulnerability", "cve", "encryption", "firewall"},
    "game": {"game", "game-engine", "unity", "unreal-engine", "godot"},
    "tool": {"cli", "command-line", "terminal", "utility", "scraper", "downloader"},
}


def filter_repos_by_category(repos: list[dict], category: str) -> list[dict]:
    """根据分类过滤项目列表。"""
    if not category:
        return list(repos or [])
    category_key = str(category).strip().casefold()
    target_languages = CATEGORY_LANGUAGES.get(category_key, set())
    target_keywords = CATEGORY_KEYWORDS.get(category_key, set())
    target_topics = CATEGORY_TOPICS.get(category_key, set())
    filtered = []
    for repo in repos or []:
        if not isinstance(repo, dict):
            continue
        language = str(repo.get("language") or "").strip().casefold()
        searchable = " ".join(
            str(repo.get(field) or "")
            for field in ("full_name", "name", "description", "description_zh", "tags")
        ).casefold()
        topics = {str(t or "").strip().casefold().replace("_", "-").replace(" ", "-") for t in (repo.get("topics") or [])}
        if (
            language in target_languages
            or bool(topics & target_topics)
            or any(keyword in searchable for keyword in target_keywords)
        ):
            filtered.append(repo)
    return filtered


# ---------------------------------------------------------------------------
# 主题标签规范化
# ---------------------------------------------------------------------------


def normalize_topics(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = re.split(r"[,;\n]", value)
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]
    result = []
    seen = set()
    for item in values:
        topic = str(item or "").strip()
        if not topic:
            continue
        key = topic.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(topic)
    return result


# ---------------------------------------------------------------------------
# GitHub 服务
# ---------------------------------------------------------------------------

REPOSITORY_PAGE_SIZE = 50
TRENDING_PAGE_SIZE = 50


class GitHubService:
    """GitHub API 服务：搜索、热榜、详情、翻译。"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = load_config_file(config_path)
        self.http = HttpClient(self.config)
        self.db = Database(config_path.replace(".json", ".db"))
        self.cache = TranslationCache(self.db)
        self.favorites = FavoritesStore(self.config)
        self.history = DownloadHistoryStore(self.config)
        self.ranking = RankingHistoryStore(self.db)
        self._readme_image_cache: dict[str, str] = {}
        self._readme_image_cache_lock = threading.Lock()

    def get_oauth_url(self) -> str:
        client_id = str(self.config.get("oauth_client_id") or "").strip()
        if not client_id:
            return ""
        return f"https://github.com/login/oauth/authorize?client_id={client_id}&scope=repo,read:user"

    def exchange_oauth_code(self, code: str) -> bool:
        client_id = str(self.config.get("oauth_client_id") or "").strip()
        if not client_id:
            return False
        try:
            resp = self.http.post(
                "https://github.com/login/oauth/access_token",
                json={"client_id": client_id, "code": code},
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            token = data.get("access_token")
            if token:
                self.config["github_token"] = token
                self.save_config()
                self.http.update_config(self.config)
                return True
        except Exception:
            pass
        return False

    def save_config(self) -> None:
        save_config_file(self.config_path, self.config)

    # ------------------------------------------------------------------
    # 搜索项目
    # ------------------------------------------------------------------

    def search_repos(
        self,
        keyword: str = "",
        page: int = 1,
        per_page: int = REPOSITORY_PAGE_SIZE,
        languages: list[str] | None = None,
        sort: str | None = None,
    ) -> list[dict]:
        """通过 GitHub Search API 搜索项目。

        languages: 分类语言列表，非空时用 `language:A OR language:B` 组合查询，
                   并忽略 config 中的全局语言（顶部语言下拉）。
        sort:      排序方式，覆盖 config 中的 sort（如 "stars"）。
        """
        query_parts = [self.config.get("query", "stars:>500")]
        if keyword:
            query_parts.insert(0, keyword)
        if languages:
            # 分类语言 OR 组合（空格转连字符，如 jupyter notebook -> jupyter-notebook）
            lang_query = " OR ".join(f"language:{str(lang).strip().replace(' ', '-')}" for lang in languages)
            query_parts.append(f"({lang_query})")
        else:
            lang = self.config.get("language", "")
            if lang:
                query_parts.append(f"language:{lang}")
        query = " ".join(query_parts)
        sort = sort or self.config.get("sort", "updated")
        params = {
            "q": query,
            "sort": sort,
            "order": "desc",
            "per_page": min(int(per_page), 100),
            "page": max(1, int(page)),
        }
        resp = self.http.get("https://api.github.com/search/repositories", params=params)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        repos = []
        for item in items:
            if not isinstance(item, dict):
                continue
            repos.append(self._parse_repo(item))
        return repos

    # ------------------------------------------------------------------
    # 热榜
    # ------------------------------------------------------------------

    def scrape_trending(self, since: str = "daily", language: str = "", page: int = 1, per_page: int = TRENDING_PAGE_SIZE) -> list[dict]:
        """从 GitHub Trending 抓取热榜项目。"""
        url = "https://github.com/trending"
        if language:
            url += f"/{language}"
        url += f"?since={since}"
        resp = self.http.get(url)
        resp.raise_for_status()
        return self._parse_trending_html(resp.text, since)

    def _parse_trending_html(self, html: str, since: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        repos = []
        for article in soup.select("article.Box-row"):
            try:
                repo = self._parse_trending_article(article, since)
                if repo:
                    repos.append(repo)
            except Exception:
                continue
        return repos

    def _parse_trending_article(self, article, since: str) -> dict | None:
        # 项目名
        h2 = article.select_one("h2 a")
        if not h2:
            return None
        href = h2.get("href", "").strip("/")
        if not href:
            return None
        full_name = href
        # 描述
        desc_elem = article.select_one("p")
        description = desc_elem.get_text(strip=True) if desc_elem else ""
        # 语言
        lang_elem = article.select_one("[itemprop='programmingLanguage']")
        language = lang_elem.get_text(strip=True) if lang_elem else ""
        # Stars
        stars = 0
        star_elems = article.select("a.Link--muted")
        for elem in star_elems:
            href_val = elem.get("href", "")
            if "/stargazers" in href_val:
                text = elem.get_text(strip=True).replace(",", "")
                try:
                    stars = int(text)
                except ValueError:
                    pass
                break
        # 本周新增 Stars
        period_stars = 0
        period_elem = article.select_one("span.d-inline-block.float-sm-right")
        if period_elem:
            text = period_elem.get_text(strip=True).replace(",", "")
            m = re.search(r"(\d+)", text)
            if m:
                period_stars = int(m.group(1))
        # Topics (从链接中提取)
        topics = []
        topic_elems = article.select("a.topic-tag")
        for t in topic_elems:
            topic_text = t.get_text(strip=True)
            if topic_text:
                topics.append(topic_text)
        return {
            "full_name": full_name,
            "html_url": f"https://github.com/{full_name}",
            "description": description,
            "language": language,
            "stars": stars,
            "period_stars": period_stars,
            "topics": topics,
            "trending_since": since,
        }

    # ------------------------------------------------------------------
    # 项目详情
    # ------------------------------------------------------------------

    def get_repo_detail(self, full_name: str) -> dict | None:
        """获取项目详细信息。"""
        url = f"https://api.github.com/repos/{full_name}"
        try:
            resp = self.http.get(url)
            resp.raise_for_status()
            return self._parse_repo(resp.json())
        except Exception as e:
            logger.warning("获取项目详情失败 %s: %s", full_name, e)
            return None

    def get_readme(self, full_name: str) -> str:
        """获取项目 README 内容。"""
        url = f"https://api.github.com/repos/{full_name}/readme"
        resp = self.http.get(url, headers={"Accept": "application/vnd.github.v3.raw"})
        resp.raise_for_status()
        return resp.text

    def get_release(self, full_name: str) -> dict | None:
        """获取最新 release 信息。"""
        url = f"https://api.github.com/repos/{full_name}/releases/latest"
        resp = self.http.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return {
            "tag_name": data.get("tag_name", ""),
            "name": data.get("name", ""),
            "body": data.get("body", ""),
            "published_at": data.get("published_at", ""),
            "html_url": data.get("html_url", ""),
        }

    # ------------------------------------------------------------------
    # 翻译
    # ------------------------------------------------------------------

    def translate_text(self, text: str, source: str = "en", target: str = "zh-CN", deadline: float = 0) -> str:
        """翻译文本，优先使用缓存，然后尝试供应商，最后回退本地。"""
        if not text or not text.strip():
            return text
        # 检查缓存
        if self.config.get("translation_cache_enabled", True):
            cached = self.cache.get(text, target)
            if cached:
                return cached
        # 调用翻译服务（复用 http 会话连接）
        from github_open_source_browser.services.translation_service import translate_text as _do_translate
        translated, _used = _do_translate(text, source, target, self.config, deadline, session=self.http.session)
        if translated and translated != text:
            if self.config.get("translation_cache_enabled", True):
                self.cache.set(text, translated)
            return translated
        return text

    def translate_description(self, text: str, target: str = "zh-CN", deadline: float = 0) -> str:
        """翻译项目简介。"""
        return self.translate_text(text, "en", target, deadline)

    def translate_readme(self, markdown_text: str, target: str = "zh-CN", deadline: float = 0) -> str:
        """翻译 README 内容，保留 Markdown 结构，优先使用缓存。"""
        if not markdown_text or not markdown_text.strip():
            return markdown_text
        # 检查缓存
        if self.config.get("translation_cache_enabled", True):
            cached = self.cache.get(markdown_text, target)
            if cached:
                return cached
        from github_open_source_browser.services.translation_service import translate_readme_markdown
        translated = translate_readme_markdown(markdown_text, "en", target, self.config, deadline, session=self.http.session)
        if translated and translated != markdown_text:
            if self.config.get("translation_cache_enabled", True):
                self.cache.set(markdown_text, translated)
            return translated
        return markdown_text

    # ------------------------------------------------------------------
    # 图片下载
    # ------------------------------------------------------------------

    def download_image_as_base64(self, url: str, timeout: float = 3.0) -> str:
        """下载图片并返回 base64 编码。"""
        import base64
        with self._readme_image_cache_lock:
            if url in self._readme_image_cache:
                return self._readme_image_cache[url]
        try:
            mirror_url = self.http.get_mirror_url(url)
            resp = self.http.get(mirror_url, timeout=timeout)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "image/png")
            b64 = base64.b64encode(resp.content).decode("ascii")
            result = f"data:{content_type};base64,{b64}"
            with self._readme_image_cache_lock:
                self._readme_image_cache[url] = result
            return result
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _parse_repo(self, item: dict) -> dict:
        """将 GitHub API 返回的项目数据规范化。"""
        return {
            "full_name": item.get("full_name", ""),
            "name": item.get("name", ""),
            "html_url": item.get("html_url", ""),
            "description": item.get("description") or "",
            "language": item.get("language") or "",
            "stars": item.get("stargazers_count", 0),
            "forks": item.get("forks_count", 0),
            "open_issues": item.get("open_issues_count", 0),
            "watchers": item.get("watchers_count", 0),
            "topics": normalize_topics(item.get("topics")),
            "license": (item.get("license") or {}).get("spdx_id", ""),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
            "pushed_at": item.get("pushed_at", ""),
            "default_branch": item.get("default_branch", "main"),
            "owner_avatar": (item.get("owner") or {}).get("avatar_url", ""),
            "owner_login": (item.get("owner") or {}).get("login", ""),
        }
