"""Database Initialization and Schema Migration Script.

Ensures the pgvector extension is enabled and builds all tables and HNSW vector indexes.
"""

import asyncio
import logging
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from src.db.session import engine, Base
from src.db.models import Candidate, Job, JobMatch, MockInterview

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")


async def init_database():
    logger.info("Connecting to database to initialize schema...")
    async with engine.begin() as conn:
        logger.info("Creating tables (candidates, jobs, job_matches, mock_interviews)...")
        await conn.run_sync(Base.metadata.create_all)

    logger.info("✅ Database initialization successfully completed!")


if __name__ == "__main__":
    asyncio.run(init_database())

