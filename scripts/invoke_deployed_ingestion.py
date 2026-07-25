"""Invoca el IngestionFunction YA DEPLOYADO en AWS real (no local) para confirmar
que el paquete Lambda arranca sin ModuleNotFoundError. Descartable."""
import argparse
import base64
import json
from pathlib import Path

import boto3

FUNCTION_NAME = "claro-y-simple-dev-IngestionFunction-f6lHayOr4p3C"
REGION = "us-east-1"

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF = _REPO_ROOT / "backend" / "ingestion" / "scan_contrato_prueba.pdf"


def build_multipart_event(pdf_bytes: bytes, filename: str) -> dict:
    boundary = "----RealTextractTest"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = header + pdf_bytes + footer
    return {
        "body": base64.b64encode(body).decode("ascii"),
        "isBase64Encoded": True,
        "headers": {"Content-Type": f"multipart/form-data; boundary={boundary}"},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Invoca el IngestionFunction deployado con un PDF de prueba."
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        type=Path,
        default=DEFAULT_PDF,
        help=f"Ruta al PDF a enviar (default: {DEFAULT_PDF}).",
    )
    args = parser.parse_args()

    pdf_path = args.pdf_path
    event = build_multipart_event(pdf_path.read_bytes(), pdf_path.name)

    client = boto3.client("lambda", region_name=REGION)
    response = client.invoke(
        FunctionName=FUNCTION_NAME,
        Payload=json.dumps(event).encode("utf-8"),
    )
    payload = response["Payload"].read().decode("utf-8")
    print("StatusCode:", response["StatusCode"])
    print("FunctionError:", response.get("FunctionError", "(ninguno)"))
    print(json.dumps(json.loads(payload), indent=2, ensure_ascii=False))