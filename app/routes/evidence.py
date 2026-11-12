import os
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.database.models import Group, Member, Expense, ExpenseEvidence
from app.schemas.evidence import (
    EvidenceResponse,
    EvidenceLinkRequest,
    DuplicateCheckResponse,
)
from app.services.duplicate_detector import compute_file_hash, check_evidence_duplicate
from app.services.ai_service import (
    extract_receipt_information,
    extract_audio_expense,
)
from app.services.whatsapp_parser import parse_whatsapp_chat


router = APIRouter(
    prefix="/api/groups/{group_id}/evidence",
    tags=["Evidence & Activity Media"]
)

ALLOWED_EXTENSIONS = {
    # Images
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".heic": "image",
    # Documents
    ".pdf": "pdf", ".doc": "document", ".docx": "document",
    # Audio
    ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".ogg": "audio", ".webm": "audio",
    # Video
    ".mp4": "video", ".mov": "video", ".avi": "video", ".mkv": "video",
    # WhatsApp exports
    ".txt": "whatsapp_export"
}


def sanitize_filename(name: str) -> str:
    cleaned = os.path.basename(name).replace("..", "").replace("/", "").replace("\\", "")
    return cleaned or "uploaded_file"


def to_evidence_response(ev: ExpenseEvidence) -> EvidenceResponse:
    parsed_json = None
    if ev.extracted_data_json:
        try:
            parsed_json = json.loads(ev.extracted_data_json)
        except Exception:
            parsed_json = None

    return EvidenceResponse(
        id=ev.id,
        group_id=ev.group_id,
        uploaded_by_member_id=ev.uploaded_by_member_id,
        filename=ev.filename,
        stored_filename=ev.stored_filename,
        file_type=ev.file_type,
        mime_type=ev.mime_type,
        file_size=ev.file_size,
        file_hash=ev.file_hash,
        upload_time=ev.upload_time,
        status=ev.status,
        extracted_data_json=ev.extracted_data_json,
        expense_id=ev.expense_id,
        link_status=ev.link_status,
        notes=ev.notes,
        extracted_data=parsed_json,
    )


@router.post(
    "/upload",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_evidence(
    group_id: int,
    file: UploadFile = File(...),
    uploaded_by_member_id: int | None = Form(default=None),
    activity_id: int | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    if uploaded_by_member_id:
        member = db.query(Member).filter(Member.id == uploaded_by_member_id, Member.group_id == group_id).first()
        if not member:
            raise HTTPException(400, "Uploader is not a member of this group.")

    raw_filename = file.filename or "upload"
    sanitized_name = sanitize_filename(raw_filename)
    suffix = Path(sanitized_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file format '{suffix}'. Allowed: Images (JPG, PNG, WEBP), PDFs, Audio (MP3, WAV, M4A), Video (MP4, MOV), WhatsApp chat (.txt)."
        )

    file_type = ALLOWED_EXTENSIONS[suffix]

    # Read bytes safely
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(400, f"File exceeds maximum allowed size of {settings.max_upload_size_mb} MB.")

    # Compute SHA-256 hash for duplicate detection
    file_hash = compute_file_hash(file_bytes)

    # Save to disk with secure UUID filename
    os.makedirs(settings.upload_dir, exist_ok=True)
    unique_stored_name = f"{uuid.uuid4().hex}_{sanitized_name}"
    file_path = os.path.join(settings.upload_dir, unique_stored_name)

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # AI Information Extraction
    members = db.query(Member).filter(Member.group_id == group_id).all()
    member_names = [m.name for m in members]

    extracted_dict = {}
    proc_status = "processed"

    try:
        if file_type in ("image", "pdf"):
            extracted_dict = extract_receipt_information(
                file_bytes,
                file.content_type or "image/jpeg",
                sanitized_name
            )
        elif file_type == "audio":
            extracted_dict = extract_audio_expense(
                file_bytes,
                file.content_type or "audio/mpeg",
                member_names
            )
        elif file_type == "whatsapp_export":
            text_str = file_bytes.decode("utf-8", errors="ignore")
            candidates = parse_whatsapp_chat(text_str, member_names)
            extracted_dict = {
                "chat_candidates": candidates,
                "candidate_count": len(candidates),
                "notes": f"Identified {len(candidates)} potential expense messages from chat export."
            }
        elif file_type == "video":
            extracted_dict = {
                "video_evidence": True,
                "notes": f"Video evidence recorded ({file_size / (1024 * 1024):.1f} MB)."
            }
    except Exception as exc:
        proc_status = "review_needed"
        extracted_dict = {"extraction_error": str(exc)}

    # Run duplicate detection
    extracted_amt_paise = None
    if "total_amount_rupees" in extracted_dict:
        try:
            amt = float(extracted_dict["total_amount_rupees"])
            if amt > 0:
                extracted_amt_paise = int(amt * 100)
        except (ValueError, TypeError):
            pass

    merchant = extracted_dict.get("merchant_name")

    dup_report = check_evidence_duplicate(
        db=db,
        group_id=group_id,
        file_hash=file_hash,
        extracted_amount_paise=extracted_amt_paise,
        extracted_merchant=merchant,
        description=sanitized_name
    )

    extracted_dict["duplicate_check"] = dup_report
    if dup_report["is_duplicate"]:
        proc_status = "review_needed"

    evidence = ExpenseEvidence(
        group_id=group_id,
        activity_id=activity_id,
        uploaded_by_member_id=uploaded_by_member_id,
        filename=sanitized_name,
        stored_filename=unique_stored_name,
        file_type=file_type,
        mime_type=file.content_type,
        file_size=file_size,
        file_hash=file_hash,
        upload_time=datetime.now(timezone.utc),
        status=proc_status,
        extracted_data_json=json.dumps(extracted_dict),
        expense_id=None,
        link_status="unmatched",
        notes=notes
    )

    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return to_evidence_response(evidence)


@router.get("/", response_model=list[EvidenceResponse])
def list_evidence(
    group_id: int,
    link_status: str | None = None,
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    query = db.query(ExpenseEvidence).filter(ExpenseEvidence.group_id == group_id)
    if link_status:
        query = query.filter(ExpenseEvidence.link_status == link_status)

    evidences = query.order_by(ExpenseEvidence.id.desc()).all()
    return [to_evidence_response(e) for e in evidences]


@router.get("/{evidence_id}/file")
def get_evidence_file(
    group_id: int,
    evidence_id: int,
    db: Session = Depends(get_db)
):
    evidence = db.query(ExpenseEvidence).filter(
        ExpenseEvidence.id == evidence_id,
        ExpenseEvidence.group_id == group_id
    ).first()
    if not evidence:
        raise HTTPException(404, "Evidence not found")

    file_path = os.path.join(settings.upload_dir, evidence.stored_filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "Stored file missing from server.")

    return FileResponse(
        path=file_path,
        filename=evidence.filename,
        media_type=evidence.mime_type or "application/octet-stream"
    )


@router.patch("/{evidence_id}/link", response_model=EvidenceResponse)
def link_evidence_to_expense(
    group_id: int,
    evidence_id: int,
    data: EvidenceLinkRequest,
    db: Session = Depends(get_db)
):
    evidence = db.query(ExpenseEvidence).filter(
        ExpenseEvidence.id == evidence_id,
        ExpenseEvidence.group_id == group_id
    ).first()
    if not evidence:
        raise HTTPException(404, "Evidence not found")

    if data.expense_id:
        exp = db.query(Expense).filter(Expense.id == data.expense_id, Expense.group_id == group_id).first()
        if not exp:
            raise HTTPException(404, "Target expense not found in this group.")
        evidence.expense_id = data.expense_id
        evidence.link_status = data.link_status
    else:
        evidence.expense_id = None
        evidence.link_status = "unmatched"

    if data.notes:
        evidence.notes = data.notes

    db.commit()
    db.refresh(evidence)
    return to_evidence_response(evidence)


@router.post("/{evidence_id}/check-duplicates", response_model=DuplicateCheckResponse)
def check_duplicates_for_evidence(
    group_id: int,
    evidence_id: int,
    db: Session = Depends(get_db)
):
    evidence = db.query(ExpenseEvidence).filter(
        ExpenseEvidence.id == evidence_id,
        ExpenseEvidence.group_id == group_id
    ).first()
    if not evidence:
        raise HTTPException(404, "Evidence not found")

    amt_paise = None
    merchant = None
    if evidence.extracted_data_json:
        try:
            d = json.loads(evidence.extracted_data_json)
            if "total_amount_rupees" in d:
                amt_paise = int(float(d["total_amount_rupees"]) * 100)
            merchant = d.get("merchant_name")
        except Exception:
            pass

    report = check_evidence_duplicate(
        db=db,
        group_id=group_id,
        file_hash=evidence.file_hash,
        extracted_amount_paise=amt_paise,
        extracted_merchant=merchant,
        description=evidence.filename,
        current_evidence_id=evidence.id
    )

    return DuplicateCheckResponse(**report)


@router.post("/{evidence_id}/retry", response_model=EvidenceResponse)
def retry_evidence_processing(
    group_id: int,
    evidence_id: int,
    db: Session = Depends(get_db)
):
    evidence = db.query(ExpenseEvidence).filter(
        ExpenseEvidence.id == evidence_id,
        ExpenseEvidence.group_id == group_id
    ).first()
    if not evidence:
        raise HTTPException(404, "Evidence not found")

    file_path = os.path.join(settings.upload_dir, evidence.stored_filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "Stored file missing from server.")

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    members = db.query(Member).filter(Member.group_id == group_id).all()
    member_names = [m.name for m in members]

    extracted_dict = {}
    proc_status = "processed"

    try:
        if evidence.file_type in ("image", "pdf"):
            extracted_dict = extract_receipt_information(
                file_bytes,
                evidence.mime_type or "image/jpeg",
                evidence.filename
            )
        elif evidence.file_type == "audio":
            extracted_dict = extract_audio_expense(
                file_bytes,
                evidence.mime_type or "audio/mpeg",
                member_names
            )
        elif evidence.file_type == "whatsapp_export":
            text_str = file_bytes.decode("utf-8", errors="ignore")
            candidates = parse_whatsapp_chat(text_str, member_names)
            extracted_dict = {
                "chat_candidates": candidates,
                "candidate_count": len(candidates),
                "notes": f"Identified {len(candidates)} potential expense messages from chat export."
            }
        else:
            extracted_dict = {"notes": f"File type '{evidence.file_type}' re-verified."}
    except Exception as exc:
        proc_status = "failed"
        extracted_dict = {"extraction_error": str(exc)}

    evidence.status = proc_status
    evidence.extracted_data_json = json.dumps(extracted_dict)
    db.commit()
    db.refresh(evidence)

    return to_evidence_response(evidence)


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(
    group_id: int,
    evidence_id: int,
    db: Session = Depends(get_db)
):
    evidence = db.query(ExpenseEvidence).filter(
        ExpenseEvidence.id == evidence_id,
        ExpenseEvidence.group_id == group_id
    ).first()
    if not evidence:
        raise HTTPException(404, "Evidence not found")

    file_path = os.path.join(settings.upload_dir, evidence.stored_filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    db.delete(evidence)
    db.commit()
