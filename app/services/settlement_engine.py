
def calculate_member_balances(expenses, settlements=()):
    """
    Positive balance: member should receive money.
    Negative balance: member owes money.
    All amounts are in paise.
    """

    balances = {}

    for expense in expenses:
        payer_id = expense.paid_by_member_id

        balances[payer_id] = (
            balances.get(payer_id, 0)
            + expense.total_amount_paise
        )

        for share in expense.shares:
            member_id = share.member_id

            balances[member_id] = (
                balances.get(member_id, 0)
                - share.amount_paise
            )

    # Apply completed payments only.
    for settlement in settlements:
        if settlement.status == "completed":
            sender = settlement.from_member_id
            receiver = settlement.to_member_id
            amount = settlement.amount_paise

            balances[sender] = balances.get(sender, 0) + amount
            balances[receiver] = balances.get(receiver, 0) - amount

    return balances


def simplify_debts(balances):
    creditors = []
    debtors = []

    for member_id, balance in balances.items():
        if balance > 0:
            creditors.append([member_id, balance])
        elif balance < 0:
            debtors.append([member_id, -balance])

    settlements = []

    i = 0
    j = 0

    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i][1], creditors[j][1])

        settlements.append({
            "from_member_id": debtors[i][0],
            "to_member_id": creditors[j][0],
            "amount_paise": amount
        })

        debtors[i][1] -= amount
        creditors[j][1] -= amount

        if debtors[i][1] == 0:
            i += 1

        if creditors[j][1] == 0:
            j += 1

    return settlements
