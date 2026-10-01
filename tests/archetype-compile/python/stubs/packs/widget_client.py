"""harness: the consumer's API client testing/contract-testing.md's pact test drives (app-level code: it
reads the envelope's data for one widget)."""
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class Widget:
    id: str
    name: str
    status: str


class WidgetClient:
    def __init__(self, base_url: str, token: str = "harness-token") -> None:
        self._base_url = base_url
        self._token = token

    def get_widget(self, widget_id: str) -> Widget:
        resp = httpx.get(f"{self._base_url}/api/v1/widgets/{widget_id}",
                         headers={"Authorization": f"Bearer {self._token}"})
        resp.raise_for_status()
        data = resp.json()["data"]
        return Widget(id=data["id"], name=data["name"], status=data["status"])
