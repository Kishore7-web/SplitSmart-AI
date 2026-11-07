from app.database.models import Group, Member
from app.schemas.members import MemberCreate, MemberResponse


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Group
from app.schemas.groups import GroupCreate, GroupResponse


router = APIRouter(
    prefix="/api/groups",
    tags=["Groups"]
)


@router.post(
    "/",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED
)
def create_group(
    group_data: GroupCreate,
    db: Session = Depends(get_db)
):
    new_group = Group(
        name=group_data.name.strip(),
        description=group_data.description
    )

    db.add(new_group)
    db.commit()
    db.refresh(new_group)

    return new_group


@router.get("/", response_model=list[GroupResponse])
def get_all_groups(db: Session = Depends(get_db)):
    return db.query(Group).order_by(Group.id.desc()).all()


@router.get("/{group_id}", response_model=GroupResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()

    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    return group


@router.post(
    "/{group_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED
)
def add_member(
    group_id: int,
    member_data: MemberCreate,
    db: Session = Depends(get_db)
):
    group = db.query(Group).filter(Group.id == group_id).first()

    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    member = Member(
        group_id=group_id,
        name=member_data.name.strip(),
        email=member_data.email
    )

    db.add(member)
    db.commit()
    db.refresh(member)

    return member


@router.get(
    "/{group_id}/members",
    response_model=list[MemberResponse]
)
def get_group_members(
    group_id: int,
    db: Session = Depends(get_db)
):
    group = db.query(Group).filter(Group.id == group_id).first()

    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    return (
        db.query(Member)
        .filter(Member.group_id == group_id)
        .order_by(Member.id)
        .all()
    )

