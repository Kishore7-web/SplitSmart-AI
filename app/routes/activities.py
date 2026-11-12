from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Group, Activity, Expense
from app.schemas.activities import ActivityCreate, ActivityUpdate, ActivityResponse
from app.core.auth import get_optional_current_user, check_group_permission, User


router = APIRouter(
    prefix="/api/groups/{group_id}/activities",
    tags=["Activities & Sub-events"]
)


def enrich_activity_response(activity: Activity, db: Session) -> ActivityResponse:
    expenses = db.query(Expense).filter(Expense.activity_id == activity.id).all()
    spent = sum(e.total_amount_paise for e in expenses)
    budget = activity.budget_paise or 0
    rem = budget - spent if budget > 0 else 0

    return ActivityResponse(
        id=activity.id,
        group_id=activity.group_id,
        name=activity.name,
        description=activity.description,
        budget_paise=budget,
        start_date=activity.start_date,
        end_date=activity.end_date,
        status=activity.status or "active",
        created_at=activity.created_at,
        spent_paise=spent,
        remaining_paise=rem,
        expense_count=len(expenses)
    )


@router.post("/", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
def create_activity(
    group_id: int,
    data: ActivityCreate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    check_group_permission(db, group_id, user, "manage_activities")

    activity = Activity(
        group_id=group_id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        budget_paise=data.budget_paise,
        start_date=data.start_date,
        end_date=data.end_date,
        status="active"
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)

    return enrich_activity_response(activity, db)


@router.get("/", response_model=list[ActivityResponse])
def list_activities(
    group_id: int,
    status_filter: str | None = None,
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    query = db.query(Activity).filter(Activity.group_id == group_id)
    if status_filter:
        query = query.filter(Activity.status == status_filter)

    activities = query.order_by(Activity.id.asc()).all()
    return [enrich_activity_response(a, db) for a in activities]


@router.get("/{activity_id}", response_model=ActivityResponse)
def get_activity(group_id: int, activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.group_id == group_id
    ).first()
    if not activity:
        raise HTTPException(404, "Activity not found")

    return enrich_activity_response(activity, db)


@router.patch("/{activity_id}", response_model=ActivityResponse)
def update_activity(
    group_id: int,
    activity_id: int,
    data: ActivityUpdate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.group_id == group_id
    ).first()
    if not activity:
        raise HTTPException(404, "Activity not found")

    check_group_permission(db, group_id, user, "manage_activities")

    if data.name is not None:
        activity.name = data.name.strip()
    if data.description is not None:
        activity.description = data.description.strip() if data.description else None
    if data.budget_paise is not None:
        activity.budget_paise = data.budget_paise
    if data.start_date is not None:
        activity.start_date = data.start_date
    if data.end_date is not None:
        activity.end_date = data.end_date
    if data.status is not None:
        activity.status = data.status

    db.commit()
    db.refresh(activity)
    return enrich_activity_response(activity, db)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    group_id: int,
    activity_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.group_id == group_id
    ).first()
    if not activity:
        raise HTTPException(404, "Activity not found")

    check_group_permission(db, group_id, user, "manage_activities")

    # Unlink any associated expenses before deleting activity
    db.query(Expense).filter(Expense.activity_id == activity_id).update({"activity_id": None})
    db.delete(activity)
    db.commit()
