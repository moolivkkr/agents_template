"""harness-only stand-in for app/auth/jwt.py (websocket-pattern-python.md imports validate_jwt and
JWTError from it; the real decode is auth-middleware-python.md's). Test tokens: "valid:<tenant>:<user>"."""
from dataclasses import dataclass, field


class JWTError(Exception):
    pass


@dataclass(frozen=True)
class Claims:
    user_id: str
    tenant_id: str
    roles: list[str] = field(default_factory=list)


def validate_jwt(token: str) -> Claims:
    parts = token.split(":")
    if len(parts) != 3 or parts[0] != "valid":
        raise JWTError("invalid token")
    return Claims(user_id=parts[2], tenant_id=parts[1], roles=["user"])
