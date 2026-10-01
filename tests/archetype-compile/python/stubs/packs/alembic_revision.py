"""harness: one revision for languages/python.md's async env.py to apply and revert."""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("harness_migrated", sa.Column("id", sa.Integer, primary_key=True))


def downgrade() -> None:
    op.drop_table("harness_migrated")
