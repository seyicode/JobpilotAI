from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from jobpilot.db.models import PreferencesRecord
from jobpilot.db.session import get_session
from jobpilot.services.preferences import JobPreferences

router = APIRouter(prefix="/preferences", tags=["preferences"])

SessionDep = Annotated[Session, Depends(get_session)]
RECORD_ID = 1


class PreferencesOut(JobPreferences):
    updated_at: datetime | None


@router.get("", response_model=PreferencesOut)
def get_preferences(session: SessionDep) -> PreferencesOut:
    """Return saved preferences, or defaults if none have been saved."""
    record = session.get(PreferencesRecord, RECORD_ID)
    if record is None:
        return PreferencesOut(updated_at=None)
    # Validating on read applies defaults for fields added after the row was saved.
    return PreferencesOut(**JobPreferences.model_validate(record.data).model_dump(),
                          updated_at=record.updated_at)


@router.put("", response_model=PreferencesOut)
def save_preferences(payload: JobPreferences, session: SessionDep) -> PreferencesOut:
    """Replace all preferences."""
    record = session.get(PreferencesRecord, RECORD_ID)
    if record is None:
        record = PreferencesRecord(id=RECORD_ID, data=payload.model_dump())
        session.add(record)
    else:
        record.data = payload.model_dump()
    session.commit()
    session.refresh(record)
    return PreferencesOut(**payload.model_dump(), updated_at=record.updated_at)
