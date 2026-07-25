"""
Script ad-hoc para validar la invocación real a Amazon Bedrock.
NO es parte de tasks.md. Descartar cuando ya no sea necesario.

Este script NO usa mocks. Requiere credenciales AWS reales y acceso a Bedrock.

Modos de uso
============

Modo A — desde DynamoDB (requiere document_id con extracción previa en ContractExtractions):

    cd backend/analysis
    set -a; source .env; set +a
    cd ../..
    python scripts/test_bedrock_real.py --document-id <uuid>

Modo B — desde archivo de texto plano (no toca DynamoDB):

    cd backend/analysis
    set -a; source .env; set +a
    cd ../..
    python scripts/test_bedrock_real.py --raw-text-file <path/al/archivo.txt>

Variables de entorno requeridas (cargar desde .env antes de correr):
  - AWS_DEFAULT_REGION
  - BEDROCK_MODEL_ID
  - BEDROCK_TIMEOUT_SECONDS
  - MAX_CONTEXT_CHARS
  Para modo A también:
  - EXTRACTIONS_TABLE_NAME
  - ANALYSES_TABLE_NAME
"""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

# La raíz del repo debe estar en sys.path para que los imports
# absolutos de backend.* resuelvan sin backend/__init__.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.analysis.analyzer import (  # noqa: E402
    build_prompt,
    calculate_risk_score,
    invoke_bedrock,
    validate_context_length,
)
from backend.analysis.handler import lambda_handler  # noqa: E402
from backend.analysis.models import AnalysisResult, Clause  # noqa: E402


class FakeContext:
    aws_request_id = "adhoc-bedrock-real-test"


def _extract_json(raw: str) -> str:
    """Extrae JSON de la respuesta aunque el modelo lo envuelva en ```json ... ```."""
    stripped = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", stripped)
    if match:
        return match.group(1).strip()
    return stripped


def mode_document_id(document_id: str) -> None:
    event = {"body": json.dumps({"document_id": document_id})}
    result = lambda_handler(event, FakeContext())
    print(f"statusCode: {result['statusCode']}")
    body = json.loads(result["body"])
    print(json.dumps(body, ensure_ascii=False, indent=2))


def mode_raw_text_file(file_path: str) -> None:
    raw_text = Path(file_path).read_text(encoding="utf-8")
    document_id = str(uuid.uuid4())
    print(f"document_id generado: {document_id}")

    validate_context_length(raw_text)
    prompt = build_prompt(raw_text)
    raw_response = invoke_bedrock(prompt)

    print("\n--- RAW RESPONSE FROM BEDROCK ---")
    print(repr(raw_response[:500]))
    print("---\n")

    json_str = _extract_json(raw_response)
    data = json.loads(json_str)

    model_clauses = data.get("clauses", [])
    clauses = [
        Clause(
            clause_text=c["clause_text"],
            category=c["category"],
            risk_level=c["risk_level"],
            explanation=c["explanation"],
            suggested_question=c["suggested_question"],
        )
        for c in model_clauses
    ]
    risk_score = calculate_risk_score(clauses)

    result = AnalysisResult(
        document_id=document_id,
        summary_plain=data["summary_plain"],
        risk_score=risk_score,
        clauses=clauses,
        overall_recommendation=data["overall_recommendation"],
    )
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Valida invocación real a Bedrock (sin mocks)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--document-id",
        metavar="UUID",
        help="UUID de un documento ya procesado en ContractExtractions.",
    )
    group.add_argument(
        "--raw-text-file",
        metavar="PATH",
        help="Ruta a un archivo de texto plano. Llama a analyze_contract directamente.",
    )
    args = parser.parse_args()

    if args.document_id:
        mode_document_id(args.document_id)
    else:
        mode_raw_text_file(args.raw_text_file)


if __name__ == "__main__":
    main()
