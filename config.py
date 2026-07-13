"""
config.py
Toggle between free local mode (Ollama) and cloud mode (Gemini API) --
same pattern as the Med-Context AI project.

Switch with (PowerShell):
    [System.Environment]::SetEnvironmentVariable("LLM_BACKEND", "gemini", "User")
    [System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "your_key", "User")

Leave unset to default to local/Ollama -- no key needed, just slower.
"""

import os

LLM_BACKEND = os.environ.get("LLM_BACKEND", "local").lower()

# --- Local (Ollama) settings ---
OLLAMA_MODEL = "llama3.1"

# --- Gemini API settings ---
# NOTE: Google's model lineup is currently in heavy flux (mid-2026) --
# several models (2.5-flash, 2.5-flash-lite) are being phased out and are
# already blocked for NEW accounts specifically, even though they still
# work for older accounts. "gemini-flash-latest" is the safest bet: it's
# an auto-updating alias that Google keeps pointed at whatever current
# model your account actually has access to. Tradeoff: the model it
# currently resolves to (gemini-3.5-flash) has a small free-tier quota for
# new accounts (as low as 20 requests/day) -- fine for testing a handful
# of transactions, but you'll hit the wall on a full 40-transaction batch.
# For bulk runs, either switch LLM_BACKEND=local (unlimited, just slower),
# or wait for the daily quota reset (midnight Pacific time).
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-flash-latest"

# --- Data settings ---
TRANSACTIONS_FILE = "transactions.csv"
RESULTS_FILE = "flagged_transactions.csv"
RISK_THRESHOLD = 60  # transactions scoring at/above this are "flagged" in the dashboard

# Cap how many transactions fraud_agent.py analyzes in one run -- useful for
# testing against a tight free-tier quota (e.g. set to 15 to comfortably
# stay under a 20/day limit while confirming everything works, then raise
# it once you're on local mode or a higher quota).
MAX_TRANSACTIONS = None  # None = analyze all rows


def describe():
    if LLM_BACKEND == "gemini":
        key_status = "SET" if GEMINI_API_KEY else "MISSING (required for Gemini mode!)"
        return f"Backend: Gemini API ({GEMINI_MODEL}) | API key: {key_status}"
    return f"Backend: Local Ollama ({OLLAMA_MODEL})"