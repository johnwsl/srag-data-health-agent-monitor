import logging
import logging.config
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configura logging para stdout (capturado pelo driver json-file do Docker)."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "default",
                },
            },
            "root": {
                "handlers": ["stdout"],
                "level": level,
            },
            "loggers": {
                "app": {
                    "level": level,
                    "handlers": ["stdout"],
                    "propagate": False,
                },
                "uvicorn": {
                    "level": level,
                    "handlers": ["stdout"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": level,
                    "handlers": ["stdout"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": "WARNING",
                    "handlers": ["stdout"],
                    "propagate": False,
                },
            },
        }
    )
