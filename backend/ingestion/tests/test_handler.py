"""Tests unitarios del handler de ingesta."""
import base64
import json
import re
from unittest.mock import patch

from botocore.exceptions import ClientError

from ingestion.handler import lambda_handler, MAX_FILE_SIZE_BYTES
from shared.exceptions import ExtractionError, ExtractionErrorCode


class TestHandlerSuccessTextExtraction:
    """Camino feliz: PDF con texto embebido → extracción exitosa."""

    def test_returns_status_code_200(self, lambda_context, sample_pdf_bytes):
        """Verifica que el handler retorne HTTP 200 en el camino feliz."""
        event = build_multipart_event(sample_pdf_bytes)

        with (
            patch("ingestion.handler._s3_client") as mock_s3,
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            mock_s3.put_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_s3.head_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_dynamo.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 200

    def test_response_contains_document_id(self, lambda_context, sample_pdf_bytes):
        """Verifica que el body de la respuesta contenga un document_id."""
        event = build_multipart_event(sample_pdf_bytes)

        with (
            patch("ingestion.handler._s3_client") as mock_s3,
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            mock_s3.put_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_s3.head_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_dynamo.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

            response = lambda_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert "document_id" in body
        # Debe ser un UUID v4
        assert re.match(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
            body["document_id"],
        )

    def test_put_item_called_once(self, lambda_context, sample_pdf_bytes):
        """Verifica que put_item sea llamado exactamente una vez."""
        event = build_multipart_event(sample_pdf_bytes)

        with (
            patch("ingestion.handler._s3_client") as mock_s3,
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            mock_s3.put_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_s3.head_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_dynamo.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

            lambda_handler(event, lambda_context)

        assert mock_dynamo.put_item.call_count == 1

    def test_put_item_has_contract1_fields(self, lambda_context, sample_pdf_bytes):
        """Verifica que el ítem escrito en DynamoDB tenga los campos del Contrato 1."""
        event = build_multipart_event(sample_pdf_bytes)

        with (
            patch("ingestion.handler._s3_client") as mock_s3,
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            mock_s3.put_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_s3.head_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_dynamo.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

            lambda_handler(event, lambda_context)

        # Obtener el item del primer (y único) put_item
        call_args = mock_dynamo.put_item.call_args
        item = call_args[1]["Item"]

        # Verificar campos del Contrato 1
        assert "document_id" in item
        assert "raw_text" in item
        assert "extraction_method" in item
        assert item["extraction_method"]["S"] == "text"
        assert "page_count" in item
        assert int(item["page_count"]["N"]) >= 1
        assert "metadata" in item
        assert "filename" in item["metadata"]["M"]
        assert "uploaded_at" in item["metadata"]["M"]
        uploaded_at = item["metadata"]["M"]["uploaded_at"]["S"]
        assert re.match(
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$',
            uploaded_at,
        ), f"uploaded_at no cumple ISO 8601 UTC: {uploaded_at}"
        # Verificar campo extra ttl
        assert "ttl" in item


def build_multipart_event(
    pdf_bytes: bytes,
    filename: str = "sample_text.pdf",
    *,
    field_name: str = "file",
    part_content_type: str = "application/pdf",
) -> dict:
    """Construye un evento de API Gateway con multipart/form-data.

    Args:
        pdf_bytes: Contenido binario del PDF.
        filename: Nombre del archivo en Content-Disposition.
        field_name: Nombre del campo multipart (por defecto "file").
        part_content_type: Content-Type de la parte (por defecto "application/pdf").

    Returns:
        Dict con el evento listo para pasar a lambda_handler.
    """
    boundary = "----TestBoundary456"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {part_content_type}\r\n\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = header + pdf_bytes + footer

    return {
        "body": base64.b64encode(body).decode("ascii"),
        "isBase64Encoded": True,
        "headers": {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    }


class TestHandlerValidationErrors:
    """Casos de error de validación de archivo."""

    def test_handler_invalid_content_type(self, lambda_context, sample_pdf_bytes):
        """Content-Type de la parte multipart distinto de application/pdf → 400 INVALID_FILE_TYPE."""
        event = build_multipart_event(sample_pdf_bytes, part_content_type="text/plain")

        with (
            patch("ingestion.handler._s3_client"),
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "INVALID_FILE_TYPE"
        # Verificar que no se haya escrito nada en DynamoDB
        mock_dynamo.put_item.assert_not_called()

    def test_handler_wrong_field_name(self, lambda_context, sample_pdf_bytes):
        """Campo multipart distinto de 'file' → 400 MISSING_FILE."""
        event = build_multipart_event(sample_pdf_bytes, field_name="document")

        with (
            patch("ingestion.handler._s3_client"),
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "MISSING_FILE"
        mock_dynamo.put_item.assert_not_called()


class TestHandlerFileValidationErrors:
    """Task 13: Errores de validación de archivo."""

    def test_handler_missing_file(self, lambda_context):
        """Sin archivo en el multipart → 400 MISSING_FILE."""
        boundary = "----TestBoundary456"
        event = {
            "body": base64.b64encode(
                ("--" + boundary + "--\r\n").encode()
            ).decode("ascii"),
            "isBase64Encoded": True,
            "headers": {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        }

        with (
            patch("ingestion.handler._s3_client"),
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "MISSING_FILE"
        mock_dynamo.put_item.assert_not_called()

    def test_handler_invalid_file_type(self, lambda_context):
        """Archivo .txt en vez de PDF → 400 INVALID_FILE_TYPE."""
        event = build_multipart_event(
            b"Esto no es un PDF",
            filename="sample.txt",
            part_content_type="text/plain",
        )

        with (
            patch("ingestion.handler._s3_client"),
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "INVALID_FILE_TYPE"
        mock_dynamo.put_item.assert_not_called()

    def test_handler_file_too_large(self, lambda_context):
        """Archivo de 11 MB → 413 FILE_TOO_LARGE."""
        large_bytes = b"0" * (MAX_FILE_SIZE_BYTES + 1)
        event = build_multipart_event(large_bytes)

        with (
            patch("ingestion.handler._s3_client"),
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 413
        body = json.loads(response["body"])
        assert body["error_code"] == "FILE_TOO_LARGE"
        mock_dynamo.put_item.assert_not_called()


class TestHandlerEmptyExtraction:
    """Task 14: EMPTY_EXTRACTION sin escritura en DynamoDB."""

    def test_handler_empty_extraction_no_dynamo_write(self, lambda_context, empty_pdf_bytes):
        """PDF sin texto extraíble → 422 EMPTY_EXTRACTION con document_id, sin put_item."""
        event = build_multipart_event(empty_pdf_bytes)

        with (
            patch("ingestion.handler._s3_client") as mock_s3,
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
            patch("ingestion.handler.extract_text") as mock_extract,
        ):
            mock_extract.side_effect = ExtractionError(
                ExtractionErrorCode.EMPTY_EXTRACTION,
                "El documento no contiene texto extraíble.",
            )
            mock_s3.put_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_s3.head_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 422
        body = json.loads(response["body"])
        assert body["error_code"] == "EMPTY_EXTRACTION"
        assert "document_id" in body
        assert re.match(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
            body["document_id"],
        ), f"document_id no es un UUID v4 válido: {body['document_id']}"
        mock_dynamo.put_item.assert_not_called()


class TestHandlerInfrastructureFailures:
    """Task 15: Fallas de infraestructura S3 y DynamoDB."""

    def test_handler_s3_upload_failure(self, lambda_context, sample_pdf_bytes):
        """S3.put_object lanza ClientError → 502 STORAGE_FAILURE, sin put_item."""
        event = build_multipart_event(sample_pdf_bytes)
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}

        with (
            patch("ingestion.handler._s3_client") as mock_s3,
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            mock_s3.put_object.side_effect = ClientError(error_response, "PutObject")

            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 502
        body = json.loads(response["body"])
        assert body["error_code"] == "STORAGE_FAILURE"
        mock_dynamo.put_item.assert_not_called()

    def test_handler_dynamodb_persistence_failure(self, lambda_context, sample_pdf_bytes):
        """S3 OK, DynamoDB.put_item lanza ClientError → 502 PERSISTENCE_FAILURE."""
        event = build_multipart_event(sample_pdf_bytes)
        error_response = {
            "Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Slow down"},
        }

        with (
            patch("ingestion.handler._s3_client") as mock_s3,
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
        ):
            mock_s3.put_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_s3.head_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_dynamo.put_item.side_effect = ClientError(error_response, "PutItem")

            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 502
        body = json.loads(response["body"])
        assert body["error_code"] == "PERSISTENCE_FAILURE"


class TestHandlerTextractErrors:
    """Task 16: Errores de Textract en el handler."""

    def test_handler_textract_failure_returns_422(self, lambda_context, sample_pdf_bytes):
        """Textract lanza excepción → 422 TEXTRACT_FAILURE, sin put_item."""
        event = build_multipart_event(sample_pdf_bytes)

        with (
            patch("ingestion.handler._s3_client") as mock_s3,
            patch("ingestion.handler._dynamodb_client") as mock_dynamo,
            patch("ingestion.handler.extract_text") as mock_extract,
        ):
            mock_extract.side_effect = ExtractionError(
                ExtractionErrorCode.TEXTRACT_FAILURE,
                "Error en Textract: connection timeout",
            )
            mock_s3.put_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_s3.head_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 422
        body = json.loads(response["body"])
        assert body["error_code"] == "TEXTRACT_FAILURE"
        assert "document_id" not in body, "document_id no debe aparecer en errores que no sean EMPTY_EXTRACTION"
        mock_dynamo.put_item.assert_not_called()


class TestHandlerInternalError:
    """Task 17: Error interno inesperado."""

    def test_handler_internal_error(self, lambda_context, sample_pdf_bytes):
        """uuid.uuid4() lanza Exception → 500 INTERNAL_ERROR sin detalles internos."""
        event = build_multipart_event(sample_pdf_bytes)

        with (
            patch("ingestion.handler._s3_client"),
            patch("ingestion.handler._dynamodb_client"),
            patch("uuid.uuid4", side_effect=Exception("unexpected failure")),
        ):
            response = lambda_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error_code"] == "INTERNAL_ERROR"
        # El mensaje no debe exponer detalles internos
        assert "unexpected" not in body["message"]
        assert "Error interno" in body["message"]
