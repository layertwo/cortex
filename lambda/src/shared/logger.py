"""
Portable structured JSON logger for Cortex API.

Works identically in Lambda and container environments.
Replaces aws-lambda-powertools Logger.
"""

import logging

import structlog

from src.environment.config_provider import log_level

_log_level = getattr(logging, log_level().upper(), logging.INFO)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(_log_level),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger().bind(logger=name)
