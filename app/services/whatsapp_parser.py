import re
from datetime import datetime
from typing import Any


CHAT_LINE_REGEX = re.compile(
    r'^(?:\[?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\]?\s*[-:]?\s*)([^:]+):\s*(.+)$'
)

EXPENSE_KEYWORDS = [
    "paid", "spent", "rs", "rupee", "rupees", "inr", "₹", "bill",
    "dinner", "lunch", "cab", "uber", "ola", "petrol", "diesel",
    "hotel", "booking", "flight", "ticket", "split", "advance",
    "bought", "grocery", "groceries", "toll"
]

# Match amounts like:
# ₹1500, Rs. 1500, 1500 rs, 1500 rupees, paid 1500, spent 800
AMOUNT_REGEX = re.compile(
    r'(?:(?:rs\.?|inr|₹|paid|spent)\s*(\d+(?:,\d+)*(?:\.\d{1,2})?)|(\d+(?:,\d+)*(?:\.\d{1,2})?)\s*(?:rs\.?|rupees?|inr|bucks)?)',
    re.IGNORECASE
)


def parse_whatsapp_chat(text_content: str, known_member_names: list[str]) -> list[dict[str, Any]]:
    candidates = []
    lines = text_content.splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = CHAT_LINE_REGEX.match(line)
        if not match:
            continue

        date_str, time_str, sender, msg = match.groups()
        sender = sender.strip()
        msg = msg.strip()

        msg_lower = msg.lower()
        has_keyword = any(kw in msg_lower for kw in EXPENSE_KEYWORDS)
        if not has_keyword:
            continue

        # Extract amount
        amount_paise = None
        # Try explicit currency or 'paid X' match first
        explicit_match = re.search(
            r'(?:(?:rs\.?|inr|₹|paid|spent)\s*(\d+(?:,\d+)*(?:\.\d{1,2})?)|(\d+(?:,\d+)*(?:\.\d{1,2})?)\s*(?:rs\.?|rupees?|inr|bucks))',
            msg,
            re.IGNORECASE
        )
        if explicit_match:
            raw_amt = explicit_match.group(1) or explicit_match.group(2)
            if raw_amt:
                try:
                    cleaned_amt = float(raw_amt.replace(",", ""))
                    amount_paise = int(cleaned_amt * 100)
                except ValueError:
                    amount_paise = None
        else:
            # Fallback to any standalone number in the message
            num_match = re.search(r'\b(\d+(?:,\d+)*(?:\.\d{1,2})?)\b', msg)
            if num_match:
                try:
                    cleaned_amt = float(num_match.group(1).replace(",", ""))
                    amount_paise = int(cleaned_amt * 100)
                except ValueError:
                    amount_paise = None

        matched_member = None
        for member_name in known_member_names:
            if member_name.lower() in sender.lower() or sender.lower() in member_name.lower():
                matched_member = member_name
                break

        candidates.append({
            "raw_line": line,
            "sender": sender,
            "matched_member": matched_member,
            "date_str": date_str,
            "time_str": time_str,
            "message": msg,
            "suggested_amount_paise": amount_paise,
            "suggested_description": msg[:100],
        })

    return candidates
