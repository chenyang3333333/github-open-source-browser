# -*- coding: utf-8 -*-
"""翻译服务：按供应商分发翻译文本和 README，失败时沿回退链降级。"""
from __future__ import annotations

import json
import logging
import socket
import time

import requests

from github_open_source_browser.translator import local_translate, tc3_authorization

try:
    from deep_translator import DeeplTranslator, GoogleTranslator
except Exception:
    DeeplTranslator = None
    GoogleTranslator = None

logger = logging.getLogger(__name__)

# LLM 类供应商：统一走 OpenAI-compatible 接口
_LLM_PROVIDERS = {"openai_compatible", "claude", "gemini", "mimo"}
# 全部可用供应商
_ALL_PROVIDERS = _LLM_PROVIDERS | {"auto", "tencent", "deepl", "google", "microsoft", "local"}

# ---------------------------------------------------------------------------
# 语言名称映射
# ---------------------------------------------------------------------------

_LANG_NAMES = {
    "zh-cn": "Simplified Chinese",
    "zh": "Simplified Chinese",
    "zh-tw": "Traditional Chinese",
    "en": "English",
    "en-us": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "tr": "Turkish",
}


def _target_lang_name(target: str) -> str:
    """将目标语言代码转换为英文语言名称。"""
    return _LANG_NAMES.get(target.lower().strip(), target)


# ---------------------------------------------------------------------------
# 供应商分发
# ---------------------------------------------------------------------------


def _has_llm_config(config: dict) -> bool:
    """是否已配置 LLM（OpenAI-compatible）翻译参数。"""
    return bool(
        str(config.get("translation_api_url") or "").strip()
        and str(config.get("translation_api_key") or "").strip()
        and str(config.get("translation_model") or "").strip()
    )


def _resolve_auto_provider(config: dict) -> str:
    """auto 模式主引擎优先级：已配置 LLM > 腾讯云 > Edge 微软（免 key）> Google。"""
    if _has_llm_config(config):
        return "openai_compatible"
    if str(config.get("tencent_secret_id") or "").strip() and str(config.get("tencent_secret_key") or "").strip():
        return "tencent"
    return "microsoft"


def _tencent_lang_code(lang: str) -> str:
    """将应用语言代码映射为腾讯云 TMT 语言代码。"""
    t = (lang or "").strip().lower().replace("_", "-")
    if t in ("zh", "zh-cn", "zh-hans"):
        return "zh"
    if t in ("zh-tw", "zh-hant"):
        return "zh-TW"
    return (lang or "").strip() or "auto"


def _tencent_translate(text: str, source: str, target: str, config: dict, session=None) -> str:
    """腾讯云机器翻译 TMT（TC3 签名）。国内可直连，有免费额度。"""
    secret_id = str(config.get("tencent_secret_id") or "").strip()
    secret_key = str(config.get("tencent_secret_key") or "").strip()
    if not (secret_id and secret_key):
        return ""
    if len(text) > 2000:
        return ""  # TMT 单次上限 2000 字符，超长交由 LLM / 本地词典兜底
    host, action, version, region = "tmt.tencentcloudapi.com", "TextTranslate", "2018-03-21", "ap-guangzhou"
    payload = {
        "SourceText": text,
        "Source": _tencent_lang_code(source),
        "Target": _tencent_lang_code(target),
        "ProjectId": 0,
    }
    try:
        auth, body, ts = tc3_authorization(secret_id, secret_key, host, "tmt", action, version, region, payload)
        headers = {
            "Authorization": auth,
            "Content-Type": "application/json; charset=utf-8",
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Timestamp": ts,
            "X-TC-Version": version,
            "X-TC-Region": region,
        }
        sender = session.post if session is not None else requests.post
        resp = sender(f"https://{host}/", headers=headers, data=body.encode("utf-8"), timeout=8)
        resp.raise_for_status()
        response = resp.json().get("Response") or {}
        if response.get("Error"):
            logger.warning("腾讯云翻译错误: %s", response["Error"].get("Message"))
            return ""
        return str(response.get("TargetText") or "").strip()
    except Exception as e:
        logger.warning("腾讯云翻译失败: %s", e)
        return ""


def _with_socket_timeout(seconds: float, func):
    """临时设置 socket 默认超时执行 func。deep_translator 请求无 timeout 参数，
    不设超时访问被墙域名（Google/DeepL）会挂死。"""
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(seconds)
    try:
        return func()
    finally:
        socket.setdefaulttimeout(old)


def _deepl_translate(text: str, target: str, config: dict) -> str:
    """DeepL 翻译（免费 API）。使用 translation_api_key 作为 DeepL 密钥。"""
    if DeeplTranslator is None:
        return ""
    api_key = str(config.get("translation_api_key") or "").strip()
    if not api_key:
        return ""
    try:
        tgt = "zh" if target.lower().replace("_", "-").startswith("zh") else target.lower().replace("_", "-")

        def _do():
            translator = DeeplTranslator(source="en", target=tgt, api_key=api_key, use_free_api=True)
            return translator.translate(text) or ""

        return _with_socket_timeout(6, _do)
    except Exception as e:
        logger.warning("DeepL 翻译失败: %s", e)
        return ""


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
    if provider in _LLM_PROVIDERS:
        return _chat_completion_translate(text, target, config, deadline, session)
    if provider == "tencent":
        return _tencent_translate(text, source, target, config, session)
    if provider == "deepl":
        return _deepl_translate(text, target, config)
    if provider == "google":
        return _google_translate(text, target)
    if provider == "microsoft":
        return _microsoft_translate(text, source, target, session, deadline)
    if provider == "local":
        return local_translate(text, target)
    return ""


# ---------------------------------------------------------------------------
# LLM 翻译核心
# ---------------------------------------------------------------------------

def _chat_completion_translate(text: str, target: str, config: dict, deadline: float = 0, session=None) -> str:
    """通用 OpenAI-compatible chat completions 翻译。"""
    api_key = str(config.get("translation_api_key") or "").strip()
    if not api_key:
        return ""
    base_url = str(config.get("translation_api_url") or "").strip().rstrip("/")
    if not base_url:
        return ""
    model = str(config.get("translation_model") or "").strip()
    if not model:
        return ""
    lang_name = _target_lang_name(target)
    prompt = (
        f"Translate the following text to {lang_name}. "
        "Only output the translation, nothing else.\n\n"
        f"{text}"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4000,
    }
    timeout = max(1, min(deadline - time.monotonic(), 60)) if deadline > 0 else 5
    try:
        # 传入 session 时复用连接，避免每次 TCP+TLS 握手
        sender = session.post if session is not None else requests.post
        resp = sender(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.warning("翻译 API 调用失败: %s", e)
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


def _chat_completion_readme(
    markdown_text: str, target: str, config: dict, deadline: float = 0, session=None
) -> str:
    """将整个 README 一次性发给 LLM 翻译，保留 Markdown 结构。"""
    api_key = str(config.get("translation_api_key") or "").strip()
    base_url = str(config.get("translation_api_url") or "").strip().rstrip("/")
    model = str(config.get("translation_model") or "").strip()
    if not (api_key and base_url and model):
        return ""
    lang_name = _target_lang_name(target)
    prompt = (
        f"Translate the following Markdown document to {lang_name}. "
        "Keep all Markdown formatting, code blocks, links, images, HTML tags "
        "and structure exactly as-is. Only translate the human-readable text. "
        "Output ONLY the translated Markdown, no explanations.\n\n"
        f"{markdown_text}"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 8000,
    }
    # 请求前先检查总超时是否已到期，避免请求开始前就超时
    if deadline > 0 and time.monotonic() >= deadline:
        return ""
    # 超时取 deadline 剩余时间（上限60s）；未传 deadline 时用固定30s
    # 这样长 README 请求有总时长上限，不会无限占用线程
    timeout = max(1, min(deadline - time.monotonic(), 60)) if deadline > 0 else 30
    try:
        # 传入 session 时复用连接，避免每次 TCP+TLS 握手
        sender = session.post if session is not None else requests.post
        resp = sender(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            translated = choices[0].get("message", {}).get("content", "").strip()
            if translated:
                return translated
    except Exception as e:
        logger.warning("README 翻译失败: %s", e)
    return ""


def _translate_readme_with_provider(
    markdown_text: str, source: str, target: str, provider: str, config: dict, deadline: float, session=None
) -> str:
    """README 结构复杂，仅 LLM（保留 Markdown）与本地词典（逐词替换不破坏结构）可用。"""
    if provider in _LLM_PROVIDERS:
        return _chat_completion_readme(markdown_text, target, config, deadline, session)
    if provider == "local":
        return local_translate(markdown_text, target)
    return ""


def translate_readme_markdown(
    markdown_text: str,
    source: str = "en",
    target: str = "zh-CN",
    config: dict | None = None,
    deadline: float = 0,
    session=None,
) -> str:
    """翻译 README Markdown 内容，保留格式结构。

    按供应商分发（仅 LLM / 本地词典可用），失败沿回退链降级，最后本地词典兜底。
    策略：将整个 README 一次性发给 LLM 翻译，避免逐段请求导致的超时累积和进度卡住问题。
    """
    if not markdown_text or not markdown_text.strip():
        return markdown_text
    # 仅当源语言和目标语言均为英文时才跳过；源语言非英文时仍需正常翻译
    if source.lower().startswith("en") and target.lower().startswith("en"):
        return markdown_text
    cfg = config if isinstance(config, dict) else {}
    provider = str(cfg.get("translation_provider") or "auto").strip().casefold()
    if provider == "auto":
        provider = _resolve_auto_provider(cfg)
    translated = _translate_readme_with_provider(markdown_text, source, target, provider, cfg, deadline, session)
    if translated and translated != markdown_text:
        return translated
    # 供应商回退链
    for p in cfg.get("fallback_chain") or []:
        p = str(p or "").strip().casefold()
        if p in ("", "auto", provider) or p not in _ALL_PROVIDERS:
            continue
        translated = _translate_readme_with_provider(markdown_text, source, target, p, cfg, deadline, session)
        if translated and translated != markdown_text:
            return translated
    # 本地词典兜底
    translated = local_translate(markdown_text, target)
    if translated and translated != markdown_text:
        return translated
    return markdown_text


def translate_batch_texts(
    texts: list[str],
    target: str = "zh-CN",
    config: dict | None = None,
) -> list[str]:
    """批量翻译多段文本，一次 API 调用完成。

    将多段文本编号后拼成一个 prompt 发给 LLM，解析返回的编号结果。
    返回与输入等长的列表，翻译失败的条目保留原文。
    """
    if not texts:
        return []
    cfg = config if isinstance(config, dict) else {}
    api_key = str(cfg.get("translation_api_key") or "").strip()
    base_url = str(cfg.get("translation_api_url") or "").strip().rstrip("/")
    model = str(cfg.get("translation_model") or "").strip()
    if not (api_key and base_url and model):
        return list(texts)
    lang_name = _target_lang_name(target)
    # 编号拼接
    numbered = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(texts))
    prompt = (
        f"Translate each numbered line below to {lang_name}. "
        "Keep the [N] numbering prefix exactly. "
        "Output ONLY the translated lines, nothing else.\n\n"
        + numbered
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4000,
    }
    timeout = 15
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "").strip()
            return _parse_numbered_response(content, texts)
    except Exception as e:
        logger.warning("批量翻译失败: %s", e)
    return list(texts)


def _parse_numbered_response(content: str, originals: list[str]) -> list[str]:
    """解析 LLM 返回的编号文本，与原文对应。"""
    import re as _re
    result = list(originals)
    # 匹配 [1] xxx 或 [1]xxx 格式
    pattern = _re.compile(r"\[(\d+)\]\s*(.*)")
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        m = pattern.match(line)
        if m:
            idx = int(m.group(1)) - 1
            translated = m.group(2).strip()
            if 0 <= idx < len(result) and translated:
                result[idx] = translated
    return result
