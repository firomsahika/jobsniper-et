"""Gemini AI Core Service (Async HTTP Client via httpx).

Handles:
- Structured CV entity extraction
- Channel job post parsing & normalization
- 768-dimension text embedding generation (text-embedding-004)
- Stage 2 LLM precision matching & gap advisory
- Tailored cover letter drafting
- Audio transcription (OGG Opus) & STAR mock interview feedback
"""

import asyncio
import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx
from src.config.settings import settings
from src.queue.redis_client import redis_manager
from src.core.document_parser import document_parser

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.chat_model = settings.GEMINI_MODEL or "gemini-1.5-flash"
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
    # 2. Structured CV Parsing (AI + Local Heuristic Fallback)
    # -------------------------------------------------------------
    async def parse_cv_text(self, cv_text: str, file_name: str = "", user_full_name: str = "") -> Dict[str, Any]:
        """Extracts structured JSON data from raw CV text with dual-layer AI and local heuristic parsing."""
        # 1. Compute robust local heuristic extraction from document text
        heuristics = document_parser.extract_profile_heuristics(
            raw_text=cv_text,
            file_name=file_name,
            default_name=user_full_name
        )

        if not self.is_configured() or not cv_text.strip():
            return heuristics

        prompt = f"""You are a professional recruiting intelligence system. 
Extract structured information from the following CV/Resume text into strict JSON format with exactly these keys:
- "full_name": candidate's name (string)
- "primary_title": current or target professional job title (string, e.g. "Fullstack Software Engineer" or "Senior Backend Developer")
- "highest_education": clean degree and field of study without introductory sentences (string, e.g. "B.Sc. in Computer Science and Engineering")
- "years_of_experience": integer estimated total years of relevant work experience (number, 0 if fresh graduate)
- "skills": comprehensive list of all technical, software, language, framework, database, and tool skills mentioned in the resume (array of strings, e.g. 10-25 skills)
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
            parsed = json.loads(raw)

            # Ensure essential fields are not generic defaults
            if not parsed.get("full_name") or parsed.get("full_name") in ["Applicant", "None", ""]:
                parsed["full_name"] = heuristics["full_name"]
            if not parsed.get("primary_title") or parsed.get("primary_title") in ["Professional", "Applicant", ""]:
                parsed["primary_title"] = heuristics["primary_title"]
            elif "full" in parsed.get("primary_title", "").lower() and "stack" in parsed.get("primary_title", "").lower():
                parsed["primary_title"] = "Fullstack Software Engineer"

            gemini_skills = parsed.get("skills", [])
            heur_skills = heuristics.get("skills", [])
            all_skills = list(dict.fromkeys(gemini_skills + heur_skills))
            parsed["skills"] = all_skills[:25]

            raw_edu = parsed.get("highest_education", "")
            if not raw_edu or raw_edu in ["Not Specified", "Higher Education"] or any(raw_edu.lower().startswith(b) for b in ['addis', 'ababa', 'university', 'baba']):
                parsed["highest_education"] = heuristics["highest_education"]
            else:
                cleaned_edu = document_parser.clean_education_degree(raw_edu)
                parsed["highest_education"] = cleaned_edu if cleaned_edu != "Higher Education" else heuristics["highest_education"]

            if parsed.get("years_of_experience", 0) <= 0 and heuristics["years_of_experience"] > 0:
                parsed["years_of_experience"] = heuristics["years_of_experience"]

            # Merge projects & portfolio links
            parsed["projects"] = parsed.get("projects") or heuristics.get("projects", [])
            parsed["portfolio_url"] = parsed.get("portfolio_url") or heuristics.get("portfolio_url", "")

            return parsed
        except Exception as e:
            logger.error(f"AI API CV parsing error, using high-accuracy heuristic extraction: {e}")
            return heuristics

    # -------------------------------------------------------------
    # 3. Channel Job Listing Parsing
    # -------------------------------------------------------------
    async def parse_job_post(self, raw_post: str, channel_title: str) -> Dict[str, Any]:
        """Parses a raw Telegram channel post into structured job metadata using local heuristics with AI assistance."""
        # 1. Fast, high-accuracy local heuristic extraction
        heuristics = document_parser.extract_job_heuristics(raw_post, channel_title)
        if heuristics.get("title") and heuristics.get("title") != "Professional Opportunity":
            return heuristics

        if not self.is_configured() or not raw_post.strip():
            return heuristics

        prompt = f"""You are an expert recruitment parser for Ethiopian Telegram job channels.
Parse the following vacancy message into strict JSON with exactly these keys:
- "title": Job position title (e.g., "Fullstack Developer", "Senior Software Engineer", "Junior Accountant")
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
{raw_post[:8000]}
"""
        try:
            raw = await self._generate_content([{"text": prompt}], temperature=0.1)
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)
            if not parsed.get("employment_type"):
                parsed["employment_type"] = heuristics.get("employment_type", "Full-time")
            ai_skills = parsed.get("required_skills", []) or []
            heur_skills = heuristics.get("required_skills", []) or []
            parsed["required_skills"] = list(dict.fromkeys(ai_skills + heur_skills))[:15]
            return parsed
        except Exception as e:
            logger.debug(f"AI post parsing fallback to heuristics: {e}")
            return heuristics

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
        from src.core.matching_engine import classify_role_domain, evaluate_domain_compatibility

        # 1. Domain Pre-Check & Classification
        cand_domain = classify_role_domain(
            candidate_profile.get("primary_title", ""),
            candidate_profile.get("summary", ""),
            candidate_profile.get("skills", [])
        )
        job_domain = classify_role_domain(
            job_structured.get("title", ""),
            job_raw,
            job_structured.get("required_skills", [])
        )
        is_compat, max_domain_score, reason = evaluate_domain_compatibility(cand_domain, job_domain)

        # Incompatible domain hard rejection
        if not is_compat:
            return {
                "match_score": int(max_domain_score),
                "strengths": [
                    f"Candidate has strong background in {cand_domain}.",
                    f"Target position requires specialization in {job_domain}."
                ],
                "gap_advisory": f"Role is in {job_domain}, which falls outside your {candidate_profile.get('primary_title', 'software engineering')} specialization."
            }

        # Dynamic fallback calculation based on true overlap
        def compute_smart_fallback() -> Dict[str, Any]:
            cand_skills = [s.lower() for s in candidate_profile.get("skills", [])]
            job_skills = [s.lower() for s in job_structured.get("required_skills", [])]
            matched = [s for s in job_skills if any(cs in s or s in cs for cs in cand_skills)]
            overlap_ratio = len(matched) / max(1, min(len(job_skills), 6)) if job_skills else 0.5
            skill_pts = int(overlap_ratio * 40)
            domain_pts = 35 if cand_domain == job_domain else 20

            t_cand = candidate_profile.get("primary_title", "").lower()
            t_job = job_structured.get("title", "").lower()
            title_pts = 15 if any(w in t_job for w in t_cand.split()) else 5

            c_exp = candidate_profile.get("years_of_experience", 0)
            j_exp = job_structured.get("required_experience_years", 0)
            exp_pts = 10 if c_exp >= j_exp else 5

            calculated_score = min(int(max_domain_score), domain_pts + skill_pts + title_pts + exp_pts)
            strengths = []
            if matched:
                strengths.append(f"Matching technical competencies: {', '.join(matched[:3])}.")
            else:
                strengths.append(f"Strong foundation in {candidate_profile.get('primary_title', 'modern software engineering')}.")
            strengths.append(f"Direct experience alignment with {c_exp} years in the domain.")

            missing = [s for s in job_skills if s not in matched]
            gap = f"Prepare to discuss hands-on experience with {missing[0]}." if missing else "Emphasize past system architecture and performance achievements."

            return {
                "match_score": calculated_score,
                "strengths": strengths[:2],
                "gap_advisory": gap
            }

        if not self.is_configured():
            return compute_smart_fallback()

        prompt = f"""You are an elite Chief Technology Officer & Talent Matching Director.
Evaluate the exact contextual, domain, and technical alignment between this Candidate Profile and Job Listing.
Be analytical, objective, and realistic.

CRITICAL DOMAIN & CONTEXT MATCHING RULES:
1. SEMANTIC CONTEXT: If candidate is a Fullstack / Software Engineer and the job is Network Engineering, Telecom, Hardware Technician, Civil Engineering, or Finance, score MUST be below 25%.
2. ROLE RELEVANCE: If candidate is Fullstack Software Engineer, matching with Backend or Frontend roles IS ALLOWED only if skill overlap is high (>= 75%).
3. SKILL OVERLAP: Measure overlap between Candidate skills and Job Required skills.
4. EXPERIENCE: Candidate has {candidate_profile.get('years_of_experience', 0)} yrs, Job requires {job_structured.get('required_experience_years', 0)} yrs.

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
            parsed = json.loads(raw)
            # Ensure score does not breach max domain compatibility
            if parsed.get("match_score", 0) > max_domain_score:
                parsed["match_score"] = int(max_domain_score)
            return parsed
        except Exception as e:
            logger.error(f"Error evaluating match precision: {e}")
            return compute_smart_fallback()

    # -------------------------------------------------------------
    # 5. Tailored Cover Letter Generator (Context- & Project-Aware)
    # -------------------------------------------------------------
    async def generate_cover_letter(
        self,
        candidate_name: str,
        candidate_profile: Dict[str, Any],
        job_data: Dict[str, Any]
    ) -> str:
        """Generates an executive, highly targeted 3-paragraph cover letter based on candidate's real projects and experience."""
        title = job_data.get("title") or "Software Engineer"
        company = job_data.get("company") or "your organization"
        cand_title = candidate_profile.get("primary_title") or "Fullstack Software Engineer"
        cand_skills = candidate_profile.get("skills", [])
        skills_highlight = ", ".join(cand_skills[:5]) if cand_skills else "modern software engineering and problem-solving"
        years_exp = candidate_profile.get("years_of_experience", 2)
        edu = candidate_profile.get("highest_education", "Computer Science & Engineering")
        cand_projects = candidate_profile.get("projects", [])
        portfolio_url = candidate_profile.get("portfolio_url", "")

        projects_summary = "\n".join(f"- {p}" for p in cand_projects[:3]) if cand_projects else "Architected scalable full-stack web platforms and microservices with high test coverage."
        proj_ref = f"delivering projects such as {cand_projects[0]}" if cand_projects else f"architecting high-performance systems with {skills_highlight}"

        fallback = f"""Dear Hiring Team at {company},

I am writing to express my strong enthusiasm for the {title} position. With my background as a {cand_title} holding a {edu} and {years_exp}+ years of hands-on experience, I am confident in my ability to contribute meaningfully to {company}'s technical roadmap.

Throughout my experience, I have focused on {proj_ref}, designing scalable architectures, optimizing database throughput, and shipping robust features. My deep expertise in {skills_highlight} directly aligns with the requirements outlined in your {title} vacancy, enabling me to ramp up quickly and deliver immediate business impact.

I would welcome the opportunity to discuss how my qualifications, technical leadership, and proactive mindset can drive measurable success for {company}. Thank you for your time and consideration.

Sincerely,
{candidate_name}"""

        if not self.is_configured():
            return fallback

        raw_job_post = job_data.get("raw_text", "")
        prompt = f"""You are an executive recruiting coach and professional career copywriter.
Analyze the candidate's actual projects, portfolio, and work history from their resume, along with the vacancy details.
Write an exceptional, compelling 3-paragraph cover letter specifically tailored to the following candidate and job vacancy.

Candidate Information:
- Full Name: {candidate_name}
- Current/Target Role: {cand_title}
- Education: {edu}
- Experience: {years_exp} years
- Core Skills: {', '.join(cand_skills)}
- Portfolio/GitHub: {portfolio_url or 'Available upon request'}
- Key Projects & Experience from Resume:
{projects_summary}
- Profile Summary: {candidate_profile.get('summary', '')}

Job Vacancy Information:
- Role Title: {title}
- Company: {company}
- Location: {job_data.get('location', 'Addis Ababa')}
- Required Skills: {json.dumps(job_data.get('required_skills', []))}
- Stated Deadline: {job_data.get('deadline', 'Open')}
- Job Post Context:
\"\"\"
{raw_job_post[:2500]}
\"\"\"

Rules:
1. Exactly 3 impactful paragraphs:
   - Paragraph 1: Enthusiastic opening directly naming the {title} role at {company}, stating candidate's degree ({edu}) and core engineering strengths.
   - Paragraph 2: EVIDENCE-DRIVEN & PROJECT-FOCUSED. Directly cite 1-2 specific projects or hands-on accomplishments ({skills_highlight}, {years_exp} yrs exp) from the candidate's background, connecting them directly to the company's stated job requirements.
   - Paragraph 3: Professional closing conveying enthusiasm for {company} and a polite, confident call to action for an interview.
2. Tone: Confident, articulate, modern, professional. Absolutely NO generic clichés or lazy template phrasing.
3. Plain letter format. No header address blocks. Start with "Dear Hiring Team at {company}," and end with "Sincerely,\n{candidate_name}".
"""
        for attempt in range(2):
            try:
                letter = await self._generate_content([{"text": prompt}], temperature=0.25)
                if letter and len(letter.strip()) > 100:
                    return letter.strip()
            except Exception as e:
                logger.warning(f"Gemini cover letter generation attempt {attempt + 1} error: {e}")
                if attempt == 0:
                    await asyncio.sleep(2.0)

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
