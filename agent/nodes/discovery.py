import hashlib
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any

from agent.state import AgentState, JobListing
from db.database import is_job_discovered, init_db, save_job, get_preferences

# The 3 free public APIs that don't require auth keys
FREE_APIS = {
    "remotive": "https://remotive.com/api/remote-jobs",
    "remoteok": "https://remoteok.com/api",
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
}

def make_job_id(url: str) -> str:
    """Create a deterministic ID based on the URL"""
    return hashlib.sha256(url.encode()).hexdigest()[:16]

def parse_remotive(data: dict) -> List[JobListing]:
    """Parse Remotive API response"""
    listings = []
    jobs = data.get("jobs", [])
    for job in jobs:
        url = job.get("url", "")
        if not url:
            continue
        
        try:
            posted_at = datetime.strptime(job.get("publication_date", ""), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            posted_at = datetime.utcnow()
            
        listings.append({
            "id": make_job_id(url),
            "title": job.get("title", ""),
            "company": job.get("company_name", ""),
            "url": url,
            "source": "remotive",
            "description": job.get("description", ""),
            "posted_at": posted_at,
            "discovered_at": datetime.utcnow()
        })
    return listings

def parse_remoteok(data: List[dict]) -> List[JobListing]:
    """Parse RemoteOK API response"""
    listings = []
    # RemoteOK returns a list where the first item is a "legal" notice, the rest are jobs
    for job in data:
        if "legal" in job:
            continue
            
        url = job.get("url", "")
        if not url:
            continue
            
        try:
            posted_at = datetime.fromtimestamp(int(job.get("date", datetime.utcnow().timestamp())))
        except (ValueError, TypeError):
            posted_at = datetime.utcnow()
            
        listings.append({
            "id": make_job_id(url),
            "title": job.get("position", ""),
            "company": job.get("company", ""),
            "url": url,
            "source": "remoteok",
            "description": job.get("description", ""),
            "posted_at": posted_at,
            "discovered_at": datetime.utcnow()
        })
    return listings

def parse_arbeitnow(data: dict) -> List[JobListing]:
    """Parse Arbeitnow API response"""
    listings = []
    jobs = data.get("data", [])
    for job in jobs:
        url = job.get("url", "")
        if not url:
            continue
            
        try:
            # Arbeitnow returns unix timestamp
            posted_at = datetime.fromtimestamp(job.get("created_at", datetime.utcnow().timestamp()))
        except (ValueError, TypeError):
            posted_at = datetime.utcnow()
            
        listings.append({
            "id": make_job_id(url),
            "title": job.get("title", ""),
            "company": job.get("company_name", ""),
            "url": url,
            "source": "arbeitnow",
            "description": job.get("description", ""),
            "posted_at": posted_at,
            "discovered_at": datetime.utcnow()
        })
    return listings

def fetch_board(client: httpx.Client, source: str, url: str) -> List[JobListing]:
    """Fetch and parse a single job board"""
    try:
        # RemoteOK requires a custom user-agent often, or it 403s
        headers = {"User-Agent": "OpenApplyAgent/1.0"}
        resp = client.get(url, headers=headers, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        
        if source == "remotive":
            return parse_remotive(data)
        elif source == "remoteok":
            return parse_remoteok(data)
        elif source == "arbeitnow":
            return parse_arbeitnow(data)
            
    except Exception as e:
        print(f"Error fetching from {source}: {e}")
        return []
    return []

def run(state: AgentState) -> dict:
    """
    Discovery Node implementation:
    1. Fetch from 3 free APIs
    2. Deduplicate
    3. Filter by Preferences (target_titles, blocked_companies)
    4. Filter by Age
    5. Save to DB
    """
    # Ensure DB is initialized
    init_db()
    # Use actual DB preferences
    prefs = get_preferences() or {}
    
    target_titles = [t.lower() for t in prefs.get("target_titles", [])]
    blocked_companies = [b.lower() for b in prefs.get("blocked_companies", [])]
    max_age_days = int(prefs.get("max_age_days", 14)) # Use default 14 if not present
    cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
    
    all_raw_listings: List[JobListing] = []
    errors = []
    
    # Step 1: Fetch
    with httpx.Client(follow_redirects=True) as client:
        for source, url in FREE_APIS.items():
            listings = fetch_board(client, source, url)
            all_raw_listings.extend(listings)
            
    # Step 2-4: Filter & Deduplicate
    seen_ids = set()
    fresh_listings = []
    
    for job in all_raw_listings:
        # Skip if already processed in this run
        if job["id"] in seen_ids:
            continue
            
        # Skip age
        if getattr(job, "posted_at", datetime.utcnow()) < cutoff_date:
            continue
            
        # Skip blocked companies
        if job["company"].lower() in blocked_companies:
            continue
            
        # Filter by Target titles (if any target titles exist, require matching substring)
        if target_titles:
            job_title_lower = job["title"].lower()
            if not any(target in job_title_lower for target in target_titles):
                continue
                
        # Check DB to prevent re-processing across runs
        if is_job_discovered(job["id"]):
            continue
            
        # Job passed all filters:
        seen_ids.add(job["id"])
        fresh_listings.append(job)
        
        # Step 5: Save discovered job to DB
        try:
            save_job(job)
        except Exception as e:
            errors.append(f"DB save error for {job['id']}: {e}")
            
    return {
        "raw_listings": fresh_listings,  # These will be appended by operator.add 
        "discovery_complete": True,
        "errors": errors
    }
