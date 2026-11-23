"""Candidate Model Specification."""

import uuid
from datetime import time, datetime
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector
from src.db.session import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    ui_language = Column(String(10), default="en")  # en, am, om
    cv_raw_text_encrypted = Column(Text, nullable=True)
    structured_profile = Column(JSONB, default=dict)
    cv_embedding = Column(Vector(768), nullable=True)
    min_match_score = Column(Integer, default=80)
    quiet_hours_start = Column(Time, default=time(22, 0))
    quiet_hours_end = Column(Time, default=time(7, 0))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    def __repr__(self):
        return f"<Candidate(telegram_id={self.telegram_id}, name='{self.full_name}', score={self.min_match_score}%)>"

