"""
Option 1: email-based applications.

The genuinely safe automation path — no ToS to violate, since it's just
sending an email on the user's behalf, the same as if they attached the
files in Gmail themselves. Requires SMTP_* to be set in .env.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_NAME


def is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_application_email(to_email: str, applicant_name: str, job_title: str,
                            cover_letter: str, resume_text: str) -> tuple[bool, str]:
    """Sends the cover letter as the email body and the tailored resume as a
    .txt attachment. Returns (success, message)."""
    if not is_configured():
        return False, "Email sending isn't configured (SMTP_* missing in .env)."

    msg = MIMEMultipart()
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = f"Application: {job_title} — {applicant_name}"
    msg.attach(MIMEText(cover_letter, "plain"))

    attachment = MIMEApplication(resume_text.encode("utf-8"), Name="resume.txt")
    attachment["Content-Disposition"] = 'attachment; filename="resume.txt"'
    msg.attach(attachment)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True, "Sent."
    except Exception as e:
        return False, f"Email send failed: {e}"