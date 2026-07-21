"""Excepciones propias del conector AWS S3.

Separan los tres tipos de fallo que el usuario debe distinguir:
autenticación, red/servidor y datos. Nunca exponemos excepciones
crípticas del SDK subyacente.
"""


class S3ConnectorError(Exception):
    """Error base del conector."""


class S3AuthError(S3ConnectorError):
    """Credenciales inválidas o permisos IAM insuficientes."""


class S3NetworkError(S3ConnectorError):
    """No se pudo alcanzar el servicio (red, timeout, error temporal de AWS)."""


class S3DataError(S3ConnectorError):
    """La operación es válida pero el bucket/objeto no existe o los datos son inválidos."""
