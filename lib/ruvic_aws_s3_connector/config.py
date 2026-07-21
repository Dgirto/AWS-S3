"""Configuración del conector leída desde variables de entorno.

Convención de la plataforma: cada campo del formulario de configuración
llega como variable de entorno {ENV_PREFIX}{CAMPO} en mayúsculas.
Para este conector el prefijo es RUVIC_AWS_S3_.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENV_PREFIX = "RUVIC_AWS_S3_"


@dataclass(frozen=True)
class S3Config:
    """Parámetros de conexión a Amazon S3."""

    access_key_id: str
    secret_access_key: str
    region: str
    bucket: str
    connect_timeout: int = 10

    @classmethod
    def from_env(cls) -> "S3Config":
        """Construye la configuración desde las variables RUVIC_AWS_S3_*.

        Raises:
            ValueError: si falta alguna variable obligatoria.

        Ejemplo:
            >>> config = S3Config.from_env()
            >>> config.bucket
            'mi-bucket-produccion'
        """
        missing = [
            f"{ENV_PREFIX}{name}"
            for name in ("ACCESS_KEY_ID", "SECRET_ACCESS_KEY", "REGION", "BUCKET")
            if not os.environ.get(f"{ENV_PREFIX}{name}")
        ]
        if missing:
            raise ValueError(
                "Faltan variables de entorno del conector aws_s3: "
                + ", ".join(missing)
                + ". Configura el conector en Settings → Conectores."
            )
        return cls(
            access_key_id=os.environ[f"{ENV_PREFIX}ACCESS_KEY_ID"],
            secret_access_key=os.environ[f"{ENV_PREFIX}SECRET_ACCESS_KEY"],
            region=os.environ[f"{ENV_PREFIX}REGION"],
            bucket=os.environ[f"{ENV_PREFIX}BUCKET"],
            connect_timeout=int(os.environ.get(f"{ENV_PREFIX}CONNECT_TIMEOUT", "10")),
        )
