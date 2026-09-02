"""
Shared state passed between LangGraph nodes.

One GraphState flows through the whole graph per user turn. The `intent`
field, set by the router, decides which node(s) run next. Everything else
is optional context that nodes read/write as needed.
"""
from typing import TypedDict, Optional, Literal

Intent = Literal[
    "roadmap",
    "resume_upload",
    "resume_build",
    "resume_score",
    "tailor",
    "job_search",
    "status",
    "unknown",
]


class GraphState(TypedDict, total=False):
    user_id: str                   # WhatsApp phone number
    user_text: str                 # raw incoming message text
    intent: Intent

    # Resume-related
    resume_text: Optional[str]
    resume_id: Optional[int]
    score: Optional[float]
    score_feedback: Optional[dict]

    # Guided resume-builder sub-flow
    builder_stage: Optional[str]
    builder_answers: Optional[dict]

    # Tailoring
    job_description: Optional[str]
    tailored_resume: Optional[str]
    cover_letter: Optional[str]
    application_id: Optional[int]

    # Job search
    job_query: Optional[str]
    job_results: Optional[list]

    # Final text sent back to the user
    reply_text: Optional[str]