from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.database.models import Group, Settlement, PaymentTransaction
from app.schemas.payments import (
    PayPalCreateOrderRequest,
    PayPalOrderResponse,
    PayPalCaptureRequest,
    PayPalCaptureResponse,
    PayPalConfigResponse,
)
from app.services.paypal_service import (
    is_paypal_configured,
    create_paypal_order,
    capture_paypal_order,
)


router = APIRouter(
    prefix="/api/groups/{group_id}/payments",
    tags=["PayPal Sandbox Payments"]
)


@router.get("/config", response_model=PayPalConfigResponse)
def get_payment_config(group_id: int, db: Session = Depends(get_db)):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    configured = is_paypal_configured()
    return PayPalConfigResponse(
        enabled=configured,
        mode=settings.paypal_mode,
        client_id_configured=bool(settings.paypal_client_id and settings.paypal_client_id != "your_paypal_sandbox_client_id"),
        client_secret_configured=bool(settings.paypal_client_secret and settings.paypal_client_secret != "your_paypal_sandbox_client_secret"),
        base_url=settings.paypal_base_url,
    )


@router.post("/orders", response_model=PayPalOrderResponse)
def create_order(
    group_id: int,
    req: PayPalCreateOrderRequest,
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    settlement = db.query(Settlement).filter(
        Settlement.id == req.settlement_id,
        Settlement.group_id == group_id
    ).first()
    if not settlement:
        raise HTTPException(404, "Settlement not found in this group.")

    if settlement.status == "completed":
        raise HTTPException(400, "This settlement has already been completed.")

    if not is_paypal_configured():
        raise HTTPException(
            503,
            "PayPal Sandbox credentials are not configured. "
            "Please configure PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env."
        )

    try:
        order_data = create_paypal_order(
            amount_paise=req.amount_paise,
            settlement_id=settlement.id,
            return_url=req.return_url,
            cancel_url=req.cancel_url,
        )

        # Record payment transaction state in database
        tx = PaymentTransaction(
            group_id=group_id,
            settlement_id=settlement.id,
            order_id=order_data["order_id"],
            amount_paise=req.amount_paise,
            currency="USD",
            status="APPROVAL_PENDING",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(tx)
        db.commit()

        return PayPalOrderResponse(**order_data)

    except ValueError as val_err:
        raise HTTPException(400, str(val_err))
    except Exception as exc:
        raise HTTPException(502, f"PayPal service error: {str(exc)}")


@router.post("/capture", response_model=PayPalCaptureResponse)
def capture_order(
    group_id: int,
    req: PayPalCaptureRequest,
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    settlement = db.query(Settlement).filter(
        Settlement.id == req.settlement_id,
        Settlement.group_id == group_id
    ).first()
    if not settlement:
        raise HTTPException(404, "Settlement not found")

    if not is_paypal_configured():
        raise HTTPException(503, "PayPal Sandbox credentials are not configured.")

    try:
        capture_result = capture_paypal_order(req.order_id)
        status_val = capture_result.get("status")

        # Find or create transaction record
        tx = db.query(PaymentTransaction).filter(
            PaymentTransaction.order_id == req.order_id,
            PaymentTransaction.group_id == group_id
        ).first()

        if not tx:
            tx = PaymentTransaction(
                group_id=group_id,
                settlement_id=settlement.id,
                order_id=req.order_id,
                amount_paise=settlement.amount_paise,
                currency="USD",
                status=status_val or "UNKNOWN",
                created_at=datetime.now(timezone.utc),
            )
            db.add(tx)

        tx.capture_id = capture_result.get("capture_id")
        tx.status = status_val
        tx.payer_email = capture_result.get("payer_email")
        tx.updated_at = datetime.now(timezone.utc)

        # Update settlement ONLY if capture succeeded (COMPLETED)
        if status_val == "COMPLETED":
            settlement.status = "completed"
            settlement.payment_provider = "PayPal Sandbox"
            settlement.provider_reference = f"PayPal Order {req.order_id}"
            settlement.completed_at = datetime.now(timezone.utc)
            db.commit()

            return PayPalCaptureResponse(
                success=True,
                order_id=req.order_id,
                capture_id=capture_result.get("capture_id"),
                status="COMPLETED",
                settlement_id=settlement.id,
                message="Payment captured successfully. Settlement marked as completed."
            )
        else:
            tx.status = "FAILED"
            db.commit()
            return PayPalCaptureResponse(
                success=False,
                order_id=req.order_id,
                capture_id=capture_result.get("capture_id"),
                status=status_val or "FAILED",
                settlement_id=settlement.id,
                message=f"PayPal order status is '{status_val}'. Settlement remains pending."
            )

    except ValueError as val_err:
        raise HTTPException(400, str(val_err))
    except Exception as exc:
        raise HTTPException(502, f"PayPal capture error: {str(exc)}")


@router.get("/transactions")
def list_payment_transactions(group_id: int, db: Session = Depends(get_db)):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    return (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.group_id == group_id)
        .order_by(PaymentTransaction.id.desc())
        .all()
    )
