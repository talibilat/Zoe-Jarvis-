from __future__ import annotations

import logging
import os
import re
import sys
from typing import Iterable

from loguru import logger as _logger


_AZURE_COGNITIVE_PATTERNS = (
    r"cognitiveservices\.azure\.com",
    r"HTTP Request.*POST.*azure\.com",
    r"HTTP Request.*GET.*azure\.com",
    r"HTTP Request.*PUT.*azure\.com",
    r"HTTP Request.*DELETE.*azure\.com",
)
_NOISY_WARNING_LOGGERS = (
    "pymongo",
    "pymongo.command",
    "pymongo.connection",
    "pymongo.server_selection",
    "pymongo.topology",
    "pymongo.server",
    "urllib3",
    "azure",
    "azure.core",
    "azure.core.pipeline",
    "azure.core.pipeline.policies",
    "azure.ai.openai",
    "openai",
    "httpx",
    "httpcore",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.connection",
    "azure.cognitiveservices",
    "azure.cognitiveservices.vision",
    "azure.cognitiveservices.speech",
    "azure.cognitiveservices.textanalytics",
    "multipart",
    "multipart.multipart",
    "multipart.parser",
    "fastapi",
    "starlette",
    "uvicorn",
    "uvicorn.access",
    "logging",
)
_VALID_LEVELS = {
    "TRACE",
    "DEBUG",
    "INFO",
    "SUCCESS",
    "WARNING",
    "ERROR",
    "CRITICAL",
}


class AzureCognitiveServicesFilter(logging.Filter):
    """Filter to block Azure Cognitive Services HTTP request logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in _AZURE_COGNITIVE_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return False
        return True


class InterceptHandler(logging.Handler):
    """Intercept standard logging and route records into loguru."""

    def __init__(self) -> None:
        super().__init__()
        self.addFilter(AzureCognitiveServicesFilter())

    def emit(self, record: logging.LogRecord) -> None:
        if not self.filter(record):
            return

        try:
            level: str | int = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        extra = getattr(record, "extra", {})
        if not isinstance(extra, dict):
            extra = {}

        _logger.opt(depth=depth, exception=record.exc_info).bind(**extra).log(
            level, record.getMessage()
        )


def _resolve_log_level() -> str:
    level_name = (
        (os.getenv("APP_LOG_LEVEL") or os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    )
    return level_name if level_name in _VALID_LEVELS else "INFO"


def _resolve_json_logs() -> bool:
    raw = (os.getenv("APP_JSON_LOGS") or os.getenv("LOG_JSON") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _set_levels(logger_names: Iterable[str], level: int) -> None:
    for name in logger_names:
        logging.getLogger(name).setLevel(level)


def setup_logging():
    log_level = _resolve_log_level()
    json_logs = _resolve_json_logs()

    logging.root.handlers = []
    logging.root.propagate = False

    intercept_handler = InterceptHandler()
    logging.root.handlers = [intercept_handler]
    logging.root.addFilter(AzureCognitiveServicesFilter())
    logging.root.setLevel(log_level)

    for name in list(logging.root.manager.loggerDict.keys()):
        current_logger = logging.getLogger(name)
        current_logger.handlers = []
        current_logger.propagate = True

    _set_levels(_NOISY_WARNING_LOGGERS, logging.WARNING)

    _logger.remove()
    _logger.add(
        sys.stdout,
        serialize=json_logs,
        level=log_level,
        format="{message}",
        colorize=False,
    )
    return _logger


def configure_logger() -> None:
    setup_logging()


logger = _logger
setup_logging()
