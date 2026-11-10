from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Group, Member, Expense, Settlement, ExpenseEvidence, PaymentTransaction
from app.schemas.analytics import (
    FinancialOverview,
    CategorySpending,
    MemberContribution,
    BudgetStatus,
    SpendingForecast,
    HistoricalRecommendation,
)
from app.services.financial_analyst import (
    get_group_financial_overview,
    get_category_breakdown,
    get_member_contributions,
    get_budget_status,
    get_spending_forecast,
    get_historical_recommendations,
)


router = APIRouter(
    prefix="/api/groups/{group_id}/analytics",
    tags=["Financial Intelligence & Analytics"]
)


@router.get("/overview", response_model=FinancialOverview)
def get_overview(group_id: int, db: Session = Depends(get_db)):
    try:
        data = get_group_financial_overview(db, group_id)
        return FinancialOverview(**data)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/categories", response_model=list[CategorySpending])
def get_categories(group_id: int, db: Session = Depends(get_db)):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")
    data = get_category_breakdown(db, group_id)
    return [CategorySpending(**item) for item in data]


@router.get("/contributions", response_model=list[MemberContribution])
def get_contributions(group_id: int, db: Session = Depends(get_db)):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")
    data = get_member_contributions(db, group_id)
    return [MemberContribution(**item) for item in data]


@router.get("/budget", response_model=BudgetStatus)
def get_budget(group_id: int, db: Session = Depends(get_db)):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")
    data = get_budget_status(db, group_id)
    return BudgetStatus(**data)


@router.get("/forecast", response_model=SpendingForecast)
def get_forecast(group_id: int, db: Session = Depends(get_db)):
    try:
        data = get_spending_forecast(db, group_id)
        return SpendingForecast(**data)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/recommendations", response_model=list[HistoricalRecommendation])
def get_recommendations(group_id: int, db: Session = Depends(get_db)):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")
    data = get_historical_recommendations(db, group_id)
    return [HistoricalRecommendation(**item) for item in data]


@router.get("/timeline")
def get_group_activity_timeline(group_id: int, db: Session = Depends(get_db)):
    """
    Chronological activity timeline connecting expenses, receipts,
    evidence uploads, and settlement transactions for the group.
    """
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    members = db.query(Member).filter(Member.group_id == group_id).all()
    member_map = {m.id: m.name for m in members}

    expenses = db.query(Expense).filter(Expense.group_id == group_id).all()
    evidences = db.query(ExpenseEvidence).filter(ExpenseEvidence.group_id == group_id).all()
    settlements = db.query(Settlement).filter(Settlement.group_id == group_id).all()
    transactions = db.query(PaymentTransaction).filter(PaymentTransaction.group_id == group_id).all()

    timeline_items = []

    # 1. Group creation event
    timeline_items.append({
        "type": "group_created",
        "timestamp": group.created_at,
        "title": f"Group Created: {group.name}",
        "description": f"Activity: {group.activity_type.capitalize()} · Target Budget: ₹{(group.budget_paise or 0) / 100:.2f}",
        "badge": "Group",
        "color": "purple"
    })

    # 2. Expenses
    for exp in expenses:
        timeline_items.append({
            "type": "expense",
            "timestamp": exp.expense_date or exp.created_at,
            "title": f"Expense: {exp.description}",
            "amount_paise": exp.total_amount_paise,
            "description": f"Paid by {member_map.get(exp.paid_by_member_id, 'Member')} · Category: {exp.category}",
            "badge": exp.category,
            "color": "blue",
            "id": exp.id
        })

    # 3. Evidence Uploads
    for ev in evidences:
        uploader = member_map.get(ev.uploaded_by_member_id, "Member") if ev.uploaded_by_member_id else "Member"
        timeline_items.append({
            "type": "evidence",
            "timestamp": ev.upload_time,
            "title": f"Evidence Uploaded: {ev.filename}",
            "description": f"Uploaded by {uploader} · Type: {ev.file_type.upper()} · Status: {ev.status}",
            "badge": ev.file_type.capitalize(),
            "color": "orange",
            "id": ev.id,
            "link_status": ev.link_status
        })

    # 4. Settlements
    for st in settlements:
        from_name = member_map.get(st.from_member_id, "Member")
        to_name = member_map.get(st.to_member_id, "Member")
        st_date = st.completed_at or st.created_at
        timeline_items.append({
            "type": "settlement",
            "timestamp": st_date,
            "title": f"Settlement: {from_name} → {to_name}",
            "amount_paise": st.amount_paise,
            "description": f"Status: {st.status.upper()} · Provider: {st.payment_provider or 'Manual'}",
            "badge": "Settlement",
            "color": "green" if st.status == "completed" else "yellow",
            "id": st.id
        })

    # 5. Payment transactions (PayPal)
    for tx in transactions:
        timeline_items.append({
            "type": "payment_transaction",
            "timestamp": tx.updated_at or tx.created_at,
            "title": f"PayPal Sandbox: Order #{tx.order_id[:8]}",
            "amount_paise": tx.amount_paise,
            "description": f"Status: {tx.status} · Currency: {tx.currency}",
            "badge": "PayPal",
            "color": "indigo",
            "id": tx.id
        })

    # Sort descending by timestamp
    timeline_items.sort(key=lambda x: x["timestamp"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    return {
        "group_id": group_id,
        "count": len(timeline_items),
        "timeline": timeline_items
    }
