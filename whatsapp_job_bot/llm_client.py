"""
Single shared NVIDIA NIM client (via langchain-nvidia-ai-endpoints) +
helpers so nodes don't each reinvent prompt plumbing.
"""
import json
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from config import NVIDIA_API_KEY, NVIDIA_MODEL

client = ChatNVIDIA(
    model=NVIDIA_MODEL,
    api_key=NVIDIA_API_KEY,
    temperature=0.7,
    max_completion_tokens=4096,
)


def ask(system: str, user: str, max_tokens: int = 1500) -> str:
    """Plain text completion."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    response = client.bind(max_completion_tokens=max_tokens).invoke(messages)
    return response.content


def ask_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """
    Completion where we force JSON-only output. We tell the model explicitly
    not to wrap in markdown fences, then defensively strip fences anyway.
    """
    strict_system = system + "\n\nRespond with ONLY valid JSON. No markdown, no preamble."
    raw = ask(strict_system, user, max_tokens=max_tokens)
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)