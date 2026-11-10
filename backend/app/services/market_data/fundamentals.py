"""Deterministic annual metrics with formulas, periods, and input observations."""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.services.market_data.financials import AnnualFinancialStatements, AnnualFinancialPeriod


class MetricInput(BaseModel):
    field: str
    period_end: date
    value: Decimal


class FinancialMetric(BaseModel):
    key: str
    label: str
    status: Literal["available", "missing_data", "not_meaningful", "sector_not_supported"]
    value: Decimal | None = None
    unit: Literal["percent", "currency"]
    period_end: date | None = None
    formula: str
    formula_version: Literal["1"] = "1"
    inputs: list[MetricInput] = Field(default_factory=list)
    calculated_at: AwareDatetime


def _input(period: AnnualFinancialPeriod, field: str) -> MetricInput | None:
    value = getattr(period, field)
    return MetricInput(field=field, period_end=period.period_end, value=value) if value is not None else None


def _metric(
    key: str,
    label: str,
    unit: Literal["percent", "currency"],
    formula: str,
    period: AnnualFinancialPeriod | None,
    inputs: list[MetricInput | None],
    *,
    financial_sector: bool,
    calculation: Decimal | None,
    meaningful: bool = True,
) -> FinancialMetric:
    complete = [item for item in inputs if item is not None]
    status: Literal["available", "missing_data", "not_meaningful", "sector_not_supported"]
    if financial_sector:
        status = "sector_not_supported"
    elif len(complete) != len(inputs):
        status = "missing_data"
    elif not meaningful:
        status = "not_meaningful"
    else:
        status = "available"
    return FinancialMetric(
        key=key,
        label=label,
        status=status,
        value=calculation if status == "available" else None,
        unit=unit,
        period_end=period.period_end if period else None,
        formula=formula,
        inputs=complete,
        calculated_at=datetime.now(timezone.utc),
    )


def calculate_annual_metrics(statements: AnnualFinancialStatements) -> list[FinancialMetric]:
    """Use like-dated annual observations; skip generic ratios for financial firms."""

    latest = statements.periods[0] if statements.periods else None
    previous = statements.periods[1] if len(statements.periods) > 1 else None
    financial_sector = statements.sector == "Financial Services"
    revenue = _input(latest, "revenue") if latest else None
    operating = _input(latest, "operating_income") if latest else None
    net = _input(latest, "net_income") if latest else None
    prev_revenue = _input(previous, "revenue") if previous else None
    comparable_years = (
        latest is not None
        and previous is not None
        and 330 <= (latest.period_end - previous.period_end).days <= 400
    )
    ocf = _input(latest, "operating_cash_flow") if latest else None
    capex = _input(latest, "capital_expenditure") if latest else None
    positive_revenue = revenue is not None and revenue.value > 0
    percent = lambda value: (value * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return [
        _metric(
            "operating_margin", "Operating margin", "percent", "operating_income / revenue * 100",
            latest, [operating, revenue], financial_sector=financial_sector,
            calculation=percent(operating.value / revenue.value) if operating and positive_revenue else None,
            meaningful=positive_revenue,
        ),
        _metric(
            "net_margin", "Net margin", "percent", "net_income / revenue * 100",
            latest, [net, revenue], financial_sector=financial_sector,
            calculation=percent(net.value / revenue.value) if net and positive_revenue else None,
            meaningful=positive_revenue,
        ),
        _metric(
            "revenue_growth", "Revenue growth", "percent", "(revenue - prior_revenue) / prior_revenue * 100",
            latest, [revenue, prev_revenue], financial_sector=financial_sector,
            calculation=percent((revenue.value - prev_revenue.value) / prev_revenue.value)
            if positive_revenue and prev_revenue and prev_revenue.value > 0 and comparable_years else None,
            meaningful=positive_revenue and prev_revenue is not None and prev_revenue.value > 0 and comparable_years,
        ),
        _metric(
            "free_cash_flow", "Free cash flow", "currency", "operating_cash_flow + capital_expenditure (negative outflow)",
            latest, [ocf, capex], financial_sector=financial_sector,
            calculation=ocf.value + capex.value if ocf and capex and capex.value <= 0 else None,
            meaningful=capex is not None and capex.value <= 0,
        ),
    ]
