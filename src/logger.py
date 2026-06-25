import logging
import os
from logging.handlers import RotatingFileHandler

os.makedirs("logs", exist_ok=True)

_formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)-8s %(module)s: %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)

def get_logger(name: str = "radar-voos") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setFormatter(_formatter)
    logger.addHandler(ch)

    fh = RotatingFileHandler(
        "logs/radar-voos.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(_formatter)
    logger.addHandler(fh)

    return logger

logger = get_logger()
