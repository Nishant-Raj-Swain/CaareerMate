"""
Wires all nodes into a single LangGraph StateGraph.
Flow: router -> (conditional) -> one of the task nodes -> END.
"""
from langgraph.graph import StateGraph, END
from state import GraphState

from nodes.router import router_node
from nodes.roadmap import roadmap_node
from nodes.resume_score import resume_score_node
from nodes.resume_builder import resume_builder_node
from nodes.tailor import tailor_node
from nodes.job_search import job_search_node


def status_node(state: GraphState) -> GraphState:
    import db
    rows = db.list_applications(state["user_id"])
    if not rows:
        return {**state, "reply_text": "No tracked applications yet. Tailor a resume to a job "
                                        "description and I'll start tracking it."}
    lines = []
    for r in rows:
        lines.append(f"#{r['id']} · {r['job_title']} @ {r['company'] or '—'} · *{r['status']}*")
    return {**state, "reply_text": "*Your applications:*\n\n" + "\n".join(lines)}


def unknown_node(state: GraphState) -> GraphState:
    reply = (
        "I can help with:\n"
        "• /roadmap <domain> — get a learning roadmap\n"
        "• Upload a resume file — I'll score it\n"
        "• /build — build a resume from scratch (no file needed)\n"
        "• /jobsearch <role/keywords> — find job listings\n"
        "• Paste a job description — I'll tailor your resume + write a cover letter\n"
        "• /status — see your tracked applications"
    )
    return {**state, "reply_text": reply}


def _route(state: GraphState) -> str:
    return state.get("intent", "unknown")


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("router", router_node)
    graph.add_node("roadmap", roadmap_node)
    graph.add_node("resume_score", resume_score_node)
    graph.add_node("resume_build", resume_builder_node)
    graph.add_node("tailor", tailor_node)
    graph.add_node("job_search", job_search_node)
    graph.add_node("status", status_node)
    graph.add_node("unknown", unknown_node)

    graph.set_entry_point("router")
    graph.add_conditional_edges(
        "router",
        _route,
        {
            "roadmap": "roadmap",
            "resume_upload": "resume_score",
            "resume_score": "resume_score",
            "resume_build": "resume_build",
            "tailor": "tailor",
            "job_search": "job_search",
            "status": "status",
            "unknown": "unknown",
        },
    )

    for node in ["roadmap", "resume_score", "resume_build", "tailor", "job_search", "status", "unknown"]:
        graph.add_edge(node, END)

    return graph.compile()