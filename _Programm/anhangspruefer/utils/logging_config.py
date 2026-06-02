"""Logging configuration for Anhangsprüfer."""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_file: Path | None = None,
    console_output: bool = True
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file
        console_output: Whether to output to console

    Returns:
        Configured root logger
    """
    logger = logging.getLogger("anhangspruefer")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    logger.handlers = []

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name under the anhangspruefer namespace."""
    return logging.getLogger(f"anhangspruefer.{name}")


def create_audit_log_entry(
    action: str,
    details: dict,
    user: str = "system"
) -> str:
    """
    Create a formatted audit log entry.

    These entries are designed for audit trail documentation.
    """
    timestamp = datetime.now().isoformat()
    entry = f"[AUDIT] {timestamp} | User: {user} | Action: {action}"

    for key, value in details.items():
        entry += f" | {key}: {value}"

    return entry
