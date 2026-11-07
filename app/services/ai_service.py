
import json

import httpx

from app.core.config import settings


GEMINI_MODEL = "gemini-2.5-flash"


def parse_expense_with_ai(text: str, member_names: list[str]):
    if not settings.gemini_api_key:
        raise ValueError("Gemini API key is not configured.")

    prompt = f"""
You are an expense information extraction assistant.

Extract expense information from the user's sentence.

Available group members:
{json.dumps(member_names)}

User sentence:
{text}

Return ONLY valid JSON with this structure:
{{
    "description": "Dinner",
    "amount_rupees": "900.00",
    "payer_name": "Arun",
    "participants": ["Arun", "Rahul"],
    "split_type": "equal"
}}

Rules:
1. Use only names from the available group members.
2. Do not invent member names.
3. Amount must be a positive rupee amount.
4. Use equal split unless a custom split is explicitly requested.
5. If information is missing or ambiguous, return an error field.
6. Do not calculate individual shares.
"""

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
    )

    try:
        response = httpx.post(
            url,
            params={"key": settings.gemini_api_key},
            json={
                "contents": [
                    {"parts": [{"text": prompt}]}
                ],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            },
            timeout=30.0
        )

        response.raise_for_status()
        result = response.json()

        candidates = result.get("candidates", [])

        if not candidates:
            raise ValueError("AI could not understand the expense.")

        output = candidates[0]["content"]["parts"][0]["text"]
        parsed = json.loads(output)

        if parsed.get("error"):
            raise ValueError(str(parsed["error"]))

        required = [
            "description",
            "amount_rupees",
            "payer_name",
            "participants",
            "split_type"
        ]

        if any(key not in parsed for key in required):
            raise ValueError("AI returned incomplete expense information.")

        if not isinstance(parsed["participants"], list):
            raise ValueError("Invalid participant information.")

        if parsed["split_type"] not in ("equal", "custom"):
            raise ValueError("Invalid split type.")

        return parsed

    except httpx.HTTPError as exc:
        raise ValueError("Gemini API request failed.") from exc

    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Could not process the AI response.") from exc
