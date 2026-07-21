from __future__ import annotations

import os

import boto3


def get_boto3_client(service_name: str):
    """
    Retorna un cliente boto3 apuntando a LocalStack si AWS_ENDPOINT_URL está definida.

    Si AWS_ENDPOINT_URL está presente en el entorno, se usa como endpoint_url.
    Si está ausente, boto3 usa los endpoints reales de AWS (comportamiento por defecto).
    """
    kwargs: dict = {}
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client(service_name, **kwargs)
