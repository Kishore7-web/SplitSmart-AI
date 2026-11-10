import json
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException

from app.database.database import SessionLocal
from app.database.models import Group, Member, Expense, ExpenseShare, Settlement, ExpenseEvidence, PaymentTransaction
from app.schemas.groups import GroupCreate
from app.schemas.members import MemberCreate
from app.schemas.expenses import ExpenseCreate
from app.schemas.ai import AIParseRequest, AIDraftExpenseConfirm
from app.schemas.settlements import SettlementCreate

from app.routes.groups import create_group, get_group, get_group_members, add_member
from app.routes.expenses import create_expense, get_expenses
from app.routes.settlements import create_settlement, complete_settlement, get_group_balances, get_simplified_settlements
from app.routes.ai import parse_expense, confirm_draft_expense, extract_expense_details
from app.routes.analytics import get_group_activity_timeline

from app.services.expense_calculator import (
    calculate_equal_split,
    calculate_custom_split,
    calculate_percentage_split,
)
from app.services.settlement_engine import calculate_member_balances, simplify_debts
from app.services.duplicate_detector import compute_file_hash, check_evidence_duplicate
from app.services.whatsapp_parser import parse_whatsapp_chat
from app.services.financial_analyst import (
    get_group_financial_overview,
    get_category_breakdown,
    get_member_contributions,
    get_budget_status,
    get_spending_forecast,
    get_historical_recommendations,
)
from app.services.ai_service import parse_expense_with_ai, answer_financial_query
from app.services.paypal_service import convert_paise_to_usd, is_paypal_configured


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# SCENARIO 1: Create Group with Activity Type, Budget, Dates, and Members
# ---------------------------------------------------------------------------

def test_scenario_1_create_group_and_members(db):
    # 1. Create a trip group with target budget and dates
    group_data = GroupCreate(
        name="Manali Expedition 2026",
        description="College graduation trip to the Himalayas",
        activity_type="trip",
        start_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 6, 7, tzinfo=timezone.utc),
        budget_paise=6000000,  # ₹60,000.00
        currency="INR"
    )
    group = create_group(group_data=group_data, db=db)
    assert group.id > 0
    assert group.name == "Manali Expedition 2026"
    assert group.activity_type == "trip"
    assert group.budget_paise == 6000000
    assert group.currency == "INR"

    # 2. Add Owner and Members
    m1 = add_member(group.id, MemberCreate(name="Arun", email="arun@example.com", phone="+91 98765 00001", role="owner"), db=db)
    assert m1.role == "owner"

    m2 = add_member(group.id, MemberCreate(name="Bala", email="bala@example.com", role="admin"), db=db)
    assert m2.role == "admin"

    m3 = add_member(group.id, MemberCreate(name="Chitra", role="member"), db=db)
    assert m3.role == "member"

    # Verify members
    members = get_group_members(group.id, db=db)
    assert len(members) == 3
    names = [m.name for m in members]
    assert "Arun" in names and "Bala" in names and "Chitra" in names


# ---------------------------------------------------------------------------
# SCENARIO 2: Natural Language Expense Parsing & Draft Confirmation
# ---------------------------------------------------------------------------

def test_scenario_2_ai_nl_expense_draft_flow(db):
    grp = create_group(GroupCreate(name="Roommates Flat 301", activity_type="roommates", budget_paise=4000000), db=db)
    m_arun = add_member(grp.id, MemberCreate(name="Arun"), db=db)
    m_rahul = add_member(grp.id, MemberCreate(name="Rahul"), db=db)

    # Step 1: Parse natural language text
    parse_req = AIParseRequest(
        group_id=grp.id,
        text="Arun paid 1500 rupees for dinner with Rahul",
        current_member_id=m_arun.id
    )
    parsed = parse_expense(parse_req, db=db)

    assert parsed.amount_paise == 150000  # ₹1,500.00
    assert parsed.paid_by_member_id == m_arun.id
    assert m_arun.id in parsed.participant_ids
    assert m_rahul.id in parsed.participant_ids
    assert parsed.category == "Food & Dining"

    # Step 2: Confirm the draft into database
    draft_confirm = AIDraftExpenseConfirm(
        group_id=grp.id,
        description=parsed.description,
        total_amount_paise=parsed.amount_paise,
        paid_by_member_id=parsed.paid_by_member_id,
        participant_ids=parsed.participant_ids,
        split_type="equal",
        category=parsed.category
    )
    saved = confirm_draft_expense(draft_confirm, db=db)
    assert saved.total_amount_paise == 150000
    assert len(saved.shares) == 2
    assert sum(s.amount_paise for s in saved.shares) == 150000


# ---------------------------------------------------------------------------
# SCENARIO 3 & 4: Receipt Extraction & Duplicate Detection
# ---------------------------------------------------------------------------

def test_scenario_3_and_4_evidence_duplicate_detection(db):
    grp = create_group(GroupCreate(name="Evidence Test Group"), db=db)
    m = add_member(grp.id, MemberCreate(name="Tester"), db=db)

    # 1. Compute hash of sample receipt bytes
    sample_receipt_bytes = b"RECEIPT_TAJ_HOTEL_DINNER_2400_RUPEES_FOR_GROUP"
    file_hash = compute_file_hash(sample_receipt_bytes)

    # Insert initial evidence
    ev1 = ExpenseEvidence(
        group_id=grp.id,
        uploaded_by_member_id=m.id,
        filename="taj_hotel_bill.jpg",
        stored_filename="uuid_taj_hotel_bill.jpg",
        file_type="image",
        file_size=len(sample_receipt_bytes),
        file_hash=file_hash,
        upload_time=datetime.now(timezone.utc),
        status="processed",
        extracted_data_json=json.dumps({"merchant_name": "Taj Hotel", "total_amount_rupees": "2400.00"})
    )
    db.add(ev1)
    db.commit()

    # 2. Exact Hash Duplicate Detection
    dup_report_exact = check_evidence_duplicate(
        db=db,
        group_id=grp.id,
        file_hash=file_hash,
        current_evidence_id=None
    )
    assert dup_report_exact["is_duplicate"] is True
    assert dup_report_exact["duplicate_type"] == "exact_hash"
    assert dup_report_exact["matched_evidence_id"] == ev1.id

    # 3. Fuzzy Duplicate Detection (Same Amount and Merchant)
    exp = create_expense(
        grp.id,
        ExpenseCreate(
            description="Taj Hotel Dinner",
            total_amount_paise=240000,
            paid_by_member_id=m.id,
            split_type="equal",
            participant_ids=[m.id],
            category="Food & Dining",
            merchant="Taj Hotel"
        ),
        db=db
    )

    dup_report_fuzzy = check_evidence_duplicate(
        db=db,
        group_id=grp.id,
        file_hash="different_hash_from_another_photo",
        extracted_amount_paise=240000,
        extracted_merchant="Taj Hotel",
        description="Dinner at Taj Hotel"
    )
    assert dup_report_fuzzy["is_duplicate"] is True
    assert dup_report_fuzzy["duplicate_type"] == "fuzzy_similarity"
    assert dup_report_fuzzy["matched_expense_id"] == exp.id


# ---------------------------------------------------------------------------
# SCENARIO 5: Financial Analysis, Budgets, and Balances
# ---------------------------------------------------------------------------

def test_scenario_5_financial_analysis(db):
    grp = create_group(GroupCreate(name="Analytics Suite Group", budget_paise=1000000), db=db)
    m1 = add_member(grp.id, MemberCreate(name="Alice"), db=db)
    m2 = add_member(grp.id, MemberCreate(name="Bob"), db=db)

    # Alice pays ₹4,000 for Food
    create_expense(
        grp.id,
        ExpenseCreate(
            description="Team Feast",
            total_amount_paise=400000,
            paid_by_member_id=m1.id,
            split_type="equal",
            participant_ids=[m1.id, m2.id],
            category="Food & Dining"
        ),
        db=db
    )

    # Bob pays ₹2,000 for Taxi
    create_expense(
        grp.id,
        ExpenseCreate(
            description="Airport Taxi",
            total_amount_paise=200000,
            paid_by_member_id=m2.id,
            split_type="equal",
            participant_ids=[m1.id, m2.id],
            category="Transportation"
        ),
        db=db
    )

    # Test Overview
    overview = get_group_financial_overview(db, grp.id)
    assert overview["total_budget_paise"] == 1000000
    assert overview["total_expense_paise"] == 600000  # ₹6,000.00
    assert overview["remaining_budget_paise"] == 400000  # ₹4,000.00
    assert overview["budget_consumed_percentage"] == 60.0

    # Test Categories
    cats = get_category_breakdown(db, grp.id)
    cat_map = {c["category"]: c["amount_paise"] for c in cats}
    assert cat_map["Food & Dining"] == 400000
    assert cat_map["Transportation"] == 200000

    # Test Contributions
    contribs = get_member_contributions(db, grp.id)
    c_map = {c["member_name"]: c for c in contribs}
    assert c_map["Alice"]["paid_paise"] == 400000
    assert c_map["Alice"]["owed_paise"] == 300000
    assert c_map["Alice"]["net_balance_paise"] == 100000  # +₹1,000 to receive

    assert c_map["Bob"]["paid_paise"] == 200000
    assert c_map["Bob"]["owed_paise"] == 300000
    assert c_map["Bob"]["net_balance_paise"] == -100000  # -₹1,000 to pay

    # Test Budget Status
    b_status = get_budget_status(db, grp.id)
    assert b_status["status_level"] == "safe"
    assert "₹4,000.00 remaining" in b_status["alert_message"]


# ---------------------------------------------------------------------------
# SCENARIO 6: AI Financial Assistant Grounded DB Queries
# ---------------------------------------------------------------------------

def test_scenario_6_ai_assistant_grounded_answers(db):
    grp = create_group(GroupCreate(name="Wedding Planning", budget_paise=5000000), db=db)
    arun = add_member(grp.id, MemberCreate(name="Arun"), db=db)
    add_member(grp.id, MemberCreate(name="Deepak"), db=db)

    create_expense(
        grp.id,
        ExpenseCreate(
            description="Floral Stage Decor",
            total_amount_paise=180000,
            paid_by_member_id=arun.id,
            split_type="equal",
            participant_ids=[arun.id],
            category="Tickets & Events"
        ),
        db=db
    )

    # 1. Ask total spent
    ans1 = answer_financial_query(db, grp.id, "How much have we spent so far?")
    assert "₹1,800.00" in ans1["reply"]

    # 2. Ask who paid what
    ans2 = answer_financial_query(db, grp.id, "How much has Arun paid?")
    assert "Arun" in ans2["reply"]
    assert "₹1,800.00" in ans2["reply"]

    # 3. Ask highest expense
    ans3 = answer_financial_query(db, grp.id, "What was our highest expense?")
    assert "Floral Stage Decor" in ans3["reply"]
    assert "₹1,800.00" in ans3["reply"]


# ---------------------------------------------------------------------------
# SCENARIO 7: Settlement & Exact Debt Simplification
# ---------------------------------------------------------------------------

def test_scenario_7_settlement_and_simplification(db):
    grp = create_group(GroupCreate(name="Debt Minimization Group"), db=db)
    m1 = add_member(grp.id, MemberCreate(name="User1"), db=db)
    m2 = add_member(grp.id, MemberCreate(name="User2"), db=db)
    m3 = add_member(grp.id, MemberCreate(name="User3"), db=db)

    # User1 pays ₹90 for all 3 -> each owes ₹30. Net: User1: +60, User2: -30, User3: -30
    create_expense(
        grp.id,
        ExpenseCreate(
            description="Shared Groceries",
            total_amount_paise=9000,
            paid_by_member_id=m1.id,
            split_type="equal",
            participant_ids=[m1.id, m2.id, m3.id]
        ),
        db=db
    )

    simplified = get_simplified_settlements(grp.id, db=db)
    settlements = simplified["settlements"]
    assert len(settlements) == 2
    amounts = [s["amount_paise"] for s in settlements]
    assert amounts == [3000, 3000]

    # Create and complete settlement
    st = create_settlement(
        grp.id,
        SettlementCreate(
            from_member_id=m2.id,
            to_member_id=m1.id,
            amount_paise=3000
        ),
        db=db
    )
    assert st.status == "pending"

    completed = complete_settlement(grp.id, st.id, db=db)
    assert completed.status == "completed"

    # Verify balances updated: User2 is settled (0), User1 has +30, User3 owes -30
    bal_res = get_group_balances(db, grp.id)
    assert bal_res[m2.id] == 0
    assert bal_res[m1.id] == 3000
    assert bal_res[m3.id] == -3000


# ---------------------------------------------------------------------------
# SCENARIO 8: PayPal Sandbox Service & Status Handling
# ---------------------------------------------------------------------------

def test_scenario_8_paypal_conversion_and_config():
    # 1. Test paise to USD conversion at 85 INR/USD
    usd_str, inr_str, rate = convert_paise_to_usd(8500)  # ₹85.00
    assert usd_str == "1.00"
    assert inr_str == "85.00"
    assert rate == 85.0

    # 2. Check PayPal configuration checker
    cfg = is_paypal_configured()
    assert isinstance(cfg, bool)


# ---------------------------------------------------------------------------
# SCENARIO 9: Error Handling & Fixed Known Issue Verification
# ---------------------------------------------------------------------------

def test_scenario_9_fixed_zero_member_group_error(db):
    # REPRODUCE PREVIOUS KNOWN ISSUE: Calling AI extraction on a group with 0 members
    zero_grp = create_group(GroupCreate(name="Empty Group"), db=db)

    # Calling extract_expense_details should raise clean HTTPException(400) explaining members needed
    with pytest.raises(HTTPException) as exc_info:
        extract_expense_details(
            AIParseRequest(group_id=zero_grp.id, text="I paid 800 rupees for petrol"),
            db=db
        )
    assert exc_info.value.status_code == 400
    assert "no active members" in exc_info.value.detail


def test_scenario_9_percentage_split_and_rounding():
    # Equal 50/50
    shares = calculate_percentage_split(10000, {1: 50.0, 2: 50.0})
    assert shares == {1: 5000, 2: 5000}

    # 3-way split: 33.33%, 33.33%, 33.34% -> exact 10000 paise
    shares_3 = calculate_percentage_split(10000, {1: 33.33, 2: 33.33, 3: 33.34})
    assert sum(shares_3.values()) == 10000

    # Mismatched total percentage raises ValueError
    with pytest.raises(ValueError):
        calculate_percentage_split(10000, {1: 40.0, 2: 40.0})


def test_scenario_whatsapp_parser():
    sample_chat = """
[12/03/2026, 14:30:15] Arun: I paid 1500 for dinner yesterday
[12/03/2026, 15:10:00] Rahul: Got it, split with me
[12/03/2026, 16:45:22] Chitra: Hey everyone, great meeting today!
[13/03/2026, 09:12:05] Arun: Petrol 800 rs for the trip
    """
    candidates = parse_whatsapp_chat(sample_chat, ["Arun", "Rahul", "Chitra"])
    assert len(candidates) >= 2
    amounts = [c["suggested_amount_paise"] for c in candidates if c["suggested_amount_paise"]]
    assert 150000 in amounts  # 1500 rs
    assert 80000 in amounts   # 800 rs
