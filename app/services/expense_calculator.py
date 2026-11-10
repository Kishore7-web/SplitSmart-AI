from decimal import Decimal, ROUND_HALF_UP


def calculate_equal_split(total_amount_paise: int, member_ids: list[int]) -> dict[int, int]:
    if total_amount_paise <= 0:
        raise ValueError("Amount must be positive.")

    if not member_ids or len(set(member_ids)) != len(member_ids):
        raise ValueError("Participants must be unique and non-empty.")

    count = len(member_ids)
    base_amount, remainder = divmod(total_amount_paise, count)

    return {
        member_id: base_amount + (1 if index < remainder else 0)
        for index, member_id in enumerate(member_ids)
    }


def calculate_custom_split(total_amount_paise: int, shares: dict[int, int]) -> dict[int, int]:
    if not shares or any(amount <= 0 for amount in shares.values()):
        raise ValueError("Custom shares must be positive.")

    if sum(shares.values()) != total_amount_paise:
        raise ValueError("Custom shares must equal the total expense.")

    return shares


def calculate_percentage_split(total_amount_paise: int, percentages: dict[int, float]) -> dict[int, int]:
    """
    Splits total_amount_paise according to percentage weights.
    Guarantees exact sum equality in paise with deterministic rounding.
    """
    if not percentages:
        raise ValueError("Percentages must be provided.")

    total_percent = sum(percentages.values())
    if abs(total_percent - 100.0) > 0.1:
        raise ValueError(f"Percentages must sum to 100% (currently {total_percent:.2f}%).")

    calculated_shares = {}
    total_allocated = 0

    sorted_members = sorted(percentages.keys())
    for member_id in sorted_members:
        pct = Decimal(str(percentages[member_id]))
        share = int(((Decimal(total_amount_paise) * pct) / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        calculated_shares[member_id] = share
        total_allocated += share

    # Fix any rounding discrepancy (usually +/- 1 or 2 paise) by adjusting the largest share
    diff = total_amount_paise - total_allocated
    if diff != 0:
        # Find member with largest percentage to absorb rounding
        largest_member = max(sorted_members, key=lambda m: percentages[m])
        calculated_shares[largest_member] += diff

    return calculated_shares
