"""
fraud_agent.py
For each transaction, computes the customer's baseline (typical city, typical
spend) and compares the current transaction against it and against their most
recent prior transaction (for duplicate/velocity checks) -- then asks the LLM
to act as a Senior Payment Auditor and return a risk score + plain-English
narrative, grounded in those computed facts (not left to guess).

Run:
    python generate_data.py   (once, to create transactions.csv)
    python fraud_agent.py
"""

import json
import re

import pandas as pd

import config
import llm_backend

SYSTEM_PROMPT = """You are a Senior Payment Auditor reviewing transactions for a bank's
fraud investigation team. For each transaction you are given the transaction itself,
the customer's typical (baseline) spending pattern, and their most recent prior
transaction.

RULES:
1. Base your assessment ONLY on the facts provided. Do not invent details.
2. Check specifically for:
   - Velocity anomalies: a large distance/city change in a short time window.
   - MCC / merchant category mismatch: an unusually high amount for the
     stated category (e.g. thousands of dollars at a grocery store).
   - Duplicate / replay: same amount and merchant as the immediately prior
     transaction, seconds apart.
3. Respond with ONLY a JSON object, no other text, no markdown fences:
   {
     "risk_score": <integer 0-100>,
     "flags": [<short strings, e.g. "Geographic velocity anomaly">],
     "narrative": "<one or two plain-English sentences a non-technical
                    investigator can act on, explaining WHY this is or
                    isn't suspicious>"
   }
4. A transaction consistent with the customer's normal pattern should score
   low (below 20) with an empty flags list -- don't manufacture suspicion
   where the facts don't support it.
5. Never state fraud as certain. Frame findings as "flagged for review" --
   final determination is a human decision, not this model's.
"""


def build_customer_baselines(df):
    baselines = {}
    for customer_id, group in df.groupby("customer_id"):
        baselines[customer_id] = {
            "home_city": group["city"].mode().iloc[0],
            "home_country": group["country"].mode().iloc[0],
            "avg_amount": round(group["amount"].mean(), 2),
            "typical_category": group["mcc_category"].mode().iloc[0],
        }
    return baselines


def build_prompt(row, prev_row, baseline):
    time_since_prev = "N/A (first known transaction for this customer)"
    prev_block = "None -- this is the earliest known transaction for this customer."
    if prev_row is not None:
        delta = row["timestamp"] - prev_row["timestamp"]
        time_since_prev = str(delta)
        prev_block = (
            f'{prev_row["amount"]} at {prev_row["merchant_name"]} '
            f'({prev_row["city"]}, {prev_row["country"]}), '
            f'{prev_row["timestamp"]}'
        )

    return f"""TRANSACTION UNDER REVIEW:
- ID: {row["transaction_id"]}
- Customer: {row["customer_id"]}
- Amount: ${row["amount"]}
- Merchant: {row["merchant_name"]} (category: {row["mcc_category"]})
- Location: {row["city"]}, {row["country"]}
- Time: {row["timestamp"]}

CUSTOMER BASELINE (typical pattern):
- Home city: {baseline["home_city"]}, {baseline["home_country"]}
- Typical spend: ${baseline["avg_amount"]}
- Typical category: {baseline["typical_category"]}

MOST RECENT PRIOR TRANSACTION:
- {prev_block}
- Time since prior transaction: {time_since_prev}
"""


def parse_llm_json(raw_text):
    """Strips markdown code fences if present, then parses JSON. Falls back
    to a clearly-marked error result if the model didn't return valid JSON,
    rather than silently dropping the transaction."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
    try:
        result = json.loads(cleaned)
        result["risk_score"] = max(0, min(100, int(result.get("risk_score", 0))))
        result.setdefault("flags", [])
        result.setdefault("narrative", "")
        return result
    except (json.JSONDecodeError, ValueError, TypeError):
        return {
            "risk_score": -1,
            "flags": ["PARSE_ERROR"],
            "narrative": f"Could not parse model output. Raw response: {raw_text[:200]}",
        }


def analyze_transactions(df):
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["customer_id", "timestamp"]).reset_index(drop=True)

    baselines = build_customer_baselines(df)

    results = []
    last_seen = {}  # customer_id -> previous row

    for _, row in df.iterrows():
        prev_row = last_seen.get(row["customer_id"])
        baseline = baselines[row["customer_id"]]

        prompt = build_prompt(row, prev_row, baseline)
        raw = llm_backend.chat(SYSTEM_PROMPT, prompt)
        parsed = parse_llm_json(raw)

        results.append({
            "transaction_id": row["transaction_id"],
            "customer_id": row["customer_id"],
            "amount": row["amount"],
            "merchant_name": row["merchant_name"],
            "city": row["city"],
            "country": row["country"],
            "timestamp": row["timestamp"],
            "risk_score": parsed["risk_score"],
            "flags": "; ".join(parsed["flags"]),
            "narrative": parsed["narrative"],
        })

        last_seen[row["customer_id"]] = row

    return pd.DataFrame(results)


def main():
    print(config.describe())
    try:
        df = pd.read_csv(config.TRANSACTIONS_FILE)
    except FileNotFoundError:
        print(f"'{config.TRANSACTIONS_FILE}' not found. Run generate_data.py first.")
        return

    print(f"Analyzing {len(df)} transactions...")
    results = analyze_transactions(df)
    results.to_csv(config.RESULTS_FILE, index=False)

    flagged = results[results["risk_score"] >= config.RISK_THRESHOLD]
    print(f"\nDone. Wrote {len(results)} results to '{config.RESULTS_FILE}'.")
    print(f"{len(flagged)} transaction(s) flagged at risk score >= {config.RISK_THRESHOLD}:\n")
    for _, r in flagged.iterrows():
        print(f"  [{r['risk_score']}] {r['transaction_id']} ({r['customer_id']}) -- {r['narrative']}")


if __name__ == "__main__":
    main()
