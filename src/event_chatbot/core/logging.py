import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
PACKAGE_LOGGER = "event_chatbot"


def configure_logging(level: str | None = None) -> None:
    log_level = (level or os.getenv("LOG_LEVEL") or os.getenv("APP_LOG_LEVEL") or "INFO").upper()
    resolved_level = getattr(logging, log_level, logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    logging.basicConfig(level=resolved_level, format=LOG_FORMAT, stream=sys.stdout, force=True)

    package_logger = logging.getLogger(PACKAGE_LOGGER)
    package_logger.setLevel(resolved_level)
    package_logger.propagate = False
    if not package_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        package_logger.addHandler(handler)
    for handler in package_logger.handlers:
        handler.setLevel(resolved_level)
        handler.setFormatter(formatter)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
