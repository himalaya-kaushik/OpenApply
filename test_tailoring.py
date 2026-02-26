"""
test_tailoring.py — Integration test for the tailoring node.

Runs against real data from the DB:
1. Loads user profile + preferences
2. Takes the first APPLY/REVIEW scored job from the DB
3. Runs the tailoring node
4. Prints tailored bullets, cover letter preview, and PDF path
5. Verifies app status in DB = pending_approval
"""

import sys
import json
import logging
from datetime import datetime

from db.database import init_db, SessionLocal, get_user_profile, get_preferences
from db.models import Score, Job, Application
from agent.state import AgentState
from agent.nodes.tailoring import run as run_tailoring

logging.basicConfig(level=logging.WARNING)

init_db()

print("=== 1: LOADING PROFILE & PREFERENCES ===")
profile = get_user_profile()
prefs = get_preferences() or {}
if not profile:
    print("No profile found — run setup first.")
    sys.exit(1)

print(f"Profile: {profile.get('name')} | {profile.get('email')}")
print(f"Min Score: {prefs.get('min_fit_score', 80)}")

print("\n=== 2: FINDING SCORED JOBS (APPLY or REVIEW) ===")
db = SessionLocal()
# Get up to 2 APPLY/REVIEW jobs
scores = (
    db.query(Score)
    .filter(Score.recommendation.in_(["APPLY", "REVIEW"]))
    .limit(2)
    .all()
)
if not scores:
    print("No APPLY/REVIEW scored jobs found in DB. Run test_pipeline.py first.")
    db.close()
    sys.exit(0)

# Build minimal state with scored_listings
scored_listings = []
for s in scores:
    job_row = db.query(Job).filter(Job.id == s.job_id).first()
    if not job_row:
        continue
    job = {
        "id": job_row.id,
        "title": job_row.title,
        "company": job_row.company,
        "url": job_row.url,
        "source": job_row.source,
        "description": job_row.description or "",
        "posted_at": job_row.posted_at,
        "discovered_at": job_row.discovered_at,
    }
    score_dict = {
        "score": s.score,
        "skill_match": json.loads(s.skill_match) if s.skill_match else [],
        "skill_gaps": json.loads(s.skill_gaps) if s.skill_gaps else [],
        "seniority_match": bool(s.seniority_match),
        "location_match": bool(s.location_match),
        "reasoning": s.reasoning or "",
        "recommendation": s.recommendation,
    }
    scored_listings.append((job, score_dict))
    print(f"  → {job['title']} @ {job['company']} (Score: {s.score}, Rec: {s.recommendation})")
db.close()

print(f"\n=== 3: RUNNING TAILORING NODE ON {len(scored_listings)} JOB(S) ===")
state: AgentState = {
    "user_profile": profile,
    "preferences": prefs,
    "raw_listings": [],
    "scored_listings": scored_listings,
    "tailored_apps": [],
    "submitted": [],
    "pending_human_review": [],
    "human_decisions": [],
    "current_node": "tailoring",
    "cycle_id": "test_tailoring_run",
    "errors": [],
    "requires_human_input": False,
    "discovery_complete": True,
    "scoring_complete": True,
}

result = run_tailoring(state)

print("\n=== 4: RESULTS ===")
for app in result.get("tailored_apps", []):
    job = app["job"]
    print(f"\n{'='*50}")
    print(f"Job:     {job['title']} @ {job['company']}")
    print(f"PDF:     {app['resume_pdf_path']}")
    print(f"Summary: {app['changes_summary']}")
    print(f"\nTailored Bullets ({len(app['tailored_bullets'])}):")
    for b in app["tailored_bullets"]:
        print(f"  • {b}")
    print(f"\nCover Letter Preview (first 300 chars):")
    print(f"  {app['cover_letter'][:300]}...")

if result.get("errors"):
    print(f"\nErrors encountered ({len(result['errors'])}):")
    for e in result["errors"]:
        print(f"  ✗ {e}")

print("\n=== 5: DB VERIFICATION ===")
db = SessionLocal()
for app in result.get("tailored_apps", []):
    job_id = app["job"]["id"]
    row = db.query(Application).filter(Application.job_id == job_id).first()
    if row:
        print(f"[{job_id[:12]}] Status: {row.status} | PDF: {row.resume_pdf_path}")
    else:
        print(f"[{job_id[:12]}] Application row NOT FOUND.")
db.close()

print("\nDone.")
