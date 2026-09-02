"""
Central config. Loads from .env so nothing sensitive is hardcoded.
Copy .env.example to .env and fill in your real values before running.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- WhatsApp Cloud API (Meta) ---
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
WHATSAPP_PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
WHATSAPP_VERIFY_TOKEN = os.environ["WHATSAPP_VERIFY_TOKEN"]
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v20.0")

# --- LLM (NVIDIA NIM via langchain-nvidia-ai-endpoints) ---
NVIDIA_API_KEY = os.environ["NVIDIA_API_KEY"]
NVIDIA_MODEL = "moonshotai/kimi-k3"

# --- Job search ---
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

# --- Email-based applications (SMTP) ---
# Gmail: use an "app password", not your real password. smtp.gmail.com, port 587.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Job Application")

DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_data.db")