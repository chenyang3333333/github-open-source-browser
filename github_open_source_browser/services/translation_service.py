# -*- coding: utf-8 -*-
"""翻译服务：按供应商分发翻译文本和 README，失败时沿回退链降级。

仅保留本地(local)、谷歌(google)、Edge 微软(microsoft)三类免费服务。
已移除大模型(LLM)与腾讯云翻译。
"""
from __future__ import annotations

import json
import logging
import re
import socket

import requests

from github_open_source_browser.translator import local_translate

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

logger = logging.getLogger(__name__)

# 全部可用供应商
_ALL_PROVIDERS = {"auto", "google", "microsoft", "local"}

# ---------------------------------------------------------------------------
# 供应商分发
# ---------------------------------------------------------------------------


def _resolve_auto_provider(config: dict) -> str:
    """auto 模式主引擎优先级：Edge 微软（免 key、国内直连），回退链再尝试 Google / 本地词典。"""
    return "microsoft"


def _with_socket_timeout(seconds: float, func):
    """临时设置 socket 默认超时执行 func。deep_translator 的 Google 请求无 timeout 参数，
    不设超时访问被墙域名会挂死。"""
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(seconds)
    try:
        return func()
    finally:
        socket.setdefaulttimeout(old)


def _google_translate(text: str, target: str) -> str:
    """Google 免费网页翻译（无需密钥）。国内网络不可用时自然失败并回退。"""
    if GoogleTranslator is None:
        return ""
    try:
        tgt = _google_lang_code(target)

        def _do():
            return GoogleTranslator(source="auto", target=tgt).translate(text) or ""

        return _with_socket_timeout(6, _do)
    except Exception as e:
        logger.warning("Google 翻译失败: %s", e)
        return ""


def _google_lang_code(lang: str) -> str:
    """规范化语言代码，兼容 deep_translator 的格式（zh-cn -> zh-CN）。"""
    t = (lang or "").strip().lower().replace("_", "-")
    mapping = {"zh": "zh-CN", "zh-cn": "zh-CN", "zh-tw": "zh-TW", "en": "en", "en-us": "en"}
    return mapping.get(t, t)


def _microsoft_lang_code(lang: str) -> str:
    """将应用语言代码映射为微软翻译（Edge）语言代码。"""
    t = (lang or "").strip().lower().replace("_", "-")
    if t in ("zh", "zh-cn", "zh-hans"):
        return "zh-CHS"
    if t in ("zh-tw", "zh-hant"):
        return "zh-CHT"
    return (lang or "").strip() or "en"


def _microsoft_translate(text: str, source: str, target: str, session=None) -> str:
    """Edge 浏览器同款微软翻译：免 key、国内直连。"""
    try:
        url = "https://edge.microsoft.com/translate/translatetext"
        params = {"from": _microsoft_lang_code(source), "to": _microsoft_lang_code(target), "api-version": "3.0"}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
            "Origin": "https://www.microsoft.com",
            "Referer": "https://www.microsoft.com/",
        }
        sender = session.post if session is not None else requests.post
        resp = sender(
            url, params=params, headers=headers,
            data=json.dumps([text], ensure_ascii=False).encode("utf-8"), timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        if data and data[0].get("translations"):
            return data[0]["translations"][0].get("text", "").strip()
    except Exception as e:
        logger.warning("微软翻译失败: %s", e)
    return ""


def _translate_with_provider(
    text: str, source: str, target: str, provider: str, config: dict, deadline: float, session=None
) -> str:
    """按供应商分发单段文本翻译，失败返回空串。"""
    if provider == "google":
        return _google_translate(text, target)
    if provider == "microsoft":
        return _microsoft_translate(text, source, target, session)
    if provider == "local":
        return local_translate(text, target)
    return ""


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

def translate_text(
    text: str,
    source: str = "en",
    target: str = "zh-CN",
    config: dict | None = None,
    deadline: float = 0,
    session=None,
) -> tuple[str, bool]:
    """翻译单段文本。按供应商分发，失败沿回退链降级，最后本地词典兜底。返回 (翻译结果, 是否成功)。"""
    if not text or not text.strip():
        return text, False
    # 仅当源语言和目标语言均为英文时才跳过（避免无意义的英文->英文翻译）；
    # 源语言非英文（如 zh->en）时仍需正常翻译
    if source.lower().startswith("en") and target.lower().startswith("en"):
        return text, False
    cfg = config if isinstance(config, dict) else {}
    provider = str(cfg.get("translation_provider") or "auto").strip().casefold()
    if provider == "auto":
        provider = _resolve_auto_provider(cfg)
    translated = _translate_with_provider(text, source, target, provider, cfg, deadline, session)
    if translated and translated.strip() and translated != text:
        return translated, True
    # 供应商回退链
    for p in cfg.get("fallback_chain") or []:
        p = str(p or "").strip().casefold()
        if p in ("", "auto", provider) or p not in _ALL_PROVIDERS:
            continue
        translated = _translate_with_provider(text, source, target, p, cfg, deadline, session)
        if translated and translated.strip() and translated != text:
            return translated, True
    # 本地词典兜底（仅英译中）
    translated = local_translate(text, target)
    if translated and translated != text:
        return translated, True
    return text, False


def translate_readme_markdown(
    markdown_text: str,
    source: str = "en",
    target: str = "zh-CN",
    config: dict | None = None,
    deadline: float = 0,
    session=None,
) -> str:
    """翻译 README Markdown 内容：保留结构（代码块/行内代码/URL/图片/HTML/标题/列表标记），
    普通文本段落走代理翻译（Google / Edge 微软），失败降级本地词典，最后回退原文。"""
    if not markdown_text or not markdown_text.strip():
        return markdown_text
    # 仅当源语言和目标语言均为英文时才跳过（避免无意义的英文->英文翻译）
    if source.lower().startswith("en") and target.lower().startswith("en"):
        return markdown_text
    cfg = config if isinstance(config, dict) else {}
    lines = markdown_text.split("\n")
    out: list[str] = []
    in_code = False
    segment: list[str] = []

    def flush():
        if not segment:
            return
        seg_text = "\n".join(segment)
        segment.clear()
        out.append(_translate_readme_text(seg_text, source, target, cfg, deadline, session))

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            in_code = not in_code
            out.append(line)  # 代码块标记原样保留
            continue
        if in_code:
            out.append(line)  # 代码块内容原样保留
            continue
        if not stripped:
            flush()
            out.append(line)
            continue
        # 结构行（标题/列表/引用/表格/分隔线/图片）：单独处理，普通文本段合并后整段翻译
        if _README_STRUCT_RE.match(stripped):
            flush()
            out.append(_translate_readme_text(line, source, target, cfg, deadline, session))
            continue
        segment.append(line)
    flush()
    return "\n".join(out)


# 结构行判定：标题、无序/有序列表、引用、表格、分隔线、图片
_README_STRUCT_RE = re.compile(r'^(#{1,6}\s|[-*+]\s|\d+[.)]\s|>\s?|\||---|!\[)')
# 结构前缀（供 _translate_readme_text 提取并保护，避免代理改写 #、- 等标记）
_README_PREFIX_RE = re.compile(r'^(#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|\>\s?|\||---|!\[)')
# 行内保护：行内代码、链接/图片、HTML 标签、裸 URL
_README_INLINE_RE = re.compile(
    r'(`[^`\n]+`'
    r'|\[[^\]\n]*\]\([^)\n]*\)'
    r'|<[^>\n]+>'
    r'|https?://[^\s)\]>\n]+)'
)


def _protect_inline(text: str) -> tuple[str, list[str]]:
    """行内代码/链接/图片/HTML/URL 占位保护，翻译后还原，避免代理改写结构。"""
    tokens: list[str] = []

    def _repl(m) -> str:
        tokens.append(m.group(0))
        return f"@@PH{len(tokens) - 1}@@"

    return _README_INLINE_RE.sub(_repl, text), tokens


def _restore_inline(text: str, tokens: list[str]):
    """还原占位符；占位符被翻译破坏时返回 None 表示回退。"""
    if tokens and "@@PH" not in text:
        return None

    def _repl(m):
        idx = int(m.group(1))
        return tokens[idx] if 0 <= idx < len(tokens) else m.group(0)

    result = re.sub(r"@@PH(\d+)@@", _repl, text)
    if "@@PH" in result:
        return None
    return result


def _translate_readme_text(
    text: str, source: str, target: str, config: dict, deadline: float, session
) -> str:
    """翻译 README 单行/段落：结构前缀与行内结构占位保护 → 代理翻译 → 还原；任何失败回退原文。"""
    if not text or not text.strip():
        return text
    pm = _README_PREFIX_RE.match(text)
    prefix = pm.group(0) if pm else ""
    body = text[len(prefix):]
    protected, tokens = _protect_inline(body)
    translated, _ = translate_text(protected, source, target, config, deadline, session)
    if not translated or translated == protected:
        return text
    restored = _restore_inline(translated, tokens) if tokens else translated
    if restored is None or restored == body:
        return text
    return prefix + restored
