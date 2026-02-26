-- User Profile master table
CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY DEFAULT 1,
    name TEXT,
    email TEXT,
    raw_json TEXT,  -- full profile stored as JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User Preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY DEFAULT 1,
    target_titles TEXT,      -- JSON array
    locations TEXT,          -- JSON array
    remote_preference TEXT,
    salary_floor INTEGER,
    blocked_companies TEXT,  -- JSON array
    min_fit_score INTEGER DEFAULT 80,
    daily_run_time TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);