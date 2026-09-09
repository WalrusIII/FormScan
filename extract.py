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
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MAX_IMAGE_MB = 10   # reject files larger than this (cost/abuse guard)

# Sonnet reads messy handwriting better than Haiku. If this string 404s,
# check the Models page in the API console; Haiku ("claude-haiku-4-5-20251001")
# is a working fallback.
MODEL = "claude-sonnet-5"

# We control this form, so we hand the model its exact field list instead of
# making it re-derive the layout from every photo. Giving it the "template" up
# front means it spends its effort reading handwriting, not guessing structure
# — which is both more accurate and cheaper.
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

# The system prompt sets the model's role and its hardest guardrail: never
# invent data. The tool schema (below) enforces output format, so the prompt only concerns judgment.
SYSTEM = (
    "You are a precise document data-extraction assistant. "
    "Return ONLY valid JSON, no prose or markdown. "
    "Never infer or auto-complete values that are not visibly written on the form."
)

# The prompt handles JUDGMENT only, what to extract and how to rate confidence.
# The bias-toward-flagging rule is a deliberate domain choice: in a
# medical context a missed error costs a patient outreach and a care delay, while
# an extra review costs seconds, so the two error types are not equal, and we
# tune toward over-flagging on purpose.
PROMPT = f"""This image is a filled-in "Medical Order Form". Extract the values.

Here are the exact fields on this form:
{EXPECTED_FIELDS}


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
- Return every field from the list, even blank ones."""


# This tool is the enforced output contract. Rather than asking for JSON as free
# text and hoping it parses, we hand the API a schema and force the model to call
# this tool, so the response comes back already structured and validated. That is
# what eliminated the intermittent JSON parse failures (trailing commas, truncation).
EXTRACTION_TOOL = {
    "name": "record_form_fields",
    "description": "Record every extracted field from the medical order form, "
                   "with a per-field confidence and review flag.",
    "input_schema": {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "description": "One object per field on the form.",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {
                            "type": "string",
                            "description": "The field name from the schema."
                        },
                        "value": {
                            "type": ["string", "array", "null"],
                            "description": "Best reading; a list for test_type; null if blank/illegible."
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"]
                        },
                        "needs_review": {"type": "boolean"},
                        "note": {
                            "type": "string",
                            "description": "Short reason when confidence is not high; else empty."
                        }
                    },
                    "required": ["field", "value", "confidence", "needs_review", "note"]
                }
            }
        },
        "required": ["fields"]
    }
}


# The API needs the image's MIME type declared explicitly; we infer it from
    # the file extension. An unknown extension returns None, which the caller
    # treats as "unsupported" rather than sending a bad request.
def media_type_for(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
    }.get(ext)


# The vision API accepts image bytes as a base64 string inside the message,
    # so we read the file and encode it here.
def encode_image_bytes(image_bytes):
    # Encode raw image bytes (from a file OR an upload) as base64 for the API.
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def extract_from_bytes(image_bytes, media_type):
    """Core extraction: works with raw image bytes from any source."""
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_form_fields"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": media_type,
                    "data": encode_image_bytes(image_bytes)}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )

    # A response can contain several blocks (e.g. a thinking block before the
        # answer), so we find the tool_use block by TYPE rather than assuming it's
        # first. Its .input is already a parsed, schema-validated dict; no JSON
        # string to clean up. The raise is a safety net if no tool call comes back.
    for block in message.content:
        if block.type == "tool_use":
            return block.input["fields"]
    raise ValueError("Model did not return a tool call")



def extract_fields(image_path):
    """CLI entry point: read a file from disk, then extract from its bytes."""
    media = media_type_for(image_path)
    if media is None:
        raise ValueError(f"Unsupported image type: {image_path} (use jpg/png/webp)")

    # Size guard: reject oversized files before doing any work. Protects against
    # runaway API cost and denial-of-service via huge uploads.
    size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if size_mb > MAX_IMAGE_MB:
        raise ValueError(f"Image is {size_mb:.1f} MB, over the {MAX_IMAGE_MB} MB limit.")

    with open(image_path, "rb") as f:
        return extract_from_bytes(f.read(), media)



def display(results):
    review = []
    print("\n{:<28}{:<22}{:<10}".format("FIELD", "VALUE", "CONFIDENCE"))
    print("-" * 62)
    for f in results:
        # Normalize the three "empty" shapes (None, "", []) to one label so an
        # unchecked multi-select reads the same as a blank text box.
        val = f.get("value")
        val = "(blank)" if val in (None, "", []) else str(val)
        conf = f.get("confidence", "?")
        flag = "  <-- REVIEW" if f.get("needs_review") else ""
        # Values are truncated only to keep the table columns aligned in the
        # terminal. The full value is still in the review summary below.
        print("{:<28}{:<22}{:<10}{}".format(
            f.get("field", "?")[:27], val[:21], conf, flag))
        if f.get("needs_review"):
            review.append(f)

    # The review summary is the actual product of the tool: the short list a
    # human should confirm, each with the model's reason for doubting it.
    if review:
        print("\nFields needing human review:")
        for f in review:
            note = f.get("note") or "low confidence"
            print(f"  - {f.get('field')}: '{f.get('value')}'  ({note})")
    else:
        print("\nNo low-confidence fields flagged.")


if __name__ == "__main__":
    # Take the image path from the command line; fall back to a default name.
    path = sys.argv[1] if len(sys.argv) > 1 else "form.jpg"
    if not os.path.exists(path):
        print(f"Image not found: {path}\nUsage: python extract.py path/to/form.jpg")
        sys.exit(1)
    print(f"Extracting from: {path}")
    results = extract_fields(path)
    display(results)