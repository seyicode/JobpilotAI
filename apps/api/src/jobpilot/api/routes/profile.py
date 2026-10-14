import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from jobpilot.db.models import ProfileRecord
from jobpilot.db.session import get_session
from jobpilot.services.resumes.schema import UserProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profile"])

SessionDep = Annotated[Session, Depends(get_session)]
RECORD_ID = 1


class ProfileOut(UserProfile):
    updated_at: datetime | None


def load_profile_details(session: Session) -> UserProfile:
    record = session.get(ProfileRecord, RECORD_ID)
    return UserProfile.model_validate(record.data if record else {})


@router.get("", response_model=ProfileOut)
def get_profile(session: SessionDep) -> ProfileOut:
    record = session.get(ProfileRecord, RECORD_ID)
    return ProfileOut(**load_profile_details(session).model_dump(),
                      updated_at=record.updated_at if record else None)


@router.put("", response_model=ProfileOut)
def save_profile(payload: UserProfile, session: SessionDep) -> ProfileOut:
    """Replace the profile. Contact details are never logged."""
    record = session.get(ProfileRecord, RECORD_ID)
    if record is None:
        record = ProfileRecord(id=RECORD_ID, data=payload.model_dump())
        session.add(record)
    else:
        record.data = payload.model_dump()
    session.commit()
    session.refresh(record)
    logger.info("profile saved")
    return ProfileOut(**payload.model_dump(), updated_at=record.updated_at)
