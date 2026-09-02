"""
WhatsApp webhook server (Flask).

Drives a draft-and-confirm apply flow: after a resume is tailored, the bot

asks how to apply (email / Greenhouse auto-fill / manual), collects

whatever's missing (applicant profile, target email or job URL), shows

exactly what it's about to send, and only acts after an explicit "Confirm"

button tap.

Run with: python app.py  (dev server)

or: gunicorn app:app (production)

"""

import logging
import re

from flask import Flask, request

from config import WHATSAPP_VERIFY_TOKEN
from graph import build_graph
from resume_parsing import extract_text
import whatsapp_client
import email_apply
import greenhouse_apply
import db

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

app = Flask(__name__)

compiled_graph = build_graph()

db.init_db()

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")

user_sessions: dict[str, dict] = {}


def _session(user_id: str) -> dict:
    return user_sessions.setdefault(user_id, {})


HELP_TEXT = (
    "I can help with:\n"
    "• /roadmap <domain> — get a learning roadmap\n"
    "• Upload a resume file (.pdf/.docx) — I'll score it\n"
    "• /build — build a resume from scratch (no file needed)\n"
    "• /jobsearch <role/keywords> — find job listings\n"
    "• Paste a job description — I'll tailor your resume, write a cover letter, "
    "and offer to apply for you (email, ATS auto-fill, or you do it manually)\n"
    "• /status — see your tracked applications"
)


# ---------------------------------------------------------------- webhook --

@app.route("/webhook", methods=["GET"])
def verify():

    mode = request.args.get("hub.mode")

    token = request.args.get("hub.verify_token")

    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def receive():

    print("🔥 WEBHOOK POST RECEIVED")

    data = request.get_json(force=True, silent=True) or {}

    print("📦 DATA:", data)

    try:

        for entry in data.get("entry", []):

            for change in entry.get("changes", []):

                value = change.get("value", {})

                print("📨 VALUE:", value)

                for message in value.get("messages", []):

                    print("📩 MESSAGE:", message)

                    _handle_message(message, value)

    except Exception:

        logger.exception("❌ Error handling webhook payload")

    return "OK", 200


def _handle_message(message: dict, value: dict):

    user_id = message["from"]

    msg_type = message.get("type")

    contacts = value.get("contacts", [])

    display_name = contacts[0]["profile"]["name"] if contacts else None

    db.upsert_user(user_id, display_name)

    if msg_type == "text":

        _handle_text(user_id, message["text"]["body"].strip())

    elif msg_type == "document":

        _handle_document(user_id, message["document"])

    elif msg_type == "interactive":

        _handle_interactive(user_id, message["interactive"])

    else:

        whatsapp_client.send_text(
            user_id,
            "I can read text messages, resume files, and button taps right now."
        )


# ------------------------------------------------------------- text input --

def _handle_text(user_id: str, text: str):

    session = _session(user_id)

    lower = text.lower()

    if session.get("pending_app"):

        if _continue_apply_flow_text(user_id, session, text):
            return

    if lower in ("hi", "hello", "start", "/start"):

        whatsapp_client.send_text(
            user_id,
            "Hey! I'm your career assistant. I can build a learning roadmap, "
            "score/tailor your resume, write cover letters, and apply for you.\n\n"
            + HELP_TEXT,
        )

        return

    if lower.startswith("/roadmap"):

        domain = text[len("/roadmap"):].strip()

        if not domain:

            whatsapp_client.send_text(
                user_id,
                "Usage: /roadmap <domain or interest>"
            )

            return

        result = compiled_graph.invoke({
            "user_id": user_id,
            "user_text": domain,
            "intent": "roadmap"
        })

        whatsapp_client.send_text(user_id, result["reply_text"])

        return

    if lower.startswith("/build"):

        session["builder_stage"] = None

        session["builder_answers"] = {}

        result = compiled_graph.invoke({
            "user_id": user_id,
            "user_text": "",
            "intent": "resume_build",
            "builder_stage": None,
            "builder_answers": {},
        })

        session["builder_stage"] = result.get("builder_stage")

        session["builder_answers"] = result.get("builder_answers", {})

        whatsapp_client.send_text(user_id, result["reply_text"])

        return

    if lower.startswith("/jobsearch"):

        query = text[len("/jobsearch"):].strip()

        if not query:

            whatsapp_client.send_text(
                user_id,
                "Usage: /jobsearch <role/keywords>"
            )

            return

        result = compiled_graph.invoke({
            "user_id": user_id,
            "user_text": query,
            "job_query": query,
            "intent": "job_search"
        })

        whatsapp_client.send_text(user_id, result["reply_text"])

        return

    if lower.startswith("/status"):

        result = compiled_graph.invoke({
            "user_id": user_id,
            "user_text": "",
            "intent": "status"
        })

        whatsapp_client.send_text(user_id, result["reply_text"])

        return

    if session.get("builder_stage") and session["builder_stage"] != "done":

        result = compiled_graph.invoke({
            "user_id": user_id,
            "user_text": text,
            "intent": "resume_build",
            "builder_stage": session["builder_stage"],
            "builder_answers": session.get("builder_answers", {}),
        })

        session["builder_stage"] = result.get("builder_stage")

        session["builder_answers"] = result.get("builder_answers", {})

        whatsapp_client.send_text(user_id, result["reply_text"])

        return

    if len(text) > 300:

        result = compiled_graph.invoke({
            "user_id": user_id,
            "user_text": text,
            "job_description": text,
            "intent": "tailor"
        })

        whatsapp_client.send_text(user_id, result["reply_text"])

        application_id = result.get("application_id")

        if application_id:

            _start_apply_flow(user_id, session, application_id)

        return

    result = compiled_graph.invoke({
        "user_id": user_id,
        "user_text": text
    })

    whatsapp_client.send_text(
        user_id,
        result.get("reply_text", HELP_TEXT)
    )


def _handle_document(user_id: str, document: dict):

    filename = document.get("filename", "resume.pdf")

    media_id = document["id"]

    media_url = whatsapp_client.get_media_url(media_id)

    if not media_url:

        whatsapp_client.send_text(
            user_id,
            "Couldn't fetch that file — try sending it again."
        )

        return

    file_bytes = whatsapp_client.download_media(media_url)

    try:

        resume_text = extract_text(file_bytes, filename)

    except ValueError as e:

        whatsapp_client.send_text(user_id, str(e))

        return

    whatsapp_client.send_text(
        user_id,
        "Got it — scoring your resume..."
    )

    result = compiled_graph.invoke({
        "user_id": user_id,
        "user_text": "",
        "resume_text": resume_text,
        "intent": "resume_upload",
    })

    whatsapp_client.send_text(user_id, result["reply_text"])


# ------------------------------------------------------- apply flow: core --

def _start_apply_flow(
    user_id: str,
    session: dict,
    application_id: int
):

    session["pending_app"] = {
        "application_id": application_id,
        "stage": "choose_channel",
        "channel": None
    }

    whatsapp_client.send_buttons(
        user_id,
        "How do you want to apply to this one?",
        [
            ("apply_email", "Email it"),
            ("apply_greenhouse", "ATS auto-fill"),
            ("apply_manual", "I'll do it myself"),
        ],
    )


def _handle_interactive(user_id: str, interactive: dict):

    if interactive.get("type") != "button_reply":

        return

    button_id = interactive["button_reply"]["id"]

    session = _session(user_id)

    pending = session.get("pending_app")

    if not pending:

        return

    if button_id == "apply_manual":

        db.update_application(
            pending["application_id"],
            status="ready",
            apply_channel="manual"
        )

        whatsapp_client.send_text(
            user_id,
            "No problem — marked as ready for you to apply manually. "
            "Send /status any time to see it."
        )

        session.pop("pending_app", None)

        return

    if button_id == "apply_email":

        pending["channel"] = "email"

        _advance_apply_flow(user_id, session)

        return

    if button_id == "apply_greenhouse":

        pending["channel"] = "greenhouse"

        _advance_apply_flow(user_id, session)

        return

    if button_id == "confirm_send":

        _execute_application(user_id, session)

        return

    if button_id == "cancel_send":

        db.update_application(
            pending["application_id"],
            status="ready"
        )

        whatsapp_client.send_text(
            user_id,
            "Cancelled — nothing was sent. It's saved as 'ready' "
            "if you want to try again later."
        )

        session.pop("pending_app", None)

        return


def _missing_profile_fields(user_id: str) -> list[str]:

    user = db.get_user(user_id)

    missing = []

    if not user or not user["full_name"]:

        missing.append("full_name")

    if not user or not user["email"]:

        missing.append("email")

    if not user or not user["phone"]:

        missing.append("phone")

    return missing


PROFILE_PROMPTS = {

    "full_name":
        "What's your full name (as it should appear on applications)?",

    "email":
        "What email address should applications use?",

    "phone":
        "What phone number should applications use?",
}


def _advance_apply_flow(user_id: str, session: dict):

    pending = session["pending_app"]

    missing = _missing_profile_fields(user_id)

    if missing:

        pending["stage"] = f"need_profile_{missing[0]}"

        whatsapp_client.send_text(
            user_id,
            PROFILE_PROMPTS[missing[0]]
        )

        return

    if pending["channel"] == "email" and not pending.get("apply_target"):

        pending["stage"] = "await_email_target"

        whatsapp_client.send_text(
            user_id,
            "What email address should I send the application to?"
        )

        return

    if pending["channel"] == "greenhouse" and not pending.get("apply_target"):

        pending["stage"] = "await_url_target"

        whatsapp_client.send_text(
            user_id,
            "Paste the Greenhouse job posting URL "
            "(e.g. https://boards.greenhouse.io/company/jobs/12345)."
        )

        return

    _show_confirm(user_id, session)


def _continue_apply_flow_text(
    user_id: str,
    session: dict,
    text: str
) -> bool:

    pending = session["pending_app"]

    stage = pending["stage"]

    if stage.startswith("need_profile_"):

        field = stage[len("need_profile_"):]

        if field == "email" and not EMAIL_RE.match(text):

            whatsapp_client.send_text(
                user_id,
                "That doesn't look like a valid email — try again."
            )

            return True

        db.update_user_profile(
            user_id,
            **{field: text}
        )

        _advance_apply_flow(user_id, session)

        return True

    if stage == "await_email_target":

        if not EMAIL_RE.match(text):

            whatsapp_client.send_text(
                user_id,
                "That doesn't look like a valid email — try again."
            )

            return True

        pending["apply_target"] = text

        _advance_apply_flow(user_id, session)

        return True

    if stage == "await_url_target":

        parsed = greenhouse_apply.parse_greenhouse_url(text)

        if not parsed:

            if text.strip().lower() == "skip":

                db.update_application(
                    pending["application_id"],
                    status="ready"
                )

                session.pop("pending_app", None)

                whatsapp_client.send_text(
                    user_id,
                    "Okay — marked as ready for manual application."
                )

                return True

            whatsapp_client.send_text(
                user_id,
                "That doesn't look like a Greenhouse job URL "
                "(expected something like boards.greenhouse.io/company/jobs/12345). "
                "Try again, or reply 'skip' to apply manually instead."
            )

            return True

        board_token, job_id = parsed

        details = greenhouse_apply.fetch_job_details(
            board_token,
            job_id
        )

        if not details:

            whatsapp_client.send_text(
                user_id,
                "Couldn't fetch that posting — double check the URL, "
                "or reply 'skip'."
            )

            return True

        pending["apply_target"] = text

        pending["greenhouse"] = {
            "board_token": board_token,
            "job_id": job_id,
            "details": details
        }

        db.update_application(
            pending["application_id"],
            job_title=details["title"] or "Untitled role",
            company=details["company"],
            job_url=details["url"]
        )

        _advance_apply_flow(user_id, session)

        return True

    return False


def _show_confirm(user_id: str, session: dict):

    pending = session["pending_app"]

    application = db.get_application(
        pending["application_id"]
    )

    user = db.get_user(user_id)

    if pending["channel"] == "email":

        summary = (
            f"Ready to email your application for "
            f"*{application['job_title']}* to "
            f"{pending['apply_target']}, from "
            f"{user['full_name']} <{user['email']}>.\n\n"
            "This actually sends the email. Confirm?"
        )

    else:

        gh = pending["greenhouse"]["details"]

        summary = (
            f"Ready to attempt auto-fill for "
            f"*{gh['title']}* at {gh['company']} "
            f"({pending['apply_target']}).\n\n"
            "⚠️ This is best-effort — postings with custom questions "
            "may not go through cleanly. "
            "I'll tell you either way. Confirm?"
        )

    pending["stage"] = "await_confirm"

    whatsapp_client.send_buttons(
        user_id,
        summary,
        [
            ("confirm_send", "✅ Confirm & send"),
            ("cancel_send", "❌ Cancel"),
        ]
    )


def _execute_application(user_id: str, session: dict):

    pending = session.pop("pending_app")

    application = db.get_application(
        pending["application_id"]
    )

    user = db.get_user(user_id)

    resume = (
        db.get_resume(application["resume_id"])
        if application["resume_id"]
        else None
    )

    resume_text = resume["content"] if resume else ""

    if pending["channel"] == "email":

        success, message = email_apply.send_application_email(

            to_email=pending["apply_target"],

            applicant_name=user["full_name"],

            job_title=application["job_title"],

            cover_letter=application["cover_letter"] or "",

            resume_text=resume_text,

        )

        db.update_application(

            pending["application_id"],

            status="applied" if success else "failed",

            apply_channel="email",

            apply_target=pending["apply_target"],

            notes=message,

        )

        whatsapp_client.send_text(
            user_id,
            ("✅ " if success else "❌ ") + message
        )

        return

    if pending["channel"] == "greenhouse":

        gh = pending["greenhouse"]

        success, message = greenhouse_apply.submit_application(

            board_token=gh["board_token"],
            job_id=gh["job_id"],

            full_name=user["full_name"],
            email=user["email"],
            phone=user["phone"],

            resume_text=resume_text,
            cover_letter=application["cover_letter"] or "",

        )

        db.update_application(

            pending["application_id"],

            status="applied" if success else "failed",

            apply_channel="greenhouse",

            apply_target=pending["apply_target"],

            notes=message,

        )

        fallback = (
            ""
            if success
            else f"\n\nYou can apply directly here: "
                 f"{gh['details']['url']}"
        )

        whatsapp_client.send_text(
            user_id,
            ("✅ " if success else "❌ ") + message + fallback
        )

        return


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True
    )