"""Validación local del conector aws_s3: ejercita las 4 capacidades.

Uso:
    python validate_local.py

Requiere las variables RUVIC_AWS_S3_* exportadas en el entorno, apuntando
a un bucket real (o LocalStack) donde el usuario/rol tenga permiso de
lectura y escritura. No necesita ningún objeto previo: sube uno de
prueba, lo lista, lo descarga y genera una URL prefirmada.
"""

from ruvic_aws_s3_connector import S3Client, setup_logging

setup_logging("INFO")
client = S3Client()

print("== 1. Subir objeto de prueba ==")
uploaded = client.upload_object(
    "ruvic/validate_local/prueba.txt", "Contenido de prueba de validate_local.py"
)
print(f"  {uploaded}")

print("== 2. Listar objetos (prefijo ruvic/validate_local/) ==")
objects = client.list_objects(prefix="ruvic/validate_local/", limit=10)
for obj in objects:
    print(f"  {obj['key']} ({obj['size']} bytes, {obj['last_modified']})")
assert any(o["key"] == "ruvic/validate_local/prueba.txt" for o in objects), "No aparece el objeto subido"

print("== 3. Descargar el objeto ==")
downloaded = client.download_object("ruvic/validate_local/prueba.txt")
text = downloaded["content"].decode("utf-8")
print(f"  contenido={text!r} size={downloaded['size']}")
assert text == "Contenido de prueba de validate_local.py", "El contenido descargado no coincide"

print("== 4. Generar URL prefirmada ==")
url = client.generate_presigned_url("ruvic/validate_local/prueba.txt", expires_in=300)
print(f"  {url}")
assert url.startswith("http"), "La URL prefirmada no tiene el formato esperado"

print("\nTodo OK: upload_object, list_objects, download_object y generate_presigned_url funcionan.")
