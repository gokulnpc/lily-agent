"""OpenSearch client over the VPC endpoint, SigV4-signed with the caller's IAM
(IRSA) credentials. Live-only — unit tests use the pure builders in index.py."""

from __future__ import annotations

from typing import Any

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection


def opensearch_client(endpoint: str, *, region: str = "us-east-1") -> OpenSearch:
    """`endpoint` is the domain host (no scheme), e.g. the terraform
    `opensearch_endpoint` output."""
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, region, "es")
    return OpenSearch(
        hosts=[{"host": endpoint, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=8,
    )


def ensure_index(client: Any, name: str, mapping: dict[str, Any]) -> bool:
    """Create the index if absent. Returns True if created."""
    if client.indices.exists(index=name):
        return False
    client.indices.create(index=name, body=mapping)
    return True
