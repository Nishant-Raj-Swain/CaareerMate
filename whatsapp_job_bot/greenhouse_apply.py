"""
Option 2: ATS-native applications via Greenhouse's public endpoints.

IMPORTANT:
  - Greenhouse's public Job Board API (boards-api.greenhouse.io) is
    documented and safe to call for *reading* job postings.
  - The application *submission* call below posts to Greenhouse's public
    embed form endpoint the same way a browser does. This is NOT an
    official, versioned API — Greenhouse can change it without notice,
    and many postings add custom questions, EEOC fields, or CAPTCHAs this
    code does not fill in. Treat it as best-effort, expect failures, and
    always give the user the job URL as a fallback.
  - This is why it's gated behind the same human-confirm step as email
    applications — nothing submits without an explicit "confirm".
"""
import re
import httpx

BOARD_API = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
EMBED_APPLY_URL = "https://boards.greenhouse.io/embed/job_app?for={board_token}&token={job_id}"

URL_PATTERN = re.compile(
    r"boards\.greenhouse\.io/(?:embed/job_app\?for=)?([\w-]+)/?.*?(?:jobs/|token=)(\d+)"
)


def parse_greenhouse_url(url: str) -> tuple[str, str] | None:
    """Extracts (board_token, job_id) from a Greenhouse job URL, or None."""
    match = URL_PATTERN.search(url)
    if not match:
        return None
    return match.group(1), match.group(2)


def fetch_job_details(board_token: str, job_id: str) -> dict | None:
    """Public, documented, read-only — safe to call freely."""
    url = BOARD_API.format(board_token=board_token, job_id=job_id)
    try:
        resp = httpx.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return {
            "title": data.get("title"),
            "company": board_token.replace("-", " ").title(),
            "location": (data.get("location") or {}).get("name"),
            "url": data.get("absolute_url"),
        }
    except Exception:
        return None


def submit_application(board_token: str, job_id: str, full_name: str, email: str,
                        phone: str, resume_text: str, cover_letter: str) -> tuple[bool, str]:
    """
    Best-effort submission. Returns (success, message). Expect failures on
    postings with custom required questions — caller should fall back to
    giving the user the direct URL.
    """
    first_name, _, last_name = full_name.partition(" ")
    last_name = last_name or "-"

    url = EMBED_APPLY_URL.format(board_token=board_token, job_id=job_id)
    fields = {
        "job_application[first_name]": first_name,
        "job_application[last_name]": last_name,
        "job_application[email]": email,
        "job_application[phone]": phone,
        "job_application[cover_letter_text]": cover_letter,
    }
    files = {
        "job_application[resume]": ("resume.txt", resume_text.encode("utf-8"), "text/plain"),
    }

    try:
        resp = httpx.post(url, data=fields, files=files, timeout=30, follow_redirects=True)
        if resp.status_code in (200, 201, 302):
            return True, "Submitted (best-effort — worth confirming manually if this posting had extra questions)."
        return False, f"Greenhouse returned status {resp.status_code}; this posting likely needs manual questions answered."
    except Exception as e:
        return False, f"Auto-fill failed: {e}"