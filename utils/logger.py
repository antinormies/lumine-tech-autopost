import logging
import os
import sys


SESSION_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "session.log")


def setup_logger(name: str = "lumine") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    file_handler = logging.FileHandler(SESSION_LOG, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
