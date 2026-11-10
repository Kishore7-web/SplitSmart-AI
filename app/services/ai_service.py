import base64
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
import httpx

from app.core.config import settings
from app.database.models import Group, Member, Expense, Settlement, ExpenseEvidence
from app.services.settlement_engine import calculate_member_balances


CATEGORIES = [
    "Food & Dining",
    "Transportation",
    "Fuel",
    "Accommodation",
    "Shopping",
    "Tickets & Events",
    "Bills & Utilities",
    "General"
]


def is_gemini_configured() -> bool:
    """Check if a Gemini API key is configured and not default placeholder."""
    return bool(
        settings.gemini_api_key
        and settings.gemini_api_key.strip()
        and settings.gemini_api_key != "your_gemini_api_key_here"
    )


# ---------------------------------------------------------------------------
# 1. Natural Language Expense Parser (Gemini + Rule-based Fallback)
# ---------------------------------------------------------------------------

def parse_expense_with_ai(
    text: str,
    member_names: list[str],
    current_user_name: str | None = None
) -> dict[str, Any]:
    """
    Parse a natural language expense description using Gemini API,
    with a deterministic fallback parser if API is unconfigured or offline.
    """
    if not text or not text.strip():
        raise ValueError("Expense description text cannot be empty.")

    if not member_names:
        raise ValueError("Group has no members. Add members to the group first.")

    # Try Gemini API if configured
    if is_gemini_configured():
        try:
            return _call_gemini_parse(text, member_names, current_user_name)
        except Exception as e:
            print(f"Gemini API call failed ({e}), falling back to heuristic parser.")

    # Heuristic / Rule-based parser fallback
    return _rule_based_parse_expense(text, member_names, current_user_name)


def _call_gemini_parse(
    text: str,
    member_names: list[str],
    current_user_name: str | None
) -> dict[str, Any]:
    prompt = f"""
You are an expert expense parser for SplitSmart AI 2.0 ("The Financial Memory of a Group").
Extract structured expense information from the user sentence.

Available Group Members:
{json.dumps(member_names)}

Current Logged-in / Active Member (if sentence says "I", "me", "myself"):
{json.dumps(current_user_name or member_names[0])}

Allowed Categories:
{json.dumps(CATEGORIES)}

User Sentence:
"{text}"

Return ONLY valid JSON matching this exact schema:
{{
    "description": "Short description of expense",
    "amount_rupees": "1500.00",
    "payer_name": "Name from Available Group Members, or null if unclear",
    "participants": ["Name1", "Name2"],
    "split_type": "equal",
    "category": "Food & Dining",
    "merchant": "Merchant name or null",
    "confidence": 0.95,
    "missing_fields": [],
    "clarification_prompt": null
}}

Rules:
1. "amount_rupees" must be a positive decimal string (e.g. "800.00").
2. "payer_name" must be one of the Available Group Members. If user says "I paid", use the Current Logged-in Member.
3. If payer cannot be determined, set "payer_name": null, add "payer" to "missing_fields", and ask for clarification.
4. "participants" must only contain names from Available Group Members. If sentence says "we" or doesn't restrict participants, include all Available Group Members.
5. "split_type" can be "equal" or "custom". Default to "equal".
6. "category" must be one of the Allowed Categories.
7. Return ONLY the JSON object, nothing else.
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"

    response = httpx.post(
        url,
        params={"key": settings.gemini_api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        },
        timeout=httpx.Timeout(15.0, connect=2.0)
    )
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini returned no candidates.")

    raw_text = candidates[0]["content"]["parts"][0]["text"]
    parsed = json.loads(raw_text)

    # Sanitize and validate
    return _validate_and_normalize_parsed_expense(parsed, member_names, current_user_name)


def _rule_based_parse_expense(
    text: str,
    member_names: list[str],
    current_user_name: str | None
) -> dict[str, Any]:
    """Reliable deterministic extraction for offline or API-free testing."""
    text_lower = text.lower()

    # 1. Amount Extraction
    # Match patterns like: ₹1500, 1500 rs, rs 1500, 1,500 rupees, 1500.50
    amount_rupees = None
    amt_match = re.search(
        r'(?:(?:₹|rs\.?|inr)\s*(\d+(?:,\d+)*(?:\.\d{1,2})?)|(\d+(?:,\d+)*(?:\.\d{1,2})?)\s*(?:₹|rs\.?|rupees?|inr|bucks)?)',
        text,
        re.IGNORECASE
    )
    if amt_match:
        val = amt_match.group(1) or amt_match.group(2)
        if val:
            try:
                cleaned = float(val.replace(",", ""))
                if cleaned > 0:
                    amount_rupees = f"{cleaned:.2f}"
            except ValueError:
                pass

    if not amount_rupees:
        # Fallback search for any isolated number
        num_match = re.search(r'\b(\d+(?:\.\d{1,2})?)\b', text)
        if num_match:
            amount_rupees = f"{float(num_match.group(1)):.2f}"
        else:
            amount_rupees = "0.00"

    # 2. Payer Detection
    payer = None
    missing_fields = []

    # Check for "I paid", "paid by me", "myself"
    if re.search(r'\b(i|me|myself)\s+paid\b|\bpaid\s+by\s+(me|myself)\b', text_lower):
        payer = current_user_name or member_names[0]
    else:
        # Check against member names
        for name in member_names:
            if re.search(rf'\b{re.escape(name.lower())}\b', text_lower):
                payer = name
                break

    if not payer:
        if len(member_names) == 1:
            payer = member_names[0]
        else:
            missing_fields.append("payer")

    # 3. Participants
    participants = []
    # If specific members mentioned after "between", "among", "split with", "for"
    for name in member_names:
        if re.search(rf'\b{re.escape(name.lower())}\b', text_lower):
            if name not in participants:
                participants.append(name)

    # If no specific participants mentioned or user says "we", "all", "everyone"
    if not participants or "we" in text_lower or "all" in text_lower or "everyone" in text_lower or len(participants) == 1:
        participants = list(member_names)

    # 4. Category Classification
    category = "General"
    if any(k in text_lower for k in ["dinner", "lunch", "breakfast", "food", "restaurant", "cafe", "meal", "drinks", "snacks", "pizza"]):
        category = "Food & Dining"
    elif any(k in text_lower for k in ["petrol", "diesel", "cng", "fuel", "gas"]):
        category = "Fuel"
    elif any(k in text_lower for k in ["uber", "ola", "cab", "taxi", "bus", "train", "flight", "metro", "auto", "toll"]):
        category = "Transportation"
    elif any(k in text_lower for k in ["hotel", "resort", "airbnb", "stay", "room", "lodge", "hostel"]):
        category = "Accommodation"
    elif any(k in text_lower for k in ["movie", "ticket", "concert", "museum", "entry", "park"]):
        category = "Tickets & Events"
    elif any(k in text_lower for k in ["shopping", "clothes", "mall", "market", "groceries"]):
        category = "Shopping"
    elif any(k in text_lower for k in ["bill", "electricity", "wifi", "internet", "water", "rent"]):
        category = "Bills & Utilities"

    # 5. Clean Description
    # Remove amounts and filler phrases
    clean_desc = re.sub(r'(?:₹|rs\.?|inr|rupees?)\s*\d+(?:,\d+)*(?:\.\d{1,2})?', '', text, flags=re.IGNORECASE)
    clean_desc = re.sub(r'\b\d+(?:,\d+)*(?:\.\d{1,2})?\s*(?:₹|rs\.?|rupees?|inr)\b', '', clean_desc, flags=re.IGNORECASE)
    clean_desc = clean_desc.strip(" .,-")
    if not clean_desc or len(clean_desc) < 3:
        clean_desc = f"{category} Expense"

    clarification = None
    if missing_fields:
        clarification = f"Please specify who paid for this expense ({', '.join(member_names)})."

    return {
        "description": clean_desc[:100],
        "amount_rupees": amount_rupees,
        "payer_name": payer,
        "participants": participants,
        "split_type": "equal",
        "category": category,
        "merchant": None,
        "confidence": 0.85 if not missing_fields else 0.5,
        "missing_fields": missing_fields,
        "clarification_prompt": clarification,
    }


def _validate_and_normalize_parsed_expense(
    parsed: dict[str, Any],
    member_names: list[str],
    current_user_name: str | None
) -> dict[str, Any]:
    member_map = {m.lower(): m for m in member_names}

    payer = parsed.get("payer_name")
    if payer and payer.lower() in member_map:
        payer = member_map[payer.lower()]
    elif current_user_name and current_user_name.lower() in member_map:
        payer = current_user_name
    elif len(member_names) == 1:
        payer = member_names[0]
    else:
        payer = None

    valid_participants = []
    for p in parsed.get("participants", []):
        if isinstance(p, str) and p.lower() in member_map:
            v = member_map[p.lower()]
            if v not in valid_participants:
                valid_participants.append(v)

    if not valid_participants:
        valid_participants = list(member_names)

    category = parsed.get("category", "General")
    if category not in CATEGORIES:
        category = "General"

    amount_str = str(parsed.get("amount_rupees", "0.00")).replace(",", "").strip()
    try:
        amt = float(amount_str)
        if amt < 0:
            amt = 0.0
        amount_str = f"{amt:.2f}"
    except ValueError:
        amount_str = "0.00"

    missing = []
    if not payer:
        missing.append("payer")
    if amount_str == "0.00":
        missing.append("amount")

    return {
        "description": str(parsed.get("description", "Shared Expense")).strip()[:100],
        "amount_rupees": amount_str,
        "payer_name": payer,
        "participants": valid_participants,
        "split_type": parsed.get("split_type", "equal"),
        "category": category,
        "merchant": parsed.get("merchant"),
        "confidence": float(parsed.get("confidence", 0.9)),
        "missing_fields": missing,
        "clarification_prompt": parsed.get("clarification_prompt"),
    }


# ---------------------------------------------------------------------------
# 2. Receipt and Document Understanding (Gemini Vision + Fallback)
# ---------------------------------------------------------------------------

def extract_receipt_information(
    file_bytes: bytes,
    mime_type: str,
    original_filename: str
) -> dict[str, Any]:
    """
    Extract structured receipt details from image or PDF using Gemini multimodal model.
    Falls back to file metadata heuristic if Gemini is unconfigured or offline.
    """
    if is_gemini_configured() and mime_type.startswith(("image/", "application/pdf")):
        try:
            return _call_gemini_receipt_vision(file_bytes, mime_type)
        except Exception as e:
            print(f"Gemini receipt extraction failed ({e}), using metadata fallback.")

    # Fallback receipt extractor
    return _fallback_receipt_extract(original_filename, len(file_bytes), mime_type)


def _call_gemini_receipt_vision(file_bytes: bytes, mime_type: str) -> dict[str, Any]:
    b64_data = base64.b64encode(file_bytes).decode("utf-8")

    prompt = f"""
You are an expert OCR and financial document analysis assistant for SplitSmart AI 2.0.
Carefully examine this receipt, invoice, or bill.
Extract all visible details accurately. Do NOT hallucinate values not present.

Return ONLY valid JSON matching this schema:
{{
    "merchant_name": "Store/Restaurant Name or null",
    "receipt_date": "YYYY-MM-DD or null",
    "currency": "INR",
    "total_amount_rupees": "1250.00",
    "subtotal_rupees": "1150.00",
    "tax_rupees": "100.00",
    "items": [
        {{"name": "Item Description", "quantity": 1, "price_rupees": "500.00"}}
    ],
    "category": "Food & Dining",
    "confidence": 0.95,
    "notes": "Any discounts or payment method mentioned"
}}
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"

    response = httpx.post(
        url,
        params={"key": settings.gemini_api_key},
        json={
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": b64_data
                        }
                    }
                ]
            }],
            "generationConfig": {"responseMimeType": "application/json"}
        },
        timeout=httpx.Timeout(15.0, connect=2.0)
    )
    response.raise_for_status()
    result = response.json()

    candidates = result.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini returned empty candidate list.")

    raw_json = candidates[0]["content"]["parts"][0]["text"]
    return json.loads(raw_json)


def _fallback_receipt_extract(filename: str, file_size: int, mime_type: str) -> dict[str, Any]:
    # Heuristic guess from filename
    fname_lower = filename.lower()
    merchant = "Uploaded Receipt"
    category = "General"

    if any(k in fname_lower for k in ["hotel", "room", "stay"]):
        category = "Accommodation"
        merchant = "Hotel Booking"
    elif any(k in fname_lower for k in ["food", "dinner", "lunch", "cafe", "restaurant", "swiggy", "zomato"]):
        category = "Food & Dining"
        merchant = "Restaurant Bill"
    elif any(k in fname_lower for k in ["fuel", "petrol", "diesel", "hp", "shell", "indianoil"]):
        category = "Fuel"
        merchant = "Fuel Station"
    elif any(k in fname_lower for k in ["uber", "ola", "travel", "flight", "ticket"]):
        category = "Transportation"
        merchant = "Travel Service"

    return {
        "merchant_name": merchant,
        "receipt_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "currency": "INR",
        "total_amount_rupees": "0.00",
        "subtotal_rupees": "0.00",
        "tax_rupees": "0.00",
        "items": [],
        "category": category,
        "confidence": 0.6,
        "notes": f"File '{filename}' ({file_size} bytes) accepted. Confirm amounts manually."
    }


# ---------------------------------------------------------------------------
# 3. Audio & Voice Note Extraction
# ---------------------------------------------------------------------------

def extract_audio_expense(file_bytes: bytes, mime_type: str, member_names: list[str]) -> dict[str, Any]:
    """
    Process an audio voice message for expense tracking.
    Uses Gemini multimodal audio processing if configured; otherwise provides review draft.
    """
    if is_gemini_configured() and mime_type.startswith("audio/"):
        try:
            b64_data = base64.b64encode(file_bytes).decode("utf-8")
            prompt = f"""
You are a voice expense transcription assistant for SplitSmart AI.
Listen to this audio note carefully. Transcribe what was said and extract any expense details.
Available Group Members: {json.dumps(member_names)}

Return ONLY valid JSON:
{{
    "transcript": "Exact transcription of the audio",
    "description": "Expense description",
    "amount_rupees": "800.00",
    "payer_name": "Name from available members or null",
    "category": "Food & Dining",
    "confidence": 0.90
}}
"""
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
            response = httpx.post(
                url,
                params={"key": settings.gemini_api_key},
                json={
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inlineData": {"mimeType": mime_type, "data": b64_data}}
                        ]
                    }],
                    "generationConfig": {"responseMimeType": "application/json"}
                },
                timeout=httpx.Timeout(15.0, connect=2.0)
            )
            response.raise_for_status()
            res = response.json()
            candidates = res.get("candidates", [])
            if candidates:
                raw_json = candidates[0]["content"]["parts"][0]["text"]
                return json.loads(raw_json)
        except Exception as e:
            print(f"Gemini audio processing failed: {e}")

    return {
        "transcript": "Voice note uploaded.",
        "description": "Audio Voice Expense",
        "amount_rupees": "0.00",
        "payer_name": member_names[0] if member_names else None,
        "category": "General",
        "confidence": 0.5,
        "notes": "Voice recording saved. Please review and input the confirmed amount."
    }


# ---------------------------------------------------------------------------
# 4. Database-Grounded AI Financial Assistant
# ---------------------------------------------------------------------------

def answer_financial_query(
    db,  # Session
    group_id: int,
    user_query: str
) -> dict[str, Any]:
    """
    Answer natural language questions about the group's financial memory.
    STRICTLY grounded in database records using controlled retrieval functions.
    Never invents numbers or financial states.
    """
    group = db.get(Group, group_id)
    if not group:
        raise ValueError("Group not found")

    members = db.query(Member).filter(Member.group_id == group_id, Member.is_active.is_(True)).all()
    expenses = db.query(Expense).filter(Expense.group_id == group_id).all()
    settlements = db.query(Settlement).filter(Settlement.group_id == group_id).all()
    evidences = db.query(ExpenseEvidence).filter(ExpenseEvidence.group_id == group_id).all()

    # Controlled retrieval
    balances = calculate_member_balances(expenses, settlements)
    total_spent_paise = sum(e.total_amount_paise for e in expenses)
    budget_paise = group.budget_paise or 0
    remaining_budget_paise = budget_paise - total_spent_paise if budget_paise > 0 else 0

    member_name_map = {m.id: m.name for m in members}

    # Member contributions
    member_paid = {m.id: 0 for m in members}
    for e in expenses:
        member_paid[e.paid_by_member_id] = member_paid.get(e.paid_by_member_id, 0) + e.total_amount_paise

    # Top payer
    top_payer_id = max(member_paid.keys(), key=lambda mid: member_paid[mid]) if expenses else None
    top_payer_name = member_name_map.get(top_payer_id, "None") if top_payer_id else "None"

    # Category summaries
    cat_summary = {}
    for e in expenses:
        cat = e.category or "General"
        cat_summary[cat] = cat_summary.get(cat, 0) + e.total_amount_paise

    grounded_context = {
        "group_name": group.name,
        "activity_type": group.activity_type,
        "currency": group.currency or "INR",
        "budget": f"₹{budget_paise / 100:,.2f}",
        "total_spent": f"₹{total_spent_paise / 100:,.2f}",
        "remaining_budget": f"₹{remaining_budget_paise / 100:,.2f}",
        "active_members": [m.name for m in members],
        "member_contributions": {
            member_name_map[mid]: f"₹{amt / 100:,.2f}" for mid, amt in member_paid.items()
        },
        "member_balances": {
            member_name_map.get(mid, f"Member #{mid}"): (
                f"+₹{bal / 100:,.2f} (should receive)" if bal > 0 else (
                    f"-₹{abs(bal) / 100:,.2f} (owes)" if bal < 0 else "₹0.00 (settled)"
                )
            ) for mid, bal in balances.items()
        },
        "category_spending": {
            cat: f"₹{amt / 100:,.2f}" for cat, amt in cat_summary.items()
        },
        "top_contributor": f"{top_payer_name} (₹{member_paid.get(top_payer_id, 0) / 100:,.2f})" if top_payer_id else "No expenses yet",
        "expense_count": len(expenses),
        "recent_expenses": [
            {
                "id": e.id,
                "description": e.description,
                "amount": f"₹{e.total_amount_paise / 100:,.2f}",
                "paid_by": member_name_map.get(e.paid_by_member_id, "Unknown"),
                "category": e.category,
                "date": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "N/A"
            }
            for e in sorted(expenses, key=lambda x: x.id, reverse=True)[:5]
        ],
        "evidence_count": len(evidences),
        "pending_settlements": [
            {
                "from": member_name_map.get(s.from_member_id, "Unknown"),
                "to": member_name_map.get(s.to_member_id, "Unknown"),
                "amount": f"₹{s.amount_paise / 100:,.2f}"
            }
            for s in settlements if s.status == "pending"
        ]
    }

    # If Gemini API is available, ask Gemini with the exact grounded context
    if is_gemini_configured():
        try:
            return _call_gemini_assistant(user_query, grounded_context)
        except Exception as e:
            print(f"Gemini assistant error ({e}), using deterministic financial answer engine.")

    # Deterministic grounded question answering engine
    return _deterministic_answer(user_query, grounded_context, expenses, members, balances, member_name_map)


def _call_gemini_assistant(user_query: str, grounded_context: dict) -> dict[str, Any]:
    prompt = f"""
You are the AI Financial Intelligence Assistant for SplitSmart AI 2.0 ("The Financial Memory of a Group").
You must answer the user's question using ONLY the provided database ground truth records.

GROUND TRUTH DATABASE RECORDS:
{json.dumps(grounded_context, indent=2)}

USER QUESTION:
"{user_query}"

INSTRUCTIONS:
1. Answer directly and concisely with clear, accurate numbers from the records.
2. Format amounts in INR with rupee sign (₹).
3. DO NOT invent or estimate numbers that are not in the records.
4. If the database does not contain enough information to answer, state that clearly and suggest what is missing.
5. If the user asks about an unknown member or activity not in the group, explain that they are not part of this group.
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    response = httpx.post(
        url,
        params={"key": settings.gemini_api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}]
        },
        timeout=httpx.Timeout(15.0, connect=2.0)
    )
    response.raise_for_status()
    result = response.json()
    candidates = result.get("candidates", [])
    reply = candidates[0]["content"]["parts"][0]["text"] if candidates else "No response generated."

    return {
        "reply": reply,
        "sources": ["SplitSmart Database (Group Records, Expenses, Balances)"],
        "grounded_data": grounded_context
    }


def _deterministic_answer(
    query: str,
    context: dict,
    expenses: list,
    members: list,
    balances: dict,
    name_map: dict
) -> dict[str, Any]:
    q = query.lower()

    if not expenses:
        return {
            "reply": f"No expenses have been recorded yet in '{context['group_name']}'. Record your first expense or upload a receipt to start building the group's financial history.",
            "sources": ["Group Database"],
            "grounded_data": context
        }

    # 1. Total spending question
    if any(k in q for k in ["how much have we spent", "total spent", "total expense", "how much spent"]):
        return {
            "reply": f"The total recorded spending for '{context['group_name']}' is {context['total_spent']} across {context['expense_count']} transactions.",
            "sources": ["Expenses Database"],
            "grounded_data": context
        }

    # 2. Budget questions
    if any(k in q for k in ["budget remain", "remaining budget", "left in budget", "how much budget"]):
        if context["budget"] == "₹0.00":
            return {
                "reply": f"No group budget has been set yet. Total spending is {context['total_spent']}.",
                "sources": ["Group Database"],
                "grounded_data": context
            }
        return {
            "reply": f"Total budget is {context['budget']}. With {context['total_spent']} spent so far, the remaining budget is {context['remaining_budget']}.",
            "sources": ["Group Budget & Expenses Database"],
            "grounded_data": context
        }

    # 3. Who paid the most?
    if any(k in q for k in ["who paid the most", "highest contributor", "top payer", "who spent the most"]):
        return {
            "reply": f"The top contributor is {context['top_contributor']}.",
            "sources": ["Expenses Database"],
            "grounded_data": context
        }

    # 4. Highest single expense
    if any(k in q for k in ["highest expense", "largest expense", "biggest expense", "most expensive"]):
        top_exp = max(expenses, key=lambda x: x.total_amount_paise)
        payer = name_map.get(top_exp.paid_by_member_id, "Unknown")
        return {
            "reply": f"The highest recorded expense is '{top_exp.description}' for ₹{top_exp.total_amount_paise / 100:,.2f}, paid by {payer} in category '{top_exp.category}'.",
            "sources": ["Expenses Database"],
            "grounded_data": context
        }

    # 5. Specific member query
    for m in members:
        if m.name.lower() in q:
            paid = context["member_contributions"].get(m.name, "₹0.00")
            bal = context["member_balances"].get(m.name, "₹0.00")
            return {
                "reply": f"{m.name} has paid a total of {paid}. Current net balance is {bal}.",
                "sources": ["Member & Expense Database"],
                "grounded_data": context
            }

    # 6. Category query
    for cat, amt in context["category_spending"].items():
        if cat.lower() in q or (cat == "Food & Dining" and any(k in q for k in ["food", "dinner", "lunch"])) or (cat == "Accommodation" and "hotel" in q):
            return {
                "reply": f"Total spending on '{cat}' is {amt}.",
                "sources": ["Category Analytics"],
                "grounded_data": context
            }

    # 7. Unpaid / pending settlements
    if any(k in q for k in ["unpaid", "pending", "settlement", "who owes"]):
        pending = context["pending_settlements"]
        if not pending:
            return {
                "reply": "There are no pending settlement payments recorded right now. View Settlements for suggested simplified payment paths.",
                "sources": ["Settlements Database"],
                "grounded_data": context
            }
        lines = [f"• {p['from']} owes {p['to']} {p['amount']}" for p in pending]
        return {
            "reply": "Current pending settlements:\n" + "\n".join(lines),
            "sources": ["Settlements Database"],
            "grounded_data": context
        }

    # Default fallback summary
    return {
        "reply": f"In '{context['group_name']}', {context['total_spent']} has been spent so far by {len(members)} active members. Top contributor is {context['top_contributor']}. Remaining budget: {context['remaining_budget']}.",
        "sources": ["SplitSmart Group Financial Memory"],
        "grounded_data": context
    }
