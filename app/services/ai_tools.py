import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session, selectinload

from app.database.models import Group, Member, Activity, Expense, Settlement, ExpenseEvidence, CustomCategory
from app.services.settlement_engine import calculate_member_balances, simplify_debts
from app.services.expense_calculator import calculate_equal_split
from app.core.auth import User, check_group_permission


# Permitted tool specifications for Gemini Function Calling
GEMINI_TOOLS_DECLARATIONS = [
    {
        "name": "create_group_structure",
        "description": "Propose creating a new group with specified activities, members, and budgets.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Group title"},
                "description": {"type": "STRING", "description": "Group purpose"},
                "budget_rupees": {"type": "NUMBER", "description": "Overall budget in rupees"},
                "activities": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of sub-activity names"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_activity",
        "description": "Add a new custom activity with an allocated budget under an existing group.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "group_id": {"type": "INTEGER", "description": "ID of the group"},
                "name": {"type": "STRING", "description": "Activity name (e.g. Photography, Stage Lighting)"},
                "budget_rupees": {"type": "NUMBER", "description": "Budget allocated for this activity in rupees"}
            },
            "required": ["group_id", "name"]
        }
    },
    {
        "name": "update_group_budget",
        "description": "Update the total financial budget for a group.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "group_id": {"type": "INTEGER", "description": "ID of the group"},
                "budget_rupees": {"type": "NUMBER", "description": "New budget in rupees"}
            },
            "required": ["group_id", "budget_rupees"]
        }
    },
    {
        "name": "create_category",
        "description": "Create a new custom expense category for a group.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "group_id": {"type": "INTEGER", "description": "ID of the group"},
                "name": {"type": "STRING", "description": "New category name"}
            },
            "required": ["group_id", "name"]
        }
    },
    {
        "name": "retrieve_group_summary",
        "description": "Retrieve verified financial summary, total spending, budget, and member balances for a group.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "group_id": {"type": "INTEGER", "description": "ID of the group"}
            },
            "required": ["group_id"]
        }
    },
    {
        "name": "retrieve_balances",
        "description": "Retrieve net balance and simplified settlement obligations for all members of a group.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "group_id": {"type": "INTEGER", "description": "ID of the group"}
            },
            "required": ["group_id"]
        }
    },
    {
        "name": "retrieve_expenses",
        "description": "Retrieve recent expenses with payer, category, and amount details for a group.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "group_id": {"type": "INTEGER", "description": "ID of the group"},
                "limit": {"type": "INTEGER", "description": "Max expenses to return (default 10)"}
            },
            "required": ["group_id"]
        }
    }
]


def execute_tool_call(
    db: Session,
    tool_name: str,
    tool_args: dict[str, Any],
    user: User | None = None
) -> dict[str, Any]:
    """
    Validates and executes a function call requested by the AI assistant against backend services.
    Enforces authorization and returns ground truth database results.
    """
    if tool_name == "retrieve_group_summary":
        group_id = int(tool_args["group_id"])
        group = db.get(Group, group_id)
        if not group:
            return {"error": "Group not found"}

        expenses = db.query(Expense).filter(Expense.group_id == group_id, Expense.status == "confirmed").all()
        settlements = db.query(Settlement).filter(Settlement.group_id == group_id, Settlement.status == "completed").all()
        members = db.query(Member).filter(Member.group_id == group_id, Member.is_active.is_(True)).all()

        total_spent_paise = sum(e.total_amount_paise for e in expenses)
        budget_paise = group.budget_paise or 0

        balances = calculate_member_balances(expenses, settlements)
        name_map = {m.id: m.name for m in members}

        return {
            "group_name": group.name,
            "activity_type": group.activity_type,
            "total_budget": f"₹{budget_paise / 100:,.2f}",
            "total_spent": f"₹{total_spent_paise / 100:,.2f}",
            "remaining_budget": f"₹{(budget_paise - total_spent_paise) / 100:,.2f}" if budget_paise > 0 else "N/A",
            "member_count": len(members),
            "expense_count": len(expenses),
            "balances": {name_map.get(mid, f"Member #{mid}"): f"₹{bal / 100:,.2f}" for mid, bal in balances.items()}
        }

    elif tool_name == "retrieve_balances":
        group_id = int(tool_args["group_id"])
        group = db.get(Group, group_id)
        if not group:
            return {"error": "Group not found"}

        expenses = db.query(Expense).filter(Expense.group_id == group_id, Expense.status == "confirmed").all()
        settlements = db.query(Settlement).filter(Settlement.group_id == group_id, Settlement.status == "completed").all()
        members = db.query(Member).filter(Member.group_id == group_id).all()
        name_map = {m.id: m.name for m in members}

        balances = calculate_member_balances(expenses, settlements)
        simplified = simplify_debts(balances)

        return {
            "group_name": group.name,
            "balances": [
                {
                    "member": name_map.get(mid, f"Member #{mid}"),
                    "balance": f"₹{bal / 100:,.2f}",
                    "status": "owes" if bal < 0 else ("receives" if bal > 0 else "settled")
                }
                for mid, bal in balances.items()
            ],
            "suggested_settlements": [
                {
                    "from": name_map.get(s["from_member_id"], "Unknown"),
                    "to": name_map.get(s["to_member_id"], "Unknown"),
                    "amount": f"₹{s['amount_paise'] / 100:,.2f}"
                }
                for s in simplified
            ]
        }

    elif tool_name == "retrieve_expenses":
        group_id = int(tool_args["group_id"])
        limit = int(tool_args.get("limit", 10))

        expenses = (
            db.query(Expense)
            .filter(Expense.group_id == group_id)
            .order_by(Expense.id.desc())
            .limit(limit)
            .all()
        )
        members = db.query(Member).filter(Member.group_id == group_id).all()
        name_map = {m.id: m.name for m in members}

        return {
            "expenses": [
                {
                    "id": e.id,
                    "description": e.description,
                    "amount": f"₹{e.total_amount_paise / 100:,.2f}",
                    "paid_by": name_map.get(e.paid_by_member_id, "Unknown"),
                    "category": e.category,
                    "date": e.expense_date.strftime("%Y-%m-%d") if e.expense_date else "N/A"
                }
                for e in expenses
            ]
        }

    elif tool_name == "create_activity":
        group_id = int(tool_args["group_id"])
        name = str(tool_args["name"]).strip()
        budget_paise = int(float(tool_args.get("budget_rupees", 0)) * 100)

        check_group_permission(db, group_id, user, "manage_activities")

        activity = Activity(
            group_id=group_id,
            name=name,
            budget_paise=budget_paise,
            status="active"
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)

        return {
            "success": True,
            "activity_id": activity.id,
            "name": activity.name,
            "budget": f"₹{activity.budget_paise / 100:,.2f}",
            "message": f"Activity '{activity.name}' created successfully with budget ₹{activity.budget_paise / 100:,.2f}."
        }

    elif tool_name == "update_group_budget":
        group_id = int(tool_args["group_id"])
        budget_rupees = float(tool_args["budget_rupees"])
        budget_paise = int(budget_rupees * 100)

        group = db.get(Group, group_id)
        if not group:
            return {"error": "Group not found"}

        check_group_permission(db, group_id, user, "manage_budgets")

        group.budget_paise = budget_paise
        db.commit()

        return {
            "success": True,
            "group_id": group.id,
            "new_budget": f"₹{group.budget_paise / 100:,.2f}",
            "message": f"Group budget updated to ₹{group.budget_paise / 100:,.2f}."
        }

    elif tool_name == "create_category":
        group_id = int(tool_args["group_id"])
        name = str(tool_args["name"]).strip()

        check_group_permission(db, group_id, user, "manage_group")

        cat = CustomCategory(group_id=group_id, name=name, is_default=False)
        db.add(cat)
        db.commit()
        db.refresh(cat)

        return {
            "success": True,
            "category_id": cat.id,
            "name": cat.name,
            "message": f"Category '{cat.name}' created."
        }

    return {"error": f"Unknown tool '{tool_name}'"}
