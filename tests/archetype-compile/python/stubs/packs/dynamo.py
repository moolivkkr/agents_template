"""harness: the values databases/dynamodb.md's fragment uses (the caller's tenant, the item to write)."""
from __future__ import annotations

import os

tenant_id = os.environ.get("HARNESS_TENANT_ID", "t-1")
widget: dict[str, str] = {
    "PK": f"TENANT#{tenant_id}",
    "SK": os.environ.get("HARNESS_WIDGET_SK", "WIDGET#w-1"),
    "name": "Widget",
}


def create_widgets_table(dynamodb) -> None:  # noqa: ANN001 — a boto3 DynamoDB service resource
    """The table the fragment queries: PK/SK string keys, on-demand billing."""
    dynamodb.create_table(
        TableName="Widgets",
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    ).wait_until_exists()
