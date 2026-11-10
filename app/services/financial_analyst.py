from datetime import datetime, timezone
from sqlalchemy.orm import Session, selectinload
from app.database.models import Group, Member, Expense, Settlement
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


def get_group_financial_overview(db: Session, group_id: int) -> dict:
    group = db.get(Group, group_id)
    if not group:
        raise ValueError("Group not found")

    members = db.query(Member).filter(Member.group_id == group_id, Member.is_active.is_(True)).all()
    expenses = db.query(Expense).options(selectinload(Expense.shares)).filter(Expense.group_id == group_id).all()
    settlements = db.query(Settlement).filter(Settlement.group_id == group_id).all()

    total_expense_paise = sum(exp.total_amount_paise for exp in expenses)
    budget_paise = group.budget_paise or 0

    confirmed_settlements_paise = sum(
        s.amount_paise for s in settlements if s.status == "completed"
    )
    pending_settlements_paise = sum(
        s.amount_paise for s in settlements if s.status == "pending"
    )

    remaining_budget_paise = budget_paise - total_expense_paise if budget_paise > 0 else 0
    budget_pct = (total_expense_paise / budget_paise * 100) if budget_paise > 0 else 0.0

    return {
        "total_budget_paise": budget_paise,
        "total_expense_paise": total_expense_paise,
        "confirmed_settlements_paise": confirmed_settlements_paise,
        "pending_settlements_paise": pending_settlements_paise,
        "remaining_budget_paise": remaining_budget_paise,
        "budget_consumed_percentage": round(budget_pct, 1),
        "active_members_count": len(members),
        "expense_count": len(expenses),
        "currency": group.currency or "INR",
    }


def get_category_breakdown(db: Session, group_id: int) -> list[dict]:
    expenses = db.query(Expense).filter(Expense.group_id == group_id).all()
    total_expense = sum(e.total_amount_paise for e in expenses)

    cat_map: dict[str, dict] = {}
    for exp in expenses:
        cat = exp.category or "General"
        if cat not in cat_map:
            cat_map[cat] = {"amount_paise": 0, "count": 0}
        cat_map[cat]["amount_paise"] += exp.total_amount_paise
        cat_map[cat]["count"] += 1

    result = []
    for cat, data in sorted(cat_map.items(), key=lambda x: x[1]["amount_paise"], reverse=True):
        pct = (data["amount_paise"] / total_expense * 100) if total_expense > 0 else 0.0
        result.append({
            "category": cat,
            "amount_paise": data["amount_paise"],
            "percentage": round(pct, 1),
            "count": data["count"],
        })

    return result


def get_member_contributions(db: Session, group_id: int) -> list[dict]:
    members = db.query(Member).filter(Member.group_id == group_id, Member.is_active.is_(True)).all()
    expenses = db.query(Expense).options(selectinload(Expense.shares)).filter(Expense.group_id == group_id).all()
    settlements = db.query(Settlement).filter(Settlement.group_id == group_id).all()

    balances = calculate_member_balances(expenses, settlements)

    paid_map = {m.id: 0 for m in members}
    owed_map = {m.id: 0 for m in members}

    for exp in expenses:
        paid_map[exp.paid_by_member_id] = paid_map.get(exp.paid_by_member_id, 0) + exp.total_amount_paise
        for share in exp.shares:
            owed_map[share.member_id] = owed_map.get(share.member_id, 0) + share.amount_paise

    contributions = []
    for m in members:
        contributions.append({
            "member_id": m.id,
            "member_name": m.name,
            "role": m.role or "member",
            "paid_paise": paid_map.get(m.id, 0),
            "owed_paise": owed_map.get(m.id, 0),
            "net_balance_paise": balances.get(m.id, 0),
        })

    return sorted(contributions, key=lambda x: x["paid_paise"], reverse=True)


def get_budget_status(db: Session, group_id: int) -> dict:
    overview = get_group_financial_overview(db, group_id)
    budget = overview["total_budget_paise"]
    spent = overview["total_expense_paise"]
    remaining = overview["remaining_budget_paise"]
    pct = overview["budget_consumed_percentage"]

    if budget <= 0:
        return {
            "budget_paise": 0,
            "spent_paise": spent,
            "remaining_paise": 0,
            "status_level": "none",
            "alert_message": "No budget set for this group yet. Set a budget in group settings to track utilization."
        }

    if pct >= 100:
        level = "danger"
        message = f"Budget exceeded by ₹{abs(remaining)/100:,.2f} ({pct:.1f}% spent). Immediate spending pause recommended."
    elif pct >= 80:
        level = "warning"
        message = f"Approaching budget limit ({pct:.1f}% consumed). Remaining budget is ₹{remaining/100:,.2f}."
    else:
        level = "safe"
        message = f"Spending is healthy ({pct:.1f}% of budget consumed). ₹{remaining/100:,.2f} remaining."

    return {
        "budget_paise": budget,
        "spent_paise": spent,
        "remaining_paise": remaining,
        "status_level": level,
        "alert_message": message
    }


def get_spending_forecast(db: Session, group_id: int) -> dict:
    group = db.get(Group, group_id)
    if not group:
        raise ValueError("Group not found")

    expenses = db.query(Expense).filter(Expense.group_id == group_id).order_by(Expense.created_at).all()
    total_spent = sum(e.total_amount_paise for e in expenses)
    budget = group.budget_paise or 0

    if len(expenses) < 2 or not group.start_date:
        return {
            "estimated_total_spending_paise": total_spent,
            "estimated_remaining_budget_paise": max(0, budget - total_spent),
            "burn_rate_daily_paise": 0,
            "days_elapsed": 0,
            "days_remaining": 0,
            "projected_overrun_paise": 0,
            "is_reliable": False,
            "explanation": "Insufficient activity dates or expense records to generate an explainable projection. Record more expenses with activity dates for forecasts."
        }

    now = datetime.now(timezone.utc)
    start = group.start_date
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    elapsed_days = max(1, (now - start).days + 1)
    daily_burn = int(total_spent / elapsed_days)

    if group.end_date:
        end = group.end_date
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        total_duration = max(elapsed_days, (end - start).days + 1)
        remaining_days = max(0, (end - now).days)
    else:
        # Default assumption 7 days if no end date
        total_duration = elapsed_days + 3
        remaining_days = 3

    estimated_total = total_spent + (daily_burn * remaining_days)
    overrun = max(0, estimated_total - budget) if budget > 0 else 0
    estimated_remaining = max(0, budget - estimated_total) if budget > 0 else 0

    return {
        "estimated_total_spending_paise": estimated_total,
        "estimated_remaining_budget_paise": estimated_remaining,
        "burn_rate_daily_paise": daily_burn,
        "days_elapsed": elapsed_days,
        "days_remaining": remaining_days,
        "projected_overrun_paise": overrun,
        "is_reliable": True,
        "explanation": f"Based on {elapsed_days} day(s) of activity with an average daily burn of ₹{daily_burn/100:.2f}. Projected spending over {total_duration} total days is ₹{estimated_total/100:.2f}."
    }


def get_historical_recommendations(db: Session, group_id: int) -> list[dict]:
    group = db.get(Group, group_id)
    if not group:
        return []

    expenses = db.query(Expense).filter(Expense.group_id == group_id).all()
    total_spent = sum(e.total_amount_paise for e in expenses)
    budget = group.budget_paise or 0

    recs = []

    # Category insights
    breakdown = get_category_breakdown(db, group_id)
    for cat in breakdown:
        if cat["category"] in ("Food & Dining", "Accommodation") and cat["percentage"] > 45.0:
            recs.append({
                "title": f"High {cat['category']} Ratio",
                "category": cat["category"],
                "recommendation": f"{cat['category']} currently accounts for {cat['percentage']:.1f}% of all expenses. For future activities, consider budgeting a higher allocation or negotiating group rates.",
                "based_on": f"Current category spending data ({cat['count']} transactions totaling ₹{cat['amount_paise']/100:.2f})."
            })

    if budget > 0 and total_spent > budget:
        recs.append({
            "title": "Budget Reserve Recommendation",
            "category": "Budgeting",
            "recommendation": f"Current activity exceeded target budget by ₹{(total_spent - budget)/100:.2f}. For future {group.activity_type} events, add a 15-20% contingency reserve upfront.",
            "based_on": f"Actual spend of ₹{total_spent/100:.2f} vs planned ₹{budget/100:.2f}."
        })

    if not recs:
        recs.append({
            "title": "Expense Tracking Cadence",
            "category": "Best Practice",
            "recommendation": "Maintain daily receipt uploads to prevent end-of-activity settlement delays and missing expense records.",
            "based_on": "SplitSmart Group Activity Financial Memory best practices."
        })

    return recs
