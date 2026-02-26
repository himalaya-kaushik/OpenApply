"""
pdf/generator.py — ReportLab PDF generation from tailored resume content.

Takes the original profile + a list of tailored bullets and renders
a clean, single-column PDF resume saved to generated_resumes/.
"""

import os
import re
import json
from datetime import date
from typing import List, Dict, Any

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable
)


# ── Style helpers ──────────────────────────────────────────────

def _make_styles():
    base = getSampleStyleSheet()
    styles = {
        "name": ParagraphStyle(
            "Name",
            fontName="Helvetica-Bold",
            fontSize=18,
            spaceAfter=2,
            alignment=TA_CENTER,
        ),
        "contact": ParagraphStyle(
            "Contact",
            fontName="Helvetica",
            fontSize=9,
            spaceAfter=6,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#444444"),
        ),
        "section_header": ParagraphStyle(
            "SectionHeader",
            fontName="Helvetica-Bold",
            fontSize=11,
            spaceBefore=10,
            spaceAfter=2,
            textColor=colors.HexColor("#1a1a2e"),
        ),
        "job_title": ParagraphStyle(
            "JobTitle",
            fontName="Helvetica-Bold",
            fontSize=10,
            spaceAfter=1,
        ),
        "job_meta": ParagraphStyle(
            "JobMeta",
            fontName="Helvetica-Oblique",
            fontSize=9,
            spaceAfter=3,
            textColor=colors.HexColor("#555555"),
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            fontName="Helvetica",
            fontSize=9,
            spaceAfter=2,
            leftIndent=14,
            bulletIndent=6,
        ),
        "skills": ParagraphStyle(
            "Skills",
            fontName="Helvetica",
            fontSize=9,
            spaceAfter=4,
        ),
        "edu": ParagraphStyle(
            "Edu",
            fontName="Helvetica",
            fontSize=9,
            spaceAfter=2,
        ),
    }
    return styles


def _sanitize(text: str) -> str:
    """Escape special ReportLab XML characters."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def _safe_filename(text: str) -> str:
    """Strip characters unsafe for filenames."""
    return re.sub(r"[^\w\-_]", "_", text).strip("_")[:40]


# ── Main generation function ───────────────────────────────────

def generate_resume_pdf(
    profile: Dict[str, Any],
    tailored_bullets: List[str],
    job: Dict[str, Any],
    output_dir: str = "generated_resumes",
) -> str:
    """
    Renders a single-column PDF resume and saves it to output_dir.
    The tailored_bullets replace the bullets of the first (most recent)
    experience entry. Everything else comes from the profile as-is.

    Returns the absolute path of the saved PDF.
    """
    os.makedirs(output_dir, exist_ok=True)

    company_safe = _safe_filename(job.get("company", "company"))
    title_safe   = _safe_filename(job.get("title", "role"))
    today        = date.today().strftime("%Y-%m-%d")
    filename     = f"{company_safe}_{title_safe}_{today}.pdf"
    output_path  = os.path.abspath(os.path.join(output_dir, filename))

    doc = SimpleDocTemplate(
        output_path,
        pagesize=LETTER,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    S = _make_styles()
    story = []

    # ── Header ──────────────────────────────────────────────
    name    = _sanitize(profile.get("name", ""))
    email   = _sanitize(profile.get("email", ""))
    phone   = _sanitize(profile.get("phone", ""))
    loc     = _sanitize(profile.get("location", ""))
    links   = profile.get("links", {})
    linkedin = _sanitize(links.get("linkedin", ""))
    github   = _sanitize(links.get("github", ""))

    contact_parts = [p for p in [email, phone, loc, linkedin, github] if p]
    contact_line  = "  •  ".join(contact_parts)

    story.append(Paragraph(name, S["name"]))
    if contact_line:
        story.append(Paragraph(contact_line, S["contact"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc"), spaceAfter=6))

    # ── Skills ──────────────────────────────────────────────
    skills = profile.get("skills", [])
    if skills:
        story.append(Paragraph("SKILLS", S["section_header"]))
        skills_text = " • ".join(_sanitize(s) for s in skills)
        story.append(Paragraph(skills_text, S["skills"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd"), spaceAfter=4))

    # ── Experience ──────────────────────────────────────────
    experiences = profile.get("experiences", [])
    if experiences:
        story.append(Paragraph("EXPERIENCE", S["section_header"]))
        for i, exp in enumerate(experiences):
            title_text = _sanitize(exp.get("title", ""))
            company_text = _sanitize(exp.get("company", ""))
            dates_text   = _sanitize(exp.get("dates", ""))

            story.append(Paragraph(f"<b>{title_text}</b> — {company_text}", S["job_title"]))
            story.append(Paragraph(dates_text, S["job_meta"]))

            # Use tailored bullets for the first (most recent) experience
            if i == 0 and tailored_bullets:
                bullets = tailored_bullets
            else:
                bullets = exp.get("bullets", [])

            for b in bullets:
                story.append(Paragraph(f"• {_sanitize(str(b))}", S["bullet"]))

            story.append(Spacer(1, 4))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd"), spaceAfter=4))

    # ── Education ───────────────────────────────────────────
    education = profile.get("education", [])
    if education:
        story.append(Paragraph("EDUCATION", S["section_header"]))
        for edu in education:
            degree = _sanitize(edu.get("degree", ""))
            inst   = _sanitize(edu.get("institution", ""))
            year   = _sanitize(str(edu.get("year", "")))
            story.append(Paragraph(f"<b>{degree}</b> — {inst}, {year}", S["edu"]))

    doc.build(story)
    return output_path
