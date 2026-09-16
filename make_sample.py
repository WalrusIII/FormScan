"""
One-time helper: run extraction on a sample form and save the result to
sample_result.json, so demo mode can show real output without an API call.
Run locally (needs your .env key): python make_sample.py
"""

import json
from extract import extract_fields

SAMPLE_IMAGE = "test_order_form2.jpg"   # the messy one — shows off the flagging
OUTPUT = "sample_result.json"

results = extract_fields(SAMPLE_IMAGE)

with open(OUTPUT, "w") as f:
    json.dump(results, f, indent=2)

print(f"Saved {len(results)} fields to {OUTPUT}")