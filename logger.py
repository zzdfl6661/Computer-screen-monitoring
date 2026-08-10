import logging
import os
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger


def setup_logger(name='app', log_level=logging.DEBUG):
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    logger.propagate = False

    if logger.handlers:
        return logger

    os.makedirs('logs', exist_ok=True)

    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10 * 1024 * 1024,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    json_formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(message)s %(module)s %(funcName)s %(lineno)d',
        rename_fields={
            'asctime': 'timestamp',
            'levelname': 'level',
            'module': 'module',
            'funcName': 'function',
            'lineno': 'line'
        }
    )

    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    file_handler.setFormatter(json_formatter)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
