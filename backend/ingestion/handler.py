from __future__ import annotations

import base64
import io
import json
import os
import uuid
from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from python_multipart import parse_form
from pydantic import ValidationError as PydanticValidationError

from shared.aws_utils import get_boto3_client
from shared.exceptions import (
    ConfigurationError,
    ExtractionError,
    StorageError,
    ValidationError,
    StorageErrorCode,
    ValidationErrorCode,
)
from ingestion.extractor import extract_text
from ingestion.models import ExtractionMetadata, ExtractionResult, build_dynamodb_item

# ---------------------------------------------------------------------------
# Inicialización a nivel de módulo (cold start)
# ---------------------------------------------------------------------------

logger = Logger(service="ingestion", level=os.getenv("LOG_LEVEL", "INFO"))

# Leer variables requeridas — falla en cold start si alguna falta
_DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE_NAME")
if not _DYNAMODB_TABLE:
    raise ConfigurationError("Variable de entorno requerida no definida: DYNAMODB_TABLE_NAME")

_S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
if not _S3_BUCKET:
    raise ConfigurationError("Variable de entorno requerida no definida: S3_BUCKET_NAME")

_AWS_REGION = os.environ.get("AWS_REGION")
if not _AWS_REGION:
    raise ConfigurationError("Variable de entorno requerida no definida: AWS_REGION")

# Clientes boto3 — respetan AWS_ENDPOINT_URL si está definida (LocalStack)
_s3_client = get_boto3_client("s3")
_dynamodb_client = get_boto3_client("dynamodb")

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
PDF_MAGIC_BYTES = b"%PDF"


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------


def _parse_multipart(event: dict) -> tuple[bytes, str]:
    """
    Extrae los bytes del PDF y el filename del evento de API Gateway.

    Returns:
        Tupla (pdf_bytes, filename).
    """
    body = event.get("body", "")
    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body)
    else:
        body = body.encode("latin-1") if isinstance(body, str) else body

    headers = event.get("headers", {}) or {}
    # Normalizar clave de Content-Type (API Gateway puede enviarlo en minúsculas)
    content_type = headers.get("Content-Type") or headers.get("content-type") or ""
    if not content_type:
        raise ValidationError(
            ValidationErrorCode.MISSING_FILE,
            "No se recibió ningún archivo en el campo 'file'.",
        )

    found_files: list[tuple[bytes, str]] = []
    _validation_error: ValidationError | None = None

    def on_file(file):
        nonlocal _validation_error

        # Validar que el campo se llame exactamente "file"
        # Usar getattr como defensa ante cambios de API en python-multipart
        field_name = (getattr(file, "field_name", None) or b"").decode("utf-8", errors="replace")
        if field_name != "file":
            return  # Ignorar cualquier otro campo

        # Validar Content-Type de la parte
        part_content_type = getattr(file, "content_type", None) or ""
        if part_content_type != "application/pdf":
            _validation_error = ValidationError(
                ValidationErrorCode.INVALID_FILE_TYPE,
                "El archivo debe ser un PDF válido.",
            )
            return

        # Leer todo el contenido acumulado por File en su buffer interno
        file_obj = getattr(file, "file_object", None)
        if file_obj is None:
            return
        file_obj.seek(0)
        file_data = file_obj.read()
        fname = (getattr(file, "file_name", None) or b"").decode("utf-8", errors="replace")
        found_files.append((file_data, fname))

    def on_field(field):
        pass  # Ignorar campos que no sean archivos

    stream = io.BytesIO(body)
    parse_form(
        headers={"Content-Type": content_type.encode("utf-8")},
        input_stream=stream,
        on_field=on_field,
        on_file=on_file,
    )

    # Propagar errores de validación detectados dentro del callback
    # (evita depender de cómo el parser maneje excepciones en callbacks)
    if _validation_error is not None:
        raise _validation_error

    if not found_files:
        raise ValidationError(
            ValidationErrorCode.MISSING_FILE,
            "No se recibió ningún archivo en el campo 'file'.",
        )

    pdf_data, fname = found_files[0]
    return pdf_data, fname


def _validate_pdf(pdf_bytes: bytes, filename: str) -> None:
    """Lanza ValidationError si el archivo no es un PDF válido o supera el límite."""
    if not pdf_bytes:
        raise ValidationError(
            ValidationErrorCode.MISSING_FILE,
            "No se recibió ningún archivo.",
        )
    if len(pdf_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            ValidationErrorCode.FILE_TOO_LARGE,
            "El archivo supera el límite de 10 MB.",
        )
    if not pdf_bytes.startswith(PDF_MAGIC_BYTES):
        raise ValidationError(
            ValidationErrorCode.INVALID_FILE_TYPE,
            "El archivo debe ser un PDF válido.",
        )


def _upload_to_s3(pdf_bytes: bytes, s3_key: str) -> None:
    """Sube el PDF a S3. Lanza StorageError si falla."""
    try:
        _s3_client.put_object(
            Bucket=_S3_BUCKET,
            Key=s3_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
    except Exception as exc:
        raise StorageError(
            StorageErrorCode.STORAGE_FAILURE,
            f"Error al subir a S3: {exc}",
        ) from exc


def _verify_s3_object(s3_key: str) -> None:
    """Verifica que el objeto existe en S3. Lanza StorageError si falla."""
    try:
        _s3_client.head_object(Bucket=_S3_BUCKET, Key=s3_key)
    except Exception as exc:
        raise StorageError(
            StorageErrorCode.STORAGE_FAILURE,
            f"Error al verificar objeto en S3: {exc}",
        ) from exc


def _persist_result(result: ExtractionResult) -> None:
    """Serializa ExtractionResult y escribe en DynamoDB. Lanza StorageError si falla."""
    logger.debug("Serializando ExtractionResult para DynamoDB", document_id=result.document_id)
    try:
        item = build_dynamodb_item(result)
        logger.debug("Escribiendo item en DynamoDB", document_id=result.document_id)
        _dynamodb_client.put_item(TableName=_DYNAMODB_TABLE, Item=item)
    except Exception as exc:
        raise StorageError(
            StorageErrorCode.PERSISTENCE_FAILURE,
            f"Error al escribir en DynamoDB: {exc}",
        ) from exc


def _http_response(status_code: int, body: dict) -> dict:
    """Formatea una respuesta HTTP compatible con API Gateway proxy integration."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context: object) -> dict:
    """
    Punto de entrada del Lambda de ingesta.

    Args:
        event: Evento de API Gateway (formato proxy integration).
        context: Contexto Lambda con aws_request_id.

    Returns:
        Dict con statusCode, headers y body serializado como JSON.
    """
    request_id = getattr(context, "aws_request_id", "local")
    logger.append_keys(request_id=request_id)

    document_id: str | None = None

    try:
        # 1. Parsear body multipart → bytes del PDF y filename
        pdf_bytes, filename = _parse_multipart(event)

        # 2. Validar PDF
        _validate_pdf(pdf_bytes, filename)

        # 3. Generar document_id
        document_id = str(uuid.uuid4())
        s3_key = f"contracts/{document_id}.pdf"

        # 4. Subir a S3
        _upload_to_s3(pdf_bytes, s3_key)

        # 5. Verificar objeto en S3 (Req. 2.3)
        _verify_s3_object(s3_key)

        # 6. Extraer texto
        uploaded_at = datetime.now(tz=timezone.utc)
        extraction = extract_text(
            pdf_bytes=pdf_bytes,
            document_id=document_id,
            s3_key=s3_key,
            s3_bucket=_S3_BUCKET,
        )

        # 7. Construir ExtractionResult completo — la validación Pydantic ocurre aquí
        logger.debug("Construyendo ExtractionResult", document_id=document_id)
        try:
            result = ExtractionResult(
                document_id=document_id,
                raw_text=extraction.raw_text,
                extraction_method=extraction.extraction_method,
                page_count=extraction.page_count,
                metadata=ExtractionMetadata(
                    filename=filename[:255],
                    uploaded_at=uploaded_at,
                ),
                ttl=int(uploaded_at.timestamp()) + 86400,
            )
        except PydanticValidationError as exc:
            logger.error(
                "Falla de validación al construir ExtractionResult",
                document_id=document_id,
                error=str(exc),
            )
            return _http_response(500, {
                "error_code": "VALIDATION_FAILURE",
                "message": "Error interno de validación de datos.",
            })

        # 8. Persistir en DynamoDB
        _persist_result(result)

        logger.info(
            "Extracción exitosa",
            document_id=document_id,
            extraction_method=result.extraction_method,
            page_count=result.page_count,
            file_name=filename,
        )

        return _http_response(200, {"document_id": document_id})

    except ValidationError as exc:
        logger.warning(
            "ValidationError",
            error_code=exc.error_code.value,
            error_message=exc.message,
        )
        status = 413 if exc.error_code.value == "FILE_TOO_LARGE" else 400
        return _http_response(status, {"error_code": exc.error_code.value, "message": exc.message})

    except StorageError as exc:
        logger.error(
            "StorageError",
            document_id=document_id,
            error_code=exc.error_code.value,
            error_message=exc.message,
        )
        return _http_response(502, {"error_code": exc.error_code.value, "message": exc.message})

    except ExtractionError as exc:
        is_empty = exc.error_code.value == "EMPTY_EXTRACTION"
        if is_empty:
            logger.warning(
                "ExtractionError",
                document_id=document_id,
                error_code=exc.error_code.value,
                error_message=exc.message,
            )
        else:
            logger.error(
                "ExtractionError",
                document_id=document_id,
                error_code=exc.error_code.value,
                error_message=exc.message,
            )
        body: dict = {"error_code": exc.error_code.value, "message": exc.message}
        # document_id solo se incluye en EMPTY_EXTRACTION (Contrato 3)
        if document_id and exc.error_code.value == "EMPTY_EXTRACTION":
            body["document_id"] = document_id
        return _http_response(422, body)

    except Exception as exc:
        logger.exception("Error inesperado", document_id=document_id)
        return _http_response(500, {
            "error_code": "INTERNAL_ERROR",
            "message": "Error interno del servidor.",
        })
