from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Text,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


# --------------------------------------------------
# 0. USER TABLE (Authentication & Authorization)
# --------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    memberships: Mapped[list["Member"]] = relationship(
        back_populates="user",
        foreign_keys="Member.user_id",
    )


# --------------------------------------------------
# 1. GROUP TABLE
# --------------------------------------------------

class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activity_type: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    budget_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    members: Mapped[list["Member"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

    activities: Mapped[list["Activity"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

    categories: Mapped[list["CustomCategory"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

    custom_fields: Mapped[list["CustomField"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

    roles: Mapped[list["CustomRole"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

    settlements: Mapped[list["Settlement"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

    evidences: Mapped[list["ExpenseEvidence"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

    transactions: Mapped[list["PaymentTransaction"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

    conversation_logs: Mapped[list["AIConversationLog"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


# --------------------------------------------------
# 2. ACTIVITY TABLE (Specific Events/Sub-activities)
# --------------------------------------------------

class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    budget_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, completed, archived

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    group: Mapped["Group"] = relationship(back_populates="activities")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="activity")
    evidences: Mapped[list["ExpenseEvidence"]] = relationship(back_populates="activity")


# --------------------------------------------------
# 3. CUSTOM CATEGORY TABLE
# --------------------------------------------------

class CustomCategory(Base):
    __tablename__ = "custom_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(30), nullable=True)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    group: Mapped["Group"] = relationship(back_populates="categories")


# --------------------------------------------------
# 4. CUSTOM FIELDS TABLES
# --------------------------------------------------

class CustomField(Base):
    __tablename__ = "custom_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[str] = mapped_column(String(30), default="text", nullable=False)  # text, number, date, select
    options_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str] = mapped_column(String(30), default="group", nullable=False)  # group, activity, expense
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    group: Mapped["Group"] = relationship(back_populates="custom_fields")
    values: Mapped[list["CustomFieldValue"]] = relationship(
        back_populates="field",
        cascade="all, delete-orphan",
    )


class CustomFieldValue(Base):
    __tablename__ = "custom_field_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    field_id: Mapped[int] = mapped_column(
        ForeignKey("custom_fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    field: Mapped["CustomField"] = relationship(back_populates="values")


# --------------------------------------------------
# 5. CUSTOM ROLES & PERMISSIONS
# --------------------------------------------------

class CustomRole(Base):
    __tablename__ = "custom_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    group: Mapped["Group"] = relationship(back_populates="roles")
    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    members: Mapped[list["Member"]] = relationship(
        back_populates="custom_role",
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("custom_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_key: Mapped[str] = mapped_column(String(50), nullable=False)

    role: Mapped["CustomRole"] = relationship(back_populates="permissions")


# --------------------------------------------------
# 6. MEMBER TABLE
# --------------------------------------------------

class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    custom_role_id: Mapped[int | None] = mapped_column(
        ForeignKey("custom_roles.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    role: Mapped[str] = mapped_column(String(30), default="member", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group: Mapped["Group"] = relationship(back_populates="members")
    user: Mapped["User | None"] = relationship(back_populates="memberships", foreign_keys=[user_id])
    custom_role: Mapped["CustomRole | None"] = relationship(back_populates="members", foreign_keys=[custom_role_id])

    paid_expenses: Mapped[list["Expense"]] = relationship(
        back_populates="payer",
        foreign_keys="Expense.paid_by_member_id",
    )

    expense_shares: Mapped[list["ExpenseShare"]] = relationship(
        back_populates="member",
    )

    sent_settlements: Mapped[list["Settlement"]] = relationship(
        back_populates="sender",
        foreign_keys="Settlement.from_member_id",
    )

    received_settlements: Mapped[list["Settlement"]] = relationship(
        back_populates="receiver",
        foreign_keys="Settlement.to_member_id",
    )

    uploaded_evidences: Mapped[list["ExpenseEvidence"]] = relationship(
        back_populates="uploader",
    )


# --------------------------------------------------
# 7. EXPENSE TABLE
# --------------------------------------------------

class Expense(Base):
    __tablename__ = "expenses"

    __table_args__ = (
        CheckConstraint(
            "total_amount_paise > 0",
            name="check_expense_amount_positive",
        ),
        CheckConstraint(
            "split_type IN ('equal', 'custom', 'percentage')",
            name="check_expense_split_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
    )

    paid_by_member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id"),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(String(300), nullable=False)
    total_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    split_type: Mapped[str] = mapped_column(String(20), default="equal", nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="General", nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(150), nullable=True)
    expense_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="confirmed", nullable=False)  # draft, confirmed

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    group: Mapped["Group"] = relationship(back_populates="expenses")
    activity: Mapped["Activity | None"] = relationship(back_populates="expenses")

    payer: Mapped["Member"] = relationship(
        back_populates="paid_expenses",
        foreign_keys=[paid_by_member_id],
    )

    shares: Mapped[list["ExpenseShare"]] = relationship(
        back_populates="expense",
        cascade="all, delete-orphan",
    )

    evidences: Mapped[list["ExpenseEvidence"]] = relationship(
        back_populates="expense",
    )


# --------------------------------------------------
# 8. EXPENSE SHARE TABLE
# --------------------------------------------------

class ExpenseShare(Base):
    __tablename__ = "expense_shares"

    __table_args__ = (
        UniqueConstraint(
            "expense_id",
            "member_id",
            name="unique_expense_member_share",
        ),
        CheckConstraint(
            "amount_paise >= 0",
            name="check_share_amount_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    expense_id: Mapped[int] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=False,
    )

    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id"),
        nullable=False,
    )

    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    expense: Mapped["Expense"] = relationship(back_populates="shares")
    member: Mapped["Member"] = relationship(back_populates="expense_shares")


# --------------------------------------------------
# 9. SETTLEMENT TABLE
# --------------------------------------------------

class Settlement(Base):
    __tablename__ = "settlements"

    __table_args__ = (
        CheckConstraint(
            "amount_paise > 0",
            name="check_settlement_amount_positive",
        ),
        CheckConstraint(
            "from_member_id != to_member_id",
            name="check_different_settlement_members",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed', 'cancelled')",
            name="check_settlement_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )

    from_member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id"),
        nullable=False,
    )

    to_member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id"),
        nullable=False,
    )

    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    payment_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parent_settlement_id: Mapped[int | None] = mapped_column(ForeignKey("settlements.id", ondelete="SET NULL"), nullable=True)
    verified_by_member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    group: Mapped["Group"] = relationship(back_populates="settlements")

    sender: Mapped["Member"] = relationship(
        back_populates="sent_settlements",
        foreign_keys=[from_member_id],
    )

    receiver: Mapped["Member"] = relationship(
        back_populates="received_settlements",
        foreign_keys=[to_member_id],
    )

    transactions: Mapped[list["PaymentTransaction"]] = relationship(
        back_populates="settlement",
    )


# --------------------------------------------------
# 10. EXPENSE EVIDENCE TABLE
# --------------------------------------------------

class ExpenseEvidence(Base):
    __tablename__ = "expense_evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
    )

    uploaded_by_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # image, pdf, audio, video, whatsapp_export, text
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    upload_time: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )  # pending, processed, failed, review_needed

    extracted_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    expense_id: Mapped[int | None] = mapped_column(
        ForeignKey("expenses.id", ondelete="SET NULL"),
        nullable=True,
    )

    link_status: Mapped[str] = mapped_column(
        String(30),
        default="unmatched",
        nullable=False,
    )  # unmatched, suggested, confirmed

    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    group: Mapped["Group"] = relationship(back_populates="evidences")
    activity: Mapped["Activity | None"] = relationship(back_populates="evidences")
    uploader: Mapped["Member"] = relationship(back_populates="uploaded_evidences")
    expense: Mapped["Expense"] = relationship(back_populates="evidences")


# --------------------------------------------------
# 11. PAYMENT TRANSACTION TABLE
# --------------------------------------------------

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    settlement_id: Mapped[int | None] = mapped_column(
        ForeignKey("settlements.id", ondelete="SET NULL"),
        nullable=True,
    )

    order_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    capture_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)

    status: Mapped[str] = mapped_column(
        String(30),
        default="CREATED",
        nullable=False,
    )  # CREATED, APPROVAL_PENDING, APPROVED, CAPTURED, FAILED, CANCELLED

    payer_email: Mapped[str | None] = mapped_column(String(150), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    group: Mapped["Group"] = relationship(back_populates="transactions")
    settlement: Mapped["Settlement"] = relationship(back_populates="transactions")


# --------------------------------------------------
# 12. AI CONVERSATION LOG TABLE
# --------------------------------------------------

class AIConversationLog(Base):
    __tablename__ = "ai_conversation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    group: Mapped["Group | None"] = relationship(back_populates="conversation_logs")
