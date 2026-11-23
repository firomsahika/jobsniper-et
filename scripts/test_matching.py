"""Integration & Unit Test Suite for JobSniper ET Core Components."""

import asyncio
import logging
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.security import security_manager
from src.core.gemini import gemini_service
from src.ingestion.deduplicator import JobDeduplicator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_suite")


async def run_tests():
    logger.info("=== 1. Testing AES-256-GCM Security Encryption ===")
    sample_cv = "Senior Software Engineer with 5 years in Addis Ababa building fintech apps."
    encrypted = security_manager.encrypt_text(sample_cv)
    decrypted = security_manager.decrypt_text(encrypted)
    assert decrypted == sample_cv, "Decryption does not match original plaintext!"
    assert encrypted != sample_cv, "Plaintext was not encrypted!"
    logger.info("✅ Security test passed: AES-256-GCM encryption & decryption verified.")

    logger.info("\n=== 2. Testing Job Deduplicator (Layer 1 SHA-256) ===")
    text1 = "Vacancy: Python Dev at EthioTech. Deadline: Dec 2026. Contact: @hr"
    text2 = "  VACANCY:   Python Dev at EthioTech.   Deadline: Dec 2026. Contact: @hr  "
    hash1 = JobDeduplicator.compute_content_hash(text1)
    hash2 = JobDeduplicator.compute_content_hash(text2)
    assert hash1 == hash2, "Normalized hashes should match for identical vacancies with different whitespace!"
    logger.info(f"✅ Deduplication test passed: Hash identical ({hash1[:16]}...)")

    logger.info("\n=== 3. Testing 768-Dimension Embedding Generation ===")
    embedding = await gemini_service.get_embedding(sample_cv)
    assert len(embedding) == 768, f"Expected 768-dim vector, got {len(embedding)}"
    logger.info(f"✅ Embedding test passed: Vector dimensions = {len(embedding)}")

    logger.info("\n=== 4. Testing Structured CV Extraction ===")
    structured_cv = await gemini_service.parse_cv_text(sample_cv)
    logger.info(f"Extracted Profile: {structured_cv.get('primary_title')} | Skills: {structured_cv.get('skills')}")
    assert "primary_title" in structured_cv, "Profile missing primary_title"
    logger.info("✅ CV Extraction test passed.")

    logger.info("\n=== 5. Testing Stage 2 LLM Match Evaluation ===")
    job_structured = {
        "title": "Senior Python Developer",
        "company": "EthioTech",
        "required_experience_years": 3,
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
    }
    match_result = await gemini_service.evaluate_match_precision(
        candidate_profile=structured_cv,
        job_structured=job_structured,
        job_raw="Looking for a Python dev with 3+ years experience.",
    )
    logger.info(f"Match Result: Score = {match_result.get('match_score')}%")
    logger.info(f"Strengths: {match_result.get('strengths')}")
    logger.info(f"Gap Advisory: {match_result.get('gap_advisory')}")
    assert match_result.get("match_score", 0) > 0, "Match score should be > 0"
    logger.info("✅ Stage 2 LLM Matching test passed.")

    logger.info("\n=== 6. Testing Tailored Cover Letter Generator ===")
    cover_letter = await gemini_service.generate_cover_letter(
        candidate_name="Abebe Bikila",
        candidate_profile=structured_cv,
        job_data=job_structured,
    )
    assert len(cover_letter) > 100, "Cover letter too short"
    assert "EthioTech" in cover_letter or "Senior Python Developer" in cover_letter or "Hiring Team" in cover_letter
    logger.info(f"Sample Draft Paragraph 1:\n{cover_letter.splitlines()[0]}")
    logger.info("✅ Cover Letter Generator test passed.")

    logger.info("\n=== 7. Testing STAR Mock Interview Evaluation ===")
    eval_res = await gemini_service.evaluate_interview_answer(
        question_num=3,
        question_text="Tell me about a time you solved a conflict.",
        user_answer="In my previous project, we had a disagreement over whether to use PostgreSQL or MongoDB. I organized a benchmark test, showed performance data, and we aligned on PostgreSQL, which reduced latency by 30%.",
        job_title="Senior Python Developer"
    )
    logger.info(f"Interview Answer Score: {eval_res.get('score')} | STAR: {eval_res.get('star_rating')}")
    logger.info(f"Coach Feedback: {eval_res.get('quick_feedback')}")
    assert eval_res.get("score") is not None, "Evaluation score missing"
    logger.info("✅ Mock Interview Coach test passed.")

    logger.info("\n🎉 ALL TESTS PASSED SUCCESSFULLY! Core engines are production-ready.")


if __name__ == "__main__":
    asyncio.run(run_tests())

