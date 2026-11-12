import json
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi import HTTPException

from app.database.models import (
    User,
    Group,
    Member,
    Activity,
    Expense,
    ExpenseShare,
    Settlement,
    ExpenseEvidence,
    PaymentTransaction,
    CustomCategory,
    CustomField,
    CustomRole,
    RolePermission,
)
from app.schemas.auth import UserRegister, UserLogin
from app.schemas.groups import GroupCreate, GroupUpdate
from app.schemas.members import MemberCreate, MemberUpdate
from app.schemas.activities import ActivityCreate, ActivityUpdate
from app.schemas.customization import CategoryCreate, CategoryUpdate, CustomFieldCreate, RoleCreate
from app.schemas.expenses import ExpenseCreate, ExpenseUpdate, ExpenseShareCreate
from app.schemas.settlements import SettlementCreate
from app.schemas.ai import (
    AIGroupProposalRequest,
    AIGroupRefineRequest,
    AIGroupConfirmRequest,
    AIToolExecuteRequest,
    AIParseRequest,
    AIDraftExpenseConfirm,
    AIChatRequest,
)

from app.routes.auth import register, login, get_me
from app.routes.groups import (
    create_group,
    get_all_groups,
    get_group,
    update_group,
    archive_group,
    restore_group,
    delete_group,
    add_member,
    get_group_members,
    update_member,
    remove_member,
)
from app.routes.activities import (
    create_activity,
    list_activities,
    get_activity,
    update_activity,
    delete_activity,
)
from app.routes.customization import (
    list_categories,
    create_category,
    update_category,
    delete_category,
    list_custom_fields,
    create_custom_field,
    delete_custom_field,
    list_custom_roles,
    create_custom_role,
    update_custom_role,
    delete_custom_role,
)
from app.routes.expenses import (
    create_expense,
    get_expenses,
    get_expense,
    update_expense,
    delete_expense,
)
from app.routes.settlements import (
    create_settlement,
    complete_settlement,
    cancel_settlement,
    get_group_balances,
    get_simplified_settlements,
    get_settlement_summary,
    get_settlement_history,
)
from app.routes.ai import (
    propose_group_from_description,
    refine_group_proposal_endpoint,
    confirm_group_creation,
    execute_controlled_tool,
    parse_expense,
    confirm_draft_expense,
    chat_with_financial_assistant,
    get_ai_status,
)
from app.services.expense_calculator import (
    calculate_equal_split,
    calculate_custom_split,
    calculate_percentage_split,
)
from app.services.settlement_engine import calculate_member_balances, simplify_debts
from app.services.paypal_service import convert_paise_to_usd, is_paypal_configured
from app.core.auth import hash_password, verify_password


# =============================================================================
# 1. AUTHENTICATION & SECURITY TESTS
# =============================================================================

def test_password_hashing():
    pwd = "SecurePassword123!"
    hashed = hash_password(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_user_registration_and_login(db):
    from fastapi import Response
    resp = Response()

    reg_data = UserRegister(
        username="lead_organizer",
        email="lead@splitsmart.org",
        password="TopSecretPassword2026!",
        full_name="Lead Organizer"
    )
    token_res = register(reg_data, response=resp, db=db)
    assert token_res.access_token
    assert token_res.user.username == "lead_organizer"

    # Login
    login_data = UserLogin(
        username_or_email="lead@splitsmart.org",
        password="TopSecretPassword2026!"
    )
    login_res = login(login_data, response=resp, db=db)
    assert login_res.access_token
    assert login_res.user.id == token_res.user.id


# =============================================================================
# 2. GROUP MANAGEMENT, ARCHIVING & DELETION TESTS
# =============================================================================

def test_group_lifecycle_and_archiving(db):
    grp = create_group(
        GroupCreate(
            name="Symposium Core Team",
            description="Organizing Annual Techfest",
            activity_type="college_symposium",
            budget_paise=5000000,
            currency="INR"
        ),
        user=None,
        db=db
    )
    assert grp.id > 0
    assert grp.is_archived is False

    # Archive
    archived = archive_group(grp.id, user=None, db=db)
    assert archived.is_archived is True
    assert archived.archived_at is not None

    # Filter archived
    active_groups = get_all_groups(include_archived=False, user=None, db=db)
    assert grp.id not in [g.id for g in active_groups]

    all_groups = get_all_groups(include_archived=True, user=None, db=db)
    assert grp.id in [g.id for g in all_groups]

    # Restore
    restored = restore_group(grp.id, user=None, db=db)
    assert restored.is_archived is False

    # Safe Delete
    delete_group(grp.id, user=None, db=db)
    with pytest.raises(HTTPException):
        get_group(grp.id, db=db)


# =============================================================================
# 3. MEMBER MANAGEMENT & ROLE PERMISSION ENFORCEMENT
# =============================================================================

def test_member_management_and_owner_protection(db):
    grp = create_group(GroupCreate(name="Role Test Group"), user=None, db=db)

    # First member automatically becomes owner
    owner = add_member(grp.id, MemberCreate(name="Alice", role="owner"), user=None, db=db)
    assert owner.role == "owner"

    member2 = add_member(grp.id, MemberCreate(name="Bob", role="member"), user=None, db=db)
    assert member2.role == "member"

    # Try to demote last owner -> should raise HTTPException(400)
    with pytest.raises(HTTPException) as exc:
        update_member(grp.id, owner.id, MemberUpdate(role="member"), user=None, db=db)
    assert exc.value.status_code == 400
    assert "last remaining owner" in exc.value.detail

    # Try to delete last owner -> should raise HTTPException(400)
    with pytest.raises(HTTPException) as exc:
        remove_member(grp.id, owner.id, user=None, db=db)
    assert exc.value.status_code == 400
    assert "last remaining owner" in exc.value.detail

    # Promote Bob to owner, now Alice can be demoted or removed safely
    update_member(grp.id, member2.id, MemberUpdate(role="owner"), user=None, db=db)
    demoted = update_member(grp.id, owner.id, MemberUpdate(role="member"), user=None, db=db)
    assert demoted.role == "member"


# =============================================================================
# 4. CUSTOM ACTIVITIES & CATEGORIES
# =============================================================================

def test_custom_activities_and_budgets(db):
    grp = create_group(GroupCreate(name="Techfest 2026", budget_paise=10000000), user=None, db=db)

    # Create Custom Activity "Stage Lighting" with ₹2,500 budget (250,000 paise)
    act = create_activity(
        grp.id,
        ActivityCreate(
            name="Stage Lighting",
            description="Professional concert lighting and trusses",
            budget_paise=250000
        ),
        user=None,
        db=db
    )
    assert act.id > 0
    assert act.name == "Stage Lighting"
    assert act.budget_paise == 250000

    # List activities
    acts = list_activities(grp.id, db=db)
    assert len(acts) == 1
    assert acts[0].name == "Stage Lighting"

    # Update activity budget to ₹4,000 (400,000 paise)
    updated_act = update_activity(
        grp.id,
        act.id,
        ActivityUpdate(budget_paise=400000),
        user=None,
        db=db
    )
    assert updated_act.budget_paise == 400000

    # Delete activity safely
    delete_activity(grp.id, act.id, user=None, db=db)
    assert len(list_activities(grp.id, db=db)) == 0


def test_custom_categories_and_renaming(db):
    grp = create_group(GroupCreate(name="Category Test Group"), user=None, db=db)
    m = add_member(grp.id, MemberCreate(name="Charlie"), user=None, db=db)

    # Create new custom category
    cat = create_category(grp.id, CategoryCreate(name="Venue Rentals", icon="building", color="#4f46e5"), user=None, db=db)
    assert cat.name == "Venue Rentals"

    # Record expense under this category
    exp = create_expense(
        grp.id,
        ExpenseCreate(
            description="Auditorium Advance",
            total_amount_paise=500000,
            paid_by_member_id=m.id,
            split_type="equal",
            participant_ids=[m.id],
            category="Venue Rentals"
        ),
        user=None,
        db=db
    )
    assert exp.category == "Venue Rentals"

    # Rename category to "Auditorium & Halls"
    updated_cat = update_category(grp.id, cat.id, CategoryUpdate(name="Auditorium & Halls"), user=None, db=db)
    assert updated_cat.name == "Auditorium & Halls"

    # Expense should automatically reflect the updated category name
    fetched_exp = get_expense(grp.id, exp.id, db=db)
    assert fetched_exp.category == "Auditorium & Halls"

    # Deleting category moves expenses to "General"
    delete_category(grp.id, cat.id, user=None, db=db)
    fetched_exp_after = get_expense(grp.id, exp.id, db=db)
    assert fetched_exp_after.category == "General"


# =============================================================================
# 5. FINANCIAL CALCULATION ENGINE & LEDGER ACCURACY
# =============================================================================

def test_financial_ledger_zero_sum_reconciliation(db):
    """
    Ensure the sum of all member net balances strictly reconciles to zero
    across complex multi-payer and custom split scenarios.
    """
    grp = create_group(GroupCreate(name="Ledger Test Group"), user=None, db=db)
    m1 = add_member(grp.id, MemberCreate(name="Arun"), user=None, db=db)
    m2 = add_member(grp.id, MemberCreate(name="Bala"), user=None, db=db)
    m3 = add_member(grp.id, MemberCreate(name="Chitra"), user=None, db=db)
    m4 = add_member(grp.id, MemberCreate(name="Deepak"), user=None, db=db)

    # Expense 1: Arun pays ₹12,000 split equally among all 4 (each owes ₹3,000)
    create_expense(
        grp.id,
        ExpenseCreate(
            description="Hotel Booking",
            total_amount_paise=1200000,
            paid_by_member_id=m1.id,
            split_type="equal",
            participant_ids=[m1.id, m2.id, m3.id, m4.id]
        ),
        user=None,
        db=db
    )

    # Expense 2: Bala pays ₹6,000 with custom split: Arun ₹2,000, Bala ₹1,000, Chitra ₹3,000
    create_expense(
        grp.id,
        ExpenseCreate(
            description="Special Dinner",
            total_amount_paise=600000,
            paid_by_member_id=m2.id,
            split_type="custom",
            participant_ids=[m1.id, m2.id, m3.id],
            custom_shares=[
                ExpenseShareCreate(member_id=m1.id, amount_paise=200000),
                ExpenseShareCreate(member_id=m2.id, amount_paise=100000),
                ExpenseShareCreate(member_id=m3.id, amount_paise=300000),
            ]
        ),
        user=None,
        db=db
    )

    # Expense 3: Chitra pays ₹4,000 with percentage split: Bala 50%, Deepak 50%
    create_expense(
        grp.id,
        ExpenseCreate(
            description="Cab Transport",
            total_amount_paise=400000,
            paid_by_member_id=m3.id,
            split_type="percentage",
            participant_ids=[m2.id, m4.id],
            percentage_shares={m2.id: 50.0, m4.id: 50.0}
        ),
        user=None,
        db=db
    )

    # Check Balances
    balances = get_group_balances(db, grp.id)

    # Net balance check: Sum of all balances MUST equal exactly 0
    total_net = sum(balances.values())
    assert total_net == 0, f"Ledger does not reconcile to zero: {total_net}"

    # Verify Arun: Paid 12,000. Shares: 3,000 (hotel) + 2,000 (dinner) = 5,000. Net = +7,000
    assert balances[m1.id] == 700000

    # Verify Deepak: Paid 0. Shares: 3,000 (hotel) + 2,000 (cab) = 5,000. Net = -5,000
    assert balances[m4.id] == -500000


# =============================================================================
# 6. EXPENSE EDITING AND RECALCULATION
# =============================================================================

def test_expense_editing_recalculation(db):
    grp = create_group(GroupCreate(name="Edit Test Group"), user=None, db=db)
    m1 = add_member(grp.id, MemberCreate(name="Payer"), user=None, db=db)
    m2 = add_member(grp.id, MemberCreate(name="Participant"), user=None, db=db)

    # Create expense of ₹2,000
    exp = create_expense(
        grp.id,
        ExpenseCreate(
            description="Initial Groceries",
            total_amount_paise=200000,
            paid_by_member_id=m1.id,
            split_type="equal",
            participant_ids=[m1.id, m2.id]
        ),
        user=None,
        db=db
    )
    assert exp.total_amount_paise == 200000

    bal1 = get_group_balances(db, grp.id)
    assert bal1[m1.id] == 100000
    assert bal1[m2.id] == -100000

    # Edit expense amount to ₹3,000
    updated_exp = update_expense(
        grp.id,
        exp.id,
        ExpenseUpdate(
            description="Revised Groceries with snacks",
            total_amount_paise=300000
        ),
        user=None,
        db=db
    )
    assert updated_exp.total_amount_paise == 300000

    bal2 = get_group_balances(db, grp.id)
    assert bal2[m1.id] == 150000
    assert bal2[m2.id] == -150000


# =============================================================================
# 7. SETTLEMENT ENGINE, PARTIAL SETTLEMENTS & CANCELLATION
# =============================================================================

def test_partial_settlement_workflow(db):
    grp = create_group(GroupCreate(name="Partial Settlement Group"), user=None, db=db)
    m1 = add_member(grp.id, MemberCreate(name="Creditor"), user=None, db=db)
    m2 = add_member(grp.id, MemberCreate(name="Debtor"), user=None, db=db)

    # Creditor pays ₹1,000 for Debtor -> Debtor owes ₹1,000 (100,000 paise)
    create_expense(
        grp.id,
        ExpenseCreate(
            description="Dinner Loan",
            total_amount_paise=100000,
            paid_by_member_id=m1.id,
            split_type="equal",
            participant_ids=[m2.id]
        ),
        user=None,
        db=db
    )

    bal_initial = get_group_balances(db, grp.id)
    assert bal_initial[m2.id] == -100000

    # Step 1: Debtor creates a partial settlement of ₹400 (40,000 paise)
    st_partial = create_settlement(
        grp.id,
        SettlementCreate(
            from_member_id=m2.id,
            to_member_id=m1.id,
            amount_paise=40000,
            payment_provider="manual",
            notes="Partial payment 1 of 2"
        ),
        user=None,
        db=db
    )
    assert st_partial.status == "pending"

    # IMPORTANT REQUIREMENT: Pending settlement must NOT reduce outstanding balance!
    bal_pending = get_group_balances(db, grp.id)
    assert bal_pending[m2.id] == -100000, "Pending settlement must not affect net balance"

    # Step 2: Complete the partial settlement
    complete_settlement(grp.id, st_partial.id, user=None, db=db)

    # Debtor's remaining balance MUST now be exactly ₹600 (60,000 paise)
    bal_after_partial = get_group_balances(db, grp.id)
    assert bal_after_partial[m2.id] == -60000
    assert bal_after_partial[m1.id] == 60000

    # Step 3: Cancellation test: create pending remaining settlement of ₹600 and cancel it
    st_cancel = create_settlement(
        grp.id,
        SettlementCreate(
            from_member_id=m2.id,
            to_member_id=m1.id,
            amount_paise=60000
        ),
        user=None,
        db=db
    )
    cancelled = cancel_settlement(grp.id, st_cancel.id, user=None, db=db)
    assert cancelled.status == "cancelled"

    # Balances remain unchanged after cancellation
    bal_after_cancel = get_group_balances(db, grp.id)
    assert bal_after_cancel[m2.id] == -60000


# =============================================================================
# 8. CONVERSATIONAL AI GROUP CREATION & FUNCTION CALLING
# =============================================================================

def test_conversational_ai_group_creation_flow(db):
    # Step 1: User prompt
    desc = "I am organizing a three-day college symposium with 8 participants and budget of ₹30,000. I want separate activities for food, decoration, transportation, accommodation, photography and stage arrangements."
    res = propose_group_from_description(AIGroupProposalRequest(description=desc))
    assert res["success"] is True
    proposal = res["proposal"]

    act_names = [a["name"].lower() for a in proposal["activities"]]
    assert any("food" in n for n in act_names)
    assert any("photography" in n for n in act_names)

    # Step 2: Conversational refinement ("Allocate ₹4,000 to photography", "Remove accommodation")
    refine_res1 = refine_group_proposal_endpoint(
        AIGroupRefineRequest(
            current_proposal=proposal,
            instruction="Allocate ₹4,000 to photography"
        )
    )
    refined_proposal = refine_res1["proposal"]
    photo_act = next((a for a in refined_proposal["activities"] if "photo" in a["name"].lower()), None)
    assert photo_act is not None
    assert float(photo_act["budget_rupees"]) == 4000.0

    refine_res2 = refine_group_proposal_endpoint(
        AIGroupRefineRequest(
            current_proposal=refined_proposal,
            instruction="Remove accommodation"
        )
    )
    final_proposal = refine_res2["proposal"]
    assert not any("accommodation" in a["name"].lower() for a in final_proposal["activities"])

    # Step 3: Confirmation -> Real Database Persistence
    created_group = confirm_group_creation(
        AIGroupConfirmRequest(structure=final_proposal),
        user=None,
        db=db
    )
    assert created_group.id > 0
    assert created_group.budget_paise == 3000000

    # Verify actual database records
    db_activities = list_activities(created_group.id, db=db)
    assert len(db_activities) >= 4
    assert any("photo" in a.name.lower() for a in db_activities)
    assert not any("accommodation" in a.name.lower() for a in db_activities)


def test_ai_controlled_tool_execution(db):
    grp = create_group(GroupCreate(name="Tool Execution Group", budget_paise=2000000), user=None, db=db)

    # 1. Execute create_activity tool
    res1 = execute_controlled_tool(
        AIToolExecuteRequest(
            tool_name="create_activity",
            tool_args={"group_id": grp.id, "name": "Stage Lighting", "budget_rupees": 2500.0}
        ),
        user=None,
        db=db
    )
    assert res1["success"] is True
    assert "Stage Lighting" in res1["name"]

    # 2. Execute update_group_budget tool
    res2 = execute_controlled_tool(
        AIToolExecuteRequest(
            tool_name="update_group_budget",
            tool_args={"group_id": grp.id, "budget_rupees": 35000.0}
        ),
        user=None,
        db=db
    )
    assert res2["success"] is True

    updated_grp = get_group(grp.id, db=db)
    assert updated_grp.budget_paise == 3500000

    # 3. Execute retrieve_group_summary tool
    res3 = execute_controlled_tool(
        AIToolExecuteRequest(
            tool_name="retrieve_group_summary",
            tool_args={"group_id": grp.id}
        ),
        user=None,
        db=db
    )
    assert "Tool Execution Group" in res3["group_name"]


# =============================================================================
# 9. PAYPAL SANDBOX INTEGRATION & CONVERSION
# =============================================================================

def test_paypal_amount_conversion_and_rounding():
    # 85 INR = 8500 paise = 1.00 USD
    usd, inr, rate = convert_paise_to_usd(8500)
    assert usd == "1.00"
    assert inr == "85.00"
    assert rate == 85.0

    # 250 INR = 25000 paise = 2.94 USD
    usd2, inr2, _ = convert_paise_to_usd(25000)
    assert usd2 == "2.94"
    assert inr2 == "250.00"
