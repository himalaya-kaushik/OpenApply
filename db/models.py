from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Job(Base):
    __tablename__ = 'jobs'

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    url = Column(String, nullable=False)
    source = Column(String)
    description = Column(Text)
    posted_at = Column(DateTime)
    discovered_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    score = relationship("Score", back_populates="job", uselist=False)
    applications = relationship("Application", back_populates="job")
    history = relationship("StatusHistory", back_populates="job")

class UserProfile(Base):
    __tablename__ = 'user_profile'
    
    id = Column(Integer, primary_key=True, default=1)
    name = Column(String)
    email = Column(String)
    raw_json = Column(Text)  # full profile stored as JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserPreferences(Base):
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True, default=1)
    target_titles = Column(Text)      # JSON array
    locations = Column(Text)          # JSON array
    remote_preference = Column(String)
    salary_floor = Column(Integer)
    blocked_companies = Column(Text)  # JSON array
    min_fit_score = Column(Integer, default=80)
    daily_run_time = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Score(Base):
    __tablename__ = 'scores'

    job_id = Column(String, ForeignKey('jobs.id'), primary_key=True)
    score = Column(Integer)
    skill_match = Column(Text)   # JSON string array
    skill_gaps = Column(Text)    # JSON string array
    seniority_match = Column(Boolean)
    location_match = Column(Boolean)
    reasoning = Column(Text)
    recommendation = Column(String)
    scored_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    job = relationship("Job", back_populates="score")

class Application(Base):
    __tablename__ = 'applications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.id'))
    status = Column(String, default='discovered')
    tailored_bullets = Column(Text)   # JSON string array
    cover_letter = Column(Text)
    resume_pdf_path = Column(String)
    submission_method = Column(String)
    applied_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text)

    # Relationships
    job = relationship("Job", back_populates="applications")

class StatusHistory(Base):
    __tablename__ = 'status_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey('jobs.id'))
    old_status = Column(String)
    new_status = Column(String)
    reason = Column(Text)
    changed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    job = relationship("Job", back_populates="history")

class BlockedCompany(Base):
    __tablename__ = 'blocked_companies'

    company_name = Column(String, primary_key=True)
    blocked_at = Column(DateTime, default=datetime.utcnow)
    reason = Column(Text)

class AgentRun(Base):
    __tablename__ = 'agent_runs'

    id = Column(String, primary_key=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    jobs_discovered = Column(Integer, default=0)
    jobs_scored = Column(Integer, default=0)
    jobs_applied = Column(Integer, default=0)
    jobs_discarded = Column(Integer, default=0)
    errors = Column(Text)   # JSON string array
