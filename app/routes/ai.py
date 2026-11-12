from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.database.models import Group, Member, Expense, ExpenseShare, ExpenseEvidence, AIConversationLog
from app.schemas.ai import (
    AIParseRequest,
    AIParseResponse,
    AIDraftExpenseConfirm,
    AIChatRequest,
    AIChatResponse,
    AIGroupProposalRequest,
    AIGroupRefineRequest,
    AIGroupConfirmRequest,
    AIToolExecuteRequest,
)
from app.schemas.groups import GroupResponse
from app.schemas.expenses import ExpenseResponse, ExpenseShareResponse
from app.services.ai_service import (
    parse_expense_with_ai,
    answer_financial_query,
    is_gemini_configured,
)
from app.services.ai_group_creator import (
    generate_group_proposal,
    refine_group_proposal,
    persist_group_structure,
)
from app.services.ai_tools import (
    execute_tool_call,
    GEMINI_TOOLS_DECLARATIONS,
)
from app.services.expense_calculator import calculate_equal_split, calculate_custom_split
from app.core.auth import get_optional_current_user, User


router = APIRouter(
    prefix="/api/ai",
    tags=["AI Assistant & Group Intelligence"]
)


# =============================================================================
# 1. AI-POWERED CONVERSATIONAL GROUP CREATION
# =============================================================================

@router.post("/propose-group")
def propose_group_from_description(
    req: AIGroupProposalRequest,
    user: User | None = Depends(get_optional_current_user)
):
    """
    Step 1: User describes group requirements in natural language.
    Gemini produces structured group information (activities, budgets, categories, members).
    """
    desc = req.description or req.prompt or req.text or ""
    if not desc.strip():
        raise HTTPException(400, "Please provide a description or prompt for the group.")
    try:
        proposal = generate_group_proposal(desc.strip())
        # Ensure budget_paise is populated if overall_budget_rupees is present
        if "overall_budget_rupees" in proposal and "budget_paise" not in proposal:
            try:
                proposal["budget_paise"] = int(float(str(proposal["overall_budget_rupees"]).replace(",", "")) * 100)
            except Exception:
                proposal["budget_paise"] = 0
        elif "budget_paise" in proposal and "overall_budget_rupees" not in proposal:
            proposal["overall_budget_rupees"] = f"{proposal['budget_paise'] / 100:.2f}"

        # Ensure activities have budget_paise
        for act in proposal.get("activities", []):
            if "budget_rupees" in act and "budget_paise" not in act:
                try:
                    act["budget_paise"] = int(float(str(act["budget_rupees"]).replace(",", "")) * 100)
                except Exception:
                    act["budget_paise"] = 0

        return {
            "success": True,
            "proposal": proposal,
            "message": "Group structure prepared. You can review, modify activities or confirm creation."
        }
    except Exception as exc:
        raise HTTPException(400, f"Failed to interpret group description: {str(exc)}")


@router.post("/refine-group-proposal")
def refine_group_proposal_endpoint(
    req: AIGroupRefineRequest,
    user: User | None = Depends(get_optional_current_user)
):
    """
    Step 2: User provides follow-up modifications (e.g. 'Add photography activity', 'Allocate ₹4,000').
    Updates the proposed structure in real-time.
    """
    instruction = req.instruction or req.prompt or ""
    if not instruction.strip():
        raise HTTPException(400, "Please provide refinement instructions.")
    try:
        updated = refine_group_proposal(req.current_proposal, instruction.strip())
        if "overall_budget_rupees" in updated and "budget_paise" not in updated:
            try:
                updated["budget_paise"] = int(float(str(updated["overall_budget_rupees"]).replace(",", "")) * 100)
            except Exception:
                updated["budget_paise"] = 0
        for act in updated.get("activities", []):
            if "budget_rupees" in act and "budget_paise" not in act:
                try:
                    act["budget_paise"] = int(float(str(act["budget_rupees"]).replace(",", "")) * 100)
                except Exception:
                    act["budget_paise"] = 0

        return {
            "success": True,
            "proposal": updated,
            "message": "Proposal updated based on your instruction."
        }
    except Exception as exc:
        raise HTTPException(400, f"Failed to refine proposal: {str(exc)}")


@router.post("/confirm-group-creation", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def confirm_group_creation(
    req: AIGroupConfirmRequest,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 3: User confirms the proposed structure.
    Backend persists real database records: Group, Activities, Members, Custom Categories, Custom Fields.
    """
    structure = req.structure or req.proposal or {}
    if not structure:
        raise HTTPException(400, "No group structure provided to confirm.")
    try:
        return persist_group_structure(db, structure, user=user)
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Failed to create group from proposal: {str(exc)}")


# =============================================================================
# 2. GEMINI FUNCTION CALLING / TOOL EXECUTION
# =============================================================================

@router.get("/tools")
def list_available_tools():
    return {
        "tools": GEMINI_TOOLS_DECLARATIONS
    }


@router.post("/execute-tool")
def execute_controlled_tool(
    req: AIToolExecuteRequest,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    try:
        res = execute_tool_call(db, req.tool_name, req.tool_args, user=user)
        return res
    except Exception as exc:
        raise HTTPException(400, f"Tool execution failed: {str(exc)}")


# =============================================================================
# 3. NATURAL LANGUAGE EXPENSE PARSER & DRAFT WORKFLOW
# =============================================================================

def extract_expense_details(data: AIParseRequest, db: Session) -> dict:
    group = db.get(Group, data.group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    members = (
        db.query(Member)
        .filter(
            Member.group_id == data.group_id,
            Member.is_active.is_(True)
        )
        .all()
    )

    if not members:
        raise HTTPException(
            400,
            "This group has no active members. Please add members to the group before analyzing expenses."
        )

    member_lookup = {
        member.name.strip().casefold(): member.id
        for member in members
    }
    member_id_to_name = {member.id: member.name for member in members}

    current_user_name = None
    if data.current_member_id and data.current_member_id in member_id_to_name:
        current_user_name = member_id_to_name[data.current_member_id]

    try:
        parsed = parse_expense_with_ai(
            data.text,
            [member.name for member in members],
            current_user_name=current_user_name
        )

        amount = Decimal(str(parsed["amount_rupees"]))
        if not amount.is_finite() or amount < 0:
            raise ValueError("Expense amount must be a valid positive number.")

        paise = int(
            (amount * 100).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP
            )
        )

        payer_id = None
        payer_name = None
        missing_fields = list(parsed.get("missing_fields", []))

        if parsed.get("payer_name"):
            p_key = parsed["payer_name"].strip().casefold()
            if p_key in member_lookup:
                payer_id = member_lookup[p_key]
                payer_name = member_id_to_name[payer_id]

        if not payer_id:
            # Fallback to current user or first active member
            if current_user_name and current_user_name.strip().casefold() in member_lookup:
                payer_id = member_lookup[current_user_name.strip().casefold()]
                payer_name = current_user_name
            elif len(members) == 1:
                payer_id = members[0].id
                payer_name = members[0].name
            else:
                if "payer" not in missing_fields:
                    missing_fields.append("payer")

        participant_ids = []
        for name in parsed.get("participants", []):
            if isinstance(name, str):
                key = name.strip().casefold()
                if key in member_lookup:
                    mid = member_lookup[key]
                    if mid not in participant_ids:
                        participant_ids.append(mid)

        if not participant_ids:
            participant_ids = [m.id for m in members]

        participant_names = [member_id_to_name[mid] for mid in participant_ids]

        description = parsed.get("description", "Shared Expense").strip()
        if not description:
            description = "Shared Expense"

        return {
            "description": description,
            "amount_paise": paise,
            "paid_by_member_id": payer_id,
            "payer_name": payer_name,
            "participant_ids": participant_ids,
            "participant_names": participant_names,
            "split_type": parsed.get("split_type", "equal"),
            "category": parsed.get("category", "General"),
            "merchant": parsed.get("merchant"),
            "confidence": parsed.get("confidence", 0.9),
            "missing_fields": missing_fields,
            "clarification_prompt": parsed.get("clarification_prompt"),
        }

    except (ValueError, InvalidOperation, KeyError, TypeError) as exc:
        raise HTTPException(400, f"AI could not parse expense: {str(exc)}")


@router.post("/parse-expense", response_model=AIParseResponse)
def parse_expense(
    data: AIParseRequest,
    db: Session = Depends(get_db)
):
    details = extract_expense_details(data, db)
    return AIParseResponse(**details)


@router.post(
    "/confirm-draft",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED
)
def confirm_draft_expense(
    draft: AIDraftExpenseConfirm,
    db: Session = Depends(get_db)
):
    group = db.get(Group, draft.group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    members = db.query(Member).filter(
        Member.group_id == draft.group_id,
        Member.is_active.is_(True)
    ).all()
    member_ids = {m.id for m in members}

    if draft.paid_by_member_id not in member_ids:
        raise HTTPException(400, "Payer is not an active member of this group.")

    for pid in draft.participant_ids:
        if pid not in member_ids:
            raise HTTPException(400, f"Participant #{pid} is not an active member of this group.")

    shares = calculate_equal_split(draft.total_amount_paise, draft.participant_ids)

    expense = Expense(
        group_id=draft.group_id,
        paid_by_member_id=draft.paid_by_member_id,
        activity_id=draft.activity_id,
        description=draft.description.strip(),
        total_amount_paise=draft.total_amount_paise,
        split_type=draft.split_type,
        category=draft.category or "General",
        merchant=draft.merchant.strip() if draft.merchant else None,
        notes=draft.notes.strip() if draft.notes else None,
        status="confirmed"
    )

    expense.shares = [
        ExpenseShare(member_id=mid, amount_paise=amount)
        for mid, amount in shares.items()
    ]

    try:
        db.add(expense)
        db.commit()
        db.refresh(expense)

        if draft.evidence_id:
            ev = db.query(ExpenseEvidence).filter(
                ExpenseEvidence.id == draft.evidence_id,
                ExpenseEvidence.group_id == draft.group_id
            ).first()
            if ev:
                ev.expense_id = expense.id
                ev.link_status = "confirmed"
                if draft.activity_id:
                    ev.activity_id = draft.activity_id
                db.commit()

        return (
            db.query(Expense)
            .options(selectinload(Expense.shares))
            .filter(Expense.id == expense.id)
            .one()
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Failed to save expense: {str(exc)}")


@router.post(
    "/create-expense",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED
)
def create_expense_using_ai(
    data: AIParseRequest,
    db: Session = Depends(get_db)
):
    details = extract_expense_details(data, db)

    payer_id = details["paid_by_member_id"]
    if not payer_id:
        first_member = db.query(Member).filter(
            Member.group_id == data.group_id,
            Member.is_active.is_(True)
        ).first()
        if not first_member:
            raise HTTPException(400, "Group has no active members.")
        payer_id = first_member.id

    shares = calculate_equal_split(
        details["amount_paise"],
        details["participant_ids"]
    )

    expense = Expense(
        group_id=data.group_id,
        paid_by_member_id=payer_id,
        description=details["description"],
        total_amount_paise=details["amount_paise"],
        split_type="equal",
        category=details.get("category", "General"),
        merchant=details.get("merchant"),
        status="confirmed"
    )

    expense.shares = [
        ExpenseShare(member_id=mid, amount_paise=amt)
        for mid, amt in shares.items()
    ]

    try:
        db.add(expense)
        db.commit()
        db.refresh(expense)

        return (
            db.query(Expense)
            .options(selectinload(Expense.shares))
            .filter(Expense.id == expense.id)
            .one()
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Failed to create expense: {str(exc)}")


# =============================================================================
# 4. DATABASE-GROUNDED AI FINANCIAL ASSISTANT
# =============================================================================

@router.post("/chat", response_model=AIChatResponse)
def chat_with_financial_assistant(
    request: AIChatRequest,
    db: Session = Depends(get_db)
):
    try:
        result = answer_financial_query(db, request.group_id, request.message)

        # Log conversation
        log = AIConversationLog(
            group_id=request.group_id,
            role="user",
            content=request.message
        )
        db.add(log)
        db.add(AIConversationLog(
            group_id=request.group_id,
            role="assistant",
            content=result["reply"]
        ))
        db.commit()

        return AIChatResponse(
            reply=result["reply"],
            sources=result.get("sources", []),
            grounded_data=result.get("grounded_data", {})
        )
    except ValueError as val_err:
        raise HTTPException(404, str(val_err))
    except Exception as exc:
        raise HTTPException(500, f"Assistant error: {str(exc)}")


@router.get("/status")
def get_ai_status():
    return {
        "gemini_configured": is_gemini_configured(),
        "model": settings.gemini_model,
        "features": [
            "Conversational Group Creation",
            "Natural Language Expense Parsing",
            "Receipt & Bill Vision Understanding",
            "Audio Note Transcription",
            "WhatsApp Export Parsing",
            "AI-Assisted Duplicate Detection",
            "Grounded Financial Assistant",
            "Gemini Function Calling Tools"
        ]
    }
