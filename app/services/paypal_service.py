from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import httpx
from app.core.config import settings

# Exchange rate for Sandbox demonstration (INR to USD)
# 1 USD ≈ 85.00 INR (8500 paise)
INR_TO_USD_RATE = Decimal("85.00")


def is_paypal_configured() -> bool:
    """Check if PayPal Sandbox credentials are configured."""
    return bool(
        settings.paypal_client_id
        and settings.paypal_client_secret
        and settings.paypal_client_id != "your_paypal_sandbox_client_id"
        and settings.paypal_client_secret != "your_paypal_sandbox_client_secret"
    )


def get_access_token() -> str:
    """Retrieve an OAuth 2.0 access token from PayPal Sandbox."""
    if not is_paypal_configured():
        raise ValueError(
            "PayPal Sandbox credentials are not configured. "
            "Please configure PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env."
        )

    try:
        response = httpx.post(
            f"{settings.paypal_base_url}/v1/oauth2/token",
            auth=(settings.paypal_client_id, settings.paypal_client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")

        if not token:
            raise ValueError("PayPal did not return an access token.")

        return token

    except httpx.HTTPStatusError as exc:
        raise ValueError(f"PayPal Sandbox authentication failed ({exc.response.status_code}): {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise ValueError("Could not connect to PayPal Sandbox endpoint.") from exc


def convert_paise_to_usd(amount_paise: int) -> tuple[str, str, float]:
    """Convert INR paise to USD decimal string with 2 decimal places."""
    amount_inr = (Decimal(amount_paise) / Decimal(100)).quantize(Decimal("0.01"))
    amount_usd = (amount_inr / INR_TO_USD_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Ensure minimum sandbox amount of $0.01
    if amount_usd <= Decimal("0"):
        amount_usd = Decimal("0.01")

    return format(amount_usd, ".2f"), format(amount_inr, ".2f"), float(INR_TO_USD_RATE)


def create_paypal_order(amount_paise: int, settlement_id: int, return_url: str | None = None, cancel_url: str | None = None) -> dict:
    """Create a PayPal v2 order for a settlement payment."""
    if amount_paise <= 0:
        raise ValueError("Settlement amount must be positive.")

    amount_usd_str, amount_inr_str, rate = convert_paise_to_usd(amount_paise)
    token = get_access_token()

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": f"settlement_{settlement_id}",
                "description": f"SplitSmart AI Settlement #{settlement_id} (₹{amount_inr_str})",
                "amount": {
                    "currency_code": "USD",
                    "value": amount_usd_str,
                },
            }
        ],
        "application_context": {
            "brand_name": "SplitSmart AI 2.0",
            "landing_page": "NO_PREFERENCE",
            "user_action": "PAY_NOW",
            "return_url": return_url or "https://example.com/return",
            "cancel_url": cancel_url or "https://example.com/cancel",
        }
    }

    try:
        response = httpx.post(
            f"{settings.paypal_base_url}/v2/checkout/orders",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=25.0,
        )
        response.raise_for_status()
        data = response.json()

        approval_url = next(
            (
                link["href"]
                for link in data.get("links", [])
                if link.get("rel") in ("approve", "payer-action")
            ),
            None,
        )

        return {
            "order_id": data["id"],
            "status": data.get("status", "CREATED"),
            "approval_url": approval_url,
            "amount_usd": amount_usd_str,
            "amount_inr": amount_inr_str,
            "exchange_rate": rate,
            "mode": settings.paypal_mode,
        }

    except httpx.HTTPStatusError as exc:
        raise ValueError(f"PayPal order creation failed: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise ValueError("Network error contacting PayPal Sandbox.") from exc


def capture_paypal_order(order_id: str) -> dict:
    """Capture payment for an approved PayPal order."""
    if not order_id or len(order_id) > 100:
        raise ValueError("Invalid PayPal order ID.")

    token = get_access_token()

    try:
        response = httpx.post(
            f"{settings.paypal_base_url}/v2/checkout/orders/{order_id}/capture",
            json={},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=25.0,
        )
        response.raise_for_status()
        data = response.json()

        status = data.get("status", "UNKNOWN")
        capture_id = None
        payer_email = None

        if "payer" in data:
            payer_email = data["payer"].get("email_address")

        purchase_units = data.get("purchase_units", [])
        if purchase_units:
            captures = purchase_units[0].get("payments", {}).get("captures", [])
            if captures:
                capture_id = captures[0].get("id")

        return {
            "order_id": data.get("id"),
            "status": status,
            "capture_id": capture_id,
            "payer_email": payer_email,
            "raw": data,
        }

    except httpx.HTTPStatusError as exc:
        raise ValueError(f"PayPal capture failed: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise ValueError("Network error capturing PayPal order.") from exc
