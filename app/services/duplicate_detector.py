import hashlib
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy.orm import Session
from app.database.models import Expense, ExpenseEvidence


def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    return hasher.hexdigest()


def text_similarity(a: str | None, b: str | None) -> float:
    """Calculate normalized string similarity ratio."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.strip().casefold(), b.strip().casefold()).ratio()


def check_evidence_duplicate(
    db: Session,
    group_id: int,
    file_hash: str | None,
    extracted_amount_paise: int | None = None,
    extracted_merchant: str | None = None,
    extracted_date: datetime | None = None,
    description: str | None = None,
    current_evidence_id: int | None = None,
) -> dict[str, Any]:
    """
    Check if an uploaded file or extracted expense is a duplicate of an existing record.
    Returns structured duplicate report with explanation.
    """
    # 1. Exact File Hash Match
    if file_hash:
        query = db.query(ExpenseEvidence).filter(
            ExpenseEvidence.group_id == group_id,
            ExpenseEvidence.file_hash == file_hash,
        )
        if current_evidence_id:
            query = query.filter(ExpenseEvidence.id != current_evidence_id)

        exact_match = query.first()
        if exact_match:
            return {
                "is_duplicate": True,
                "duplicate_type": "exact_hash",
                "similarity_score": 1.0,
                "matched_evidence_id": exact_match.id,
                "matched_expense_id": exact_match.expense_id,
                "reason": f"Exact identical file previously uploaded on {exact_match.upload_time.strftime('%Y-%m-%d %H:%M')} (Original filename: {exact_match.filename})."
            }

    # 2. Fuzzy Semantic Match against existing Expenses
    if extracted_amount_paise and extracted_amount_paise > 0:
        expenses = db.query(Expense).filter(Expense.group_id == group_id).all()

        for exp in expenses:
            # Check amount match (exact or within 2% margin)
            amount_diff = abs(exp.total_amount_paise - extracted_amount_paise)
            amount_match = amount_diff == 0 or (amount_diff / max(exp.total_amount_paise, 1)) <= 0.02

            if not amount_match:
                continue

            score = 0.5  # Base score for identical amount
            reasons = [f"Identical amount (₹{extracted_amount_paise / 100:.2f})"]

            # Merchant match
            if extracted_merchant and exp.merchant:
                m_sim = text_similarity(extracted_merchant, exp.merchant)
                if m_sim > 0.7:
                    score += 0.3
                    reasons.append(f"Matching merchant '{exp.merchant}' ({int(m_sim * 100)}% match)")

            # Description similarity
            if description and exp.description:
                d_sim = text_similarity(description, exp.description)
                if d_sim > 0.6:
                    score += 0.25
                    reasons.append(f"Similar description '{exp.description}'")

            # Date proximity check (within 48 hours)
            if extracted_date and exp.expense_date:
                time_delta = abs((exp.expense_date - extracted_date).total_seconds())
                if time_delta < 86400:  # within 1 day
                    score += 0.15
                    reasons.append("Occurred on the same date")

            if score >= 0.7:
                return {
                    "is_duplicate": True,
                    "duplicate_type": "fuzzy_similarity",
                    "similarity_score": min(1.0, round(score, 2)),
                    "matched_evidence_id": None,
                    "matched_expense_id": exp.id,
                    "reason": f"Potential duplicate of Expense #{exp.id} ('{exp.description}'): " + ", ".join(reasons) + "."
                }

    return {
        "is_duplicate": False,
        "duplicate_type": None,
        "similarity_score": 0.0,
        "matched_evidence_id": None,
        "matched_expense_id": None,
        "reason": None
    }
