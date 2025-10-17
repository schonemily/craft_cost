from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Debt:
    name: str
    balance: float
    apr: float  # annual, percent or decimal
    min_payment: float


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


def _apr_monthly(apr: float) -> float:
    # accept APR given as 0.1999 (19.99%) or 19.99 (percent)
    if apr is None:
        return 0.0
    return (apr / 100.0 if apr > 1 else apr) / 12.0


def _round2(x: float) -> float:
    return float(round(x + 1e-10, 2))


def simulate(debts_in: List[Debt], extra: float, strategy: str) -> SimulationResult:
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
            "rate": _apr_monthly(float(d.apr or 0.0)),
            "min": _round2(float(d.min_payment)),
            "interest_paid": 0.0,
            "total_paid": 0.0,
            "months": 0,
        })
    if not debts:
        return SimulationResult(strategy=strategy, months=0, interest_paid=0.0, total_paid=0.0, debts=[])

    months = 0
    cap_months = 600  # 50 years cap

    while True:
        active = [d for d in debts if d["balance"] > 0.01]
        if not active:
            break
        months += 1
        if months > cap_months:
            break

        # 1) accrue interest
        for d in active:
            intr = _round2(d["balance"] * d["rate"]) if d["rate"] > 0 else 0.0
            d["balance"] = _round2(d["balance"] + intr)
            d["interest_paid"] = _round2(d["interest_paid"] + intr)

        # recompute active after interest (all positive)
        active = [d for d in debts if d["balance"] > 0.01]
        if not active:
            break

        # 2) compute total budget: sum of mins for active + extra
        total_budget = _round2(sum(d["min"] for d in active) + max(0.0, float(extra or 0.0)))

        # 3) pay minimums to all active
        budget = total_budget
        for d in active:
            pay = min(d["min"], d["balance"])  # don't overpay at this step
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

        # 5) stamp months for debts paid off this cycle
        for d in debts:
            if d["months"] == 0 and d["balance"] <= 0.01:
                d["months"] = months

        # safety: if budget still positive but no balances reduced (e.g., zero min and zero balance), break
        if months > cap_months:
            break

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
    )
