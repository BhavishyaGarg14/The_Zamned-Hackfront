import json
import logging
from datetime import date
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger(__name__)

OCR_PROMPT = """You are a financial OCR parser. Extract EVERY debit / withdrawal transaction from this bank or credit card statement PDF.

Return ONLY a valid JSON array of objects. Each object must have:
- "date": ISO date string "YYYY-MM-DD"
- "description": exact merchant / narration string as printed on the statement
- "amount": positive number (float) representing the debited amount

Rules:
1. Include ALL debit/withdrawal/purchase rows (including ₹0 trial authorizations if listed), NOT just subscriptions.
2. Exclude credits, refunds, deposits, opening/closing balances, and summary totals.
3. Clean multi-line wrapped descriptions into a single space-separated line.
4. If the document has no debit transactions, return []."""


def extract_debits_from_pdf(pdf_bytes: bytes) -> list[dict]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            OCR_PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )

    try:
        items = json.loads(response.text or "[]")
    except json.JSONDecodeError as exc:
        log.error("PDF OCR returned invalid JSON: %s", (response.text or "")[:500])
        raise ValueError("Could not parse transactions from the uploaded PDF.") from exc

    if isinstance(items, dict):
        items = next((v for v in items.values() if isinstance(v, list)), [])

    cleaned = []
    for row in items:
        if not isinstance(row, dict):
            continue
        raw_date = str(row.get("date") or "").strip()[:10]
        desc = " ".join(str(row.get("description") or "").split())
        try:
            date.fromisoformat(raw_date)
            amt = float(str(row.get("amount", 0)).replace(",", "").replace("₹", "").strip())
        except (ValueError, TypeError):
            continue
        if desc and amt >= 0:
            cleaned.append({"date": raw_date, "description": desc, "amount": amt})

    return cleaned
