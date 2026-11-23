# **JobSniper ET — AI Job Matcher, Career Sniper & Mock Interview Coach**

# **Software Requirements Specification & Product Requirements Document**

## **1\. Document Control & Metadata**

| Field | Value |
| :---- | :---- |
| **Product Name** | JobSniper ET — AI Job Matcher, Career Sniper & Mock Interview Coach |
| **Document Version** | v1.0 |
| **Status** | Approved for Engineering |
| **Target Platform** | Telegram Bot & Telegram Mini App (TMA) |
| **Target Market** | Ethiopia / East Africa Time (UTC+3) |
| **Supported Languages** | English, Amharic (አማርኛ), Afaan Oromo |
| **Author / Lead** | Product & Systems Engineering |

---

## **2\. Executive Summary & Problem Statement**

### **Background & Market Context**

In Ethiopia, Telegram is not merely a messaging tool—it serves as the primary daily digital operating system for commerce, education, and employment listings. Tens of thousands of job vacancies are published daily across more than 50 high-volume public channels (e.g., *HaHuJobs*, *Ethiojobs*, *Sheger Jobs*, *Freelance Ethiopia*). However, candidates face severe structural frictions in navigating this fragmented landscape.

### **Problem Statement**

* **Information Overload & Fatigue:** Candidates must manually check dozens of channels daily, scrolling through hundreds of irrelevant posts.  
* **Repetitive Cross-Posting:** Agencies and posters cross-post identical or slightly modified vacancies across multiple channels, cluttering feeds.  
* **Missed Deadlines:** Fast-moving openings close within hours, causing qualified candidates to miss narrow application windows.  
* **Sub-optimal Applications:** Candidates submit generic, uncompetitive cover letters or fail to align their qualifications with implicit recruiter requirements.

### **Product Vision & Value Proposition**

**JobSniper ET** is an automated, low-bandwidth career assistant operating directly inside Telegram. It monitors 50+ target channels 24/7, deduplicates posts, extracts structured metadata, matches job criteria against candidate CVs using hybrid vector search \+ LLM evaluation, sends real-time alerts when match scores reach 80%+, drafts customized cover letters, and conducts interactive text/voice mock interviews.

---

## **3\. Target User Personas**

### **Persona 1: The Recent University Graduate**

* **Profile:** Fresh graduate in Computer Science or Business Administration from Addis Ababa University.  
* **Pain Points:** Lacks a structured corporate CV; lacks interview experience in professional English; overwhelmed by mixed-level channel postings.  
* **Needs:** Guided profile creation without uploading a PDF; step-by-step entry-level filtering; interactive mock interview practice with real-time feedback.

### **Persona 2: The Mid-Career Professional / NGO Applicant**

* **Profile:** Experienced Specialist with 5+ years in international development or finance.  
* **Pain Points:** High daily workload with limited time to scan channels; seeks specific roles (e.g., NGO, USAID, specialized consulting); loses opportunities due to rapid deadline expiry.  
* **Needs:** Strict match thresholding (\>= 80%); instant notifications; automated mapping of CV experience to job criteria; tailored application drafts.

### **Persona 3: The Remote & Freelance Tech Worker**

* **Profile:** Software Engineer or UI/UX Designer seeking international remote or local contract roles.  
* **Pain Points:** Competition for remote gigs requires immediate response; job requirements are technical and specific.  
* **Needs:** Sub-minute alert latency; technical pre-screening via mock interview scenarios; automated portfolio highlight mapping.

---

## **4\. Scope & Phased Release Plan**

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PHASED RELEASE ROADMAP                          │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE 1: MVP (Months 1–2)                                              │
│  ├─ PDF/DOCX Parsing & Text Extraction                                 │
│  ├─ Guided Fresh-Grad Profile Onboarding                               │
│  ├─ 10–15 Core Channel Listener + Deduplication                        │
│  └─ Hybrid 80%+ Matching Alerts & Basic Cover Letter Drafts            │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE 2: V1.1 (Months 3–4)                                             │
│  ├─ Expansion to 50+ Ethiopian Public Channels                        │
│  ├─ User Relevance Feedback Loop ("Not Relevant" / "Applied")          │
│  └─ 5-Question Text & Voice-Note Mock Interview Coach (STAR Method)    │
├────────────────────────────────────────────────────────────────────────┤
│ PHASE 3: V2.0 (Months 5–6)                                             │
│  ├─ Telegram Mini App (TMA) Graphical Dashboard                        │
│  ├─ CV Bullet-Point & Skills Gap Optimizer                             │
│  └─ Local Payment Integration (Chapa & Telebirr for Pro Tier)          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## **5\. Functional Requirements (FRs)**

### **FR-1: Candidate Onboarding & CV Ingestion (`/start`, `/profile`)**

* **FR-1.1 Language Selection:** The system shall prompt users upon first launch to select an interface language: English, Amharic (አማርኛ), or Afaan Oromo.  
* **FR-1.2 File Upload & Processing:** The system shall accept CV uploads in PDF and DOCX formats (up to 10MB). It shall extract raw text, run structured parsing via LLM, generate a normalized candidate profile JSON, and produce a 768-dimension vector embedding.  
* **FR-1.3 Guided Profile Builder:** For candidates without a ready CV file, the system shall provide an interactive 4-step conversational wizard collecting:  
  1. Field of study & highest degree.  
  2. Years of professional experience & primary role title.  
  3. Core technical and soft skills (comma-separated or quick-reply chips).  
  4. Preferred employment type (Full-time, Contract, Remote, Internship) & location.  
* **FR-1.4 Preferences & Quiet Hours:** Users shall be able to configure:  
  * Minimum match score threshold (Default: `80%`; Range: `70%` to `95%`).  
  * Target industry/sector filters.  
  * Quiet hours (Default: `22:00` to `07:00` EAT) during which non-critical notifications are queued.

### **FR-2: Multi-Channel Job Ingestion & Deduplication Engine**

* **FR-2.1 Real-Time Ingestion:** An automated MTProto client shall continuously monitor 50+ public Telegram channels for new posts.  
* **FR-2.2 Two-Layer Deduplication:**  
  * *Exact Matches:* SHA-256 hash calculation on normalized text string (lowercased, whitespace-stripped).  
  * *Near-Duplicates:* Cosine similarity evaluation against all job embeddings ingested over the preceding 48 hours (Threshold \>= `0.92` flags as duplicate cross-post).  
* **FR-2.3 Entity Extraction:** The pipeline shall parse raw job text into structured fields: `job_title`, `organization`, `location`, `deadline`, `required_experience_years`, `required_skills`, `salary_range` (if available), and `application_contact` (email, web link, or Telegram handle).

### **FR-3: Two-Stage Hybrid AI Matching & Sniper Alerts**

* **FR-3.1 Stage 1 (Vector Pre-Filtering):** Execute an ANN (Approximate Nearest Neighbor) cosine distance query in PostgreSQL (`pgvector`) matching candidate CV embeddings against newly ingested job embeddings. Filters top candidate candidates in \< 20ms.  
* **FR-3.2 Stage 2 (LLM Precision Scoring):** Candidates selected in Stage 1 with vector scores \>= 0.70 are evaluated by Gemini 2.5 Flash. The model verifies strict operational constraints (e.g., experience years, required certifications, language fluency) to produce:  
  * Final Match Score (`0%`–`100%`).  
  * Two bullet points detailing structural alignment.  
  * One action-oriented skill gap advisory.  
* **FR-3.3 Alert Delivery:** If Final Match Score \>= candidate threshold, an alert card is pushed via Telegram Bot API with inline action buttons:  
  `[ 📝 Generate Cover Letter ]` `[ 🎙️ Practice Mock Interview ]`  
  `[ 🔗 View Original Post ]` `[ ✅ Mark Applied ]` `[ ❌ Not Relevant ]`

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SAMPLE TELEGRAM ALERT CARD                      │
├────────────────────────────────────────────────────────────────────────┤
│ 🎯 NEW JOB MATCH: 88% Match Score                                      │
│                                                                        │
│ 💼 Senior Backend Engineer                                            │
│ 🏢 EthioTech Solutions PLC                                             │
│ 📍 Addis Ababa (Hybrid) | ⏳ Deadline: Oct 28, 2025                    │
│                                                                        │
│ 💡 Alignment Strengths:                                                │
│ • Your 4 years of Python/FastAPI experience matches the 3+ yr requirement. │
│ • Strong overlap in PostgreSQL optimization & Microservices architecture. │
│                                                                        │
│ ⚠️ Skill Gap Advisory:                                                │
│ • Job listing mentions Redis Caching; highlight your memory management projects. │
│                                                                        │
│ [ 📝 Generate Cover Letter ]  [ 🎙️ Practice Mock Interview ]           │
│ [ 🔗 View Original Post ]     [ ✅ Applied ]   [ ❌ Not Relevant ]    │
└────────────────────────────────────────────────────────────────────────┘
```

### **FR-4: One-Tap Tailored Cover Letter Generator**

* **FR-4.1 Generation Engine:** When triggered via inline button, the system ingests the target job's extracted criteria and candidate CV context to produce a concise 3-paragraph application draft.  
* **FR-4.2 Formatting:** Output is structured for copy-pasting directly into an email client or Telegram recruiter message, mapping specific past candidate achievements to stated job demands.

### **FR-5: AI Mock Interview & Communication Coach (`/interview`)**

* **FR-5.1 Execution Modes:** Accessible from any alert card or by sending custom job description text. Supports both **Text Mode** and **Voice-Note Mode** (Telegram `.ogg` Opus format).  
* **FR-5.2 Structured 5-Question Simulation Sequence:**  
  1. *Question 1:* Professional Pitch & Background Introduction.  
  2. *Question 2:* Technical / Domain Competency Challenge.  
  3. *Question 3:* Behavioral Scenario (STAR Framework requirement).  
  4. *Question 4:* Situational Problem-Solving under constraint.  
  5. *Question 5:* Role Alignment & Expected Impact / Availability.  
* **FR-5.3 Voice Processing:** Audio inputs are transcribed via Gemini's audio processing capabilities, evaluating technical substance, articulation, and vocabulary.  
* **FR-5.4 Evaluation & Feedback:** Upon completion of the session, the system issues a performance summary card detailing:  
  * Overall Readiness Score (`0.0`–`10.0`).  
  * Granular breakdowns for Grammar, Technical Depth, and STAR Structure.  
  * "10/10 Model Responses" for questions where the user scored below threshold.

---

## **6\. Non-Functional Requirements (NFRs)**

| NFR Category | Requirement Specification | Metric / Target |
| :---- | :---- | :---- |
| **Performance & Latency** | End-to-end alert latency (Telegram post to alert dispatch) | \< 60 seconds total |
|  | Bot Webhook acknowledgment latency | \< 300 milliseconds |
|  | Stage 1 Vector similarity query lookup time | \< 20 milliseconds |
| **Scalability & Throughput** | Active Concurrent Candidate Profiles supported | 50,000+ active profiles |
|  | Ingested Job Volume processing capacity | 5,000+ daily posts |
|  | Telegram API Outbound Throttling protection | \<= 25 messages/second global queue |
| **Low-Bandwidth & Mobile** | Text Payload Optimization for 2G/3G connections | Core alert message \< 4 KB |
|  | Voice-Note Handling | Compressed `.ogg` Opus audio (\<= 16kHz) |
| **Reliability & Resilience** | Job Processing Idempotency via Redis locks | Zero duplicate alerts per user |
|  | MTProto Ingestion Client Error Recovery | Exponential backoff on `FloodWait` errors |
|  | Invalid Session Cleanup | Auto-deactivation on Telegram `403 Forbidden` |
| **Security & Privacy** | At-Rest Data Encryption | AES-256-GCM for raw CV text & transcripts |
|  | In-Transit Encryption | TLS 1.3 enforced across all webhooks & APIs |
|  | User Control & Data Rights | `/delete_data` command purges all DB entries |

---

## **7\. System Architecture & Technology Stack**

### **High-Level System Architecture**

```
                    ┌─────────────────────────────────────────┐
                    │ 50+ Public Telegram Job Channels        │
                    └──────────────────┬──────────────────────┘
                                       │ Real-time MTProto Stream
                                       v
                    ┌─────────────────────────────────────────┐
                    │ Worker: Ingestion Listener (Telethon)   │
                    └──────────────────┬──────────────────────┘
                                       │ Raw Message
                                       v
                    ┌─────────────────────────────────────────┐
                    │ Redis Queue (BullMQ) & SHA-256 Check    │
                    └──────────────────┬──────────────────────┘
                                       │ Deduplicated Payload
                                       v
                    ┌─────────────────────────────────────────┐
                    │ AI Pipeline (Gemini 2.5 Flash)          │
                    │ - Extraction & Embedding Generation     │
                    └──────────────────┬──────────────────────┘
                                       │ Structured Job + Embedding
                                       v
                    ┌─────────────────────────────────────────┐
                    │ PostgreSQL 16 DB + pgvector (v0.8.7+)   │
                    └──────────────────┬──────────────────────┘
                                       │ Candidate ANN Vector Match
                                       v
                    ┌─────────────────────────────────────────┐
                    │ Two-Stage Hybrid Match Engine           │
                    │ - Stage 1: Vector Pre-Filter (<20ms)    │
                    │ - Stage 2: Gemini LLM Evaluation        │
                    └──────────────────┬──────────────────────┘
                                       │ Qualified Matches (>=80%)
                                       v
                    ┌─────────────────────────────────────────┐
                    │ Outbound Queue (Throttled Rate Limiter) │
                    └──────────────────┬──────────────────────┘
                                       │ Final Alert
                                       v
                    ┌─────────────────────────────────────────┐
                    │ Telegram Bot API / User Client          │
                    └─────────────────────────────────────────┘
```

### **Recommended Technology Stack**

| Layer | Component Technology | Selection Rationale |
| :---- | :---- | :---- |
| **Runtime & Framework** | Python 3.12+ with `aiogram` v3.x | Asynchronous core, native support for modern Telegram Bot API features. |
| **Ingestion Engine** | Telethon (Python MTProto Client) | Efficient user-bot client connection for multi-channel listening. |
| **Database & Vector Store** | PostgreSQL 16 \+ `pgvector` (v0.8.7+) | Combined relational data storage and vector indexing (`HNSW` indexes). |
| **Queue & FSM Cache** | Redis 7+ with `BullMQ` / `redis-py` | Session storage, state tracking, and rate-limited alert dispatch. |
| **Document Processing** | PyMuPDF (`fitz`) & `python-docx` | Fast text extraction from PDF and Word documents. |
| **AI Models** | Google Gemini 2.5 Flash \+ Text Embeddings | High context window, cost-efficient fast inference, native audio capability. |
| **Deployment Platform** | Docker Compose on Linux VPS (Ubuntu 22.04 LTS) | Containerized deployment behind a Caddy reverse proxy. |

---

## **8\. Database Schema Specification**

```
-- Enable Vector Extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table 1: Candidates Profile Table
CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    ui_language VARCHAR(10) DEFAULT 'en', -- en, am, om
    cv_raw_text_encrypted TEXT,
    structured_profile JSONB DEFAULT '{}'::jsonb,
    cv_embedding vector(768),
    min_match_score INT DEFAULT 80,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '07:00',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_candidates_embedding ON candidates 
USING hnsw (cv_embedding vector_cosine_ops);

-- Table 2: Ingested Job Listings
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_channel VARCHAR(255) NOT NULL,
    source_message_id BIGINT NOT NULL,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255) DEFAULT 'Not Specified',
    location VARCHAR(255) DEFAULT 'Ethiopia',
    deadline VARCHAR(100),
    structured_data JSONB DEFAULT '{}'::jsonb,
    job_embedding vector(768),
    raw_text TEXT NOT NULL,
    posted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_embedding ON jobs 
USING hnsw (job_embedding vector_cosine_ops);

-- Table 3: Job Match Results & History
CREATE TABLE job_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    match_score INT NOT NULL,
    match_reasoning TEXT[],
    skill_gap_tip TEXT,
    cover_letter_draft TEXT,
    user_feedback VARCHAR(50) DEFAULT 'pending', -- applied, not_relevant, pending
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_candidate_job UNIQUE(candidate_id, job_id)
);

-- Table 4: Mock Interview Sessions
CREATE TABLE mock_interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    job_context TEXT NOT NULL,
    mode VARCHAR(10) DEFAULT 'text', -- text, voice
    transcript JSONB DEFAULT '[]'::jsonb,
    final_score NUMERIC(3, 1),
    status VARCHAR(20) DEFAULT 'in_progress', -- in_progress, completed, abandoned
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## **9\. Edge Cases, Risk Mitigation & Success Metrics (KPIs)**

### **Risk & Mitigation Matrix**

| Identified Edge Case / Risk | Impact Level | Engineering Mitigation Strategy |
| :---- | :---- | :---- |
| **Telegram MTProto Session Rate-Limiting / Bans** | High | Use dedicated service accounts; implement staggered request intervals; apply linear backoff on `FloodWait` exceptions. |
| **Malformed / Scanned Image PDFs** | Medium | Fallback to lightweight OCR processing engine (`Tesseract`) if extracted raw text length \< 100 characters. |
| **Cross-Channel Duplicate Floods** | Medium | Combine exact SHA-256 hash checks with a 48-hour rolling cosine similarity check (`>= 0.92`) prior to LLM evaluation. |
| **Hallucinated Job Requirements in Scoring** | High | Enforce strict structured JSON outputs from Gemini models with explicit validation against input job text. |
| **Excessive Audio Bandwidth Usage** | Low | Limit voice note processing to a maximum duration of 120 seconds per response; compress audio before API transmission. |

### **Product Success Metrics (KPIs)**

| Success Metric | Target Threshold | Method of Verification |
| :---- | :---- | :---- |
| **Alert-to-Apply Click Rate** | \> 25% | Percentage of pushed match alerts resulting in user clicking "Mark Applied" or "Generate Cover Letter". |
| **False Positive Alert Rate** | \< 10% | Percentage of sent alerts marked as "Not Relevant" by end users. |
| **End-to-End Alert Latency** | \< 60 seconds | Time delta measured from channel post time to user notification timestamp. |
| **Mock Interview Completion Rate** | \> 60% | Percentage of initiated interview sessions (`/interview`) completing all 5 simulation stages. |
| **Day-30 User Retention Rate** | \> 40% | Proportion of registered candidates returning to engage with alerts or features within 30 days. |

