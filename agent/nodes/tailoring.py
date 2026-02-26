"""
agent/nodes/tailoring.py — Resume tailoring + cover letter generation node.

For each job with recommendation APPLY or REVIEW:
  1. Rewrites resume bullets to match the JD (LLM Call 1)
  2. Generates a cover letter (LLM Call 2)
  3. Renders a tailored resume PDF
  4. Saves all to SQLite and marks app as pending_approval
"""

import json
import logging
import re
from collections import Counter
from typing import List, Dict, Any, Tuple

from agent.state import AgentState, TailoredApp, FitScore, JobListing
from agent.llm import get_llm, MAX_JD_TOKENS
from db.database import get_user_profile, save_tailored_app
from pdf.generator import generate_resume_pdf

logger = logging.getLogger(__name__)

TAILORING_PROMPT = open("prompts/tailoring.txt").read()
COVER_LETTER_PROMPT = open("prompts/cover_letter.txt").read()

# Common english stopwords to exclude from keyword extraction
_STOPWORDS = {
    "the","a","an","and","or","to","of","in","for","is","are","be","with",
    "as","on","at","we","you","our","have","will","by","from","this","that",
    "your","their","its","not","but","all","they","which","who","what","how",
    "can","also","more","well","work","team","using","use","used","across",
    "within","new","been","has","had","into","able","each","strong","experience",
}


def extract_keywords(text: str, n: int = 20) -> List[str]:
    """Return the top-N meaningful words from a job description."""
    words = re.findall(r"[a-z][a-z0-9+#.]*", text.lower())
    filtered = [w for w in words if len(w) > 3 and w not in _STOPWORDS]
    return [w for w, _ in Counter(filtered).most_common(n)]


def clean_json(text: str) -> str:
    """Strip markdown fences and extract innermost JSON object.
    Also attempts crude repair of common Gemini truncation patterns."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Attempt to repair truncated JSON:
    # e.g. ends mid-string inside a bullet array
    if text.endswith('"'):
        # Could be a truncated bullet string — close it out
        text += '"], "changes_summary": ""}'
    elif text.endswith(","):
        text = text.rstrip(",") + ']'
        if '"tailored_bullets"' in text:
            text += ', "changes_summary": ""}'

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text.strip()


def run(state: AgentState) -> dict:
    """
    Tailoring node:
    - Reads scored_listings from state (list of (JobListing, FitScore) tuples)
    - Filters to APPLY/REVIEW recommendations
    - Two LLM calls per job: bullet rewrite + cover letter
    - Generates PDF
    - Saves to DB as pending_approval
    """
    llm = get_llm()
    profile = get_user_profile()
    if not profile:
        raise ValueError("No user profile found. Please complete Setup first.")

    # Collect all existing experience bullets for rewriting
    all_bullets: List[str] = []
    for exp in profile.get("experiences", []):
        all_bullets.extend(exp.get("bullets", []))

    tailored_apps: List[TailoredApp] = []
    errors: List[str] = []

    scored: List[Tuple[JobListing, FitScore]] = state.get("scored_listings", [])

    for job, score in scored:
        rec = score.get("recommendation", "SKIP")
        if rec not in ("APPLY", "REVIEW"):
            continue

        job_id = job.get("id", "unknown")
        try:
            description = str(job.get("description", ""))
            if len(description) > MAX_JD_TOKENS:
                description = description[:MAX_JD_TOKENS] + "... [truncated]"

            # ── LLM Call 1: Tailored Bullets ─────────────────────
            jd_keywords = extract_keywords(description)
            bullets_text = "\n".join(f"- {b}" for b in all_bullets[:10])  # top 10 bullets

            bullet_prompt = TAILORING_PROMPT.format(
                original_bullets=bullets_text,
                jd_keywords=", ".join(jd_keywords),
                job_description=description,
            )

            bullet_response = llm.invoke(bullet_prompt)
            bullet_json = clean_json(bullet_response.content)
            try:
                bullet_data = json.loads(bullet_json)
            except json.JSONDecodeError as decode_err:
                logger.error(f"JSON Decode Error for bullet payload: {bullet_json}")
                raise decode_err

            tailored_bullets: List[str] = bullet_data.get("tailored_bullets", [])
            changes_summary: str = bullet_data.get("changes_summary", "")

            # ── LLM Call 2: Cover Letter ──────────────────────────
            profile_summary = json.dumps({
                "skills": profile.get("skills", [])[:15],
                "experiences": [
                    {
                        "title": e.get("title"),
                        "company": e.get("company"),
                        "bullets": e.get("bullets", [])[:3],
                    }
                    for e in profile.get("experiences", [])[:3]
                ],
            }, indent=2)

            cl_prompt = COVER_LETTER_PROMPT.format(
                candidate_name=profile.get("name", ""),
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                candidate_profile=profile_summary,
                job_description=description,
            )

            cl_response = llm.invoke(cl_prompt)
            cover_letter: str = cl_response.content.strip()

            # ── PDF Generation ─────────────────────────────────────
            resume_pdf_path = generate_resume_pdf(
                profile=profile,
                tailored_bullets=tailored_bullets,
                job=job,
                output_dir="generated_resumes",
            )
            logger.info(f"PDF generated: {resume_pdf_path}")

            # ── DB Update ─────────────────────────────────────────
            save_tailored_app(
                job_id=job_id,
                tailored_bullets=tailored_bullets,
                cover_letter=cover_letter,
                pdf_path=resume_pdf_path,
            )

            # ── Build TailoredApp for state ───────────────────────
            tailored_app: TailoredApp = {
                "job": job,
                "score": score,
                "tailored_bullets": tailored_bullets,
                "changes_summary": changes_summary,
                "cover_letter": cover_letter,
                "resume_pdf_path": resume_pdf_path,
            }
            tailored_apps.append(tailored_app)

        except Exception as e:
            err_msg = f"Tailoring failed for job {job_id}: {e}"
            logger.exception(err_msg)
            errors.append(err_msg)

    return {
        "tailored_apps": tailored_apps,
        "pending_human_review": tailored_apps,
        "requires_human_input": len(tailored_apps) > 0,
        "errors": errors,
    }
