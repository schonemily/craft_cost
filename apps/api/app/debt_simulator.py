from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class Debt:
    name: str
    balance: float
    apr: float  # annual, percent or decimal
    min_payment: float
    promo_apr: Optional[float] = None  # optional promotional APR (annual)
    promo_months: Optional[int] = None  # number of months promo applies (from month 1)


@dataclass
class DebtResult:
    name: str
    months: int
    interest_paid: float
    total_paid: float


@dataclass
class SimulationResult:
    strategy: str
    months: int
    interest_paid: float
    total_paid: float
    debts: List[DebtResult]
    monthly: Optional[List[Dict[str, float]]] = None  # optional monthly schedule summary


def _apr_monthly(apr: float) -> float:
    # accept APR given as 0.1999 (19.99%) or 19.99 (percent)
    if apr is None:
        return 0.0
    return (apr / 100.0 if apr > 1 else apr) / 12.0


def _round2(x: float) -> float:
    return float(round(x + 1e-10, 2))


def simulate(
    debts_in: List[Debt],
    extra: float,
    strategy: str,
    *,
    include_schedule: bool = False,
    extra_schedule: Optional[List[Dict[str, float]]] = None,
    issuer_percent: float = 0.01,
    issuer_floor: float = 25.0,
) -> SimulationResult:
    # Sanitize inputs
    assert strategy in ("snowball", "avalanche")
    debts = []
    for d in debts_in:
        if d.balance is None or d.balance <= 0:
            continue
        if d.min_payment is None or d.min_payment <= 0:
            continue
        debts.append({
            "name": d.name or "Debt",
            "balance": _round2(float(d.balance)),
            # base and promo monthly rates
            "rate": _apr_monthly(float(d.apr or 0.0)),
            "promo_rate": _apr_monthly(float(d.promo_apr or 0.0)) if d.promo_apr is not None else None,
            "promo_months": int(d.promo_months or 0) if d.promo_months else 0,
            "min": _round2(float(d.min_payment)),
            "interest_paid": 0.0,
            "total_paid": 0.0,
            "months": 0,
            "elapsed": 0,
        })
    if not debts:
        return SimulationResult(strategy=strategy, months=0, interest_paid=0.0, total_paid=0.0, debts=[])

    months = 0
    cap_months = 600  # 50 years cap
    monthly_schedule: List[Dict[str, float]] = []

    # Preprocess extra schedule (month-indexed starting at 1)
    extras_by_month: Dict[int, float] = {}
    if extra_schedule:
        for e in extra_schedule:
            try:
                m = int(e.get("month") or e.get("monthOffset") or 0)
                amt = float(e.get("amount") or 0)
            except Exception:
                continue
            if m <= 0 or amt <= 0:
                continue
            extras_by_month[m] = extras_by_month.get(m, 0.0) + amt

    while True:
        active = [d for d in debts if d["balance"] > 0.01]
        if not active:
            break
        months += 1
        if months > cap_months:
            break

        # 1) accrue interest (apply promo rate if still within promo period)
        month_interest = 0.0
        for d in active:
            # choose monthly rate
            use_rate = d["rate"]
            if d.get("promo_rate") is not None and d.get("promo_months", 0) > 0 and d.get("elapsed", 0) < d["promo_months"]:
                use_rate = d["promo_rate"]
            intr = _round2(d["balance"] * use_rate) if use_rate > 0 else 0.0
            d["balance"] = _round2(d["balance"] + intr)
            d["interest_paid"] = _round2(d["interest_paid"] + intr)
            month_interest = _round2(month_interest + intr)

        # recompute active after interest (all positive)
        active = [d for d in debts if d["balance"] > 0.01]
        if not active:
            break

        # 2) compute total budget: sum of issuer-style minimums for active + extras (fixed + scheduled)
        # issuer min approximation: max(floor, 1% of balance + current month interest)
        per_min: Dict[int, float] = {}
        for idx, d in enumerate(active):
            issuer_min = max(issuer_floor, _round2(d["balance"] * issuer_percent + 0.0))
            # ensure at least interest is covered when possible (avoid neg-am unless budget insufficient)
            issuer_min = max(issuer_min, 0.0)
            per_min[idx] = max(d["min"], issuer_min)
        scheduled_extra = extras_by_month.get(months, 0.0)
        total_budget = _round2(sum(per_min.values()) + max(0.0, float(extra or 0.0)) + max(0.0, scheduled_extra))

        # 3) pay minimums to all active
        budget = total_budget
        for i, d in enumerate(active):
            due = per_min[i]
            pay = min(due, d["balance"])  # don't overpay at this step
            pay = _round2(pay)
            d["balance"] = _round2(d["balance"] - pay)
            d["total_paid"] = _round2(d["total_paid"] + pay)
            budget = _round2(budget - pay)

        # 4) allocate remaining budget according to strategy
        # choose order by current remaining balance / apr
        def _order_key(dd: Dict[str, Any]):
            if strategy == "snowball":
                return (dd["balance"], -dd["rate"])  # smallest balance first
            else:
                return (-dd["rate"], dd["balance"])  # highest APR first

        ordered = sorted([d for d in debts if d["balance"] > 0.01], key=_order_key)

        paid_extra_this_month = 0.0
        for d in ordered:
            if budget <= 0.0:
                break
            if d["balance"] <= 0.0:
                continue
            pay_extra = min(budget, d["balance"])  # dump remainder here
            pay_extra = _round2(pay_extra)
            d["balance"] = _round2(d["balance"] - pay_extra)
            d["total_paid"] = _round2(d["total_paid"] + pay_extra)
            budget = _round2(budget - pay_extra)
            paid_extra_this_month = _round2(paid_extra_this_month + pay_extra)

        # 5) stamp months for debts paid off this cycle
        for d in debts:
            if d["months"] == 0 and d["balance"] <= 0.01:
                d["months"] = months
            d["elapsed"] = int(d.get("elapsed", 0)) + 1

        # safety: if budget still positive but no balances reduced (e.g., zero min and zero balance), break
        if months > cap_months:
            break

        if include_schedule:
            total_balance = _round2(sum(d["balance"] for d in debts))
            total_paid_this_month = _round2(sum(d.get("total_paid", 0.0) for d in debts))
            # compute payments made this month by differencing with previous month. We don't store prev totals, so approximate principal as (minimums + extras - month_interest)
            # Better approximation: principal = total_budget - month_interest (bounded at >=0)
            month_principal = max(0.0, _round2(total_budget - month_interest))
            monthly_schedule.append({
                "month": float(months),
                "balance": total_balance,
                "interest": month_interest,
                "principal": month_principal,
            })

    # Build response
    total_interest = _round2(sum(d["interest_paid"] for d in debts))
    total_paid = _round2(sum(d["total_paid"] for d in debts))
    out_debts = [
        DebtResult(
            name=d["name"],
            months=int(d["months"] or months),
            interest_paid=_round2(d["interest_paid"]),
            total_paid=_round2(d["total_paid"]),
        )
        for d in debts
    ]
    return SimulationResult(
        strategy=strategy,
        months=int(months),
        interest_paid=total_interest,
        total_paid=total_paid,
        debts=out_debts,
        monthly=monthly_schedule if include_schedule else None,
    )
