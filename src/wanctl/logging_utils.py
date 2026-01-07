"""Shared logging utilities for CAKE system components."""

import logging
import os


def setup_logging(
    config,
    logger_prefix: str,
    debug: bool = False
) -> logging.Logger:
    """Setup logging with file and optional console output.

    Creates a logger with:
    - INFO-level file handler (main_log)
    - DEBUG-level file handler (debug_log, if debug=True)
    - DEBUG-level console handler (if debug=True)

    Args:
        config: Config object with main_log and debug_log attributes
        logger_prefix: Logger name prefix (e.g., "cake_continuous", "wan_steering")
        debug: Enable debug logging to file and console

    Returns:
        Configured logger instance

    Example:
        config = Config('config.yaml')
        logger = setup_logging(config, 'cake_continuous', debug=True)
        logger.info("System started")
    """
    logger = logging.getLogger(f"{logger_prefix}_{config.wan_name.lower()}")

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Ensure log directories exist
    for path in (config.main_log, getattr(config, 'debug_log', None)):
        if path:
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)

    # Main log - INFO level
    fh = logging.FileHandler(config.main_log)
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        f"%(asctime)s [{config.wan_name}] [%(levelname)s] %(message)s"
    ))
    logger.addHandler(fh)

    # Debug log and console - DEBUG level
    if debug and hasattr(config, 'debug_log'):
        dfh = logging.FileHandler(config.debug_log)
        dfh.setLevel(logging.DEBUG)
        dfh.setFormatter(logging.Formatter(
            f"%(asctime)s [{config.wan_name}] [%(levelname)s] %(message)s"
        ))
        logger.addHandler(dfh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter(
            f"%(asctime)s [{config.wan_name}] [%(levelname)s] %(message)s"
        ))
        logger.addHandler(ch)

    return logger
