"""Registry of Curated Ethiopian Job Channels for Real-time Monitoring."""

import os
from typing import List, Dict

# Top Ethiopian Job Channels on Telegram (Public Handles)
ETHIOPIAN_JOB_CHANNELS: List[Dict[str, str]] = [
    # --- Newly Requested Channels ---
    {"handle": "awrajobs", "name": "Awra Jobs", "category": "General & Career"},
    {"handle": "josad_software", "name": "Josad Job (Tech)", "category": "Tech & Software"},
    {"handle": "josaddigital", "name": "Josad Digital Jobs", "category": "Tech & Digital"},
    {"handle": "BeleqetJobs_works", "name": "Beleqet Jobs", "category": "General & Corporate"},
    {"handle": "embassy_ngo_jobs", "name": "Embassy & NGO Jobs", "category": "Embassy & NGO"},
    {"handle": "lucyjobs", "name": "Lucy Jobs", "category": "General Vacancies"},
    {"handle": "ennlitejobs", "name": "Ennlite Jobs", "category": "Professional"},
    {"handle": "segnigudeta", "name": "Sanyii Guddataa", "category": "Regional & Career"},
    {"handle": "bikattech", "name": "Bikat Tech", "category": "Tech & Engineering"},
    {"handle": "gadaanetwork", "name": "Gadaa Network", "category": "General & Banking"},
    {"handle": "ethiojobshub", "name": "Ethio Jobs Hub", "category": "Aggregator"},

    # --- Core Curated Ethiopian Job Ecosystem ---
    {"handle": "hahujobs", "name": "HaHuJobs", "category": "General & Tech"},
    {"handle": "ethiojobs_et", "name": "EthioJobs", "category": "Professional & Corporate"},
    {"handle": "freelance_ethiopia", "name": "Freelance Ethiopia", "category": "Tech & Freelance"},
    {"handle": "shegerjobs", "name": "Sheger Jobs", "category": "General"},
    {"handle": "ngojobs_ethiopia", "name": "NGO Jobs Ethiopia", "category": "NGO & Development"},
    {"handle": "ethiopian_jobs_network", "name": "Ethiopian Jobs Network", "category": "General"},
    {"handle": "addiswork", "name": "Addis Work", "category": "Corporate & Banking"},
    {"handle": "qetero_jobs", "name": "Qetero Jobs", "category": "General"},
    {"handle": "techjobs_ethiopia", "name": "Tech Jobs Ethiopia", "category": "Tech & Engineering"},
    {"handle": "dereja_official", "name": "Dereja Fresh Graduates", "category": "Entry-Level"},
    {"handle": "ethiopian_banking_jobs", "name": "Ethiopian Banking Careers", "category": "Banking & Finance"},
    {"handle": "un_jobs_ethiopia", "name": "UN & International Vacancies ET", "category": "International NGO"},
    {"handle": "geez_jobs", "name": "Geez Jobs", "category": "General"},
    {"handle": "habesha_jobs", "name": "Habesha Jobs", "category": "General"},
    {"handle": "ethio_tender_jobs", "name": "Ethio Tender & Vacancy", "category": "Tenders & Public"},
    {"handle": "all_ethiopian_jobs", "name": "All Ethiopian Jobs", "category": "General"},
    {"handle": "addis_recruitment", "name": "Addis Recruitment PLC", "category": "Agency"},
    {"handle": "ethio_career", "name": "Ethio Career Hub", "category": "Corporate"},
    {"handle": "remote_jobs_africa", "name": "Remote Jobs Africa / ET", "category": "Remote"},
    {"handle": "tikvah_jobs", "name": "Tikvah Jobs Ethiopia", "category": "News & Vacancies"},
]


def get_monitored_channel_handles() -> List[str]:
    """Returns list of clean Telegram channel usernames including any custom env handles."""
    handles = [ch["handle"].lstrip("@").strip() for ch in ETHIOPIAN_JOB_CHANNELS]

    # Optional: support custom handles via CUSTOM_JOB_CHANNELS in .env (comma-separated)
    custom_env = os.getenv("CUSTOM_JOB_CHANNELS", "")
    if custom_env:
        extra = [h.lstrip("@").strip() for h in custom_env.split(",") if h.strip()]
        handles.extend(extra)

    # Return unique handles preserving order
    return list(dict.fromkeys(handles))
