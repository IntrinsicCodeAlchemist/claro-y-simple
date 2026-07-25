from __future__ import annotations

import os
from typing import Optional

import boto3
from botocore.config import Config


def get_boto3_client(service_name: str, config: Optional[Config] = None):
    """
    Retorna un cliente boto3 apuntando a LocalStack si AWS_ENDPOINT_URL está definida.

    Si AWS_ENDPOINT_URL está presente en el entorno, se usa como endpoint_url.
    Si está ausente, boto3 usa los endpoints reales de AWS (comportamiento por defecto).
    Si se pasa `config`, se usa para construir el cliente (ej: timeouts).
    """
    kwargs: dict = {}
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if config is not None:
        kwargs["config"] = config
    return boto3.client(service_name, **kwargs)
