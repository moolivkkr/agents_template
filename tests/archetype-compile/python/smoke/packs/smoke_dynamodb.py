# databases/dynamodb.md: the fragment runs at import (a Query, then a conditional PutItem). moto serves
# DynamoDB in-process, so the real boto3 calls run without AWS; --live runs the same against LocalStack.
import importlib
import sys

import boto3
from botocore.exceptions import ClientError
from moto import mock_aws

from harness_stubs.dynamo import create_widgets_table

with mock_aws():
    create_widgets_table(boto3.resource("dynamodb"))
    mod = importlib.import_module("app.widgets_dynamo")
    assert mod.response["Count"] == 0, mod.response  # the Query ran before the PutItem
    item = boto3.resource("dynamodb").Table("Widgets").get_item(Key={"PK": "TENANT#t-1", "SK": "WIDGET#w-1"})
    assert item["Item"]["name"] == "Widget", item
    # attribute_not_exists(PK): the same put again is refused
    sys.modules.pop("app.widgets_dynamo")
    try:
        importlib.import_module("app.widgets_dynamo")
    except ClientError as exc:
        assert exc.response["Error"]["Code"] == "ConditionalCheckFailedException", exc.response
    else:
        raise AssertionError("the conditional put accepted a duplicate")
