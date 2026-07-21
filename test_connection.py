"""Prueba de conexión estándar del conector aws_s3.

Firma estándar Ruvic: def test_connection() -> tuple[bool, str]
- Lee la configuración EXCLUSIVAMENTE de las env vars RUVIC_AWS_S3_*.
- Nunca lanza excepciones; retorna (ok, mensaje).

Ejecutable también como script para pruebas locales:
    python test_connection.py
"""

from __future__ import annotations


def test_connection() -> tuple[bool, str]:
    """Verifica acceso al bucket configurado usando las env vars RUVIC_AWS_S3_*."""
    try:
        from ruvic_aws_s3_connector import (
            S3AuthError,
            S3Client,
            S3DataError,
            S3NetworkError,
        )
    except ImportError:
        return (
            False,
            "La librería ruvic-aws-s3-connector no está instalada. "
            "Instala con: pip install git+https://github.com/Dgirto/"
            "AWS-S3.git#subdirectory=lib",
        )

    try:
        client = S3Client()  # valida que existan las env vars
    except ValueError as exc:
        return False, str(exc)

    try:
        client.ping()
    except S3AuthError as exc:
        return False, f"Autenticación fallida: {exc}"
    except S3NetworkError as exc:
        return False, f"Error de red: {exc}"
    except S3DataError as exc:
        return False, f"Error de datos: {exc}"
    except Exception as exc:  # red de seguridad: jamás propagar
        return False, f"Error inesperado: {exc}"

    return (
        True,
        f"Conexión exitosa al bucket {client.config.bucket!r} en {client.config.region}",
    )


if __name__ == "__main__":
    ok, message = test_connection()
    print(f"{'OK' if ok else 'FALLO'}: {message}")
    raise SystemExit(0 if ok else 1)
