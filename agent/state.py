"""
agent/state.py — AgentState TypedDict

Single source of truth shared across every LangGraph node.
All nodes read from and write to this TypedDict.
Never pass data between nodes any other way.
"""

from typing import TypedDict, List, Optional, Literal, Annotated
from datetime import datetime
import operator


# ── Sub-types ──────────────────────────────────────────────


class UserProfile(TypedDict):
    name: str
    email: str
    phone: str
    location: str
    skills: List[str]
    experiences: List[dict]       # [{title, company, dates, bullets}]
    education: List[dict]
    links: dict                   # {linkedin, github, portfolio}
    raw_text: str                 # full resume text for LLM context


class JobPreferences(TypedDict):
    target_titles: List[str]      # e.g. ["ML Engineer", "AI Engineer"]
    locations: List[str]          # e.g. ["Remote", "Bangalore"]
    remote_preference: Literal["remote_only", "hybrid_ok", "onsite_ok"]
    salary_floor_usd: Optional[int]
    blocked_companies: List[str]
    min_fit_score: int            # from .env, default 80


class JobListing(TypedDict):
    id: str                       # sha256 hash of url for dedup
    title: str
    company: str
    url: str
    description: str
    source: str                   # "remotive", "linkedin", "indeed", etc.
    posted_at: Optional[datetime]
    discovered_at: datetime


class FitScore(TypedDict):
    score: int                    # 0–100
    skill_match: List[str]
    skill_gaps: List[str]
    seniority_match: bool
    location_match: bool
    reasoning: str
    recommendation: Literal["APPLY", "REVIEW", "SKIP"]


class TailoredApp(TypedDict):
    job: JobListing
    score: FitScore
    tailored_bullets: List[str]
    changes_summary: str
    cover_letter: str
    resume_pdf_path: str          # absolute path to generated PDF


class HumanDecision(TypedDict):
    job_id: str
    action: Literal["approve", "edit_approve", "skip", "block"]
    edited_bullets: Optional[List[str]]   # set if action == "edit_approve"
    edited_cover_letter: Optional[str]


class SubmissionResult(TypedDict):
    job_id: str
    success: bool
    method: str                   # "easy_apply", "greenhouse", "workday", "generic"
    error: Optional[str]
    submitted_at: datetime


# ── Main AgentState ────────────────────────────────────────


class AgentState(TypedDict):
    # Config (loaded once, never mutated)
    user_profile: UserProfile
    preferences: JobPreferences

    # Current cycle data
    raw_listings: Annotated[List[JobListing], operator.add]      # accumulate across nodes
    scored_listings: Annotated[List[tuple], operator.add]         # (JobListing, FitScore)
    tailored_apps: Annotated[List[TailoredApp], operator.add]
    submitted: Annotated[List[SubmissionResult], operator.add]

    # Control flow
    pending_human_review: List[TailoredApp]   # jobs waiting at HITL gate
    human_decisions: List[HumanDecision]       # decisions made at HITL gate
    current_node: str
    cycle_id: str                              # UUID per daily run
    errors: Annotated[List[str], operator.add]

    # Flags
    requires_human_input: bool    # True = agent has paused at HITL gate
    discovery_complete: bool
    scoring_complete: bool
