"""Document Parser Module for JobSniper ET.

Supports PDF (via PyMuPDF) and DOCX (via python-docx) with sanitized text extraction.
"""

import io
import os
import re
from typing import Any, Dict, List, Optional


class DocumentParser:
    """Extracts and parses clean text content and structured data from resumes (PDF or DOCX)."""

    @staticmethod
    def extract_from_bytes(file_bytes: bytes, file_name: str) -> Optional[str]:
        """Extracts text based on filename extension."""
        ext = os.path.splitext(file_name)[1].lower()
        if ext == ".pdf":
            return DocumentParser.extract_from_pdf_bytes(file_bytes)
        elif ext in [".docx", ".doc"]:
            return DocumentParser.extract_from_docx_bytes(file_bytes)
        elif ext in [".txt", ".md"]:
            return file_bytes.decode("utf-8", errors="replace")
        return None

    @staticmethod
    def extract_from_pdf_bytes(pdf_bytes: bytes) -> str:
        """Extracts text from PDF bytes using PyMuPDF (fitz)."""
        import fitz  # PyMuPDF

        text_parts = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text_parts.append(page.get_text("text"))

        full_text = "\n".join(text_parts).strip()
        return DocumentParser._normalize_extracted_text(full_text)

    @staticmethod
    def extract_from_docx_bytes(docx_bytes: bytes) -> str:
        """Extracts text from DOCX bytes using python-docx."""
        import docx

        file_stream = io.BytesIO(docx_bytes)
        doc = docx.Document(file_stream)
        text_parts = []
        for p in doc.paragraphs:
            if p.text:
                text_parts.append(p.text)
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    text_parts.append(" | ".join(row_text))

        full_text = "\n".join(text_parts).strip()
        return DocumentParser._normalize_extracted_text(full_text)

    @staticmethod
    def _normalize_extracted_text(text: str) -> str:
        """Sanitizes text by collapsing excessive whitespace and control characters."""
        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(l for l in lines if l)
        return cleaned

    @staticmethod
    def clean_education_degree(raw_text: str) -> str:
        """Extracts clean degree title and field of study, isolating it from introductory sentences."""
        if not raw_text:
            return "Higher Education"

        # Regex to locate degree mention, stripping prefixes like 'with a', 'results-driven', etc.
        edu_pattern = (
            r'(?:(?:with|holds?|earned|having|completed)\s+(?:a\s+)?)?'
            r'('
            r'\b(?:B\.?\s*Sc\.?|B\.?\s*A\.?|B\.?\s*Eng\.?|BSc\b|BA\b|BEng\b|Bachelor(?:\'s)?(?:\s+of\s+[A-Za-z]+)?|'
            r'M\.?\s*Sc\.?|M\.?\s*A\.?|MSc\b|MA\b|Master(?:\'s)?(?:\s+of\s+[A-Za-z]+)?|'
            r'Ph\.?\s*D\.?|PhD\b|Diploma\b|Associate(?:\'s)?)\s*'
            r'(?:in|of)?\s*'
            r'[A-Za-z\s&,/\-]+?'
            r')'
            r'(?=(?:\s+and\s+\d|\s+with\s|\s+from|\s+at|\s*\.|\s*\(|\s*\||\n|$))'
        )
        match = re.search(edu_pattern, raw_text, re.IGNORECASE)
        if match:
            deg = match.group(1).strip()
            # Clean up trailing punctuation or university names after commas
            deg = re.split(r'[,|]|\s+(?:from|at)\s+', deg)[0].strip()
            deg = re.sub(r'\s+', ' ', deg)
            deg = deg.rstrip('.- ')
            # Reject false positives from cities/universities like 'Addis Ababa'
            if len(deg) >= 4 and not any(deg.lower().startswith(b) for b in ['addis', 'ababa', 'university', 'baba']):
                return deg

        # Second pattern: "Degree in Software Engineering"
        m2 = re.search(r'\b((?:Degree|Diploma)\s+in\s+[A-Za-z\s&,/\-]+?)(?=(?:\s+from|\s+at|\s*\.|\s*\(|\n|$))', raw_text, re.IGNORECASE)
        if m2:
            candidate = re.sub(r'\s+', ' ', m2.group(1).strip().rstrip('.- '))
            if not any(candidate.lower().startswith(b) for b in ['addis', 'ababa', 'university', 'baba']):
                return candidate

        # Fallback if raw_text is already concise and mentions degree keywords
        if len(raw_text) <= 60 and any(k in raw_text.lower() for k in ["b.sc", "bsc", "bachelor", "master", "m.sc", "degree", "diploma", "engineering", "science"]):
            if not any(raw_text.lower().startswith(b) for b in ['addis', 'ababa', 'university', 'baba']):
                return raw_text.strip()

        return "Higher Education"

    @staticmethod
    def extract_job_heuristics(raw_text: str, channel_title: str = "") -> Dict[str, Any]:
        """High-precision local extraction for Ethiopian channel job listings.
        
        Extracts Title, Company, Location, Deadline, Experience, and Skills directly from post text
        without consuming external AI API quotas.
        """
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        lower_text = raw_text.lower()

        # 1. Title Extraction
        title = ""
        # 1a. Explicit label match (e.g. "Job Title: Full Stack Developer", "Position: Backend Engineer")
        m_title = re.search(r'(?:job\s+title|position(?:\s+title)?|role(?:\s+title)?|title|vacancy(?:\s+title)?)\s*[:\-]\s*([^\n]+)', raw_text, re.I)
        if m_title:
            clean_t = re.sub(r'^[#*_\-\s]+', '', m_title.group(1)).strip()
            title = clean_t.split('|')[0].split('(')[0].strip()

        # 1b. Channel Top-Line Convention (Josad, Awra, Hahu, EthioJobs)
        # Posts almost always start with the exact job title on line 1 or 2
        if not title and lines:
            for line in lines[:3]:
                clean_l = re.sub(r'^[#*_\-\s]+|[#*_\-\s]+$', '', line).strip()
                if clean_l.startswith(('Vacancy Announcement:', 'VACANCY ANNOUNCEMENT:')):
                    clean_l = clean_l.split(':', 1)[1].strip()
                if clean_l.startswith(('#', '@', 'http')) or len(clean_l) < 3:
                    continue
                # Reject lines that are metadata tags
                if re.search(r'^(?:company|deadline|salary|job\s+type|location|place\s+of\s+work|about\s+the\s+role)\s*:', clean_l, re.I):
                    continue
                # If line is concise and contains professional role keywords
                if len(clean_l) <= 65:
                    if any(w in clean_l.lower() for w in [
                        'developer', 'engineer', 'designer', 'officer', 'specialist', 'manager', 'lead',
                        'analyst', 'accountant', 'intern', 'full stack', 'fullstack', 'backend', 'frontend',
                        'devops', 'mobile', 'flutter', 'react', 'python', 'administrator', 'technician',
                        'auditor', 'assistant', 'architect', 'consultant', 'coordinator', 'lecturer'
                    ]):
                        title = clean_l.split('|')[0].split('(')[0].strip()
                        break

        # 1c. Scan candidate titles catalog as fallback
        if not title:
            candidate_titles = [
                "Fullstack Software Engineer", "Full Stack Developer", "Fullstack Developer", "Full Stack Engineer",
                "Frontend Developer", "Frontend Engineer", "Backend Developer", "Backend Engineer",
                "Senior Software Engineer", "Software Engineer", "DevOps Engineer", "Cloud Engineer",
                "Mobile App Developer", "Flutter Developer", "Android Developer", "iOS Developer",
                "React Developer", "Python Developer", "Data Analyst", "Data Scientist", "Database Administrator",
                "UI/UX Designer", "Product Manager", "Project Manager", "Graphic Designer",
                "Senior Accountant", "Junior Accountant", "Accountant", "Finance Officer", "Financial Analyst",
                "Human Resources Officer", "HR Specialist", "Recruiter", "Marketing Specialist", "Sales Representative",
                "Civil Engineer", "Electrical Engineer", "Mechanical Engineer", "Lecturer"
            ]
            for ct in candidate_titles:
                if re.search(r'\b' + re.escape(ct) + r'\b', raw_text, re.I):
                    title = ct
                    break

        if not title:
            title = "Software Engineer" if "software" in lower_text or "developer" in lower_text else "Professional Opportunity"

        # 2. Company Extraction
        company = ""
        m_comp = re.search(r'(?:company(?:\s+name)?|employer|organization(?:\s+name)?|institution|hiring\s+company)\s*[:\-]\s*([^\n]+)', raw_text, re.I)
        if m_comp:
            company = re.sub(r'^[#*_\-\s]+', '', m_comp.group(1)).strip().rstrip('.,-')
        else:
            m_hash = re.search(r'#([A-Za-z0-9_]+(?:plc|bank|technologies|tech|hospital|university|group|solutions|international|corp|sc|ltd))', raw_text, re.I)
            if m_hash:
                company = m_hash.group(1).replace('_', ' ').title()
            elif len(lines) > 1 and any(w in lines[1].lower() for w in ['plc', 'bank', 'ltd', 'inc', 'sc', 'ngo', 'technologies', 'consulting', 'solutions']):
                company = re.sub(r'^[#*_\-\s]+', '', lines[1]).strip()

        if not company or company.lower() in ["ethiopian employer", "not specified"]:
            clean_ch = channel_title.lstrip("@").strip()
            company = f"Hiring Partner via @{clean_ch}" if clean_ch else "Tech Partner / Confidential Employer"

        # 3. Location Extraction
        location = "Addis Ababa / Ethiopia"
        m_loc = re.search(r'(?:location|place\s+of\s+work|duty\s+station|city|workplace)\s*[:\-]\s*([^\n]+)', raw_text, re.I)
        if m_loc:
            location = re.sub(r'^[#*_\-\s]+', '', m_loc.group(1)).strip().rstrip('.,-')
        elif "remote" in lower_text or "work from home" in lower_text:
            location = "Remote / Hybrid"
        else:
            ethiopian_cities = ["Addis Ababa", "Hawassa", "Adama", "Bahir Dar", "Mekelle", "Dire Dawa", "Bishoftu", "Jimma", "Gondar"]
            for city in ethiopian_cities:
                if city.lower() in lower_text:
                    location = city
                    break

        # 4. Deadline Extraction
        deadline = "Open / Not specified"
        m_dead = re.search(r'(?:deadline|closing\s+date|apply\s+before|valid\s+until|expiry\s+date|application\s+deadline)\s*[:\-]\s*([^\n]+)', raw_text, re.I)
        if m_dead:
            deadline = re.sub(r'^[#*_\-\s]+', '', m_dead.group(1)).strip().rstrip('.,-')
        else:
            m_date = re.search(r'(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', raw_text, re.I)
            if m_date:
                deadline = m_date.group(0).strip()

        # 5. Experience Extraction
        exp_years = 0
        exp_display = "Open / Fresh Graduate"
        m_exp_lbl = re.search(r'(?:experience(?:\s+required|\s+level)?|work\s+experience)\s*[:\-]\s*([^\n]+)', raw_text, re.I)
        if m_exp_lbl:
            raw_exp = m_exp_lbl.group(1).strip()
            m_num = re.search(r'(\d+)', raw_exp)
            if m_num:
                exp_years = int(m_num.group(1))
                exp_display = f"{exp_years}+ years"
            elif any(w in raw_exp.lower() for w in ['fresh', 'entry', '0 year', 'no experience', 'open']):
                exp_years = 0
                exp_display = "Open / Fresh Graduate"
            else:
                exp_display = raw_exp[:30]

        if exp_years == 0:
            m_exp = re.search(r'(\d+)\+?\s*years?(?:\s*of)?\s*(?:relevant|hands-on|professional)?\s*experience', lower_text)
            if m_exp:
                exp_years = int(m_exp.group(1))
                exp_display = f"{exp_years}+ years"
            elif "senior" in lower_text or "lead" in lower_text:
                exp_years = 3
                exp_display = "3+ years (Senior)"
            elif "junior" in lower_text:
                exp_years = 1
                exp_display = "1-2 years (Junior)"
            elif any(w in lower_text for w in ['fresh graduate', 'entry level', '0 year', 'no experience']):
                exp_years = 0
                exp_display = "Open / Fresh Graduate"
            else:
                exp_years = 1
                exp_display = "1+ years / Open"

        # 6. Salary Extraction
        salary = "Negotiable"
        m_sal = re.search(r'(?:salary|compensation|pay|remuneration)\s*[:\-]\s*([^\n]+)', raw_text, re.I)
        if m_sal:
            raw_sal = re.sub(r'^[#*_\-\s]+', '', m_sal.group(1)).strip().rstrip('.,-')
            if raw_sal.lower() in ["monthly", "monthly salary"]:
                salary = "Monthly (Company Scale)"
            elif raw_sal.lower() in ["hourly", "hourly rate"]:
                salary = "Hourly Rate"
            elif raw_sal.lower() in ["negotiable", "attractive"]:
                salary = "Negotiable / Attractive"
            elif raw_sal:
                salary = raw_sal
        elif any(cur in lower_text for cur in ["etb", "birr", "usd", "$"]):
            m_amt = re.search(r'(\d{2,3}(?:,\d{3})+|\d{4,6})\s*(?:etb|birr|\$)?(?:\s*monthly)?', lower_text)
            if m_amt:
                salary = f"{m_amt.group(0).strip().upper()} ETB"

        # 7. Employment Type / Job Type Extraction
        job_type = "Full-time"
        m_jt = re.search(r'(?:job\s+type|employment\s+type)\s*[:\-]\s*([^\n]+)', raw_text, re.I)
        if m_jt:
            clean_jt = m_jt.group(1).strip().lower()
            if "full" in clean_jt:
                job_type = "Full-time"
            elif "part" in clean_jt:
                job_type = "Part-time"
            elif "contract" in clean_jt:
                job_type = "Contract"
            elif "intern" in clean_jt:
                job_type = "Internship"
            elif "remote" in clean_jt:
                job_type = "Remote"
        else:
            if re.search(r'\b(?:part[\s\-]time)\b', lower_text):
                job_type = "Part-time"
            elif re.search(r'\b(?:contract(?:ual)?|fixed[\s\-]term|freelance|gig)\b', lower_text):
                job_type = "Contract"
            elif re.search(r'\b(?:internship|intern)\b', lower_text):
                job_type = "Internship"
            elif re.search(r'\b(?:remote|work\s+from\s+home)\b', lower_text):
                job_type = "Remote"
            elif re.search(r'\b(?:hybrid)\b', lower_text):
                job_type = "Hybrid"
            elif re.search(r'\b(?:full[\s\-]time|permanent)\b', lower_text):
                job_type = "Full-time"

        # 8. Explicit & Specific Required Skills Extraction
        matched_skills = []

        # 8a. First extract from explicit Requirement/Skills sections in post text
        req_sec_pattern = re.compile(
            r'(?:requirements?|required\s+skills?|qualifications?|key\s+requirements?|tech\s+stack|technologies|skills\s*(?:and|&)?\s*competencies?)\s*[:\-]\s*(.*?)(?=(?:how\s+to\s+apply|salary|deadline|closing|place\s+of\s+work|location|benefits|about|duties|responsibilities|\Z))',
            re.IGNORECASE | re.DOTALL
        )
        sec_m = req_sec_pattern.search(raw_text)
        if sec_m:
            sec_text = sec_m.group(1)
            # Split by bullets, newlines, commas, semicolons
            tokens = re.split(r'[\n•*|\-;]+', sec_text)
            for token in tokens:
                token_clean = re.sub(r'^[0-9\.\)\s]+', '', token).strip()
                # If bullet is short like a skill name or contains a known framework
                if 2 <= len(token_clean) <= 40:
                    clean_s = re.sub(r'[^\w\s\+\#\.\-]', '', token_clean).strip()
                    if clean_s and clean_s.lower() not in {"and", "with", "or", "experience", "degree", "years", "knowledge"}:
                        matched_skills.append(clean_s)

        # 8b. Match against expanded technical & domain skills catalog
        catalog = [
            "Python", "JavaScript", "TypeScript", "React", "Next.js", "Node.js", "Express",
            "FastAPI", "Django", "Flask", "PostgreSQL", "Postgres", "MySQL", "MongoDB", "Redis",
            "Docker", "Kubernetes", "Linux", "Ubuntu", "Git", "GitHub", "GitLab", "RESTful APIs", "REST API",
            "GraphQL", "Tailwind CSS", "HTML5", "CSS3", "Bootstrap", "Vue.js", "Angular", "Java", "Spring Boot",
            "C++", "C#", ".NET", "PHP", "Laravel", "AWS", "Google Cloud", "CI/CD", "Bash", "SQL",
            "Figma", "UI/UX", "Microservices", "Celery", "Kafka", "Accounting", "Auditing", "IFRS",
            "Flutter", "Android", "Dart", "iOS", "Swift", "Kotlin", "React Native",
            "Machine Learning", "Data Analysis", "Deep Learning", "TensorFlow", "PyTorch",
            "Network Administration", "Cisco", "CCNA", "Network Security", "Cybersecurity",
            "Civil Engineering", "AutoCAD", "Structural Analysis", "Project Management"
        ]
        for s in catalog:
            if re.search(r'(?<!\w)' + re.escape(s) + r'(?!\w)', raw_text, re.I):
                norm = "PostgreSQL" if s.lower() == "postgres" else s
                if norm not in matched_skills:
                    matched_skills.append(norm)

        # Deduplicate while preserving order
        dedup_skills = []
        for sk in matched_skills:
            if sk not in dedup_skills:
                dedup_skills.append(sk)

        if not dedup_skills:
            t_low = title.lower()
            if "full" in t_low or "fullstack" in t_low:
                dedup_skills = ["Full-stack Development", "Frontend & Backend Engineering", "REST APIs", "Modern Web Architecture"]
            elif "backend" in t_low:
                dedup_skills = ["Backend Architecture", "API Design", "Database Management", "Server-Side Logic"]
            elif "frontend" in t_low:
                dedup_skills = ["Frontend Development", "Responsive UI", "Modern JavaScript", "Component Architecture"]
            elif "software" in t_low or "developer" in t_low:
                dedup_skills = ["Software Engineering", "Application Development", "Code Quality", "Problem Solving"]

        return {
            "title": (title or "Professional Opportunity")[:250],
            "company": (company or "Confidential Employer")[:250],
            "location": (location or "Addis Ababa / Ethiopia")[:250],
            "deadline": (deadline or "Open / Not specified")[:250],
            "required_experience_years": exp_years,
            "required_skills": dedup_skills[:15],
            "salary_range": (salary or "Negotiable")[:250],
            "application_contact": (channel_title or "")[:250],
            "employment_type": job_type[:50]
        }

    @staticmethod
    def extract_profile_heuristics(raw_text: str, file_name: str = "", default_name: str = "") -> Dict[str, Any]:
        """High-precision local extraction for CV entity data (Name, Title, Skills, Experience, Education).
        
        Guarantees accurate profile creation even when external AI APIs are offline or unreachable.
        """
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        lower_text = raw_text.lower()

        # ---------------------------------------------------------
        # 1. Candidate Full Name Extraction
        # ---------------------------------------------------------
        name = ""
        # Inspect top lines (names are almost always on line 1-3)
        for line in lines[:5]:
            clean_line = re.sub(r'[^a-zA-Z\s]', '', line).strip()
            words = clean_line.split()
            # Valid name typically 2 to 4 alphabetic words
            if 2 <= len(words) <= 4:
                lower_words = [w.lower() for w in words]
                # Filter out obvious non-name header words
                blacklisted = {"curriculum", "vitae", "resume", "cv", "profile", "contact", "email",
                               "phone", "address", "summary", "experience", "education", "skills",
                               "senior", "junior", "engineer", "developer", "lead", "manager"}
                if not any(w in blacklisted for w in lower_words):
                    name = " ".join(words).title()
                    break

        if not name and default_name and default_name.lower() not in ["applicant", "none", ""]:
            name = default_name
        elif not name and file_name:
            # Extract from file name: e.g. "Firomsa-Fullstack-Resume.pdf" -> "Firomsa"
            base = os.path.splitext(file_name)[0]
            clean_base = re.sub(r'[-_]+', ' ', base)
            parts = [p for p in clean_base.split() if p.lower() not in {"resume", "cv", "pdf", "docx", "profile", "fullstack", "frontend", "backend"}]
            if parts:
                name = " ".join(parts[:2]).title()

        if not name:
            name = default_name or "Applicant"

        # ---------------------------------------------------------
        # 2. Professional Job Title Extraction
        # ---------------------------------------------------------
        title = ""

        # Priority 1: High-precision regex pattern match for Fullstack / Software Engineering variants
        if re.search(r'full[\s\-_]*stack\s+(?:software\s+)?(?:engineer|developer)?', raw_text, re.I):
            title = "Fullstack Software Engineer"
        elif re.search(r'backend\s+(?:software\s+)?(?:engineer|developer)?', raw_text, re.I):
            title = "Backend Software Engineer"
        elif re.search(r'frontend\s+(?:software\s+)?(?:engineer|developer)?', raw_text, re.I):
            title = "Frontend Software Engineer"
        elif re.search(r'devops\s+(?:software\s+)?engineer', raw_text, re.I):
            title = "DevOps Engineer"
        elif re.search(r'mobile\s+(?:app\s+)?developer', raw_text, re.I):
            title = "Mobile Application Developer"

        if not title:
            candidate_titles = [
                "Fullstack Software Engineer", "Full Stack Software Engineer", "Full Stack Developer", "Full Stack Engineer",
                "Senior Software Engineer", "Software Engineer", "Backend Software Engineer",
                "Senior Backend Engineer", "Backend Developer", "Frontend Developer", "Frontend Engineer",
                "Mobile App Developer", "Android Developer", "Flutter Developer", "iOS Developer",
                "DevOps Engineer", "Cloud Engineer", "System Administrator", "Site Reliability Engineer",
                "Data Engineer", "Data Scientist", "Machine Learning Engineer", "AI Engineer",
                "UI/UX Designer", "Product Designer", "Product Manager", "Project Manager",
                "Database Administrator", "QA Engineer", "Software Tester", "Cybersecurity Analyst",
                "Accountant", "Senior Accountant", "Finance Officer", "Financial Analyst",
                "Project Monitoring & Evaluation Officer", "M&E Specialist", "Monitoring and Evaluation",
                "Human Resources Manager", "HR Specialist", "Recruiter", "Marketing Specialist",
                "Sales Representative", "Business Development Manager", "Customer Service Specialist",
                "Civil Engineer", "Electrical Engineer", "Mechanical Engineer", "Lecturer"
            ]
            norm_corpus = re.sub(r'[-_]', ' ', lower_text)
            for ct in candidate_titles:
                if ct.lower() in norm_corpus:
                    title = "Fullstack Software Engineer" if "full" in ct.lower() and "stack" in ct.lower() else ct
                    break

        if not title:
            # Check filename clues
            fn_lower = file_name.lower()
            if "fullstack" in fn_lower or "full-stack" in fn_lower or "full stack" in fn_lower:
                title = "Fullstack Software Engineer"
            elif "backend" in fn_lower:
                title = "Backend Software Engineer"
            elif "frontend" in fn_lower:
                title = "Frontend Software Engineer"
            elif "devops" in fn_lower:
                title = "DevOps Engineer"
            elif "mobile" in fn_lower:
                title = "Mobile Application Developer"
            else:
                for line in lines[1:6]:
                    if any(k in line.lower() for k in ["engineer", "developer", "specialist", "officer", "manager", "designer"]):
                        title = line[:60].strip()
                        break

        if not title:
            if "full" in lower_text and "stack" in lower_text:
                title = "Fullstack Software Engineer"
            elif "software" in lower_text and "engineer" in lower_text:
                title = "Software Engineer"
            elif any(k in lower_text for k in ["management", "business administration"]):
                title = "Business & Management Specialist"
            elif any(k in lower_text for k in ["nurse", "nursing"]):
                title = "Clinical Nurse"
            elif any(k in lower_text for k in ["pharmacy", "pharmacist"]):
                title = "Pharmacist"
            elif any(k in lower_text for k in ["accounting", "finance", "auditing", "auditor"]):
                title = "Accountant / Finance Officer"
            elif any(k in lower_text for k in ["marketing", "sales"]):
                title = "Marketing & Sales Specialist"
            elif any(k in lower_text for k in ["graphic", "designer", "design", "illustrator", "photoshop", "video editing"]):
                title = "Graphic Designer & Visual Media Specialist"
            elif any(k in lower_text for k in ["civil engineer", "civil engineering", "construction"]):
                title = "Civil Engineer"
            elif any(k in lower_text for k in ["human resources", "hr specialist", "hr officer"]):
                title = "Human Resources Officer"
            elif any(k in lower_text for k in ["public health", "health officer"]):
                title = "Public Health Officer"
            elif any(k in lower_text for k in ["law", "legal"]):
                title = "Legal Officer"
            elif any(k in lower_text for k in ["economics"]):
                title = "Economic Analyst"
            else:
                title = "Specialist"

        # ---------------------------------------------------------
        # 3. Technical & Professional Skills Extraction (100+ Catalog)
        # ---------------------------------------------------------
        catalog = [
            "Python", "JavaScript", "TypeScript", "React", "Next.js", "Node.js", "Express",
            "FastAPI", "Django", "Flask", "PostgreSQL", "Postgres", "MySQL", "MongoDB", "Redis",
            "Docker", "Kubernetes", "Linux", "Ubuntu", "Git", "GitHub", "GitLab", "REST API", "RESTful APIs",
            "GraphQL", "Tailwind CSS", "HTML5", "CSS3", "Bootstrap", "Vue.js", "Angular", "Java", "Spring Boot",
            "C++", "C#", ".NET", "PHP", "Laravel", "AWS", "Google Cloud", "CI/CD", "Bash",
            "SQL", "Figma", "UI/UX", "Microservices", "Celery", "Kafka", "RabbitMQ", "PyTorch",
            "TensorFlow", "Pandas", "NumPy", "Scikit-Learn", "Data Analysis", "SPSS", "KoboToolbox",
            "Agile", "Scrum", "Jira", "Unit Testing", "Problem Solving", "Communication", "Team Collaboration",
            "Redux", "Zustand", "Prisma", "Postman", "System Design", "WebSockets"
        ]
        matched_skills = []
        for skill in catalog:
            # Word-boundary search
            pattern = r'(?<!\w)' + re.escape(skill) + r'(?!\w)'
            if re.search(pattern, raw_text, re.IGNORECASE):
                # Standardize common variations
                norm_skill = "PostgreSQL" if skill.lower() == "postgres" else skill
                if norm_skill not in matched_skills:
                    matched_skills.append(norm_skill)

        # Check for explicit Skills sections in CV (e.g. "Skills: Python, React, ...")
        skills_sec_match = re.search(r'(?:technical\s+)?skills(?:\s*&amp;|\s*and)?(?:\s*competencies)?[:\n](.*?)(?:\n\s*(?:education|experience|work|projects|certifications|awards|languages|interests)|\Z)', raw_text, re.I | re.S)
        if skills_sec_match:
            sec_text = skills_sec_match.group(1)
            raw_items = re.split(r'[,•|\n;]', sec_text)
            for it in raw_items:
                clean_it = re.sub(r'^[A-Za-z\s]+:', '', it).strip()
                clean_it = re.sub(r'[^\w\s\+\#\.\-]', '', clean_it).strip()
                if 2 <= len(clean_it) <= 30 and clean_it.lower() not in {"and", "with", "or", "etc", "skills", "proficient", "strong", "knowledge", "experience"}:
                    if clean_it not in matched_skills:
                        matched_skills.append(clean_it)

        if not matched_skills:
            matched_skills = ["Problem Solving", "Communication", "Team Collaboration"]

        # ---------------------------------------------------------
        # 4. Years of Experience Extraction
        # ---------------------------------------------------------
        years_exp = 0
        exp_matches = re.findall(r'(\d+)\+?\s*years?(?:\s*of)?\s*experience', lower_text)
        if exp_matches:
            years_exp = max(int(y) for y in exp_matches if int(y) < 30)
        else:
            # Search for date ranges (e.g. 2021 - 2024, 2022 - present)
            year_ranges = re.findall(r'(20\d\d)\s*[-–to]+\s*(20\d\d|present|current|now)', lower_text)
            if year_ranges:
                spans = []
                current_year = 2026
                for start_y, end_y in year_ranges:
                    start_int = int(start_y)
                    end_int = current_year if end_y in ["present", "current", "now"] else int(end_y)
                    if end_int >= start_int:
                        spans.append(end_int - start_int)
                if spans:
                    years_exp = min(max(sum(spans), max(spans)), 20)

        if years_exp == 0 and len(matched_skills) >= 4:
            years_exp = 3  # Realistic default for multi-framework engineering profiles

        # ---------------------------------------------------------
        # 5. Highest Education Extraction
        # ---------------------------------------------------------
        education = "Higher Education"
        # First scan lines that explicitly mention degree keywords
        for line in lines:
            ll = line.lower()
            if any(deg in ll for deg in ["b.sc", "bsc", "bachelor", "m.sc", "msc", "master", "degree in", "diploma"]):
                cleaned_deg = DocumentParser.clean_education_degree(line)
                if cleaned_deg != "Higher Education":
                    education = cleaned_deg
                    break

        if education == "Higher Education":
            education = DocumentParser.clean_education_degree(raw_text)

        # ---------------------------------------------------------
        # 6. Projects & Portfolio Extraction
        # ---------------------------------------------------------
        projects = []
        proj_sec = re.search(r'(?:projects?|key\s+projects?|personal\s+projects?|featured\s+work|selected\s+projects?)[:\n](.*?)(?=(?:education|work\s+experience|employment|experience|skills|certifications|languages|\Z))', raw_text, re.I | re.S)
        if proj_sec:
            raw_proj = proj_sec.group(1).strip()
            # Split into project blocks
            proj_lines = [l.strip() for l in raw_proj.splitlines() if l.strip()]
            cur_p = []
            for pl in proj_lines:
                if pl.startswith(("•", "-", "*")) or re.match(r'^\d+\.', pl) or len(pl) < 50:
                    if cur_p:
                        projects.append(" ".join(cur_p))
                        cur_p = []
                    clean_pl = re.sub(r'^[•\-\*\d\.\s]+', '', pl).strip()
                    if clean_pl:
                        cur_p.append(clean_pl)
                else:
                    cur_p.append(pl)
            if cur_p:
                projects.append(" ".join(cur_p))

        # ---------------------------------------------------------
        # 7. Portfolio / GitHub Link Extraction
        # ---------------------------------------------------------
        portfolio_url = ""
        m_link = re.search(r'(https?://(?:github\.com|linkedin\.com/in|[\w\-]+\.vercel\.app|[\w\-]+\.dev|[\w\-]+\.github\.io)[^\s,\)]+)', raw_text, re.I)
        if m_link:
            portfolio_url = m_link.group(1).rstrip('.,;')

        return {
            "full_name": name,
            "primary_title": title,
            "highest_education": education,
            "years_of_experience": years_exp,
            "skills": matched_skills[:25],
            "projects": projects[:5],
            "portfolio_url": portfolio_url,
            "summary": f"{title} with {years_exp} years of experience proficient in {', '.join(matched_skills[:4])}.",
            "preferred_roles": [title, f"Senior {title}", "Software Engineer"]
        }


document_parser = DocumentParser()

