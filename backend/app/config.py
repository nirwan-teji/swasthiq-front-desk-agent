"""
config.py — Environment configuration for the SwasthiQ agent backend.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the backend directory
load_dotenv(Path(__file__).parent.parent / ".env")

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Primary and retry models available in the current Groq console.
GROQ_MODEL_PRIMARY = "openai/gpt-oss-120b"
GROQ_MODEL_FAST = "openai/gpt-oss-20b"
# Gemini fallback model
GEMINI_MODEL = "gemini-2.0-flash"

# Path to clinic data (relative to repo root)
CLINIC_JSON_PATH = Path(__file__).resolve().parent.parent.parent / "clinic.json"

# LLM temperature — MUST be 0 for determinism
LLM_TEMPERATURE = 0.0

# Maximum tool call iterations before giving up
MAX_AGENT_ITERATIONS = 12
