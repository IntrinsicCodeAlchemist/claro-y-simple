"""Script descartable para validar el camino real de Textract contra AWS.
No forma parte de tasks.md. Es solo para prueba manual.

Uso (desde la raíz del repo):
    cd backend/ingestion
    set -a; source .env; set +a
    cd ../..
    python scripts/test_textract_real.py <ruta-al-pdf>
"""
import base64
import json
import sys
from pathlib import Path

# El script vive en scripts/, y los módulos del proyecto asumen:
#   - backend/ en sys.path  (para from shared.exceptions import ...)
#   - raíz del repo en sys.path  (para from backend.ingestion import ...)
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
for _p in (_REPO_ROOT, _BACKEND_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.ingestion.handler import lambda_handler  # noqa: E402


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


class FakeContext:
    aws_request_id = "adhoc-textract-real-test"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/test_textract_real.py <ruta-al-pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"No se encontró el archivo: {pdf_path}")
        sys.exit(1)

    event = build_multipart_event(pdf_path.read_bytes(), pdf_path.name)
    response = lambda_handler(event, FakeContext())
    print("statusCode:", response["statusCode"])
    print(json.dumps(json.loads(response["body"]), indent=2, ensure_ascii=False))