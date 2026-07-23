from __future__ import annotations

import io
import os
from dataclasses import dataclass

import pdfplumber
from aws_lambda_powertools import Logger
from shared.aws_utils import get_boto3_client
from shared.exceptions import ExtractionError, ExtractionErrorCode

logger = Logger(service="ingestion", level=os.getenv("LOG_LEVEL", "INFO"))

# Cliente Textract inicializado a nivel de módulo (respeta AWS_ENDPOINT_URL)
_textract_client = get_boto3_client("textract")


@dataclass
class _PartialExtraction:
    """Resultado intermedio antes de agregar metadata."""
    raw_text: str
    extraction_method: str   # "text" | "ocr"
    page_count: int


def extract_text(
    pdf_bytes: bytes,
    document_id: str,
    s3_key: str,
    s3_bucket: str,
) -> _PartialExtraction:
    """
    Extrae texto de un PDF. Intenta pdfplumber primero; si falla o produce
    texto vacío, usa Amazon Textract como fallback.

    Args:
        pdf_bytes: Contenido binario del PDF.
        document_id: UUID del documento (para logging).
        s3_key: Clave S3 donde el PDF ya fue almacenado (para Textract).
        s3_bucket: Nombre del bucket S3.

    Returns:
        _PartialExtraction con raw_text, extraction_method y page_count.

    Raises:
        ExtractionError: Si ambos métodos fallan o producen texto vacío.
    """
    # --- Intento 1: pdfplumber ---
    logger.debug("Iniciando extracción con pdfplumber", document_id=document_id)
    try:
        text, page_count = _extract_with_pdfplumber(pdf_bytes, document_id)
        if text.strip():
            logger.debug(
                "pdfplumber extrajo texto exitosamente",
                document_id=document_id,
                page_count=page_count,
                text_length=len(text),
            )
            return _PartialExtraction(raw_text=text, extraction_method="text", page_count=page_count)
        else:
            logger.warning(
                "pdfplumber produjo texto vacío, usando fallback Textract",
                document_id=document_id,
            )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "pdfplumber lanzó excepción",
            document_id=document_id,
            error=str(exc),
        )

    # --- Intento 2: Textract (fallback) ---
    logger.debug("Iniciando extracción con Textract", document_id=document_id, s3_key=s3_key)
    return _extract_with_textract(s3_bucket, s3_key, document_id)


def _extract_with_pdfplumber(pdf_bytes: bytes, document_id: str) -> tuple[str, int]:
    """
    Abre el PDF desde memoria con pdfplumber.

    Returns:
        Tupla (texto_concatenado, page_count).
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)
        pages_text = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages_text), page_count


def _extract_with_textract(s3_bucket: str, s3_key: str, document_id: str) -> _PartialExtraction:
    """
    Llama a Textract DetectDocumentText usando el objeto S3 ya subido.

    Returns:
        _PartialExtraction con extraction_method="ocr".

    Raises:
        ExtractionError: TEXTRACT_FAILURE, S3_OBJECT_NOT_FOUND, o EMPTY_EXTRACTION.
    """
    try:
        response = _textract_client.detect_document_text(
            Document={"S3Object": {"Bucket": s3_bucket, "Name": s3_key}}
        )
    except _textract_client.exceptions.InvalidS3ObjectException as exc:
        raise ExtractionError(
            ExtractionErrorCode.S3_OBJECT_NOT_FOUND,
            f"Objeto S3 no encontrado: {exc}",
        ) from exc
    except Exception as exc:
        logger.error("Textract lanzó excepción", document_id=document_id, error=str(exc))
        raise ExtractionError(
            ExtractionErrorCode.TEXTRACT_FAILURE,
            f"Error en Textract: {exc}",
        ) from exc

    # Parsear Blocks de tipo LINE
    blocks = response.get("Blocks", [])
    lines = [b["Text"] for b in blocks if b.get("BlockType") == "LINE" and b.get("Text")]
    raw_text = "\n".join(lines)

    if not raw_text.strip():
        raise ExtractionError(
            ExtractionErrorCode.EMPTY_EXTRACTION,
            "El documento no contiene texto extraíble por ningún método.",
        )

    # Textract no reporta page_count directamente; contar PAGEs en Blocks
    page_count = len({b["Page"] for b in blocks if "Page" in b}) or 1

    logger.debug(
        "Textract extrajo texto exitosamente",
        document_id=document_id,
        page_count=page_count,
        text_length=len(raw_text),
    )

    return _PartialExtraction(raw_text=raw_text, extraction_method="ocr", page_count=page_count)
