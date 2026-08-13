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

    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件日志尽力而为：非 root 或日志目录不可写时不崩，仅退回控制台日志（容器友好）
    try:
        os.makedirs('logs', exist_ok=True)
        file_handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(json_formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        logging.getLogger('logger_setup').warning(
            f"无法写入日志文件，仅使用控制台日志: {e}"
        )

    return logger
