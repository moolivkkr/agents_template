"""harness: a local AWS endpoint for the boto3 samples — moto's server mode, a real HTTP server on
127.0.0.1 that speaks the S3, SQS, KMS and DynamoDB wire protocols (what the samples' AWS_ENDPOINT_URL
override points at in local development). No Docker: LocalStack's current image needs a license."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from moto.server import ThreadedMotoServer


@pytest.fixture(scope="session")
def aws_endpoint_url() -> Iterator[str]:
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()
