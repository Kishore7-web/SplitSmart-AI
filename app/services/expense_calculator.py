
def calculate_equal_split(total_amount_paise: int, member_ids: list[int]):
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


def calculate_custom_split(total_amount_paise: int, shares: dict[int, int]):
    if not shares or any(amount <= 0 for amount in shares.values()):
        raise ValueError("Custom shares must be positive.")

    if sum(shares.values()) != total_amount_paise:
        raise ValueError("Custom shares must equal the total expense.")

    return shares
