"""harness-only: crud-repository-python.md's WidgetRepository must satisfy crud-service-python.md's
WidgetRepository protocol, since the service is written against the protocol."""
from app.repositories.widget import WidgetRepository as PostgresWidgetRepository
from app.services.protocols import WidgetRepository


def _satisfies(repo: PostgresWidgetRepository) -> WidgetRepository:
    return repo
