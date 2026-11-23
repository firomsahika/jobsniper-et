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
        # 1. Enable pgvector extension
        logger.info("Enabling pgvector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        # 2. Create tables
        logger.info("Creating tables (candidates, jobs, job_matches, mock_interviews)...")
        await conn.run_sync(Base.metadata.create_all)

        # 3. Create HNSW Cosine vector indexes
        logger.info("Building HNSW vector indexes...")
        try:
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_candidates_embedding "
                    "ON candidates USING hnsw (cv_embedding vector_cosine_ops);"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_jobs_embedding "
                    "ON jobs USING hnsw (job_embedding vector_cosine_ops);"
                )
            )
        except Exception as e:
            logger.warning(f"Note on HNSW indexes: {e}")

    logger.info("✅ Database initialization successfully completed!")


if __name__ == "__main__":
    asyncio.run(init_database())

