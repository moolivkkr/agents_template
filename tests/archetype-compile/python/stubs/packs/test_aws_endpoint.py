"""harness: the boto3 samples over HTTP against a local AWS endpoint (databases/dynamodb.md,
infrastructure/localstack-aws-local.md). boto3 reads AWS_ENDPOINT_URL from the environment."""
from __future__ import annotations

import importlib
import sys
import uuid

import boto3
import pytest
from botocore.exceptions import ClientError

from harness_stubs.dynamo import create_widgets_table


@pytest.fixture
def aws_env(aws_endpoint_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("AWS_ENDPOINT_URL", aws_endpoint_url)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    return aws_endpoint_url


def test_dynamodb_query_and_conditional_put(aws_env: str, monkeypatch: pytest.MonkeyPatch) -> None:
    dynamodb = boto3.resource("dynamodb")
    if "Widgets" not in [t.name for t in dynamodb.tables.all()]:
        create_widgets_table(dynamodb)
    sk = f"WIDGET#{uuid.uuid4()}"
    monkeypatch.setenv("HARNESS_WIDGET_SK", sk)
    sys.modules.pop("harness_stubs.dynamo", None)
    sys.modules.pop("app.widgets_dynamo", None)
    importlib.import_module("app.widgets_dynamo")
    assert dynamodb.Table("Widgets").get_item(Key={"PK": "TENANT#t-1", "SK": sk})["Item"]["name"] == "Widget"
    sys.modules.pop("app.widgets_dynamo")
    with pytest.raises(ClientError) as exc_info:
        importlib.import_module("app.widgets_dynamo")
    assert exc_info.value.response["Error"]["Code"] == "ConditionalCheckFailedException"
    sys.modules.pop("app.widgets_dynamo", None)


def test_localstack_clients(aws_env: str) -> None:
    import app.aws_clients

    clients = importlib.reload(app.aws_clients)
    assert clients.s3.meta.endpoint_url == aws_env
    bucket = f"harness-{uuid.uuid4().hex[:12]}"
    clients.s3.create_bucket(Bucket=bucket)
    clients.s3.put_object(Bucket=bucket, Key="a.txt", Body=b"hello")
    assert clients.s3.get_object(Bucket=bucket, Key="a.txt")["Body"].read() == b"hello"

    key_id = clients.kms.create_key()["KeyMetadata"]["KeyId"]
    blob = clients.kms.encrypt(KeyId=key_id, Plaintext=b"secret")["CiphertextBlob"]
    assert clients.kms.decrypt(CiphertextBlob=blob)["Plaintext"] == b"secret"

    url = clients.sqs.create_queue(QueueName=f"harness-{uuid.uuid4().hex[:12]}")["QueueUrl"]
    clients.sqs.send_message(QueueUrl=url, MessageBody="ping")
    msgs = clients.sqs.receive_message(QueueUrl=url, WaitTimeSeconds=1).get("Messages", [])
    assert [m["Body"] for m in msgs] == ["ping"]
