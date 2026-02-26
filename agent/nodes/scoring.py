import json
import logging
from typing import Dict, Any

from agent.state import AgentState, FitScore
from agent.llm import get_llm, MAX_JD_TOKENS
from db.database import save_score, get_user_profile, get_preferences

logger = logging.getLogger(__name__)

SCORING_PROMPT = open("prompts/scoring.txt").read()

def clean_json_response(text: str) -> str:
    """Helper to remove markdown code blocks from LLM output if present,
    and also to attempt crude JSON repair if Gemini truncated the response
    mid-generation due to max_tokens limits."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
        
    text = text.strip()
    
    # Handle known truncation patterns (reasoning/recommendation cuts off)
    if text.endswith(', "reasoning'):
        text += '": "", "recommendation": "SKIP"}'
    elif text.endswith('": "APPLY"'): # missing closing brace
        text += '}'
    elif text.endswith('": "SKIP"'):
        text += '}'
    elif text.endswith('": "REVIEW"'):
        text += '}'
    elif text.endswith('"'): # chopped string mid-reasoning
        text += '", "recommendation": "SKIP"}'
        
    # Extract only the JSON between the first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        text = text[start:end+1]
        
    return text.strip()

def run(state: AgentState) -> dict:
    """
    Scoring node implementation:
    1. Instantiate LLM
    2. Loop through state["raw_listings"]
    3. Construct prompt and call LLM
    4. Parse output and calculate filtering
    5. Save to sqlite db
    """
    llm = get_llm()
    
    profile = get_user_profile()
    if profile is None:
        raise ValueError("No resume found. Please complete setup at the Setup page first.")
    prefs = get_preferences() or {}
    min_score = prefs.get("min_fit_score", 80)
    
    scored_listings = []
    errors = []
    
    # Process only raw listings
    for job in state.get("raw_listings", []):
        try:
            # Prepare profile dump safely
            profile_dump = json.dumps({
                "skills": profile.get("skills", []),
                "experiences": profile.get("experiences", []),
                "education": profile.get("education", [])
            }, indent=2)

            description = str(job.get("description", ""))
            # Statically truncate description to protect token limits
            if len(description) > MAX_JD_TOKENS:
                description = description[:MAX_JD_TOKENS] + "... [truncated]"

            prompt = SCORING_PROMPT.format(
                candidate_profile=profile_dump,
                job_description=description
            )
            
            # Invoke LLM
            response = llm.invoke(prompt)
            raw_text = response.content
            
            cleaned_text = clean_json_response(raw_text)
            score_data = json.loads(cleaned_text)
            
            # Map back to TypedDict
            fit_score: FitScore = {
                "score": int(score_data.get("score", 0)),
                "skill_match": score_data.get("skill_match", []),
                "skill_gaps": score_data.get("skill_gaps", []),
                "seniority_match": bool(score_data.get("seniority_match", False)),
                "location_match": bool(score_data.get("location_match", False)),
                "reasoning": score_data.get("reasoning", ""),
                "recommendation": score_data.get("recommendation", "SKIP"),
            }
            
            # Save into DB immediately
            save_score(job["id"], fit_score, min_score)
            
            # Determine if it passes to the next node
            rec = fit_score["recommendation"]
            if fit_score["score"] >= min_score and rec in ("APPLY", "REVIEW"):
                scored_listings.append((job, fit_score))
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            err_msg = f"Scoring failed for job {job.get('id', 'unknown')}: {str(e)}"
            logger.exception(err_msg)
            errors.append(err_msg)
            
    return {
        "scored_listings": scored_listings,  # Appends via operator.add
        "scoring_complete": True,
        "errors": errors
    }
