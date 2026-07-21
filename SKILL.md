---
name: aws-s3
description: >
  Usa la librería ruvic_aws_s3_connector para gestionar objetos en un
  bucket de Amazon S3 - listar objetos con prefijo (list_objects), subir
  contenido a una clave (upload_object), descargar el contenido de un
  objeto (download_object) y generar una URL de acceso temporal
  (generate_presigned_url). Úsala cuando el usuario pida subir, descargar,
  listar o compartir archivos en un bucket de S3.
triggers:
- s3
- aws s3
- bucket
- amazon s3
- subir archivo
- descargar archivo
---

# Conector AWS S3 (ruvic_aws_s3_connector)

Librería Python para gestionar objetos en un bucket de Amazon S3. Está **preinstalada en el runtime** cuando el conector está configurado (si no, instálala con `pip install git+https://github.com/Dgirto/AWS-S3.git#subdirectory=lib`).

## Regla crítica de credenciales

El código generado **NUNCA hardcodea credenciales**. Siempre se leen de variables de entorno, disponibles cuando el conector `aws_s3` está configurado:

| Variable | Contenido |
|----------|-----------|
| `RUVIC_AWS_S3_ACCESS_KEY_ID` | Access Key ID de IAM |
| `RUVIC_AWS_S3_SECRET_ACCESS_KEY` | Secret Access Key |
| `RUVIC_AWS_S3_REGION` | Región de AWS (ej. `us-east-1`) |
| `RUVIC_AWS_S3_BUCKET` | Bucket sobre el que opera el conector |
| `RUVIC_AWS_S3_CONNECT_TIMEOUT` | (opcional) timeout en segundos |

Si estas variables NO existen, el conector no está configurado: no generes código que lo use; indica al usuario que lo configure en **Settings → Conectores**.

## Este conector escribe (upload)

`upload_object` sube (o sobrescribe) contenido en el bucket configurado. No es de solo lectura.

## Conexión (siempre igual)

```python
from ruvic_aws_s3_connector import S3Client

client = S3Client()  # lee RUVIC_AWS_S3_* del entorno automáticamente
```

Todas las operaciones actúan sobre el bucket único configurado en `RUVIC_AWS_S3_BUCKET`; no hace falta (ni se puede) indicar otro bucket.

## Capacidad 1 — Listar objetos

```python
objects = client.list_objects(prefix="reportes/", limit=50)
for obj in objects:
    print(f"{obj['key']}: {obj['size']} bytes, modificado {obj['last_modified']}")
```

## Capacidad 2 — Subir un objeto

```python
client.upload_object("reportes/resumen.txt", "Ventas: 1200 unidades")
client.upload_object("reportes/datos.csv", contenido_bytes, content_type="text/csv")
```

`content` acepta `str` (se codifica como UTF-8) o `bytes` directamente.

## Capacidad 3 — Descargar un objeto

```python
result = client.download_object("reportes/resumen.txt")
texto = result["content"].decode("utf-8")
print(texto)
```

`content` siempre viene como `bytes`; decodifica según el tipo de archivo (texto, imagen, binario).

## Capacidad 4 — Generar una URL prefirmada

```python
url = client.generate_presigned_url("reportes/resumen.txt", expires_in=3600)
print(f"Enlace válido por 1 hora: {url}")
```

Genera un enlace temporal sin exponer las credenciales de AWS — útil para compartir un archivo con alguien que no tiene acceso al bucket. `method="put_object"` genera en cambio una URL para subir un archivo directamente (sin pasar por el conector).

## Manejo de errores

```python
from ruvic_aws_s3_connector import (
    S3AuthError, S3DataError, S3NetworkError,
)

try:
    client.upload_object("clave", "contenido")
except S3AuthError:
    print("Credenciales inválidas o sin permiso IAM sobre el bucket")
except S3NetworkError:
    print("No se pudo alcanzar S3 — revisa la región y el acceso de red")
except S3DataError as e:
    print(f"Error de datos: {e}")  # ej. el objeto no existe
```

## Buenas prácticas al generar código

1. Lee credenciales SOLO de las variables `RUVIC_AWS_S3_*` (el constructor de `S3Client` ya lo hace).
2. Nunca imprimas `RUVIC_AWS_S3_SECRET_ACCESS_KEY` en logs ni en la salida.
3. Usa `limit` razonable en `list_objects` (default 100, máximo 1000); para buckets grandes pide al usuario que acote el `prefix`.
4. `generate_presigned_url` es la forma correcta de compartir un archivo con terceros — nunca descargues el contenido y lo reenvíes si una URL temporal sirve igual.
5. `expires_in` máximo permitido por AWS es 604800 segundos (7 días).
