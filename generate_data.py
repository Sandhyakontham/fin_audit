"""
generate_data.py
Creates a synthetic transaction log with a handful of deliberately injected
fraud patterns, so you have something realistic to test fraud_agent.py
against without needing real (or even real-looking) bank data.

Injected anomaly types (matches the FinAudit AI spec's test cases):
  - Duplicate/replay: same customer, same amount & merchant, seconds apart.
  - Geographic velocity: same customer transacts in two distant cities
    within an implausibly short window.
  - MCC mismatch: an unusually high ticket value for a normally low-ticket
    merchant category (e.g. a $4,500 charge at a grocery store).

Run:
    python generate_data.py
Produces:
    transactions.csv
"""

import csv
import random
from datetime import datetime, timedelta

import config

random.seed(42)

CUSTOMERS = [
    {"id": "CUST001", "home_city": "Tampa",     "home_country": "USA", "typical_category": "Groceries",  "typical_amount": (30, 150)},
    {"id": "CUST002", "home_city": "Chicago",    "home_country": "USA", "typical_category": "Dining",     "typical_amount": (20, 90)},
    {"id": "CUST003", "home_city": "Austin",     "home_country": "USA", "typical_category": "Fuel",       "typical_amount": (25, 80)},
    {"id": "CUST004", "home_city": "Seattle",    "home_country": "USA", "typical_category": "Retail",     "typical_amount": (40, 200)},
    {"id": "CUST005", "home_city": "Denver",     "home_country": "USA", "typical_category": "Groceries",  "typical_amount": (30, 150)},
]

MERCHANTS = {
    "Groceries": ["Fresh Mart", "Corner Grocer", "SavMore Foods"],
    "Dining": ["Bistro 12", "Corner Diner", "Taco Stand"],
    "Fuel": ["QuickFuel Station", "Highway Gas Co"],
    "Retail": ["Metro Department Store", "Value Retail"],
    "Jewelry": ["Prestige Jewelers", "Luxury Timepiece Co"],
}

FAR_CITIES = [("London", "UK"), ("Lagos", "Nigeria"), ("Manila", "Philippines")]


def random_timestamp(base_day_offset):
    base = datetime(2026, 6, 1) + timedelta(days=base_day_offset)
    return base + timedelta(hours=random.randint(8, 20), minutes=random.randint(0, 59))


def make_normal_transaction(tx_id, customer, day_offset):
    lo, hi = customer["typical_amount"]
    merchant = random.choice(MERCHANTS[customer["typical_category"]])
    return {
        "transaction_id": f"TXN{tx_id:04d}",
        "customer_id": customer["id"],
        "timestamp": random_timestamp(day_offset).isoformat(),
        "amount": round(random.uniform(lo, hi), 2),
        "merchant_name": merchant,
        "mcc_category": customer["typical_category"],
        "city": customer["home_city"],
        "country": customer["home_country"],
    }


def main():
    rows = []
    tx_id = 1

    # Normal transaction history: 6 transactions per customer, spread over ~2 weeks
    for customer in CUSTOMERS:
        for day in range(0, 14, 2):
            rows.append(make_normal_transaction(tx_id, customer, day))
            tx_id += 1

    # --- Inject anomaly 1: duplicate/replay attack (CUST001) ---
    original = make_normal_transaction(tx_id, CUSTOMERS[0], 15)
    rows.append(original)
    tx_id += 1
    duplicate = dict(original)
    duplicate["transaction_id"] = f"TXN{tx_id:04d}"
    dup_time = datetime.fromisoformat(original["timestamp"]) + timedelta(seconds=18)
    duplicate["timestamp"] = dup_time.isoformat()
    rows.append(duplicate)
    tx_id += 1

    # --- Inject anomaly 2: geographic velocity (CUST002) ---
    home_txn = make_normal_transaction(tx_id, CUSTOMERS[1], 16)
    rows.append(home_txn)
    tx_id += 1
    far_city, far_country = random.choice(FAR_CITIES)
    velocity_txn = {
        "transaction_id": f"TXN{tx_id:04d}",
        "customer_id": CUSTOMERS[1]["id"],
        "timestamp": (datetime.fromisoformat(home_txn["timestamp"]) + timedelta(minutes=40)).isoformat(),
        "amount": round(random.uniform(60, 200), 2),
        "merchant_name": random.choice(MERCHANTS["Dining"]),
        "mcc_category": "Dining",
        "city": far_city,
        "country": far_country,
    }
    rows.append(velocity_txn)
    tx_id += 1

    # --- Inject anomaly 3: MCC mismatch -- huge ticket at a low-limit category (CUST005) ---
    mismatch_txn = {
        "transaction_id": f"TXN{tx_id:04d}",
        "customer_id": CUSTOMERS[4]["id"],
        "timestamp": random_timestamp(17).isoformat(),
        "amount": 4500.00,
        "merchant_name": random.choice(MERCHANTS["Groceries"]),
        "mcc_category": "Groceries",
        "city": CUSTOMERS[4]["home_city"],
        "country": CUSTOMERS[4]["home_country"],
    }
    rows.append(mismatch_txn)
    tx_id += 1

    rows.sort(key=lambda r: r["timestamp"])

    with open(config.TRANSACTIONS_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} transactions -> {config.TRANSACTIONS_FILE}")
    print("Includes 3 injected anomalies: duplicate charge, geographic velocity, MCC mismatch.")


if __name__ == "__main__":
    main()
