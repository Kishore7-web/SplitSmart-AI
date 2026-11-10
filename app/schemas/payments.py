from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class PayPalCreateOrderRequest(BaseModel):
    settlement_id: int
    amount_paise: int = Field(gt=0)
    return_url: str | None = None
    cancel_url: str | None = None


class PayPalOrderResponse(BaseModel):
    order_id: str
    status: str
    approval_url: str | None
    amount_usd: str
    amount_inr: str
    exchange_rate: float
    mode: str = "sandbox"


class PayPalCaptureRequest(BaseModel):
    order_id: str
    settlement_id: int


class PayPalCaptureResponse(BaseModel):
    success: bool
    order_id: str
    capture_id: str | None = None
    status: str
    settlement_id: int
    message: str


class PayPalConfigResponse(BaseModel):
    enabled: bool
    mode: str = "sandbox"
    client_id_configured: bool
    client_secret_configured: bool
    base_url: str
