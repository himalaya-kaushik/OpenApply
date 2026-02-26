import sys
import json
import logging
from datetime import datetime

from agent.state import AgentState
from agent.nodes.scoring import run
from db.database import init_db, save_job
from db.models import Score, Application, Job

logging.basicConfig(level=logging.INFO)

# Init DB manually
init_db()

mock_state = {
    "preferences": {
        "min_fit_score": 80
    },
    "user_profile": {
        "skills": ["Python", "SQLAlchemy", "FastAPI"],
        "experiences": [
            {"title": "Backend Dev", "bullets": ["Built APIs with Python", "Saved 100 hours of latency"]}
        ],
        "education": []
    },
    "raw_listings": [
        {
            "id": "test_job_1",
            "title": "Backend Python Engineer",
            "company": "Tech Corp",
            "url": "https://example.com/job1",
            "source": "test",
            "description": "We need a strong Backend Python Engineer who knows SQLAlchemy and FastAPI inside out. 3+ years experience required. On-site in NYC.",
            "posted_at": datetime.utcnow(),
            "discovered_at": datetime.utcnow()
        },
        {
            "id": "test_job_2",
            "title": "Frontend React Dev",
            "company": "Another Corp",
            "url": "https://example.com/job2",
            "source": "test",
            "description": "Looking for a React developer with deep CSS knowledge. Must know Next.js and Tailwind.",
            "posted_at": datetime.utcnow(),
            "discovered_at": datetime.utcnow()
        }
    ]
}

print("Adding test jobs to DB...")
from db.database import SessionLocal
db = SessionLocal()
for job in mock_state["raw_listings"]:
    # Check if exists
    if not db.query(Job).filter(Job.id == job["id"]).first():
        save_job(job)
db.close()

print("Running scoring node...")
result = run(mock_state)

scored = result.get("scored_listings", [])
errors = result.get("errors", [])

print(f"\nScoring complete. Passed threshold: {len(scored)}")
for job_dict, fit_score in scored:
    print(f"- {job_dict['title']} at {job_dict['company']}: Score {fit_score['score']} ({fit_score['recommendation']})")
    
if errors:
    print(f"\nErrors encountered: {len(errors)}")
    for e in errors:
        print(f"- {e}")
        
# Verify DB state
print("\n--- DB Verification ---")
db = SessionLocal()
for job in mock_state["raw_listings"]:
    s = db.query(Score).filter(Score.job_id == job["id"]).first()
    app = db.query(Application).filter(Application.job_id == job["id"]).first()
    
    if s and app:
        print(f"[{job['id']}] DB Score: {s.score}, Recommendation: {s.recommendation}, App Status: {app.status}")
    else:
        print(f"[{job['id']}] Not found in DB or missing relationships.")
db.close()
