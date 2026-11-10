from types import SimpleNamespace

from app.services.expense_calculator import (
    calculate_equal_split,
    calculate_custom_split,
)
from app.services.settlement_engine import (
    calculate_member_balances,
    simplify_debts,
)


def test_equal_split():
    result = calculate_equal_split(10000, [1, 2, 3])

    assert result == {
        1: 3334,
        2: 3333,
        3: 3333,
    }

    assert sum(result.values()) == 10000


def test_custom_split():
    result = calculate_custom_split(
        10000,
        {1: 6000, 2: 4000},
    )

    assert result == {1: 6000, 2: 4000}


def test_custom_split_rejects_wrong_total():
    try:
        calculate_custom_split(10000, {1: 5000, 2: 4000})
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_member_balances():
    expense = SimpleNamespace(
        paid_by_member_id=1,
        total_amount_paise=9000,
        shares=[
            SimpleNamespace(member_id=1, amount_paise=3000),
            SimpleNamespace(member_id=2, amount_paise=3000),
            SimpleNamespace(member_id=3, amount_paise=3000),
        ],
    )

    balances = calculate_member_balances([expense])

    assert balances == {
        1: 6000,
        2: -3000,
        3: -3000,
    }


def test_simplify_debts():
    balances = {
        1: 6000,
        2: -3000,
        3: -3000,
    }

    result = simplify_debts(balances)

    assert result == [
        {
            "from_member_id": 2,
            "to_member_id": 1,
            "amount_paise": 3000,
        },
        {
            "from_member_id": 3,
            "to_member_id": 1,
            "amount_paise": 3000,
        },
    ]