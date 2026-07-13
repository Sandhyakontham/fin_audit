# 🔍 FinAudit AI — Transaction Forensic Dashboard

FinAudit AI is a lightweight fraud-review tool that scores bank transactions using an LLM acting as a "Senior Payment Auditor." Rather than letting the model guess, each transaction is paired with **computed facts** — the customer's spending baseline and their most recent prior transaction — so the LLM's risk score and narrative are grounded in real signals like geographic velocity, MCC/category mismatches, and duplicate charges.

Runs entirely for free with a local **Ollama** model, or can be pointed at the **Gemini API** for cloud inference.

---

## Features

- **Grounded LLM analysis** — every prompt includes the customer's home city/country, typical spend, typical category, and their last transaction, so the model isn't scoring in a vacuum.
- **Three detection patterns built in**: duplicate/replay charges, geographic velocity anomalies, and MCC/category-vs-amount mismatches.
- **Structured, parseable output** — risk score (0–100), short flag list, and a plain-English narrative per transaction, with graceful fallback if the model returns malformed JSON.
- **Pluggable backend** — swap between free local inference (Ollama) and cloud inference (Gemini) with one environment variable, no code changes.
- **Interactive Streamlit dashboard** — generate synthetic test data or upload your own CSV, run the audit, and browse flagged transactions.
- **Synthetic data generator** — produces a realistic transaction log with injected anomalies so you can test immediately without real data.

---

## Project structure

| File | Purpose |
|---|---|
| `dashboard.py` | Streamlit UI — load/generate data, run analysis, view results |
| `fraud_agent.py` | Core logic: builds customer baselines, constructs prompts, calls the LLM, parses results |
| `llm_backend.py` | Dispatches chat calls to either Ollama (local) or Gemini (cloud) |
| `config.py` | Backend toggle, model names, file paths, risk threshold, transaction cap |
| `generate_data.py` | Creates `transactions.csv` with synthetic transactions + 3 injected fraud patterns |
| `transactions.csv` | Sample/generated transaction data |
| `requirements.txt` | Python dependencies |

---

## How it works

1. **`generate_data.py`** creates a transaction log for 5 customers with normal spending histories, plus three deliberately injected anomalies:
   - **Duplicate/replay** — same customer, amount, and merchant, ~18 seconds apart.
   - **Geographic velocity** — a transaction at home followed 40 minutes later by one in a distant country.
   - **MCC mismatch** — a $4,500 charge at a grocery store, wildly outside the category's normal ticket size.

2. **`fraud_agent.py`** groups transactions by customer, computes each customer's baseline (home city/country, average spend, typical category via `groupby`/`mode`), and walks through transactions in timestamp order, tracking each customer's most recent prior transaction.

3. For every transaction, it builds a prompt containing the transaction itself, the baseline, and the prior transaction, and sends it to the LLM via **`llm_backend.py`** with a system prompt instructing the model to act as a fraud auditor, reason only from the given facts, and return strict JSON:
   ```json
   {
     "risk_score": 85,
     "flags": ["Geographic velocity anomaly"],
     "narrative": "This customer transacted in Tampa and then Lagos within 40 minutes, which is not physically plausible and should be reviewed."
   }
   ```

4. Results are compiled into a DataFrame and written to `flagged_transactions.csv`. Anything scoring at or above `RISK_THRESHOLD` (default 60) is surfaced as "flagged" in the dashboard.

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` includes `pandas` and `streamlit` always, plus `ollama` for local mode and `google-genai` for Gemini mode — install whichever backend you plan to use (or both).

### 2. Choose a backend

**Option A — Local (default, free, no API key)**

Install and run [Ollama](https://ollama.com), then pull the model used by this project:

```bash
ollama pull llama3.1
```

No environment variables needed — `config.py` defaults to local mode.

**Option B — Gemini API (cloud)**

Get a free key from [Google AI Studio](https://aistudio.google.com/apikey), then set:

```powershell
[System.Environment]::SetEnvironmentVariable("LLM_BACKEND", "gemini", "User")
[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "your_key", "User")
```

(On macOS/Linux, use `export LLM_BACKEND=gemini` and `export GEMINI_API_KEY=your_key` instead, e.g. in your `.bashrc`/`.zshrc`.)

> **Note on Gemini quotas:** the project uses the `gemini-flash-latest` alias, which Google keeps pointed at its current flash-tier model. New accounts on the model it currently resolves to may have a small free-tier quota (as low as 20 requests/day) — enough to test a few transactions but not a full 40-transaction batch. Use `MAX_TRANSACTIONS` in `config.py` to cap a run (e.g. `15`) while testing, switch back to local mode for unlimited runs, or wait for the daily quota reset (midnight Pacific time).

### 3. Generate or supply transaction data

```bash
python generate_data.py
```

This writes `transactions.csv`. Alternatively, supply your own CSV with these columns:

```
transaction_id, customer_id, timestamp, amount, merchant_name, mcc_category, city, country
```

---

## Usage

### Run the dashboard (recommended)

```bash
streamlit run dashboard.py
```

- **Step 1:** Click "Generate sample transactions" or upload your own CSV.
- **Step 2:** Click "Run fraud analysis" — this calls the LLM once per transaction.
- **Step 3:** Review flagged transactions (risk score ≥ threshold), each with its score, narrative, and any flags. Expand "View all scored transactions" to see the full result set in a table.

### Run from the command line

```bash
python generate_data.py   # once, to create transactions.csv
python fraud_agent.py     # analyze and print flagged transactions
```

Results are written to `flagged_transactions.csv`, and a summary of flagged transactions is printed to the console.

---

## Configuration reference (`config.py`)

| Setting | Default | Description |
|---|---|---|
| `LLM_BACKEND` | `"local"` | `"local"` (Ollama) or `"gemini"` (Gemini API); set via `LLM_BACKEND` env var |
| `OLLAMA_MODEL` | `"llama3.1"` | Local model name |
| `GEMINI_API_KEY` | `""` | Required if `LLM_BACKEND="gemini"`; set via `GEMINI_API_KEY` env var |
| `GEMINI_MODEL` | `"gemini-flash-latest"` | Auto-updating Gemini alias |
| `TRANSACTIONS_FILE` | `"transactions.csv"` | Input transaction log |
| `RESULTS_FILE` | `"flagged_transactions.csv"` | Output scored results |
| `RISK_THRESHOLD` | `60` | Score at/above which a transaction is treated as "flagged" |
| `MAX_TRANSACTIONS` | `None` | Cap on rows analyzed per run (useful for quota-limited testing); `None` = analyze all |

---

## Detection logic

The system prompt instructs the LLM to check specifically for:

1. **Velocity anomalies** — a large distance/city change in a short time window.
2. **MCC/merchant category mismatch** — an unusually high amount for the stated category.
3. **Duplicate/replay** — same amount and merchant as the immediately prior transaction, seconds apart.

The model is instructed to score normal, baseline-consistent transactions low (below 20, empty flags) rather than manufacturing suspicion, and to frame any finding as "flagged for review" rather than a certain fraud determination — the final call is left to a human investigator.

---

## Notes & limitations

- This is a **decision-support tool**, not an automated fraud-blocking system. Every flagged transaction is meant for human review.
- The dashboard calls the LLM once per transaction, so analysis time scales linearly with the number of rows — expect local (Ollama) runs to be slower than Gemini, and Gemini runs to be quota-limited on free-tier accounts.
- If the LLM returns output that isn't valid JSON, `fraud_agent.py` doesn't silently drop the transaction — it returns a `risk_score` of `-1` with a `PARSE_ERROR` flag and the raw response, so parse failures stay visible instead of disappearing from results.
- Synthetic data is generated with a fixed random seed (`42`), so re-running `generate_data.py` produces the same dataset each time.

---

## Requirements

- Python 3.9+
- `pandas`, `streamlit`
- `ollama` (for local mode) — plus the [Ollama](https://ollama.com) application installed and running
- `google-genai` (for Gemini mode) — plus a free API key from [Google AI Studio](https://aistudio.google.com/apikey)
