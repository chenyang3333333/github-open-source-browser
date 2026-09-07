# -*- coding: utf-8 -*-
"""配置管理：默认值、规范化、原子保存。"""
from __future__ import annotations
from github_open_source_browser.i18n import tr

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "github_token": "",
    "query": "stars:>500",
    "sort": "updated",
    "language": "",
    "mirrors": [
        "https://ghfast.top/",
        "https://gh.ddlc.top/",
        "https://ghproxy.net/",
        "https://ghproxy.homeboyc.cn/",
        "https://gh-proxy.com/",
        "https://github.tmby.shop/",
    ],
    "mirror_mode": "auto",
    "mirror_retest_minutes": 30,
    "interval_minutes": 30,
    "use_mirror_for_download": True,
    "items_per_page": 100,
    "favorites": [],
    "download_history": [],
    "proxy": "",
    "ssl_verify": True,
    "autostart": False,
    "minimize_to_tray": True,
    "release_notify": True,
    "oauth_client_id": "",
    "tencent_secret_id": "",
    "tencent_secret_key": "",
    "dark_mode": False,
    "trending_since": "daily",
    "trending_language": "",
    "target_language": "zh-CN",
    "translation_provider": "auto",
    "translation_api_url": "",
    "translation_api_key": "",
    "translation_model": "",
    "translation_cache_enabled": True,
    "translation_timeout_seconds": 12.0,
    "translation_retry_count": 1,
    "readme_image_enabled": True,
    "readme_image_timeout": 2.5,
    "startup_auto_load": True,
    "proxy_mode": "none",
    "auto_translate_desc": True,
    "auto_translate_readme": False,
    "request_interval_ms": 200,
    "concurrent_limit": 3,
    "fallback_chain": ["tencent", "microsoft", "openai_compatible"],
}

# 增强配置的默认值（与旧版兼容）
_ENHANCED_DEFAULT_CONFIG = copy.deepcopy(DEFAULT_CONFIG)

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _text_value(value: Any) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def _config_float(value: Any, default: float, min_val: float, max_val: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(min_val, min(max_val, v))


def _config_int(value: Any, default: int, min_val: int, max_val: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_val, min(max_val, v))


def _config_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return bool(value)


# ---------------------------------------------------------------------------
# 翻译供应商规范化
# ---------------------------------------------------------------------------

_TRANSLATION_PROVIDER_OPTIONS = (
    (tr("provider.auto"), "auto"),
    (tr("provider.tencent"), "tencent"),
    (tr("provider.microsoft"), "microsoft"),
    (tr("provider.deepl"), "deepl"),
    (tr("provider.google"), "google"),
    (tr("provider.openai"), "openai_compatible"),
    (tr("provider.claude"), "claude"),
    (tr("provider.gemini"), "gemini"),
    (tr("provider.mimo"), "mimo"),
    (tr("provider.local"), "local"),
)
_TRANSLATION_PROVIDER_VALUES = {value for _, value in _TRANSLATION_PROVIDER_OPTIONS}


def normalize_translation_provider(value: Any) -> str:
    raw = _text_value(value).casefold()
    aliases = {
        "": "auto",
        "自动": "auto",
        "自动选择": "auto",
        "tencent": "tencent",
        "腾讯": "tencent",
        "腾讯云": "tencent",
        "tencent_cloud": "tencent",
        "microsoft": "microsoft",
        "微软": "microsoft",
        "微软翻译": "microsoft",
        "edge": "microsoft",
        "edge微软": "microsoft",
        "deepl": "deepl",
        "google": "google",
        "google_cloud": "google",
        "openai_compatible": "openai_compatible",
        "openai": "openai_compatible",
        "deepseek": "openai_compatible",
        "qwen": "openai_compatible",
        "claude": "claude",
        "anthropic": "claude",
        "gemini": "gemini",
        "google_ai": "gemini",
        "mimo": "mimo",
        "xiaomi": "mimo",
        "local": "local",
        "本地": "local",
    }
    return aliases.get(raw, "auto")


# ---------------------------------------------------------------------------
# 目标语言
# ---------------------------------------------------------------------------

TARGET_LANGUAGE_DISPLAY_OPTIONS = (
    (tr('lang.zh_cn'), 'zh-CN'),
    (tr('lang.zh_tw'), 'zh-TW'),
    (tr('lang.en'), 'en'),
    (tr('lang.ja'), 'ja'),
    (tr('lang.ko'), 'ko'),
    (tr('lang.fr'), 'fr'),
    (tr('lang.de'), 'de'),
    (tr('lang.es'), 'es'),
)
TARGET_LANGUAGE_VALUES = {value for _, value in TARGET_LANGUAGE_DISPLAY_OPTIONS}


def normalize_target_language(value: Any) -> str:
    raw = _text_value(value)
    if not raw:
        return 'zh-CN'
    lowered = raw.casefold().replace('_', '-')
    aliases = {
        '中文': 'zh-CN', tr('lang.zh_cn'): 'zh-CN',
        '繁体中文': 'zh-TW', tr('lang.zh_tw'): 'zh-TW',
        'english': 'en', '英语': 'en',
        tr('lang.ja'): 'ja', '日语': 'ja',
        tr('lang.ko'): 'ko', '韩语': 'ko',
        'français': 'fr', '法语': 'fr',
        'deutsch': 'de', '德语': 'de',
        'español': 'es', '西班牙语': 'es',
    }
    if lowered in aliases:
        return aliases[lowered]
    if lowered.startswith('zh-tw'):
        return 'zh-TW'
    if lowered.startswith('zh'):
        return 'zh-CN'
    for prefix, normalized in (('en', 'en'), ('ja', 'ja'), ('ko', 'ko'), ('fr', 'fr'), ('de', 'de'), ('es', 'es')):
        if lowered.startswith(prefix):
            return normalized
    return raw


# ---------------------------------------------------------------------------
# 代理规范化
# ---------------------------------------------------------------------------

def normalize_proxy_mode(raw: Any, proxy_value: Any = "") -> str:
    if raw is None:
        raw = ""
    key = str(raw).strip().casefold()
    aliases = {
        "system": "system", "跟随系统": "system", "系统代理": "system",
        "none": "none", tr("settings.proxy_none"): "none", "无": "none", "off": "none",
        "custom": "custom", "manual": "custom", "自定义": "custom", tr("settings.proxy_custom"): "custom",
    }
    return aliases.get(key, "custom" if str(proxy_value or "").strip() else "none")


def normalize_proxy_value(value: Any) -> str:
    from urllib.parse import urlparse
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "http://" + raw
    try:
        parsed = urlparse(raw)
    except Exception:
        return ""
    if parsed.scheme.casefold() not in {"http", "https", "socks5", "socks5h"}:
        return ""
    if not parsed.hostname:
        return ""
    return raw


# ---------------------------------------------------------------------------
# 完整配置规范化
# ---------------------------------------------------------------------------

def normalize_config(config: dict) -> dict:
    """补齐和校验所有配置字段，保持旧配置不丢失。"""
    if not isinstance(config, dict):
        config = {}
    for key, value in DEFAULT_CONFIG.items():
        config.setdefault(key, copy.deepcopy(value))
    config["translation_provider"] = normalize_translation_provider(config.get("translation_provider"))
    config["target_language"] = normalize_target_language(config.get("target_language", "zh-CN"))
    if config["target_language"] not in TARGET_LANGUAGE_VALUES:
        config["target_language"] = "zh-CN"
    config["translation_timeout_seconds"] = _config_float(config.get("translation_timeout_seconds"), 12.0, 1.0, 60.0)
    config["translation_retry_count"] = _config_int(config.get("translation_retry_count"), 1, 0, 3)
    config["readme_image_timeout"] = _config_float(config.get("readme_image_timeout"), 2.5, 0.75, 10.0)
    config["translation_cache_enabled"] = _config_bool(config.get("translation_cache_enabled"), True)
    config["readme_image_enabled"] = _config_bool(config.get("readme_image_enabled"), True)
    config["startup_auto_load"] = _config_bool(config.get("startup_auto_load"), True)
    config["proxy"] = normalize_proxy_value(config.get("proxy"))
    config["proxy_mode"] = normalize_proxy_mode(config.get("proxy_mode"), config.get("proxy"))
    if config["proxy_mode"] == "custom" and not config.get("proxy"):
        config["proxy_mode"] = "none"
    return config


# ---------------------------------------------------------------------------
# 配置文件读写
# ---------------------------------------------------------------------------


def load_config_file(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return unprotect_sensitive_config(normalize_config(data))
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return normalize_config({})


# ---------------------------------------------------------------------------
# DPAPI 敏感字段保护
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = {"github_token", "translation_api_key", "tencent_secret_id", "tencent_secret_key", "oauth_client_id"}

def _dpapi_available() -> bool:
    import sys
    return sys.platform == "win32"

def dpapi_protect(value: str) -> str:
    if not value or not _dpapi_available():
        return value
    try:
        import ctypes, ctypes.wintypes, base64
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
        val = value.encode("utf-8")
        blob_in = DATA_BLOB(len(val), ctypes.create_string_buffer(val, len(val)))
        blob_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return "dpapi:v1:" + base64.b64encode(data).decode("ascii")
    except Exception:
        pass
    return value

def dpapi_unprotect(value: str) -> str:
    if not value or not value.startswith("dpapi:v1:") or not _dpapi_available():
        return value
    try:
        import ctypes, ctypes.wintypes, base64
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
        raw = base64.b64decode(value[len("dpapi:v1:"):])
        blob_in = DATA_BLOB(len(raw), ctypes.create_string_buffer(raw, len(raw)))
        blob_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return data.decode("utf-8")
    except Exception:
        pass
    return value

def protect_sensitive_config(config: dict) -> dict:
    for key in _SENSITIVE_KEYS:
        val = config.get(key)
        if isinstance(val, str) and val and not val.startswith("dpapi:v1:"):
            config[key] = dpapi_protect(val)
    return config

def unprotect_sensitive_config(config: dict) -> dict:
    for key in _SENSITIVE_KEYS:
        val = config.get(key)
        if isinstance(val, str) and val.startswith("dpapi:v1:"):
            config[key] = dpapi_unprotect(val)
    return config


def save_config_file(path: str | Path, config: dict) -> bool:
    """原子保存配置：先写临时文件再替换，失败时保留旧配置。

    在副本上做规范化与敏感字段加密，避免原地修改调用方持有的配置字典
    （HttpClient 持有同一引用，若被加密成 dpapi:v1: 会导致后续 API 401）。
    """
    target = Path(path)
    protected = protect_sensitive_config(copy.deepcopy(normalize_config(config)))
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # 写临时文件
        fd, tmp_path = tempfile.mkstemp(
            dir=str(target.parent),
            prefix=".config_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(protected, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            os.close(fd)
            raise
        # 备份旧文件
        if target.exists():
            backup = target.with_suffix(".bak")
            try:
                import shutil
                shutil.copy2(str(target), str(backup))
            except Exception:
                pass
        # 替换
        os.replace(tmp_path, str(target))
        return True
    except Exception:
        # 清理临时文件
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass
        return False
