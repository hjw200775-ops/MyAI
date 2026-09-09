"""Allowlisted diagnostics: never emit exception bodies, headers or payloads.

Remote error text can echo arbitrary secrets, so translate it to a fixed safe
description rather than relying on regular expressions to hide known key shapes.
"""
import logging
import os
import re
from urllib.parse import urlsplit

logger = logging.getLogger("myai.api")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class ProviderCallError(RuntimeError):
    """Contains only a safe, user-facing diagnostic."""


class LocalValidationError(ValueError):
    pass


def safe_label(value, config=None):
    text = str(value or "unset")
    secrets = [getattr(config, "api_key", None)]
    secrets += [v for k, v in os.environ.items()
                if any(word in k.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD"))]
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted]", text)
    return re.sub(r"[^\w.:/\[\]-]", "_", text)[:100]


def configuration_summary(config):
    try:
        url = urlsplit(config.base_url)
        # No userinfo, query, fragments or arbitrary path in diagnostics.
        endpoint = f"{url.scheme}://{url.hostname}"
        path = url.path.rstrip("/")
        endpoint += path if path in ("", "/v1") else "/[custom-path]"
        endpoint += "/chat/completions"
    except ValueError:
        endpoint = "invalid-url"
    return (f"provider={safe_label(config.provider, config)} "
            f"model={safe_label(config.model, config)} "
            f"endpoint={safe_label(endpoint, config)} "
            f"key={'present' if config.api_key else 'missing'}")


def describe_error(exc):
    status = getattr(exc, "status_code", None)
    status = status if type(status) is int and 100 <= status <= 599 else None
    name = type(exc).__name__
    known = {"APIStatusError", "BadRequestError", "AuthenticationError", "PermissionDeniedError",
             "NotFoundError", "RateLimitError", "InternalServerError", "APITimeoutError",
             "APIConnectionError", "FileNotFoundError", "LocalValidationError", "ValueError",
             "RuntimeError", "ImportError", "ModuleNotFoundError"}
    kind = name if name in known else "ProviderError"
    reasons = {400: "请求参数、图片或模型能力不匹配", 401: "API Key 无效或认证失败",
               402: "账户余额不足", 403: "权限不足", 404: "模型或接口路径不存在",
               413: "请求体过大", 422: "请求参数无法处理", 429: "请求过于频繁或配额受限"}
    reason = reasons.get(status, "服务调用失败，原始错误内容已隐藏")
    if status and status >= 500:
        reason = "服务端暂时不可用"
    elif name == "APITimeoutError":
        reason = "请求超时，请检查网络或增大 MYAI_VISION_TIMEOUT"
    elif name == "APIConnectionError":
        reason = "连接失败，请检查网络、代理或证书"
    elif isinstance(exc, LocalValidationError):
        # Only our fixed validation strings are passed to this class.
        reason = str(exc)
    elif name == "FileNotFoundError":
        reason = "图片资源不存在"
    remote_detail = _safe_remote_detail(exc)
    suffix = f" | remote={remote_detail}" if remote_detail else ""
    return f"HTTP {status if status else 'N/A'} | {kind} | {reason}{suffix}"


def _safe_remote_detail(exc):
    """Map a remote body to a useful fixed label without echoing its payload.

    API error messages can reflect request text, image data or credentials.  We
    therefore recognize common DeepSeek validation messages but never print the
    arbitrary body itself.  This still distinguishes the actionable 400 causes
    while guaranteeing private conversation content cannot enter logs.
    """
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        return None
    error = body.get("error", body)
    if not isinstance(error, dict):
        return None
    message = str(error.get("message") or "").lower()
    rules = (
        (("does not support image", "not support image"), "model_does_not_support_image"),
        (("image", "user", "message"), "image_must_be_in_user_message"),
        (("model", "not exist"), "model_not_found"),
        (("invalid model",), "invalid_model"),
        (("reserved", "image", "placeholder"), "reserved_image_placeholder"),
        (("invalid", "base64"), "invalid_image_base64"),
        (("unsupported", "image", "format"), "unsupported_image_format"),
        (("image", "too large"), "image_too_large"),
        (("request", "too large"), "request_too_large"),
        (("unknown", "parameter"), "unknown_parameter"),
    )
    for terms, label in rules:
        if all(term in message for term in terms):
            return label
    return "unrecognized_remote_message_hidden"


def report_error(exc, config=None):
    summary = str(exc) if isinstance(exc, ProviderCallError) else describe_error(exc)
    if not isinstance(exc, ProviderCallError):
        if config is not None:
            summary = configuration_summary(config) + " | " + summary
        logger.error("%s", summary)
    return summary
