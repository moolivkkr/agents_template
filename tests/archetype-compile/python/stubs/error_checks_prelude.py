# harness-only: the names error-handling-python.md's "Type Checking Errors" fragment assumes in scope
from uuid import UUID

from app.errors import AppError, NotFoundError, ValidationFailedError
from app.services.widget import WidgetService

widget_service: WidgetService
tid: UUID
name: str
