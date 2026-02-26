import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import json
from .models import Base, Job, Application, BlockedCompany, Score, UserProfile, UserPreferences

load_dotenv(override=True)

# Use local sqlite db by default if not specified
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./openapply.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Create all tables if they don't exist"""
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def is_job_discovered(job_id: str) -> bool:
    """Check if a job ID already exists in the database entirely"""
    db = SessionLocal()
    try:
        exists = db.query(Job).filter(Job.id == job_id).first() is not None
        return exists
    finally:
        db.close()

def get_blocked_companies() -> List[str]:
    """Get list of blocked company names"""
    db = SessionLocal()
    try:
        blocked = db.query(BlockedCompany.company_name).all()
        return [b[0].lower() for b in blocked]
    finally:
        db.close()

def save_job(job_dict: Dict[str, Any]):
    """Save a new discovered job into the database and start application tracking"""
    db = SessionLocal()
    try:
        # Save Job
        job = Job(
            id=job_dict["id"],
            title=job_dict["title"],
            company=job_dict["company"],
            url=job_dict["url"],
            source=job_dict["source"],
            description=job_dict["description"],
            posted_at=job_dict["posted_at"],
            discovered_at=job_dict["discovered_at"]
        )
        db.add(job)
        
        # Start Application tracking row
        app = Application(
            job_id=job.id,
            status="discovered"
        )
        db.add(app)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def save_score(job_id: str, score_data: dict, min_fit_score: int):
    """
    Save scoring results for a job and update the application status.
    Uses JSON serialization for string arrays.
    """
    db = SessionLocal()
    try:
        # Create Score record
        score_record = Score(
            job_id=job_id,
            score=score_data.get("score", 0),
            skill_match=json.dumps(score_data.get("skill_match", [])),
            skill_gaps=json.dumps(score_data.get("skill_gaps", [])),
            seniority_match=score_data.get("seniority_match", False),
            location_match=score_data.get("location_match", False),
            reasoning=score_data.get("reasoning", ""),
            recommendation=score_data.get("recommendation", "SKIP")
        )
        db.merge(score_record)  # Use merge incase of duplicate runs

        # Update application status
        app = db.query(Application).filter(Application.job_id == job_id).first()
        if app:
            if score_record.score < min_fit_score or score_record.recommendation == "SKIP":
                app.status = "discarded"
                app.notes = f"Discarded by LLM scoring. Score: {score_record.score}, Rec: {score_record.recommendation}"
            elif score_record.recommendation == "REVIEW":
                app.status = "scored_review"
            else:
                app.status = "scored_high"
                
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def save_user_profile(profile_dict: Dict[str, Any]):
    """Upsert the user profile (id=1) into the db"""
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
        if not profile:
            profile = UserProfile(id=1)
            
        profile.name = profile_dict.get("name")
        profile.email = profile_dict.get("email")
        profile.raw_json = json.dumps(profile_dict)
        
        db.merge(profile)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def get_user_profile() -> Optional[Dict[str, Any]]:
    """Retrieve the user profile parsed JSON, or None if not set up"""
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
        if profile and profile.raw_json:
            return json.loads(profile.raw_json)
        return None
    finally:
        db.close()

def save_preferences(prefs_dict: Dict[str, Any]):
    """Upsert the user preferences (id=1) into the db"""
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.id == 1).first()
        if not prefs:
            prefs = UserPreferences(id=1)
            
        prefs.target_titles = json.dumps(prefs_dict.get("target_titles", []))
        prefs.locations = json.dumps(prefs_dict.get("locations", []))
        prefs.remote_preference = prefs_dict.get("remote_preference")
        prefs.salary_floor = prefs_dict.get("salary_floor")
        
        # Blocked companies are also stored as JSON array
        prefs.blocked_companies = json.dumps(prefs_dict.get("blocked_companies", []))
        
        prefs.min_fit_score = prefs_dict.get("min_fit_score", 80)
        prefs.daily_run_time = prefs_dict.get("daily_run_time")
        
        db.merge(prefs)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def get_preferences() -> Optional[Dict[str, Any]]:
    """Retrieve and parse the user preferences from the db"""
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.id == 1).first()
        if not prefs:
            return None
            
        return {
            "target_titles": json.loads(prefs.target_titles) if prefs.target_titles else [],
            "locations": json.loads(prefs.locations) if prefs.locations else [],
            "remote_preference": prefs.remote_preference,
            "salary_floor": prefs.salary_floor,
            "blocked_companies": json.loads(prefs.blocked_companies) if prefs.blocked_companies else [],
            "min_fit_score": prefs.min_fit_score,
            "daily_run_time": prefs.daily_run_time
        }
    finally:
        db.close()

def save_tailored_app(job_id: str, tailored_bullets: list, cover_letter: str, pdf_path: str):
    """
    Update the Application row for job_id after tailoring:
    - saves tailored bullets as JSON string
    - saves cover letter text
    - saves PDF path
    - sets status to 'pending_approval'
    """
    db = SessionLocal()
    try:
        app = db.query(Application).filter(Application.job_id == job_id).first()
        if not app:
            raise ValueError(f"No application row found for job_id={job_id}")
        
        app.tailored_bullets = json.dumps(tailored_bullets)
        app.cover_letter = cover_letter
        app.resume_pdf_path = pdf_path
        app.status = "pending_approval"
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
