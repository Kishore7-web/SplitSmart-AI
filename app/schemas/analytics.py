from pydantic import BaseModel


class FinancialOverview(BaseModel):
    total_budget_paise: int
    total_expense_paise: int
    confirmed_settlements_paise: int
    pending_settlements_paise: int
    remaining_budget_paise: int
    budget_consumed_percentage: float
    active_members_count: int
    expense_count: int
    currency: str = "INR"


class CategorySpending(BaseModel):
    category: str
    amount_paise: int
    percentage: float
    count: int


class MemberContribution(BaseModel):
    member_id: int
    member_name: str
    role: str
    paid_paise: int
    owed_paise: int
    net_balance_paise: int


class BudgetStatus(BaseModel):
    budget_paise: int
    spent_paise: int
    remaining_paise: int
    status_level: str  # safe, warning, danger
    alert_message: str


class SpendingForecast(BaseModel):
    estimated_total_spending_paise: int
    estimated_remaining_budget_paise: int
    burn_rate_daily_paise: int
    days_elapsed: int
    days_remaining: int
    projected_overrun_paise: int
    is_reliable: bool
    explanation: str


class HistoricalRecommendation(BaseModel):
    title: str
    category: str
    recommendation: str
    based_on: str
