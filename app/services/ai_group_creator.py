import json
import re
from datetime import datetime, timezone
from typing import Any
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import Group, Member, Activity, CustomCategory, CustomField, User
from app.schemas.groups import GroupResponse
from app.routes.groups import enrich_group_response


def is_gemini_configured() -> bool:
    return bool(
        settings.gemini_api_key
        and settings.gemini_api_key.strip()
        and settings.gemini_api_key != "your_gemini_api_key_here"
    )


GROUP_CREATION_SCHEMA = {
    "group_name": "College Symposium 2026",
    "description": "Three-day college symposium tracking activities and expenses",
    "activity_type": "college_symposium",
    "overall_budget_rupees": "30000.00",
    "currency": "INR",
    "start_date": "2026-03-15",
    "end_date": "2026-03-17",
    "members": [
        {"name": "Participant 1", "role": "owner"}
    ],
    "activities": [
        {"name": "Food", "description": "Catering and refreshments", "budget_rupees": "10000.00"},
        {"name": "Decoration", "description": "Venue styling and banners", "budget_rupees": "5000.00"},
        {"name": "Transportation", "description": "Guest and logistics travel", "budget_rupees": "4000.00"},
        {"name": "Accommodation", "description": "Lodging arrangements", "budget_rupees": "5000.00"},
        {"name": "Photography", "description": "Event coverage and media", "budget_rupees": "3000.00"},
        {"name": "Stage Arrangements", "description": "Audio, lighting and stage setup", "budget_rupees": "3000.00"}
    ],
    "suggested_categories": [
        "Food & Dining",
        "Decoration",
        "Transportation",
        "Accommodation",
        "Photography",
        "Stage & Equipment",
        "General"
    ],
    "custom_fields": [
        {"name": "Vendor Contact", "field_type": "text", "entity_type": "activity"},
        {"name": "Invoice Number", "field_type": "text", "entity_type": "expense"}
    ],
    "sharing_rules": "Expenses split equally by default among active participants of each activity"
}


def generate_group_proposal(user_description: str) -> dict[str, Any]:
    """
    Interprets natural language group requirements and prepares a structured, editable proposal.
    """
    if not user_description or not user_description.strip():
        raise ValueError("Please provide a description of the group you want to create.")

    if is_gemini_configured():
        try:
            return _call_gemini_group_create(user_description)
        except Exception as e:
            print(f"Gemini group creation failed ({e}), using heuristic group builder.")

    return _heuristic_group_proposal(user_description)


def refine_group_proposal(current_proposal: dict, user_followup: str) -> dict[str, Any]:
    """
    Takes an existing proposed group structure and applies follow-up instructions
    (e.g., 'Add a separate photography activity', 'Allocate ₹4,000 to photography', 'Remove accommodation').
    """
    if not user_followup or not user_followup.strip():
        return current_proposal

    if is_gemini_configured():
        try:
            return _call_gemini_refine_proposal(current_proposal, user_followup)
        except Exception as e:
            print(f"Gemini refinement failed ({e}), using rule-based refinement.")

    return _heuristic_refine_proposal(current_proposal, user_followup)


def _call_gemini_group_create(user_description: str) -> dict[str, Any]:
    prompt = f"""
You are the AI Group Architect for SplitSmart ("The Financial Memory of a Group").
The user wants to create a group for an activity or financial purpose.
Analyze the user description and generate a complete, structured group configuration.

USER DESCRIPTION:
"{user_description}"

OUTPUT FORMAT: Return ONLY valid JSON matching this schema:
{{
    "group_name": "Meaningful and appropriate group title",
    "description": "Clear explanation of group purpose and scope",
    "activity_type": "short_code (e.g. symposium, trip, flatmates, wedding, project, club, general)",
    "overall_budget_rupees": "Total budget string or 0.00",
    "currency": "INR",
    "start_date": "YYYY-MM-DD or null",
    "end_date": "YYYY-MM-DD or null",
    "members": [
        {{"name": "Explicitly named member or Organiser", "role": "owner"}}
    ],
    "activities": [
        {{"name": "Sub-activity name", "description": "Brief description", "budget_rupees": "1000.00"}}
    ],
    "suggested_categories": ["Category 1", "Category 2"],
    "custom_fields": [
        {{"name": "Field Name", "field_type": "text/number/date/select", "entity_type": "group/activity/expense"}}
    ],
    "sharing_rules": "Default expense sharing explanation"
}}

IMPORTANT RULES:
1. Do NOT invent fake identities or financial facts not mentioned by the user. If user says '8 participants' without names, you may suggest placeholder names like 'Member 1', 'Member 2', etc.
2. If activities are explicitly mentioned (e.g., food, decoration, stage, photography), create each as a separate item in "activities" with an appropriate budget share.
3. Sum of activity budgets should generally fit within the overall budget if provided.
4. Output raw JSON only.
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    response = httpx.post(
        url,
        params={"key": settings.gemini_api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        },
        timeout=httpx.Timeout(30.0, connect=10.0)
    )
    response.raise_for_status()
    raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw_text)


def _call_gemini_refine_proposal(current_proposal: dict, user_followup: str) -> dict[str, Any]:
    prompt = f"""
You are the AI Group Architect for SplitSmart.
Update the current group proposal according to the user's follow-up instruction.

CURRENT PROPOSAL:
{json.dumps(current_proposal, indent=2)}

USER FOLLOW-UP INSTRUCTION:
"{user_followup}"

Return the UPDATED group proposal JSON matching the same schema. Return ONLY valid JSON.
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    response = httpx.post(
        url,
        params={"key": settings.gemini_api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        },
        timeout=httpx.Timeout(30.0, connect=10.0)
    )
    response.raise_for_status()
    raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw_text)


def _heuristic_group_proposal(text: str) -> dict[str, Any]:
    text_lower = text.lower()

    # Extract overall budget
    budget_rupees = "0.00"
    amt_match = re.search(r'(?:(?:₹|rs\.?|inr|budget\s*(?:of|is)?)\s*(\d+(?:,\d+)*(?:\.\d{1,2})?)|(\d+(?:,\d+)*(?:\.\d{1,2})?)\s*(?:₹|rs\.?|rupees|budget))', text, re.IGNORECASE)
    if amt_match:
        val = amt_match.group(1) or amt_match.group(2)
        if val:
            try:
                budget_rupees = f"{float(val.replace(',', '')):.2f}"
            except ValueError:
                pass

    # Detect activities
    potential_activities = [
        ("food", "Food & Refreshments"),
        ("decoration", "Decor & Staging"),
        ("transport", "Transportation & Logistics"),
        ("travel", "Travel & Transit"),
        ("accommodation", "Accommodation & Stay"),
        ("hotel", "Hotel & Lodging"),
        ("photography", "Photography & Videography"),
        ("stage", "Stage Arrangements & Audio/Visual"),
        ("sound", "Sound & Lighting"),
        ("catering", "Catering & Meals"),
        ("shopping", "Supplies & Shopping"),
        ("venue", "Venue Rental"),
    ]

    detected_acts = []
    for key, label in potential_activities:
        if key in text_lower:
            detected_acts.append({"name": label, "description": f"{label} arrangements", "budget_rupees": "0.00"})

    if not detected_acts:
        detected_acts = [
            {"name": "Main Event", "description": "Core activity expenses", "budget_rupees": budget_rupees}
        ]
    elif budget_rupees != "0.00":
        # Split budget roughly among detected activities
        total_float = float(budget_rupees)
        share = round(total_float / len(detected_acts), 2)
        for act in detected_acts:
            act["budget_rupees"] = f"{share:.2f}"

    # Extract participant count or members
    members = []
    member_match = re.search(r'(\d+)\s*(?:participants|members|people|friends|roommates)', text_lower)
    if member_match:
        count = min(int(member_match.group(1)), 20)
        members.append({"name": "Organiser", "role": "owner"})
        for i in range(2, count + 1):
            members.append({"name": f"Participant {i}", "role": "member"})
    else:
        members.append({"name": "Organiser", "role": "owner"})

    # Group name heuristic
    name = "New Group Activity"
    if "symposium" in text_lower:
        name = "College Symposium"
    elif "trip" in text_lower or "vacation" in text_lower:
        name = "Group Trip"
    elif "roommate" in text_lower or "flat" in text_lower:
        name = "Shared Apartment"
    elif "wedding" in text_lower:
        name = "Wedding Celebration"
    elif "event" in text_lower:
        name = "Department Event"

    return {
        "group_name": name,
        "description": text[:200],
        "activity_type": "custom",
        "overall_budget_rupees": budget_rupees,
        "currency": "INR",
        "start_date": None,
        "end_date": None,
        "members": members,
        "activities": detected_acts,
        "suggested_categories": [a["name"] for a in detected_acts] + ["General"],
        "custom_fields": [
            {"name": "Responsible Lead", "field_type": "text", "entity_type": "activity"}
        ],
        "sharing_rules": "Equal splitting among active members"
    }


def _heuristic_refine_proposal(proposal: dict, instruction: str) -> dict[str, Any]:
    inst_lower = instruction.lower()
    updated = json.loads(json.dumps(proposal))

    # Add activity
    add_match = re.search(r'add\s+(?:a\s+)?(?:separate\s+)?(?:activity\s+called\s+|activity\s+for\s+)?([a-zA-Z\s]+?)(?:\s+with\s+budget|\s+activity|$|\.)', instruction, re.IGNORECASE)
    if "add" in inst_lower and add_match:
        act_name = add_match.group(1).strip().title()
        if act_name and not any(a["name"].lower() == act_name.lower() for a in updated["activities"]):
            updated["activities"].append({
                "name": act_name,
                "description": f"Activity for {act_name}",
                "budget_rupees": "0.00"
            })
            if act_name not in updated["suggested_categories"]:
                updated["suggested_categories"].append(act_name)

    # Remove activity
    rem_match = re.search(r'remove\s+([a-zA-Z\s]+)', instruction, re.IGNORECASE)
    if "remove" in inst_lower and rem_match:
        target = rem_match.group(1).strip().lower()
        updated["activities"] = [a for a in updated["activities"] if target not in a["name"].lower()]

    # Update budget of activity
    budget_match = re.search(r'(?:allocate|set|budget)\s*(?:of|to)?\s*(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)*(?:\.\d{1,2})?)\s*(?:to|for)\s*([a-zA-Z\s]+)', instruction, re.IGNORECASE)
    if budget_match:
        amt = float(budget_match.group(1).replace(",", ""))
        target = budget_match.group(2).strip().lower()
        for a in updated["activities"]:
            if target in a["name"].lower():
                a["budget_rupees"] = f"{amt:.2f}"

    # Update overall budget
    overall_match = re.search(r'(?:group\s+budget\s+to|change\s+budget\s+to|overall\s+budget\s+to)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)*(?:\.\d{1,2})?)', instruction, re.IGNORECASE)
    if overall_match:
        amt = float(overall_match.group(1).replace(",", ""))
        updated["overall_budget_rupees"] = f"{amt:.2f}"

    return updated


def persist_group_structure(db: Session, structure: dict, user: User | None = None) -> GroupResponse:
    """
    Persists confirmed group structure into database:
    Creates Group, Members, Activities, CustomCategories, and CustomFields.
    """
    name = structure.get("group_name", "New Group").strip()
    desc = structure.get("description")
    act_type = structure.get("activity_type", "general")
    currency = structure.get("currency", "INR")

    overall_budget_paise = 0
    try:
        overall_budget_paise = int(float(structure.get("overall_budget_rupees", "0")) * 100)
    except (ValueError, TypeError):
        overall_budget_paise = 0

    group = Group(
        name=name,
        description=desc,
        activity_type=act_type,
        budget_paise=overall_budget_paise,
        currency=currency,
        created_by_user_id=user.id if user else None,
        is_archived=False
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    # 1. Add Members
    members_data = structure.get("members", [])
    if not members_data:
        # Default creator as owner
        owner_name = (user.full_name or user.username) if user else "Organiser"
        db.add(Member(group_id=group.id, user_id=user.id if user else None, name=owner_name, role="owner", is_active=True))
    else:
        has_owner = False
        for idx, m in enumerate(members_data):
            m_name = m.get("name", f"Member {idx + 1}").strip()
            m_role = m.get("role", "member")
            if idx == 0 and not has_owner:
                m_role = "owner"
                has_owner = True
            db.add(Member(
                group_id=group.id,
                user_id=user.id if (user and idx == 0) else None,
                name=m_name,
                role=m_role,
                is_active=True
            ))

    # 2. Add Activities
    for act in structure.get("activities", []):
        act_name = act.get("name", "Activity").strip()
        act_desc = act.get("description")
        act_budget = 0
        try:
            act_budget = int(float(act.get("budget_rupees", "0")) * 100)
        except (ValueError, TypeError):
            act_budget = 0

        db.add(Activity(
            group_id=group.id,
            name=act_name,
            description=act_desc,
            budget_paise=act_budget,
            status="active"
        ))

    # 3. Add Custom Categories
    cats = structure.get("suggested_categories", [])
    if not cats:
        cats = ["Food & Dining", "Transportation", "Accommodation", "General"]
    for c_name in set(cats):
        db.add(CustomCategory(
            group_id=group.id,
            name=c_name.strip(),
            is_default=True
        ))

    # 4. Add Custom Fields
    for cf in structure.get("custom_fields", []):
        cf_name = cf.get("name", "Custom Field").strip()
        cf_type = cf.get("field_type", "text")
        cf_entity = cf.get("entity_type", "expense")
        db.add(CustomField(
            group_id=group.id,
            name=cf_name,
            field_type=cf_type,
            entity_type=cf_entity
        ))

    db.commit()
    db.refresh(group)

    return enrich_group_response(group, db)
