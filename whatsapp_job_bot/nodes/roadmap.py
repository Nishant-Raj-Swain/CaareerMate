"""
Given a domain/interest, produce a structured learning roadmap.
"""
from state import GraphState
from llm_client import ask

SYSTEM = """You are a career mentor. Given a domain or interest, produce a
practical, phased learning roadmap. Structure it as:

1. A short 1-2 sentence overview of what mastering this domain looks like.
2. 4-6 phases (e.g. Foundations, Core Skills, Tools, Projects, Advanced,
   Job-Readiness), each with:
   - what to learn
   - 2-3 concrete resources or resource *types* (not fake URLs — course
     names, book titles, or "official docs for X" is fine)
   - a rough time estimate
3. 2-3 portfolio project ideas that would prove competence to an employer.

Keep it concrete and skimmable. Use Markdown with headers and bullet points.
Do not pad with generic motivational text."""


def roadmap_node(state: GraphState) -> GraphState:
    domain = state.get("user_text", "").strip()
    reply = ask(SYSTEM, f"Domain/interest: {domain}", max_tokens=2000)
    return {**state, "reply_text": reply}