from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    uploaded_by_member_id: int | None = None
    filename: str
    stored_filename: str
    file_type: str
    mime_type: str | None = None
    file_size: int = 0
    file_hash: str | None = None
    upload_time: datetime
    status: str
    extracted_data_json: str | None = None
    expense_id: int | None = None
    link_status: str = "unmatched"
    notes: str | None = None
    extracted_data: dict[str, Any] | None = None


class EvidenceLinkRequest(BaseModel):
    expense_id: int | None = None
    link_status: str = Field(default="confirmed", pattern="^(unmatched|suggested|confirmed)$")
    notes: str | None = None


class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    duplicate_type: str | None = None  # exact_hash, fuzzy_similarity
    similarity_score: float = 0.0
    matched_evidence_id: int | None = None
    matched_expense_id: int | None = None
    reason: str | None = None
