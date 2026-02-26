import sys
import logging
import json
from datetime import datetime

from db.database import init_db, get_user_profile, get_preferences
from agent.state import AgentState
from agent.nodes.discovery import run as run_discovery
from agent.nodes.scoring import run as run_scoring

logging.basicConfig(level=logging.WARNING)

print("=== 1 & 2: LOADING FROM DB ===")
init_db()
profile = get_user_profile()
prefs = get_preferences()

if not profile:
    print("Cannot run pipeline: No user profile found in DB.")
    sys.exit(1)
if not prefs:
    print("Cannot run pipeline: No preferences found in DB.")
    sys.exit(1)

print("\n=== 3: PRINTING LOADED CONFIG ===")
print("USER NAME:", profile.get("name"))
print("TARGET TITLES:", prefs.get("target_titles"))
print("LOCATIONS:", prefs.get("locations"))
print("REMOTE PREF:", prefs.get("remote_preference"))
print("BLOCKED:", prefs.get("blocked_companies"))
print("MIN SCORE:", prefs.get("min_fit_score"))

print("\n=== 4: RUNNING DISCOVERY NODE ===")
# Build initial empty state
state: AgentState = {
    "user_profile": profile,
    "preferences": prefs,
    "raw_listings": [],
    "scored_listings": [],
    "tailored_apps": [],
    "submitted": [],
    "pending_human_review": [],
    "human_decisions": [],
    "current_node": "discovery",
    "cycle_id": "test_script_run",
    "errors": [],
    "requires_human_input": False,
    "discovery_complete": False,
    "scoring_complete": False
}

discovery_result = run_discovery(state)

discovered_jobs = discovery_result.get("raw_listings", [])
print("\n=== 5: DISCOVERY RESULTS ===")
print(f"Total jobs freshly discovered globally: {len(discovered_jobs)}")

if discovery_result.get("errors"):
    print("Discovery Errors:")
    for e in discovery_result["errors"]:
        print(f" - {e}")

if not discovered_jobs:
    print("\nNo new jobs discovered. Either the APIs are empty or everything is already in your DB!")
    sys.exit(0)

print("\n=== 6: RUNNING SCORING NODE (FIRST 3 JOBS) ===")
# Only score the first 3
state["raw_listings"] = discovered_jobs[:3]

scoring_result = run_scoring(state)
scored_listings = scoring_result.get("scored_listings", [])

print("\n=== 7: SCORING RESULTS ===")
print(f"Out of 3 tested, {len(scored_listings)} passed the threshold of {prefs.get('min_fit_score')}")

# scoring_result["scored_listings"] contains tuples: (JobListing, FitScore)
for job, score in scored_listings:
    print("-" * 50)
    print(f"Title: {job['title']}")
    print(f"Company: {job['company']}")
    print(f"Score: {score['score']}")
    print(f"Recommendation: {score['recommendation']}")
    print(f"Reasoning: {score['reasoning']}")

if scoring_result.get("errors"):
    print("\nScoring Errors:")
    for e in scoring_result["errors"]:
        print(f" - {e}")
