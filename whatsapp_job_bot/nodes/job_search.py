"""
Job search node. Uses Adzuna's free-tier API — a real, ToS-friendly
provider, unlike LinkedIn/Indeed which prohibit scraping/automation.
Returns candidates for review; does NOT apply.
"""
import httpx
from state import GraphState
from config import ADZUNA_APP_ID, ADZUNA_APP_KEY

ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


def _search_adzuna(query: str, country: str = "in", results: int = 5) -> list[dict]:
    if not (ADZUNA_APP_ID and ADZUNA_APP_KEY):
        return []
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": query,
        "results_per_page": results,
        "content-type": "application/json",
    }
    resp = httpx.get(ADZUNA_URL.format(country=country), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "title": job.get("title"),
            "company": (job.get("company") or {}).get("display_name"),
            "location": (job.get("location") or {}).get("display_name"),
            "url": job.get("redirect_url"),
            "description": job.get("description"),
        }
        for job in data.get("results", [])
    ]


def job_search_node(state: GraphState) -> GraphState:
    query = state.get("job_query") or state.get("user_text", "")
    if not query.strip():
        return {**state, "reply_text": "What role/keywords should I search for? e.g. "
                                        "'data analyst' or 'python backend Bengaluru'"}

    try:
        results = _search_adzuna(query)
    except Exception as e:
        return {**state, "reply_text": f"Job search failed: {e}"}

    if not results:
        reply = ("No job provider is configured yet (ADZUNA_APP_ID/ADZUNA_APP_KEY missing "
                  "in .env), or no results came back. Get free Adzuna API keys at "
                  "developer.adzuna.com and add them to .env.")
        return {**state, "job_results": [], "reply_text": reply}

    lines = []
    for i, job in enumerate(results, 1):
        lines.append(f"{i}. *{job['title']}* — {job['company'] or 'unknown'} ({job['location'] or 'n/a'})\n{job['url']}")
    reply = "Here's what I found:\n\n" + "\n\n".join(lines) + \
            "\n\nPaste any of these job descriptions to me and I'll tailor your resume + write a cover letter for it."

    return {**state, "job_results": results, "reply_text": reply}