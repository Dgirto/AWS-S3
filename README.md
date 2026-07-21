# Conector AWS S3 (CON-023)

Conector Ruvic para gestión de objetos en un bucket de Amazon S3. Permite
listar objetos, subir contenido, descargar objetos y generar URLs
prefirmadas de acceso temporal.

## Instalación

```bash
pip install git+https://github.com/Dgirto/AWS-S3.git#subdirectory=lib
```

Python 3.10+. Dependencia única: `boto3>=1.34,<2.0`.

## Permisos requeridos en AWS

Crea un usuario IAM dedicado (no reutilizar credenciales root ni de otra
aplicación) con una policy limitada al bucket específico:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::mi-bucket-produccion"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::mi-bucket-produccion/*"
    }
  ]
}
```

- `s3:ListBucket` (sobre el bucket): necesario para `s3.list_objects`.
- `s3:GetObject` (sobre los objetos): necesario para `s3.download` y
  `s3.presigned_url` en modo lectura.
- `s3:PutObject` (sobre los objetos): necesario para `s3.upload` y
  `s3.presigned_url` en modo escritura.
- No se otorgan permisos de administración (`s3:DeleteBucket`,
  `s3:PutBucketPolicy`, `s3:PutBucketAcl`, etc.) ni acceso a otros buckets.

## Variables de entorno (`RUVIC_AWS_S3_*`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `RUVIC_AWS_S3_ACCESS_KEY_ID` | Sí | Access Key ID de IAM |
| `RUVIC_AWS_S3_SECRET_ACCESS_KEY` | Sí | Secret Access Key |
| `RUVIC_AWS_S3_REGION` | Sí | Región de AWS (ej. `us-east-1`) |
| `RUVIC_AWS_S3_BUCKET` | Sí | Bucket sobre el que opera el conector |
| `RUVIC_AWS_S3_CONNECT_TIMEOUT` | No (default `10`) | Timeout de conexión en segundos |

## Pruebas locales

Con AWS real (usuario IAM de pruebas y bucket dedicado) o con
[LocalStack](https://github.com/localstack/localstack) para no tocar una
cuenta real:

```bash
docker run -d --name s3-test -p 4566:4566 localstack/localstack

aws --endpoint-url=http://localhost:4566 s3 mb s3://ruvic-test-bucket
```

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ./lib

export RUVIC_AWS_S3_ACCESS_KEY_ID=test
export RUVIC_AWS_S3_SECRET_ACCESS_KEY=test
export RUVIC_AWS_S3_REGION=us-east-1
export RUVIC_AWS_S3_BUCKET=ruvic-test-bucket

# Con LocalStack hay que apuntar el endpoint; para AWS real no se necesita
# variable de entorno adicional, boto3 usa el endpoint estándar del servicio.
python test_connection.py
python validate_local.py
```

Prueba también los casos de error (credenciales incorrectas, bucket
inexistente, objeto inexistente) y verifica que los mensajes sean claros.

## Notas de integración

- El conector opera sobre **un único bucket** (configurado en
  `RUVIC_AWS_S3_BUCKET`), consistente con el principio de mínimo
  privilegio de la policy IAM recomendada.
- `upload_object` acepta `str` (se codifica UTF-8) o `bytes` directamente;
  `download_object` siempre retorna `bytes` en el campo `content`.
- `generate_presigned_url` nunca expone las credenciales de AWS: la URL
  incluye una firma temporal válida solo por el tiempo indicado en
  `expires_in` (máximo 7 días, límite de AWS SigV4).
- Reintentos: el cliente usa el modo `standard` de boto3 con 2 intentos
  máximo, para no ocultar errores reales bajo reintentos silenciosos
  excesivos.
