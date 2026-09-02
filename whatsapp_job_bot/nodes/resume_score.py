"""
Scores an uploaded (or freshly built) resume and saves it as the user's
base resume in the DB.
"""
from state import GraphState
from llm_client import ask_json
import db

SYSTEM = """You are an ATS + hiring-manager hybrid reviewer. Given a resume's
plain text, return JSON exactly in this shape:

{
  "score": <0-100 integer, overall quality>,
  "strengths": ["...", "..."],
  "gaps": ["...", "..."],
  "ats_keywords_missing": ["...", "..."],
  "formatting_notes": "..."
}

Be specific and honest. A generic resume with no metrics should score low
(40s-50s), not a polite 80."""


def resume_score_node(state: GraphState) -> GraphState:
    resume_text = state.get("resume_text", "")
    if not resume_text.strip():
        return {**state, "reply_text": "I didn't get any resume text to score — try uploading again."}

    result = ask_json(SYSTEM, resume_text, max_tokens=1200)
    score = result.get("score")
    feedback = {k: v for k, v in result.items() if k != "score"}

    resume_id = db.save_resume(
        user_id=state["user_id"],
        content=resume_text,
        kind="base",
        score=score,
        score_feedback=feedback,
    )

    strengths = "\n".join(f"• {s}" for s in feedback.get("strengths", []))
    gaps = "\n".join(f"• {g}" for g in feedback.get("gaps", []))
    missing_kw = ", ".join(feedback.get("ats_keywords_missing", [])) or "none flagged"

    reply = (
        f"*Resume score: {score}/100*\n\n"
        f"*Strengths*\n{strengths or '—'}\n\n"
        f"*Gaps*\n{gaps or '—'}\n\n"
        f"*Possibly-missing ATS keywords*: {missing_kw}\n\n"
        f"_Formatting_: {feedback.get('formatting_notes', '—')}\n\n"
        "Send me a job description any time and I'll tailor this resume + write a cover letter for it."
    )

    return {**state, "score": score, "score_feedback": feedback,
            "resume_id": resume_id, "reply_text": reply}