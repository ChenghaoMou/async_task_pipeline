"""Logging utilities for the async task pipeline framework.

This module provides a centralized logger instance used throughout
the pipeline framework for consistent logging behavior.
"""

import logging

from rich.logging import RichHandler

FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
logger = logging.getLogger("async_task_pipeline")


"""Logger instance for the async task pipeline framework.

This logger is used throughout the framework for consistent logging.
Configure it at the application level to control log output format,
level, and destinations.

Examples
--------
>>> import logging
>>> from async_task_pipeline.utils import logger
>>>
>>> # Configure logging level
>>> logger.setLevel(logging.INFO)
>>>
>>> # Add a handler
>>> handler = logging.StreamHandler()
>>> logger.addHandler(handler)
"""

__all__ = ["logger"]
