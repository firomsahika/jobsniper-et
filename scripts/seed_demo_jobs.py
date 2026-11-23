"""Demo Job Seeder for Ethiopian Channels.

Populates PostgreSQL with realistic vacancies from HaHuJobs, Ethiojobs, and Freelance Ethiopia.
"""

import asyncio
from datetime import datetime, timezone
import logging
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.session import async_session_factory
from src.ingestion.parser import IngestionPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_jobs")

SAMPLE_JOBS = [
    {
        "channel": "@hahujobs",
        "msg_id": 101,
        "text": """📢 Vacancy Announcement: Senior Backend Engineer
🏢 Company: EthioTech Solutions PLC
📍 Location: Addis Ababa (Bole), Ethiopia (Hybrid)
⏳ Deadline: November 30, 2026
💼 Employment Type: Full-time

Qualifications & Requirements:
- B.Sc. in Computer Science, Software Engineering or related field.
- 3+ years experience with Python, FastAPI, and PostgreSQL.
- Strong knowledge of microservices architecture and Redis caching.
- Familiarity with Docker and Git version control.
- Good communication in English and Amharic.

Salary: 45,000 - 65,000 ETB / month + benefits.
Apply via Telegram: @ethiotech_hr or email jobs@ethiotech.et"""
    },
    {
        "channel": "@ethiojobs_et",
        "msg_id": 202,
        "text": """📢 NGO Job Vacancy: Project Monitoring & Evaluation Officer
🏢 Organization: International Humanitarian Aid Ethiopia
📍 Location: Hawassa, Ethiopia
⏳ Deadline: December 5, 2026
💼 Type: Contract (1 Year renewable)

Key Responsibilities:
- Design and implement project M&E frameworks.
- Data collection, analysis, and report generation using Excel and SPSS/KoboToolbox.
- Conduct field assessments and community stakeholder interviews.

Requirements:
- Bachelor's or Master's in Economics, Development Studies, Statistics, or Sociology.
- 4+ years of M&E experience in INGO sector.
- Fluency in English and Afaan Oromo or Amharic is an asset.

Salary: Competitive NGO scale.
Send CV and credentials to: ethiopia-recruitment@humanitarianaid.org"""
    },
    {
        "channel": "@freelance_ethiopia",
        "msg_id": 303,
        "text": """🚀 Freelance / Remote Contract: Senior UI/UX Designer
🏢 Agency: Addis Digital Studio
📍 Location: Remote (Ethiopia / Global)
⏳ Deadline: Open until filled

We are seeking a talented UI/UX Product Designer for a high-traffic fintech mobile application.
Requirements:
- Proven portfolio with mobile UI/UX designs (Figma).
- 2+ years designing design systems, wireframes, and high-fidelity interactive prototypes.
- Experience with user research and usability testing.
- Self-starter able to work asynchronously.

Compensation: $800 - $1,500 / project milestone.
Portfolio submission: @addisdigital_lead or portfolio@addisstudio.et"""
    },
    {
        "channel": "@dereja_official",
        "msg_id": 404,
        "text": """🎓 Fresh Graduate Opportunity: Junior Software Developer / Intern
🏢 Company: Commercial Tech Hub
📍 Location: Addis Ababa (Kazanchis)
⏳ Deadline: December 10, 2026

Calling all 2025/2026 Graduates!
We are hiring fresh talent with strong passion for programming.
Requirements:
- Degree in Computer Science, Information Systems, or Electrical Engineering (CGPA >= 3.0).
- Foundational skills in JavaScript, Python, or Java.
- Willingness to learn cloud technologies and modern web frameworks.
- No prior experience required; fresh graduates highly encouraged!

Apply: https://techhub.et/careers/fresh-2026"""
    }
]


async def seed():
    logger.info("Seeding sample Ethiopian vacancies...")
    async with async_session_factory() as session:
        pipeline = IngestionPipeline(session)
        for sample in SAMPLE_JOBS:
            job = await pipeline.process_incoming_post(
                source_channel=sample["channel"],
                message_id=sample["msg_id"],
                raw_text=sample["text"],
                posted_at=datetime.now(timezone.utc)
            )
            if job:
                logger.info(f"Seeded: {job.title} from {job.source_channel}")
            else:
                logger.info(f"Sample from {sample['channel']} already exists or skipped.")

    logger.info("✅ Seeding completed!")


if __name__ == "__main__":
    asyncio.run(seed())

