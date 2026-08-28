"""Cliente de gestión de objetos en Amazon S3.

Capacidades:
- list_objects():           listar objetos de un bucket (con prefijo opcional).
- upload_object():          subir contenido a una clave del bucket.
- download_object():        descargar el contenido de un objeto.
- generate_presigned_url():  generar una URL prefirmada de acceso temporal.

Las credenciales SIEMPRE provienen de variables de entorno RUVIC_AWS_S3_*
(ver config.S3Config.from_env). Prohibido hardcodearlas.

El conector opera sobre un único bucket configurado (principio de mínimo
privilegio: la política IAM del usuario debe limitarse a ese bucket).
"""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    EndpointConnectionError,
)

from .config import S3Config
from .exceptions import (
    S3AuthError,
    S3ConnectorError,
    S3DataError,
    S3NetworkError,
)
from .logging_utils import get_logger

_AUTH_ERROR_CODES = {
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
    "AccessDenied",
    "InvalidClientTokenId",
}
_NOT_FOUND_ERROR_CODES = {"NoSuchBucket", "NoSuchKey", "404"}
_MAX_LIST_LIMIT = 1_000
_MAX_URL_EXPIRES = 604_800  # 7 días, límite de AWS para SigV4


def _validate_key(key: str) -> str:
    if key is not None and not isinstance(key, str):
        raise S3DataError(f"key debe ser un string, no {type(key).__name__}.")
    key = (key or "").strip()
    if not key:
        raise S3DataError("key no puede estar vacía.")
    return key


def _validate_limit(limit: Any, max_limit: int) -> int:
    try:
        return max(1, min(int(limit), max_limit))
    except (TypeError, ValueError) as exc:
        raise S3DataError(f"limit inválido: {limit!r}. Debe ser un número entero.") from exc


def _wrap_client_error(exc: ClientError, not_found_message: str) -> S3ConnectorError:
    """Traduce un error de la API de S3 a una excepción propia, sin dejar
    escapar nunca el tipo crudo del SDK."""
    code = exc.response.get("Error", {}).get("Code", "")
    if code in _AUTH_ERROR_CODES:
        return S3AuthError(
            "Credenciales inválidas o sin permiso IAM suficiente sobre este "
            "bucket/objeto. Revisa la policy adjunta al usuario o rol."
        )
    if code in _NOT_FOUND_ERROR_CODES:
        return S3DataError(not_found_message)
    return S3DataError(f"Error de datos ({code}): {exc}")


class S3Client:
    """Cliente de gestión de objetos en un bucket de Amazon S3.

    Args:
        config: configuración de conexión. Si se omite, se lee de las
            variables de entorno RUVIC_AWS_S3_* (comportamiento estándar
            en el runtime de la plataforma).

    Ejemplo:
        >>> client = S3Client()             # lee RUVIC_AWS_S3_* del entorno
        >>> client.list_objects(prefix="reportes/")
        [{'key': 'reportes/2026-07.csv', 'size': 15234, 'last_modified': '2026-07-17T10:00:00Z'}]
    """

    def __init__(self, config: S3Config | None = None) -> None:
        self.config = config or S3Config.from_env()
        self._logger = get_logger()
        self._client: Any = None

    # ------------------------------------------------------------------ #
    # Conexión
    # ------------------------------------------------------------------ #

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        self._client = boto3.client(
            "s3",
            aws_access_key_id=self.config.access_key_id,
            aws_secret_access_key=self.config.secret_access_key,
            region_name=self.config.region,
            config=BotoConfig(
                connect_timeout=self.config.connect_timeout,
                read_timeout=self.config.connect_timeout,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        return self._client

    def ping(self) -> bool:
        """Verifica la conexión comprobando acceso al bucket configurado
        (HEAD del bucket, sin listar objetos).

        Returns:
            True si la conexión funciona.

        Raises:
            S3AuthError / S3NetworkError / S3DataError según el fallo.
        """
        try:
            self._get_client().head_bucket(Bucket=self.config.bucket)
        except ClientError as exc:
            raise _wrap_client_error(
                exc, f"El bucket {self.config.bucket!r} no existe o no es accesible."
            ) from exc
        except (EndpointConnectionError, BotoCoreError) as exc:
            raise S3NetworkError(
                f"No se pudo conectar al servicio S3 en la región "
                f"{self.config.region!r} (timeout {self.config.connect_timeout}s). "
                "Verifica la región y el acceso de red."
            ) from exc
        self._logger.info("Ping exitoso al bucket %s", self.config.bucket)
        return True

    # ------------------------------------------------------------------ #
    # Capacidad 1: listar objetos
    # ------------------------------------------------------------------ #

    def list_objects(self, prefix: str = "", limit: int = 100) -> list[dict[str, Any]]:
        """Lista los objetos del bucket configurado.

        Args:
            prefix: solo objetos cuya clave empiece con este prefijo
                (ej. "reportes/"). Default "" (todos).
            limit: máximo de objetos a retornar (default 100, máximo 1000).

        Returns:
            Lista de dicts: {"key", "size", "last_modified"} (last_modified
            en formato ISO 8601).

        Ejemplo:
            >>> client.list_objects(prefix="reportes/", limit=10)
            [{'key': 'reportes/2026-07.csv', 'size': 15234, 'last_modified': '2026-07-17T10:00:00Z'}]
        """
        limit = _validate_limit(limit, _MAX_LIST_LIMIT)
        client = self._get_client()
        try:
            response = client.list_objects_v2(
                Bucket=self.config.bucket, Prefix=prefix, MaxKeys=limit
            )
        except ClientError as exc:
            raise _wrap_client_error(
                exc, f"El bucket {self.config.bucket!r} no existe o no es accesible."
            ) from exc
        except (EndpointConnectionError, BotoCoreError) as exc:
            raise S3NetworkError(f"No se pudo listar objetos: {exc}") from exc

        result = [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            }
            for obj in response.get("Contents", [])
        ]
        self._logger.info(
            "Se listaron %d objetos (prefix=%r) en %s", len(result), prefix, self.config.bucket
        )
        return result

    # ------------------------------------------------------------------ #
    # Capacidad 2: subir un objeto
    # ------------------------------------------------------------------ #

    def upload_object(
        self,
        key: str,
        content: bytes | str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """Sube contenido a una clave del bucket configurado (crea el
        objeto o sobrescribe uno existente con la misma clave).

        Args:
            key: clave (ruta) del objeto dentro del bucket.
            content: contenido a subir. Un str se codifica como UTF-8.
            content_type: MIME type del objeto (opcional, ej. "text/csv").

        Returns:
            Dict con: key, size (bytes subidos).

        Ejemplo:
            >>> client.upload_object("reportes/resumen.txt", "Ventas: 1200")
            {'key': 'reportes/resumen.txt', 'size': 12}
        """
        key = _validate_key(key)
        body = content.encode("utf-8") if isinstance(content, str) else content
        client = self._get_client()
        extra: dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type
        try:
            client.put_object(Bucket=self.config.bucket, Key=key, Body=body, **extra)
        except ClientError as exc:
            raise _wrap_client_error(
                exc, f"El bucket {self.config.bucket!r} no existe o no es accesible."
            ) from exc
        except (EndpointConnectionError, BotoCoreError) as exc:
            raise S3NetworkError(f"No se pudo subir el objeto: {exc}") from exc
        self._logger.info('Subido objeto "%s" (%d bytes)', key, len(body))
        return {"key": key, "size": len(body)}

    # ------------------------------------------------------------------ #
    # Capacidad 3: descargar un objeto
    # ------------------------------------------------------------------ #

    def download_object(self, key: str) -> dict[str, Any]:
        """Descarga el contenido de un objeto del bucket configurado.

        Args:
            key: clave (ruta) del objeto dentro del bucket.

        Returns:
            Dict con: key, content (bytes), content_type, size.

        Ejemplo:
            >>> result = client.download_object("reportes/resumen.txt")
            >>> result["content"].decode("utf-8")
            'Ventas: 1200'
        """
        key = _validate_key(key)
        client = self._get_client()
        try:
            response = client.get_object(Bucket=self.config.bucket, Key=key)
            content = response["Body"].read()
        except ClientError as exc:
            raise _wrap_client_error(
                exc, f'El objeto "{key}" no existe en el bucket {self.config.bucket!r}.'
            ) from exc
        except (EndpointConnectionError, BotoCoreError) as exc:
            raise S3NetworkError(f"No se pudo descargar el objeto: {exc}") from exc
        self._logger.info('Descargado objeto "%s" (%d bytes)', key, len(content))
        return {
            "key": key,
            "content": content,
            "content_type": response.get("ContentType"),
            "size": len(content),
        }

    # ------------------------------------------------------------------ #
    # Capacidad 4: generar una URL prefirmada
    # ------------------------------------------------------------------ #

    def generate_presigned_url(
        self, key: str, expires_in: int = 3600, method: str = "get_object"
    ) -> str:
        """Genera una URL de acceso temporal a un objeto, sin exponer las
        credenciales de AWS.

        Args:
            key: clave (ruta) del objeto dentro del bucket.
            expires_in: segundos de validez de la URL (default 3600 = 1h,
                máximo 604800 = 7 días, límite de AWS).
            method: "get_object" (descarga) o "put_object" (subida) — el
                tipo de operación que la URL autoriza.

        Returns:
            URL prefirmada (str).

        Ejemplo:
            >>> client.generate_presigned_url("reportes/resumen.txt", expires_in=600)
            'https://mi-bucket.s3.amazonaws.com/reportes/resumen.txt?X-Amz-...'
        """
        key = _validate_key(key)
        if method not in ("get_object", "put_object"):
            raise S3DataError("method debe ser 'get_object' o 'put_object'.")
        if isinstance(expires_in, bool) or not isinstance(expires_in, int) or not 1 <= expires_in <= _MAX_URL_EXPIRES:
            raise S3DataError(f"expires_in debe ser un entero entre 1 y {_MAX_URL_EXPIRES} segundos.")
        client = self._get_client()
        try:
            url = client.generate_presigned_url(
                ClientMethod=method,
                Params={"Bucket": self.config.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except (ClientError, BotoCoreError) as exc:
            raise S3DataError(f"No se pudo generar la URL prefirmada: {exc}") from exc
        self._logger.info(
            'URL prefirmada generada para "%s" (method=%s, expires_in=%ds)',
            key, method, expires_in,
        )
        return url
