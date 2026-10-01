# infrastructure/localstack-aws-local.md: without AWS_ENDPOINT_URL the clients use AWS's endpoints and the
# default credential chain; with it, the LocalStack endpoint. Creating a client makes no network call.
import importlib
import os

import app.aws_clients as clients

assert "amazonaws.com" in clients.s3.meta.endpoint_url, clients.s3.meta.endpoint_url
os.environ["AWS_ENDPOINT_URL"] = "http://localhost.localstack.cloud:4566"
try:
    clients = importlib.reload(clients)
    for c in (clients.s3, clients.kms, clients.sqs):
        assert c.meta.endpoint_url == "http://localhost.localstack.cloud:4566", c.meta.endpoint_url
finally:
    del os.environ["AWS_ENDPOINT_URL"]
