"""
Step 1 — Form field extraction with per-field confidence.

Sends a photo of a filled-in medical order form to Claude's vision API,
along with the KNOWN field schema (so the model focuses on reading the
handwriting, not re-deriving the form's structure), and returns each field
with a value, a confidence level, and a needs_review flag.

Usage:
    python extract.py path/to/filled_form.jpg
"""

import os
import sys
import json
import base64
import re
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Sonnet reads messy handwriting better than Haiku. If this string 404s,
# check the Models page in the API console; Haiku ("claude-haiku-4-5-20251001")
# is a working fallback.
MODEL = "claude-sonnet-5"

# ---- The known template: we control this form, so we hardcode its schema. ----
# (v2 idea: let a user upload a blank form to auto-register an unknown template.)
EXPECTED_FIELDS = """
Text fields (read the handwriting):
  patient_first_name, patient_middle_name, patient_last_name
  dob_month, dob_day, dob_year
  phone_number, email
  street_address, street_address_line_2, city, state_province, zip_code
  icd10_code
  provider_first_name, provider_middle_name, provider_last_name
  provider_npi_number, date

Choice fields (report which option is marked, or null if none):
  gender            -> one of: Male, Female
  payment_method    -> one of: Primary Insurance, Medicare, Self Pay, Other
  payment_method_other_text -> handwritten text next to "Other", if any

Multi-select field (report a list of the checked options, or [] if none):
  test_type         -> any of: Test 1A, Test 1B, Test 2A, Test 2B
""".strip()

SYSTEM = (
    "You are a precise document data-extraction assistant. "
    "Return ONLY valid JSON, no prose or markdown. "
    "Never infer or auto-complete values that are not visibly written on the form."
)

PROMPT = f"""This image is a filled-in "Medical Order Form". Extract the values.

Here are the exact fields on this form:
{EXPECTED_FIELDS}

Return a JSON array. Each element is an object with:
  - "field": the field name from the list above
  - "value": your best reading (string, or a list for test_type), or null if blank/illegible
  - "confidence": "high" | "medium" | "low"
  - "needs_review": true if a human should verify this field, otherwise false
  - "note": a short reason when confidence is not high (e.g. "ambiguous 1 vs 7"), else ""

Rules:
Rules:
- BIAS TOWARD FLAGGING. This form is used in a medical context, where a missed
  error causes a patient outreach and a delay in care, while an unnecessary review
  costs only a few seconds. So it is far better to flag a correct field than to let
  an unclear one through unflagged. When in doubt, flag it.
- The key test: could a careful human plausibly read this field DIFFERENTLY than you
  did? If yes, set needs_review true (confidence "medium" or "low") and put the other
  plausible reading in "note" (e.g. "could be 1 or 7", "X falls between Male and Female").
  This applies even if you are fairly sure of your reading.
- Flag ambiguous marks specifically: a checkbox/radio mark placed between two options,
  a stray or partial mark, or more than one option marked, must be flagged.
- Only leave a field "high" confidence when the reading is genuinely unambiguous.
- Leave value null for empty fields; do not invent data.
- Return every field from the list, even blank ones.
Return only the JSON array."""


def media_type_for(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
    }.get(ext)


def encode_image(path):
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def parse_model_json(text):
    """Model *should* return clean JSON, but LLMs often add code fences,
    stray prose, or trailing commas. Strip those, then parse."""
    t = text.strip()

    # 1) strip ```json ... ``` fences if present
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
        t = t.strip()

    # 2) slice to the outermost [ ... ] in case of leading/trailing prose
    start, end = t.find("["), t.rfind("]")
    if start != -1 and end != -1:
        t = t[start:end + 1]

    # 3) remove trailing commas before } or ]  (the usual culprit)
    t = re.sub(r",(\s*[}\]])", r"\1", t)

    return json.loads(t)


def extract_fields(image_path):
    media = media_type_for(image_path)
    if media is None:
        raise ValueError(f"Unsupported image type: {image_path} (use jpg/png/webp)")

    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": media, "data": encode_image(image_path)}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )

    # Response may contain multiple blocks (e.g. a thinking block first);
    # grab text only from the actual text block(s), don't assume position.
    raw = "".join(block.text for block in message.content if block.type == "text")
    print("----- RAW MODEL OUTPUT -----")
    print(raw)
    print("----- END RAW -----")
    return parse_model_json(raw)


def display(results):
    review = []
    print("\n{:<28}{:<22}{:<10}".format("FIELD", "VALUE", "CONFIDENCE"))
    print("-" * 62)
    for f in results:
        val = f.get("value")
        val = "(blank)" if val in (None, "", []) else str(val)
        conf = f.get("confidence", "?")
        flag = "  <-- REVIEW" if f.get("needs_review") else ""
        print("{:<28}{:<22}{:<10}{}".format(
            f.get("field", "?")[:27], val[:21], conf, flag))
        if f.get("needs_review"):
            review.append(f)
    if review:
        print("\nFields needing human review:")
        for f in review:
            note = f.get("note") or "low confidence"
            print(f"  - {f.get('field')}: '{f.get('value')}'  ({note})")
    else:
        print("\nNo low-confidence fields flagged.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "form.jpg"
    if not os.path.exists(path):
        print(f"Image not found: {path}\nUsage: python extract.py path/to/form.jpg")
        sys.exit(1)
    print(f"Extracting from: {path}")
    results = extract_fields(path)
    display(results)