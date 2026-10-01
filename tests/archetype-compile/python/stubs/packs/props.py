"""harness: the app-level functions and model testing/property-based.md's properties are about."""
from __future__ import annotations

import base64
from dataclasses import dataclass


def encode(name: str) -> str:
    return base64.urlsafe_b64encode(name.encode()).decode()


def decode(token: str) -> str:
    return base64.urlsafe_b64decode(token.encode()).decode()


class ParseError(ValueError):
    pass


def parse(raw: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ParseError(raw) from exc


def is_valid_email(email: str) -> bool:
    local, _, domain = email.partition("@")
    return bool(local) and "." in domain


def normalize_email(email: str) -> str:
    local, _, domain = email.strip().partition("@")
    return f"{local}@{domain.lower()}"


@dataclass
class Widget:
    name: str
    description: str
    priority: int
    status: str

    def validate(self) -> list[str]:
        errors = []
        if not 1 <= len(self.name) <= 255:
            errors.append("name")
        if len(self.description) > 2000:
            errors.append("description")
        if not 0 <= self.priority <= 10:
            errors.append("priority")
        if self.status not in {"active", "draft", "archived"}:
            errors.append("status")
        return errors
