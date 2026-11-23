"""Job Listing Model Specification."""

import uuid
from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector
from src.db.session import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_channel = Column(String(255), nullable=False)
    source_message_id = Column(BigInteger, nullable=False)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    company = Column(String(255), default="Not Specified")
    location = Column(String(255), default="Ethiopia")
    deadline = Column(String(100), nullable=True)
    structured_data = Column(JSONB, default=dict)
    job_embedding = Column(Vector(768), nullable=True)
    raw_text = Column(Text, nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    def __repr__(self):
        return f"<Job(title='{self.title}', company='{self.company}', channel='{self.source_channel}')>"

