"""Logging configuration with optional structured JSON output."""

import logging
import sys

__all__ = ["get_logger", "setup_root_logger"]

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_root_logger(
    *,
    name: str = "root",
    level: str = "INFO",
    json_format: bool = False,
) -> None:
    """Configure application logging.

    Args:
        name: Root logger name for the application.
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, output logs as JSON for production.
    """
    handler = logging.StreamHandler(sys.stdout)

    if json_format:
        import structlog

        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
        )
        formatter = logging.Formatter("%(message)s")
    else:
        formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    handler.setFormatter(formatter)

    root_logger = logging.getLogger(name)
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(handler)

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=[handler],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module.

    Args:
        name: Module name (typically __name__).

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
