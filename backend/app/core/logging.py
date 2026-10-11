"""Logging that cannot leak credentials."""

from __future__ import annotations

import logging
import re

_KEY_PARAM = re.compile(r"(?i)\b(api_key|apikey|appid|key|authorization)=([^&\s]+)")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")


def redact(text: str, secrets: list[str] | tuple[str, ...] = ()) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    text = _KEY_PARAM.sub(lambda m: f"{m.group(1)}=***", text)
    return _BEARER.sub("Bearer ***", text)


class RedactingFilter(logging.Filter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self._secrets = secrets

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.getMessage()), self._secrets)
        record.args = ()
        return True


def configure_logging(level: str, secrets: list[str]) -> None:
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(RedactingFilter(secrets))
    # httpx logs full request URLs at INFO, and provider URLs carry API keys in the query string.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
