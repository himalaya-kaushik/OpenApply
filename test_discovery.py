import sys
import os

# Create mock state
from agent.state import AgentState
from agent.nodes.discovery import run
from db.database import init_db, get_db
from db.models import Job

# Init DB manually just to be sure
init_db()

mock_state = {
    "preferences": {
        "target_titles": ["Engineer", "Developer"],
        "max_age_days": 14,
        "blocked_companies": ["Canonical"]
    }
}

print("Running discovery node...")
result = run(mock_state)

jobs = result["raw_listings"]
print(f"Discovered {len(jobs)} jobs matching criteria.")

if len(jobs) > 0:
    print(f"First job: {jobs[0]['title']} at {jobs[0]['company']}")
    
db = next(get_db())
db_count = db.query(Job).count()
print(f"Jobs in SQLite DB: {db_count}")
