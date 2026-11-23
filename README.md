# 🎯 JobSniper ET — AI Job Matcher, Career Sniper & Mock Interview Coach

> **Production-grade, low-bandwidth AI Career Assistant & Telegram Bot engineered for Ethiopia and East Africa.**  
> Continuously monitors **50+ public Ethiopian job channels 24/7**, deduplicates listings, extracts structured metadata, matches candidate CVs using **Hybrid Vector Search + Gemini AI**, sends real-time sniper alerts (< 60s latency), drafts tailored cover letters in one tap, and coaches candidates through 5-question STAR mock interviews (Text & Voice Notes).

---

## 🌟 Executive System Capabilities

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

### 1. ⚡ Real-Time Ingestion & Multi-Channel Listener
- Connects directly to **50+ curated Ethiopian Telegram channels** (*HaHuJobs*, *Ethiojobs*, *Freelance Ethiopia*, *Sheger Jobs*, *NGO Vacancies*, *Dereja*, *Banking Careers*) via **Telethon MTProto client**.
- Resilient reconnection with exponential backoff on Telegram `FloodWaitError`.

### 2. 🛡️ Two-Layer Deduplication Engine
- **Layer 1 (Exact):** SHA-256 text hash over normalized string (stripped URLs, handles, and whitespace).
- **Layer 2 (Near-Duplicates):** 48-hour rolling cosine similarity check (`>= 0.92`) across all recent job embeddings in PostgreSQL, preventing duplicate alerts from cross-posting agencies.

### 3. 🎯 Two-Stage Hybrid AI Matching Engine
- **Stage 1 (Vector Pre-Filtering):** Instant Approximate Nearest Neighbor (ANN) cosine distance query in PostgreSQL with `pgvector` HNSW indexes (`< 20ms`).
- **Stage 2 (LLM Precision Scoring):** Candidates with cosine similarity `>= 0.70` are evaluated by **Gemini 2.5 Flash** to strictly verify experience years, specific tool stacks, and language fluencies.
- **Alert Dispatch:** Sends alerts only when final score meets or exceeds candidate's threshold (Default: `80%`, configurable from `70%` to `95%`).

### 4. 📝 1-Tap Tailored Cover Letter Generator
- Directly maps the candidate's verified background and achievements to the specific recruiter requirements.
- Formatted in an executive 3-paragraph structure with instant Telegram copy-paste (`<code>...</code>`).

### 5. 🎙️ AI Mock Interview Coach (STAR Framework)
- Interactive 5-question sequential simulation:
  1. *Professional Pitch & Background Introduction*
  2. *Technical & Domain Competency Challenge*
  3. *Behavioral Scenario (STAR Method: Situation, Task, Action, Result)*
  4. *Situational Problem-Solving Under High-Constraint*
  5. *Role Alignment & Closing Impact*
- **Dual Mode:** Supports **Text Mode** and **Voice Note Mode** (native `.ogg` Opus audio transcribed and analyzed via Gemini multimodal audio).
- Per-question instant scoring (`0.0 - 10.0`) + comprehensive final performance report card.

### 6. 🌐 Trilingual Localization
- Full native support for **English**, **Amharic (አማርኛ)**, and **Afaan Oromoo**.

### 7. 🔒 Bank-Grade Security & Privacy
- Sensitive CV text encrypted at-rest using **AES-256-GCM**.
- Candidate GDPR-style data purge via `/delete_data` command.
- Quiet hours queueing (`22:00` - `07:00` East Africa Time) to respect user sleep schedules.

---

## 🏗️ Architecture & Technology Stack

```
                    ┌─────────────────────────────────────────┐
                    │ 50+ Public Telegram Job Channels        │
                    └──────────────────┬──────────────────────┘
                                       │ Real-time MTProto Stream
                                       v
                    ┌─────────────────────────────────────────┐
                    │ Ingestion Listener (Telethon)           │
                    └──────────────────┬──────────────────────┘
                                       │ Raw Message
                                       v
                    ┌─────────────────────────────────────────┐
                    │ Redis Queue & SHA-256 Check             │
                    └──────────────────┬──────────────────────┘
                                       │ Deduplicated Payload
                                       v
                    ┌─────────────────────────────────────────┐
                    │ AI Pipeline (Gemini 2.5 Flash)          │
                    │ - Extraction & Embedding (768-dim)      │
                    └──────────────────┬──────────────────────┘
                                       │ Structured Job + Embedding
                                       v
                    ┌─────────────────────────────────────────┐
                    │ PostgreSQL 16 DB + pgvector (HNSW)      │
                    └──────────────────┬──────────────────────┘
                                       │ Candidate ANN Vector Match (<20ms)
                                       v
                    ┌─────────────────────────────────────────┐
                    │ Stage 2: Gemini LLM Evaluation          │
                    └──────────────────┬──────────────────────┘
                                       │ Qualified Matches (>=80%)
                                       v
                    ┌─────────────────────────────────────────┐
                    │ Outbound Dispatcher (Rate Limiter <25/s)│
                    └──────────────────┬──────────────────────┘
                                       │ Final Alert Card
                                       v
                    ┌─────────────────────────────────────────┐
                    │ Telegram Bot API / User Client          │
                    └─────────────────────────────────────────┘
```

| Layer | Component | Description |
| :--- | :--- | :--- |
| **Runtime & Bot** | Python 3.12+ / 3.13, `aiogram` v3.x | Asynchronous core, FSM, custom middlewares, rich HTML formatting. |
| **AI & LLM** | Google Gemini 2.5 Flash & `text-embedding-004` | Structured entity extraction, 768-dim embeddings, audio transcription, precision scoring. |
| **Database & Vector Store** | PostgreSQL 16 + `pgvector` | Relational tables + HNSW cosine vector index for sub-20ms candidate retrieval. |
| **Cache & Queue** | Redis 7 | State storage, rate limiting, and alert dispatch queue. |
| **Document Parser** | `PyMuPDF` (`fitz`) & `python-docx` | Fast text extraction from PDF and Word documents. |
| **Security** | `cryptography` (AES-256-GCM) | Authenticated encryption for sensitive candidate documents. |
| **Deployment** | Docker & Docker Compose | Multi-container setup (Postgres + Redis + Bot + Ingestion). |

---

## 📁 Project Directory Structure

```
jobsniperet/
├── docker-compose.yml              # PostgreSQL (pgvector), Redis 7, Bot app, Ingestion worker
├── Dockerfile                      # Multi-stage production container image
├── .env.example                    # Environment variable template
├── requirements.txt                # Pinned production dependencies
├── scripts/
│   ├── init_db.py                  # Database tables & HNSW vector indexes setup
│   ├── seed_demo_jobs.py           # Seed realistic Ethiopian vacancies
│   └── test_matching.py            # Comprehensive test & verification suite
├── src/
│   ├── config/
│   │   └── settings.py             # Pydantic v2 application configuration
│   ├── core/
│   │   ├── security.py             # AES-256-GCM encryption & decryption
│   │   ├── document_parser.py      # PDF & DOCX text extractors
│   │   ├── gemini.py               # Gemini 2.5 Flash async HTTP client (Embeddings, Scoring, Audio)
│   │   ├── matching_engine.py      # 2-Stage Hybrid AI Matching Engine
│   │   ├── cover_letter_engine.py  # 1-Tap tailored cover letter generator
│   │   └── interview_coach.py      # STAR mock interview simulation coach
│   ├── db/
│   │   ├── session.py              # Async SQLAlchemy engine & session factory
│   │   ├── models/                 # Candidate, Job, JobMatch, MockInterview
│   │   └── repositories/           # CandidateRepo, JobRepo, MatchRepo, InterviewRepo
│   ├── ingestion/
│   │   ├── channels.py             # Curated list of 50+ Ethiopian job channels
│   │   ├── deduplicator.py         # SHA-256 & 48h cosine deduplication
│   │   ├── parser.py               # Channel post normalization & structured entity extraction
│   │   └── listener.py             # Telethon MTProto 24/7 channel stream listener
│   ├── queue/
│   │   ├── redis_client.py         # Async Redis connection pool
│   │   └── dispatcher.py           # Rate-limited alert dispatcher with quiet hours
│   ├── locales/                    # Trilingual localization dictionaries
│   │   ├── en.json                 # English
│   │   ├── am.json                 # Amharic (አማርኛ)
│   │   └── om.json                 # Afaan Oromoo
│   ├── bot/
│   │   ├── bot.py                  # Bot instance, router registrations, command setup
│   │   ├── middlewares/            # I18n and Anti-spam throttling middlewares
│   │   ├── states/                 # Onboarding & Interview FSM states
│   │   ├── keyboards/              # Common, Profile, Interview, and Alert keyboards
│   │   └── handlers/               # Start, Onboarding, Profile, Alerts, Cover Letter, Interview
│   └── main.py                     # CLI launcher (--service bot, ingestion, all)
└── README.md
```

---

## 🚀 Quickstart & Production Setup

### 1. Clone & Configure Environment
```bash
cp .env.example .env
nano .env
```
Fill in your credentials:
- `TELEGRAM_BOT_TOKEN`: From [@BotFather](https://t.me/BotFather)
- `GEMINI_API_KEY`: From [Google AI Studio](https://aistudio.google.com/)
- `TELEGRAM_API_ID` & `TELEGRAM_API_HASH`: From [my.telegram.org](https://my.telegram.org) (for channel listener)

### 2. Run Database & Cache via Docker
```bash
docker compose up -d postgres redis
```

### 3. Initialize Database Schema & Vector Indexes
```bash
python3 scripts/init_db.py
```

### 4. Seed Realistic Vacancies (Optional Demo)
```bash
python3 scripts/seed_demo_jobs.py
```

### 5. Run Verification Test Suite
```bash
python3 scripts/test_matching.py
```

### 6. Launch Services
Run the Telegram Bot:
```bash
python3 -m src.main --service bot
```
Or launch both the Bot and the Channel Listener concurrently:
```bash
python3 -m src.main --service all
```

Or deploy everything with one command in Docker:
```bash
docker compose up -d --build
```

---

## 🤖 Bot Commands Reference

| Command | Description |
| :--- | :--- |
| `/start` | Launches onboarding, prompts language selection (EN/AM/OM), and builds CV profile. |
| `/profile` | Displays candidate profile card, match threshold slider, and quiet hours. |
| `/interview` | Launches interactive 5-question STAR AI mock interview coach (Text / Voice Notes). |
| `/delete_data` | Permanently purges all candidate data, resumes, and logs (GDPR & privacy compliance). |
| `/help` | Explains how the bot works, matching thresholds, and support contacts. |

---

## 📄 License
Proprietary & Confidential — Engineered for JobSniper ET.

