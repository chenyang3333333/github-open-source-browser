# -*- coding: utf-8 -*-
"""国际化模块：语言资源加载与 tr() 翻译接口。"""
from __future__ import annotations
import json
import locale
import os
from pathlib import Path
from typing import Any

_LANG_DIR = Path(__file__).parent
_current_lang = "zh_CN"
_translations: dict[str, str] = {}
_fallback: dict[str, str] = {}
_listeners: list = []
_initialized = False

def _load_lang(lang: str) -> dict[str, str]:
    path = _LANG_DIR / f"{lang}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _detect_system_lang() -> str:
    try:
        sys_lang = locale.getdefaultlocale()[0] or ""
        sys_lang = sys_lang.replace("-", "_")
        if sys_lang.startswith("zh_CN") or sys_lang.startswith("zh_Hans"):
            return "zh_CN"
        if sys_lang.startswith("zh"):
            return "zh_TW"
        if sys_lang.startswith("en"):
            return "en_US"
        if sys_lang.startswith("ja"):
            return "ja_JP"
        if sys_lang.startswith("ko"):
            return "ko_KR"
        if sys_lang.startswith("fr"):
            return "fr_FR"
        if sys_lang.startswith("de"):
            return "de_DE"
        if sys_lang.startswith("es"):
            return "es_ES"
    except Exception:
        pass
    return "zh_CN"

def init(lang: str | None = None) -> None:
    global _current_lang, _translations, _fallback, _initialized
    if lang:
        _current_lang = lang
    else:
        _current_lang = _detect_system_lang()
    _fallback = _load_lang("zh_CN")
    _translations = _load_lang(_current_lang)
    if _current_lang != "zh_CN":
        merged = dict(_fallback)
        merged.update(_translations)
        _translations = merged
    _initialized = True

def set_language(lang: str) -> None:
    global _current_lang, _translations
    _current_lang = lang
    if lang == "zh_CN":
        _translations = dict(_fallback)
    else:
        loaded = _load_lang(lang)
        merged = dict(_fallback)
        merged.update(loaded)
        _translations = merged
    for listener in _listeners:
        try:
            listener()
        except Exception:
            pass

def get_language() -> str:
    return _current_lang

def tr(key: str, **kwargs: Any) -> str:
    if not _initialized:
        init()
    text = _translations.get(key, _fallback.get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text

def on_language_changed(callback) -> None:
    if callback not in _listeners:
        _listeners.append(callback)

def remove_listener(callback) -> None:
    try:
        _listeners.remove(callback)
    except ValueError:
        pass

AVAILABLE_LANGUAGES = [
    ("简体中文", "zh_CN"),
    ("English", "en_US"),
    ("繁體中文", "zh_TW"),
    ("日本語", "ja_JP"),
    ("한국어", "ko_KR"),
    ("Français", "fr_FR"),
    ("Deutsch", "de_DE"),
    ("Español", "es_ES"),
]
