"""Application tracking: status, notes, seen time, and status history

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing jobs were pasted in by the user, so they start as shortlisted.
    op.add_column("jobs", sa.Column("application_status", sa.String(20), nullable=False,
                                    server_default="shortlisted"))
    op.alter_column("jobs", "application_status", server_default=None)
    op.add_column("jobs", sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_jobs_application_status", "jobs", ["application_status"])
    op.create_table(
        "job_status_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.clock_timestamp(), nullable=False),
    )
    op.create_index("ix_job_status_events_job_id", "job_status_events", ["job_id"])


def downgrade() -> None:
    op.drop_table("job_status_events")
    op.drop_index("ix_jobs_application_status", table_name="jobs")
    for column in ("seen_at", "notes", "status_changed_at", "application_status"):
        op.drop_column("jobs", column)
