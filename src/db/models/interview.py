"""Mock Interview Model Specification."""

import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from src.db.session import Base


class MockInterview(Base):
    __tablename__ = "mock_interviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    job_context = Column(Text, nullable=False)
    mode = Column(String(10), default="text")  # text, voice
    transcript = Column(JSONB, default=list)  # list of {question_num, question, answer, score, feedback}
    final_score = Column(Numeric(3, 1), nullable=True)
    status = Column(String(20), default="in_progress")  # in_progress, completed, abandoned
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    candidate = relationship("Candidate", backref="interviews")
    job = relationship("Job", backref="interviews")

    def __repr__(self):
        return f"<MockInterview(id={self.id}, candidate_id={self.candidate_id}, status='{self.status}')>"

