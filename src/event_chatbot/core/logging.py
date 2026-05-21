import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str | None = None) -> None:
    log_level = (level or os.getenv("LOG_LEVEL") or os.getenv("APP_LOG_LEVEL") or "INFO").upper()
    resolved_level = getattr(logging, log_level, logging.INFO)
    logging.basicConfig(level=resolved_level, format=LOG_FORMAT, stream=sys.stdout, force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
