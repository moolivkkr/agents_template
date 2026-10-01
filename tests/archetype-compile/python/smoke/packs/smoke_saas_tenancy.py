# infrastructure/saas-tenancy-models.md: the repository method returns only the caller's tenant's live
# rows (SQLite in memory; the filter is plain SQLAlchemy, the same on PostgreSQL).
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.resources import ResourceRepository
from harness_stubs.tenancy_models import Base, Resource

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
tenant_a, tenant_b = uuid4(), uuid4()
with Session(engine) as session:
    session.add_all([
        Resource(tenant_id=tenant_a, name="a1"),
        Resource(tenant_id=tenant_a, name="a-deleted", deleted_at=datetime.now(timezone.utc)),
        Resource(tenant_id=tenant_b, name="b1"),
    ])
    session.commit()
    repo = ResourceRepository()
    repo.session = session
    rows = repo.list(tenant_a)
    assert isinstance(rows, list), type(rows)
    assert [r.name for r in rows] == ["a1"], rows
    assert [r.name for r in repo.list(tenant_b)] == ["b1"]
engine.dispose()
