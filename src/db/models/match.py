"""Job Match Model Specification."""

import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
from src.db.session import Base


class JobMatch(Base):
    __tablename__ = "job_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    match_score = Column(Integer, nullable=False)
    match_reasoning = Column(ARRAY(String), nullable=True)
    skill_gap_tip = Column(Text, nullable=True)
    cover_letter_draft = Column(Text, nullable=True)
    user_feedback = Column(String(50), default="pending")  # applied, not_relevant, pending
    is_delivered = Column(Boolean, default=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="unique_candidate_job"),
    )

    candidate = relationship("Candidate", backref="matches")
    job = relationship("Job", backref="matches")

    def __repr__(self):
        return f"<JobMatch(candidate_id={self.candidate_id}, job_id={self.job_id}, score={self.match_score})>"

