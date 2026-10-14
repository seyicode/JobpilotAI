"""Job discovery: followed sources, run history, and posting observations on jobs

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("board", sa.String(100), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(40), nullable=True),
        sa.Column("last_error_message", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "board", name="uq_job_sources_provider_board"),
    )
    op.create_index("ix_job_sources_next_run_at", "job_sources", ["next_run_at"])
    op.create_table(
        "source_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp(),
                  nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        *[sa.Column(name, sa.Integer(), nullable=False)
          for name in ("fetched", "new_jobs", "seen_again", "filtered_out", "archived", "closed")],
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("error_message", sa.String(200), nullable=True),
    )
    op.create_index("ix_source_runs_source_id", "source_runs", ["source_id"])
    op.create_index("ix_source_runs_started_at", "source_runs", ["started_at"])
    op.add_column("jobs", sa.Column("source_id", postgresql.UUID(as_uuid=True),
                                    sa.ForeignKey("job_sources.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_jobs_source_id", "jobs", ["source_id"])
    op.add_column("jobs", sa.Column("source_external_id", sa.String(200), nullable=True))
    for column in ("posted_at", "first_seen_at", "last_seen_at", "closed_at"):
        op.add_column("jobs", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.create_index("uq_jobs_source_posting", "jobs", ["source_id", "source_external_id"], unique=True,
                    postgresql_where=sa.text("source_external_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_jobs_source_posting", table_name="jobs")
    for column in ("closed_at", "last_seen_at", "first_seen_at", "posted_at", "source_external_id"):
        op.drop_column("jobs", column)
    op.drop_index("ix_jobs_source_id", table_name="jobs")
    op.drop_column("jobs", "source_id")
    op.drop_table("source_runs")
    op.drop_table("job_sources")
