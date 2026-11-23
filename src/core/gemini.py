"""Gemini AI Core Service (Async HTTP Client via httpx).

Handles:
- Structured CV entity extraction
- Channel job post parsing & normalization
- 768-dimension text embedding generation (text-embedding-004)
- Stage 2 LLM precision matching & gap advisory
- Tailored cover letter drafting
- Audio transcription (OGG Opus) & STAR mock interview feedback
"""

import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx
from src.config.settings import settings
from src.queue.redis_client import redis_manager

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.chat_model = settings.GEMINI_MODEL or "gemini-2.5-flash"
        self.embedding_model = settings.EMBEDDING_MODEL or "text-embedding-004"
        self._client: Optional[httpx.AsyncClient] = None

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key != "your_gemini_api_key_here")

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=45.0)
        return self._client

    # -------------------------------------------------------------
    # 1. Embeddings Generation (768-dimensional)
    # -------------------------------------------------------------
    async def get_embedding(self, text: str) -> List[float]:
        """Generates a 768-dimensional vector embedding for candidate CV or job listing."""
        if not self.is_configured():
            # Return deterministic vector for local/demo runs
            import hashlib
            import random
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
            rng = random.Random(seed)
            return [rng.uniform(-0.1, 0.1) for _ in range(768)]

        try:
            client = await self.get_client()
            url = f"{GEMINI_BASE_URL}/{self.embedding_model}:embedContent?key={self.api_key}"
            payload = {
                "model": f"models/{self.embedding_model}",
                "content": {
                    "parts": [{"text": text[:8000].strip()}]
                }
            }
            res = await client.post(url, json=payload)
            res.raise_for_status()
            data = res.json()
            values = data.get("embedding", {}).get("values", [])
            if len(values) > 768:
                values = values[:768]
            elif len(values) < 768:
                values = values + [0.0] * (768 - len(values))
            return values
        except Exception as e:
            logger.error(f"Error generating embedding with Gemini: {e}")
            return [0.0] * 768

    # -------------------------------------------------------------
    # Helper: Generate Text / Multimodal Content
    # -------------------------------------------------------------
    async def _generate_content(self, parts: List[Dict[str, Any]], temperature: float = 0.2) -> str:
        """Sends generation request to Gemini REST API with rate-limit pacing."""
        # Enforce rate limiter to safely stay within 100% Free Tier (15 RPM)
        await redis_manager.wait_for_gemini_slot(max_rpm=14)

        client = await self.get_client()
        url = f"{GEMINI_BASE_URL}/{self.chat_model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 2048,
            }
        }
        res = await client.post(url, json=payload)
        res.raise_for_status()
        data = res.json()
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            content_parts = candidates[0]["content"].get("parts", [])
            if content_parts:
                return content_parts[0].get("text", "")
        return ""

    # -------------------------------------------------------------
    # 2. Structured CV Parsing
    # -------------------------------------------------------------
    async def parse_cv_text(self, cv_text: str) -> Dict[str, Any]:
        """Extracts structured JSON data from raw CV text."""
        default_profile = {
            "full_name": "Applicant",
            "primary_title": "Professional",
            "highest_education": "Not Specified",
            "years_of_experience": 1,
            "skills": ["Communication", "Problem Solving"],
            "summary": cv_text[:200] if cv_text else "",
            "preferred_roles": []
        }

        if not self.is_configured() or not cv_text.strip():
            return default_profile

        prompt = f"""You are a professional recruiting intelligence system. 
Extract structured information from the following CV/Resume text into strict JSON format with exactly these keys:
- "full_name": candidate's name (string)
- "primary_title": current or target professional job title (string, e.g. "Senior Backend Developer" or "Accountant")
- "highest_education": degree and institution if found (string)
- "years_of_experience": integer estimated total years of relevant work experience (number, 0 if fresh graduate)
- "skills": list of top 8-15 core technical and soft skills (array of strings)
- "summary": concise 2-sentence summary of the candidate's profile (string)
- "preferred_roles": list of 3-5 roles they are best qualified for (array of strings)

Respond ONLY with valid JSON. No markdown code blocks, no other text.

CV Text:
\"\"\"
{cv_text[:12000]}
\"\"\"
"""
        try:
            raw = await self._generate_content([{"text": prompt}], temperature=0.1)
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Error parsing CV text via Gemini: {e}")
            return default_profile

    # -------------------------------------------------------------
    # 3. Channel Job Listing Parsing
    # -------------------------------------------------------------
    async def parse_job_post(self, raw_post: str, channel_title: str) -> Dict[str, Any]:
        """Parses a raw Telegram channel post into structured job metadata."""
        default_job = {
            "title": "General Opportunity",
            "company": "Ethiopian Employer",
            "location": "Addis Ababa / Ethiopia",
            "deadline": "Open / Not specified",
            "required_experience_years": 0,
            "required_skills": [],
            "salary_range": "Negotiable",
            "application_contact": channel_title,
            "employment_type": "Full-time"
        }

        if not self.is_configured() or not raw_post.strip():
            return default_job

        prompt = f"""You are an expert recruitment parser for Ethiopian Telegram job channels.
Parse the following vacancy message into strict JSON with exactly these keys:
- "title": Job position title (e.g., "Full Stack Developer", "Field Coordinator", "Junior Accountant")
- "company": Organization or hiring company name (or "Not Specified" if absent)
- "location": City or region in Ethiopia or "Remote" (string)
- "deadline": Expiry date or application deadline as stated in the post (string)
- "required_experience_years": Minimum years of experience required (integer, 0 if fresh grad/not mentioned)
- "required_skills": List of 3-10 required tools, technologies or qualifications (array of strings)
- "salary_range": Stated salary or "Negotiable / Company Scale"
- "application_contact": Email address, Telegram handle (@username), or application link
- "employment_type": "Full-time", "Part-time", "Contract", "Internship", or "Freelance"

Respond ONLY with valid JSON. No markdown code blocks, no other text.

Post Content:
\"\"\"
{raw_post[:6000]}
\"\"\"
"""
        try:
            raw = await self._generate_content([{"text": prompt}], temperature=0.1)
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Error parsing job post via Gemini: {e}")
            return default_job

    # -------------------------------------------------------------
    # 4. Stage 2 Precision Matching & Gap Analysis
    # -------------------------------------------------------------
    async def evaluate_match_precision(
        self,
        candidate_profile: Dict[str, Any],
        job_structured: Dict[str, Any],
        job_raw: str,
    ) -> Dict[str, Any]:
        """Evaluates strict fit: years, skills, domain alignment, and returns score + strengths + gap advisory."""
        default_eval = {
            "match_score": 85,
            "strengths": [
                f"Candidate's background in {candidate_profile.get('primary_title', 'their field')} matches {job_structured.get('title', 'the role')}.",
                f"Overlapping skill competencies: {', '.join(candidate_profile.get('skills', [])[:3])}."
            ],
            "gap_advisory": "Emphasize specific projects and quantitative achievements relevant to the posting."
        }

        if not self.is_configured():
            return default_eval

        prompt = f"""You are an elite Tech Lead & Talent Matcher. Evaluate the alignment between the Candidate Profile and the Job Listing.
Be realistic, analytical, and objective. 
Assess:
1. Experience years constraint: Candidate has {candidate_profile.get('years_of_experience', 0)} yrs, Job requires {job_structured.get('required_experience_years', 0)} yrs.
2. Skill stack overlap.
3. Industry/Domain match.

Provide your evaluation in strict JSON with:
- "match_score": Integer between 0 and 100 representing true job suitability.
- "strengths": Array of exactly 2 concise, impactful bullet strings explaining why they match.
- "gap_advisory": One actionable, single-sentence tip on what skill or experience they should emphasize or study.

Candidate Profile:
{json.dumps(candidate_profile, indent=2)}

Job Details:
Title: {job_structured.get('title')}
Company: {job_structured.get('company')}
Required Exp: {job_structured.get('required_experience_years')} yrs
Required Skills: {json.dumps(job_structured.get('required_skills', []))}
Raw Description Excerpt:
{job_raw[:2500]}

Respond ONLY with valid JSON.
"""
        try:
            raw = await self._generate_content([{"text": prompt}], temperature=0.1)
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Error evaluating match precision: {e}")
            return default_eval

    # -------------------------------------------------------------
    # 5. Tailored Cover Letter Generator
    # -------------------------------------------------------------
    async def generate_cover_letter(
        self,
        candidate_name: str,
        candidate_profile: Dict[str, Any],
        job_data: Dict[str, Any]
    ) -> str:
        """Generates an executive, highly targeted 3-paragraph cover letter."""
        fallback = f"""Dear Hiring Team,

I am writing to express my strong enthusiasm for the {job_data.get('title', 'open')} position at {job_data.get('company', 'your organization')}. With my background as a {candidate_profile.get('primary_title', 'professional')} and hands-on expertise in {', '.join(candidate_profile.get('skills', [])[:4])}, I am confident in delivering immediate value to your team.

Throughout my career, I have focused on solving high-impact problems, delivering reliable results, and collaborating cross-functionally. My experience aligns closely with your stated requirements, particularly in executing robust workflows and adapting quickly to evolving priorities.

I look forward to discussing how my skills and proactive mindset will support {job_data.get('company', 'your company')}'s mission. Thank you for your time and consideration.

Sincerely,
{candidate_name}"""

        if not self.is_configured():
            return fallback

        prompt = f"""You are a top-tier executive career coach and copywriter.
Write an exceptional, compelling, 3-paragraph cover letter for the candidate applying to the given job.

Rules:
1. Exactly 3 crisp paragraphs:
   - Paragraph 1: Hook, role applied for, and core value proposition.
   - Paragraph 2: Direct proof of qualifications mapping candidate's specific background ({candidate_profile.get('skills', [])}) to the job requirements.
   - Paragraph 3: Passion for the organization and clear call-to-action for an interview.
2. Tone: Confident, professional, modern, authentic. Avoid clichés ("I am a hard worker").
3. Format as plain ready-to-copy letter. Do not include sender/recipient address header blocks. Start with "Dear Hiring Team," and end with "Sincerely,\n{candidate_name}".

Candidate Name: {candidate_name}
Candidate Profile:
{json.dumps(candidate_profile, indent=2)}

Job Details:
Title: {job_data.get('title')}
Company: {job_data.get('company')}
Required Skills: {json.dumps(job_data.get('required_skills', []))}
Location: {job_data.get('location')}
"""
        try:
            letter = await self._generate_content([{"text": prompt}], temperature=0.3)
            return letter.strip() or fallback
        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            return fallback

    # -------------------------------------------------------------
    # 6. STAR Mock Interview Simulation Engine
    # -------------------------------------------------------------
    def get_interview_question_prompt(self, question_number: int, job_title: str, company: str) -> str:
        """Returns standard interview simulation prompt based on the 5-question sequence."""
        stages = {
            1: (
                "Professional Pitch & Introduction",
                f"Give a compelling 60-90 second introduction of yourself, your professional journey, and why you are the ideal fit for the {job_title} role at {company}."
            ),
            2: (
                "Technical & Domain Competency",
                f"In your work relevant to {job_title}, describe the most technically complex challenge or project you delivered. What was the architecture/methodology and how did you ensure quality?"
            ),
            3: (
                "Behavioral Scenario (STAR Method)",
                f"Tell me about a time when you faced a critical conflict, unexpected roadblock, or tight deadline with a team member or stakeholder. Walk me through the Situation, Task, Action you personally took, and the Result."
            ),
            4: (
                "Situational Problem-Solving Under Constraint",
                f"Suppose you discover a severe bug or operational breakdown just 3 hours before a major product launch or client delivery. What are your exact step-by-step containment and resolution actions?"
            ),
            5: (
                "Role Alignment & Closing Impact",
                f"Looking at this {job_title} role at {company}, what impact do you expect to achieve in your first 90 days, and what questions would you ask us as the interviewers?"
            )
        }
        category, text = stages.get(question_number, ("General Competency", f"Why are you the best fit for {job_title}?"))
        return f"<b>{category}</b>\n\n\"{text}\""

    async def transcribe_audio_voice_note(self, audio_bytes: bytes) -> str:
        """Transcribes Telegram voice note (.ogg Opus audio) using Gemini multimodal capabilities."""
        if not self.is_configured():
            return "Audio voice response recorded (Demo mode: transcription simulated)."

        try:
            b64_data = base64.b64encode(audio_bytes).decode("utf-8")
            parts = [
                {"text": "Transcribe the following voice recording into accurate English text. Do not summarize, output the exact transcription."},
                {
                    "inline_data": {
                        "mime_type": "audio/ogg",
                        "data": b64_data
                    }
                }
            ]
            transcription = await self._generate_content(parts, temperature=0.1)
            return transcription.strip()
        except Exception as e:
            logger.error(f"Error transcribing audio with Gemini: {e}")
            return "Could not transcribe audio. Please try text response."

    async def evaluate_interview_answer(
        self,
        question_num: int,
        question_text: str,
        user_answer: str,
        job_title: str
    ) -> Dict[str, Any]:
        """Evaluates an individual answer against technical competency and STAR structure."""
        default_res = {
            "score": 7.5,
            "quick_feedback": "Good response. Be sure to highlight measurable business impact and specific tools used.",
            "star_rating": "Acceptable"
        }

        if not self.is_configured():
            return default_res

        prompt = f"""You are an expert interviewer evaluating a candidate for the position of {job_title}.
Question {question_num}: {question_text}
Candidate's Answer:
\"\"\"{user_answer}\"\"\"

Evaluate the answer and return strict JSON with:
- "score": Float between 1.0 and 10.0
- "quick_feedback": 2 concise sentences praising a strength and giving a practical correction.
- "star_rating": One of "Poor", "Adequate", "Strong", or "Mastery" (evaluate whether they showed Situation, Task, Action, and quantifiable Result).

Respond ONLY with valid JSON.
"""
        try:
            raw = await self._generate_content([{"text": prompt}], temperature=0.1)
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Error evaluating interview answer: {e}")
            return default_res

    async def generate_final_interview_report(
        self,
        job_title: str,
        qa_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generates comprehensive final evaluation report upon completing all 5 questions."""
        default_report = {
            "overall_score": 8.0,
            "tech_score": 8.0,
            "star_score": 7.5,
            "comm_score": 8.5,
            "feedback": "Strong foundational knowledge and clear articulation. Improve structural quantification in behavioral stories.",
            "recommendation": "Use concrete metrics (e.g. 'reduced latency by 35%') when describing achievements."
        }

        if not self.is_configured():
            return default_report

        prompt = f"""You are a Senior Principal Interview Bar Raiser.
The candidate completed a 5-question mock interview for: {job_title}.
Review the candidate's responses across all questions:
{json.dumps(qa_history, indent=2)}

Provide a final evaluation in strict JSON:
- "overall_score": Float 1.0 to 10.0
- "tech_score": Float 1.0 to 10.0
- "star_score": Float 1.0 to 10.0
- "comm_score": Float 1.0 to 10.0
- "feedback": 3 sentences highlighting key strengths and areas to sharpen.
- "recommendation": One high-leverage piece of advice for the real interview.

Respond ONLY with valid JSON.
"""
        try:
            raw = await self._generate_content([{"text": prompt}], temperature=0.1)
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Error generating final interview report: {e}")
            return default_report


gemini_service = GeminiService()
