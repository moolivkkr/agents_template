"""harness-only stand-in for the project's settings module (security/secure-coding.md §5): the JWT key
comes from the environment and there is no default."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    jwt_secret_key: str


settings = Settings(jwt_secret_key=os.environ["JWT_SECRET_KEY"])
