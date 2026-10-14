"""Create jobs

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("company", sa.String(200), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("canonical_url", sa.String(2000), nullable=True, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("description_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("requirements", postgresql.JSONB(), nullable=True),
        sa.Column("extraction_method", sa.String(20), nullable=True),
        sa.Column("extraction_note", sa.String(200), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])


def downgrade() -> None:
    op.drop_table("jobs")
