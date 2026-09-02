"""
Thin wrapper around Meta's WhatsApp Cloud API (Graph API).
"""
import httpx
from config import WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, GRAPH_API_VERSION

BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
AUTH_HEADERS = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
MAX_MESSAGE_CHARS = 4000


def send_text(to: str, body: str):
    """Splits into multiple messages if longer than WhatsApp's limit."""
    chunks = [body[i:i + MAX_MESSAGE_CHARS] for i in range(0, len(body), MAX_MESSAGE_CHARS)] or [""]
    url = f"{BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    for chunk in chunks:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": chunk, "preview_url": False},
        }
        resp = httpx.post(url, headers=AUTH_HEADERS, json=payload, timeout=30)
        if resp.status_code >= 400:
            print(f"[whatsapp_client] send_text failed: {resp.status_code} {resp.text}")


def send_buttons(to: str, body: str, buttons: list[tuple[str, str]]):
    """
    buttons: list of (id, title). Max 3, title max 20 chars (WhatsApp limit).
    Renders as tappable buttons; the tap comes back as an 'interactive'
    webhook message with interactive.button_reply.id.
    """
    url = f"{BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body[:1024]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": bid, "title": title[:20]}}
                    for bid, title in buttons[:3]
                ]
            },
        },
    }
    resp = httpx.post(url, headers=AUTH_HEADERS, json=payload, timeout=30)
    if resp.status_code >= 400:
        print(f"[whatsapp_client] send_buttons failed: {resp.status_code} {resp.text}")


def get_media_url(media_id: str) -> str | None:
    resp = httpx.get(f"{BASE_URL}/{media_id}", headers=AUTH_HEADERS, timeout=15)
    if resp.status_code >= 400:
        print(f"[whatsapp_client] get_media_url failed: {resp.status_code} {resp.text}")
        return None
    return resp.json().get("url")


def download_media(media_url: str) -> bytes:
    resp = httpx.get(media_url, headers=AUTH_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content