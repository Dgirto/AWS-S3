"""Conector Ruvic para gestión de objetos en Amazon S3."""

from .client import S3Client
from .config import ENV_PREFIX, S3Config
from .exceptions import (
    S3AuthError,
    S3ConnectorError,
    S3DataError,
    S3NetworkError,
)
from .logging_utils import setup_logging

__all__ = [
    "ENV_PREFIX",
    "S3AuthError",
    "S3Client",
    "S3Config",
    "S3ConnectorError",
    "S3DataError",
    "S3NetworkError",
    "setup_logging",
]

__version__ = "1.0.0"
