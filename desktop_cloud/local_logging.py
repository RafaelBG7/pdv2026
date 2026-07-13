from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

from .config import logs_dir


SENSITIVE_PATTERNS = (
    re.compile(r"([?&](?:token|key|password|senha|secret|auth)=[^&\s]+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE),
)


class SanitizingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        for pattern in SENSITIVE_PATTERNS:
            formatted = pattern.sub(lambda match: match.group(1).split("=")[0] + "=***", formatted)
        return formatted


def configure_launcher_logger() -> logging.Logger:
    path = logs_dir()
    path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("girofy.desktop")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    handler = RotatingFileHandler(path / "launcher.log", maxBytes=512_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(
        SanitizingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(handler)
    return logger
