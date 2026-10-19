"""Centralized logging configuration using Loguru.

Configures formatted terminal logging, standard library interception (uvicorn, apscheduler),
and optional file rotation for production-grade audit logging.
"""
import logging
import sys
from loguru import logger
from app.core.config import settings


class InterceptHandler(logging.Handler):
    """Intercept standard Python logging messages and redirect them to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    """Initialize and configure Loguru logger."""
    # Remove default handlers
    logger.remove()

    # Determine log level based on debug setting
    log_level = "DEBUG" if settings.DEBUG else "INFO"

    # Console stdout handler with rich formatting
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stdout,
        level=log_level,
        format=log_format,
        colorize=True,
        backtrace=settings.DEBUG,
        diagnose=settings.DEBUG,
    )

    # File log sink for persistent auditing
    logger.add(
        "logs/lottomind_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="30 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        compression="zip",
    )

    # Intercept standard library loggers
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "apscheduler", "sqlalchemy"):
        std_logger = logging.getLogger(logger_name)
        std_logger.handlers = [InterceptHandler()]
        std_logger.propagate = False
