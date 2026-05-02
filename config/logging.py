"""
Logging configuration using loguru.
"""
import sys
from loguru import logger


def setup_logging(env: str = "development") -> None:
    """
    Configure loguru: stdout with DEBUG in dev, rotating file sinks in production.

    :param env: Runtime environment, either 'development' or 'production'.
    :return: None
    """
    logger.remove()

    fmt = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"

    if env == "production":
        logger.add(
            "logs/app.log",
            format=fmt,
            rotation="10 MB",
            retention="7 days",
            level="INFO",
            encoding="utf-8",
        )
        logger.add(
            "logs/error.log",
            format=fmt,
            rotation="10 MB",
            retention="7 days",
            level="ERROR",
            encoding="utf-8",
        )
    else:
        logger.add(sys.stdout, format=fmt, level="DEBUG", colorize=True)
