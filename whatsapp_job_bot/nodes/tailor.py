"""
Takes the user's base resume + a job description, produces a tailored
resume and a cover letter, and saves both plus a draft application row.

The application_id is returned in state so app.py can immediately follow
up with "how do you want to apply?" buttons.
"""
from state import GraphState
from llm_client import ask
import db

TAILOR_SYSTEM = """You rewrite resumes to match a specific job description
without fabricating experience. Reorder and rephrase existing bullets to
foreground relevant skills, mirror the job description's terminology where
truthful, and tighten the summary. Keep it plain text, ATS-friendly, same
overall length as the input. Output ONLY the tailored resume text."""

COVER_LETTER_SYSTEM = """Write a concise, specific cover letter (250-350 words)
based on the candidate's resume and the target job description. No generic
filler ("I am writing to express my interest..."). Open with something
concrete and relevant. Plain text, ready to send."""

JOB_META_SYSTEM = """Extract the job title and company name from this job
description text. Return JSON: {"title": "...", "company": "..."}. If the
company isn't mentioned, use "Unknown"."""


def tailor_node(state: GraphState) -> GraphState:
    from llm_client import ask_json

    base_row = db.get_latest_base_resume(state["user_id"])
    if base_row is None:
        return {**state, "reply_text": "I don't have a base resume for you yet — "
                                        "upload one or send /build to create one first."}

    job_description = state.get("job_description") or state.get("user_text", "")
    if not job_description.strip():
        return {**state, "reply_text": "Send me the job description text and I'll tailor your resume to it."}

    base_resume = base_row["content"]

    tailored_resume = ask(
        TAILOR_SYSTEM,
        f"BASE RESUME:\n{base_resume}\n\nJOB DESCRIPTION:\n{job_description}",
        max_tokens=1500,
    )
    cover_letter = ask(
        COVER_LETTER_SYSTEM,
        f"RESUME:\n{tailored_resume}\n\nJOB DESCRIPTION:\n{job_description}",
        max_tokens=800,
    )

    try:
        meta = ask_json(JOB_META_SYSTEM, job_description, max_tokens=100)
        job_title = meta.get("title") or "Untitled role"
        company = meta.get("company") or "Unknown"
    except Exception:
        job_title, company = "Untitled role", "Unknown"

    tailored_id = db.save_resume(
        user_id=state["user_id"],
        content=tailored_resume,
        kind="tailored",
        job_description=job_description,
    )

    application_id = db.create_application(
        user_id=state["user_id"],
        job_title=job_title,
        company=company,
        job_url=None,
        resume_id=tailored_id,
        cover_letter=cover_letter,
        status="draft",
    )

    reply = (
        f"*{job_title}* @ {company}\n\n"
        "*Tailored resume:*\n\n" + tailored_resume +
        "\n\n*Cover letter:*\n\n" + cover_letter
    )
    return {**state, "tailored_resume": tailored_resume, "cover_letter": cover_letter,
            "application_id": application_id, "reply_text": reply}