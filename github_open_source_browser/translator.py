# -*- coding: utf-8 -*-
"""翻译模块：markdown 占位保护与腾讯云 TC3 签名等自包含逻辑。

从 main.py 抽出，便于独立维护与测试。只依赖标准库，不依赖应用主模块。
"""

import datetime as _datetime
import hashlib as _hashlib
import hmac as _hmac
import json as _json
import re as _re
import time as _time

# ---------------------------------------------------------------------------
# Markdown 占位保护层
# 翻译前把代码块、HTML、URL 等替换为不可翻译占位符，翻译后原样恢复，
# 避免第三方翻译接口破坏格式、翻译代码或丢失链接。
# ---------------------------------------------------------------------------

# 当前占位符（3 位字母序号，实测腾讯翻译不会拆分纯字母串）
PLACEHOLDER_RESIDUAL = _re.compile(r"ZXQPH[A-Z]{3}TK")

# 旧版字节码内部占位符（ZXQGOSB{n}TOKEN）被腾讯拆成带空格后恢复失败而残留
LEGACY_PLACEHOLDER_RESIDUAL = _re.compile(r"ZXQGOSB\s*\d+\s*TOKEN")


def placeholder_token(index: int) -> str:
    """生成 3 位字母序号占位符（ZXQPHAAATK…），纯字母格式避免翻译接口
    按"词+数字+词"分词拆分（实测 ZXQPH0TK 会被腾讯拆成 ZXQPH 0 TK）。"""
    n = index
    chars = []
    for _ in range(3):
        chars.append(chr(ord("A") + n % 26))
        n //= 26
    return "ZXQPH" + "".join(reversed(chars)) + "TK"


def protect_markdown_blocks(markdown_text) -> tuple[str, list[str]]:
    """把代码块、HTML 标签、RST 指令、表格分隔线、行内代码与 URL 替换为
    占位符（ZXQPHAAATK 形式），返回（保护后文本, 原文映射列表）。"""
    mappings: list[str] = []

    def _replace(match) -> str:
        token = placeholder_token(len(mappings))
        mappings.append(match.group(0))
        return token

    text = str(markdown_text or "")
    patterns = (
        # 围栏代码块（含语言标签，可跨行）
        _re.compile(r"```.*?```", _re.S),
        # 行内代码（先于 HTML，避免反引号内的 <tag> 被 HTML 规则抢先替换造成嵌套）
        _re.compile(r"`[^`\n]+`"),
        # HTML 注释与标签（含属性）
        _re.compile(r"<(?:!--.*?-->|/?[a-zA-Z][^>]*)>", _re.S),
        # reStructuredText 指令及其选项行（.. image:: 等）
        _re.compile(r"(?m)^\s*\.\.\s+[a-zA-Z_-]+::[^\n]*(?:\n\s*:[a-zA-Z_-]+:\s*[^\n]*)*"),
        # Markdown 表格分隔行（| --- | --- |）
        _re.compile(r"(?m)^\s*\|?[\s:|-]*-{3,}[\s:|-]*\|[\s:|-]*(?:-{3,}[\s:|-]*\|?)+\s*$"),
        # URL（含协议）
        _re.compile(r"https?://[^\s<>\"')\]]+"),
    )
    for pattern in patterns:
        text = pattern.sub(_replace, text)
    return text, mappings


def restore_markdown_blocks(translated_text: str, mappings: list[str]) -> str:
    result = str(translated_text or "")
    for index, original in enumerate(mappings):
        result = result.replace(placeholder_token(index), original)
    return result


def protect_markdown_fragment_noop(text, state) -> str:
    """关闭旧版字节码内部 ZXQGOSB 占位保护（已被外层保护层取代）。"""
    return str(text or "")


# ---------------------------------------------------------------------------
# 腾讯云 TC3-HMAC-SHA256 签名
# ---------------------------------------------------------------------------

def tc3_authorization(
    secret_id: str,
    secret_key: str,
    host: str,
    service_name: str,
    action: str,
    version: str,
    region: str,
    payload: dict,
) -> tuple[str, str, str]:
    """计算腾讯云 TC3 签名。

    返回 (authorization 头, body 字符串, 签名时间戳)，调用方自行组装请求头。
    仅依赖标准库，行为与原 main.py 内联实现一致。
    """
    timestamp = int(_time.time())
    date = _datetime.datetime.fromtimestamp(timestamp, tz=_datetime.timezone.utc).strftime("%Y-%m-%d")
    body = _json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    hashed_payload = _hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_headers = "content-type:application/json; charset=utf-8\nhost:" + host + "\n"
    signed_headers = "content-type;host"
    canonical_request = "\n".join(
        ("POST", "/", "", canonical_headers, signed_headers, hashed_payload)
    )
    credential_scope = f"{date}/{service_name}/tc3_request"
    string_to_sign = "\n".join(
        (
            "TC3-HMAC-SHA256",
            str(timestamp),
            credential_scope,
            _hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        )
    )
    secret_date = _hmac.new(
        ("TC3" + secret_key).encode("utf-8"),
        date.encode("utf-8"),
        _hashlib.sha256,
    ).digest()
    secret_service = _hmac.new(
        secret_date,
        service_name.encode("utf-8"),
        _hashlib.sha256,
    ).digest()
    secret_signing = _hmac.new(
        secret_service,
        b"tc3_request",
        _hashlib.sha256,
    ).digest()
    signature = _hmac.new(
        secret_signing,
        string_to_sign.encode("utf-8"),
        _hashlib.sha256,
    ).hexdigest()
    authorization = (
        "TC3-HMAC-SHA256 "
        f"Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return authorization, body, str(timestamp)
