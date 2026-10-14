"""Application tracking. Statuses are set by the user by hand; JobPilot never applies for jobs."""

from datetime import UTC, datetime
from typing import Literal, get_args

from sqlalchemy.orm import Session

from jobpilot.db.models import Job, JobStatusEvent

ApplicationStatus = Literal[
    "discovered", "shortlisted", "ready_to_apply", "applied", "interviewing", "offered", "rejected", "archived",
]
STATUSES: tuple[str, ...] = get_args(ApplicationStatus)
SAVED = ("shortlisted", "ready_to_apply")
IN_PROGRESS = ("applied", "interviewing", "offered")


def set_status(session: Session, job: Job, status: str, note: str | None = None) -> bool:
    """Change a job's status and record the change. Returns False if it was already that status."""
    if status not in STATUSES:
        raise ValueError(f"Unknown status: {status}")
    if job.application_status == status:
        return False
    session.add(JobStatusEvent(job_id=job.id, from_status=job.application_status, to_status=status,
                               note=note))
    job.application_status = status
    job.status_changed_at = datetime.now(UTC)
    return True
