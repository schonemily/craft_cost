from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .models import Transactions, TransactionsRaw

@dataclass
class Suggestion:
    id: str
    title: str
    summary: str
    estimated_monthly_saving: float
    estimated_annual_saving: float
    confidence: float
    tags: List[str]
    evidence: List[Dict[str, Any]]

STREAMING_MERCHANTS = {
    "netflix", "hulu", "disney", "prime video", "hbomax", "max", "spotify", "apple tv", "youtube premium",
}

def _recent_joined(db: Session, days: int = 90) -> List[Tuple]:
    since = func.current_date() - days
    stmt = (
        select(
            Transactions.id.label("id"),
            Transactions.user_id,
            Transactions.category,
            Transactions.merchant_norm,
            TransactionsRaw.date,
            TransactionsRaw.amount,
            TransactionsRaw.description,
        )
        .join(TransactionsRaw, Transactions.tx_id == TransactionsRaw.id)
        .where(TransactionsRaw.date >= since)
    )
    return db.execute(stmt).all()

def _group_by_merchant(rows: List[Tuple]) -> Dict[str, List[Tuple]]:
    g: Dict[str, List[Tuple]] = {}
    for r in rows:
        key = (r.merchant_norm or r.description or "").lower().strip()
        g.setdefault(key, []).append(r)
    return g

def _avg_abs_amount(rows: List[Tuple]) -> float:
    vals = [abs(float(r.amount)) for r in rows if r.amount is not None]
    return float(sum(vals) / len(vals)) if vals else 0.0

def _is_monthly_like(dates: List[date]) -> bool:
    if len(dates) < 2:
        return False
    dates = sorted([d for d in dates if d is not None])
    if len(dates) < 2:
        return False
    span_days = (dates[-1] - dates[0]).days
    avg_interval = span_days / (len(dates) - 1) if len(dates) > 1 else 0
    return 20 <= avg_interval <= 40

def suggest_recurring_subscriptions(rows: List[Tuple]) -> List[Suggestion]:
    out: List[Suggestion] = []
    groups = _group_by_merchant(rows)
    for merchant, items in groups.items():
        if not merchant:
            continue
        dates = [r.date for r in items]
        if _is_monthly_like(dates):
            amt = _avg_abs_amount(items)
            if amt <= 0:
                continue
            s = Suggestion(
                id=f"sub:{merchant}",
                title=f"Cancel or downgrade {merchant}",
                summary=f"You appear to pay about ${amt:.2f}/mo to {merchant}.",
                estimated_monthly_saving=amt,
                estimated_annual_saving=amt * 12,
                confidence=0.8,
                tags=["subscriptions"],
                evidence=[{
                    "merchant": (items[0].merchant_norm or "").lower(),
                    "samples": [
                        {
                            "date": (it.date.isoformat() if it.date else None),
                            "amount": float(abs(it.amount)) if it.amount is not None else None,
                            "description": it.description,
                        }
                        for it in sorted(items, key=lambda x: x.date or date.today())[-3:]
                    ],
                }],
            )
            out.append(s)
    return out

def suggest_streaming_consolidation(rows: List[Tuple]) -> List[Suggestion]:
    out: List[Suggestion] = []
    groups = _group_by_merchant(rows)
    active = []
    for merchant, items in groups.items():
        key = merchant.lower()
        if any(m in key for m in STREAMING_MERCHANTS) and _is_monthly_like([r.date for r in items]):
            active.append((merchant, _avg_abs_amount(items), items))
    if len(active) >= 2:
        total = sum(a for _, a, __ in active)
        save = total * 0.3
        s = Suggestion(
            id="streaming:consolidate",
            title="Consolidate streaming services",
            summary=f"Multiple streaming subscriptions detected. Consider canceling extras to save about ${save:.2f}/mo.",
            estimated_monthly_saving=save,
            estimated_annual_saving=save * 12,
            confidence=0.7,
            tags=["subscriptions", "streaming"],
            evidence=[{"merchant": m, "amount": a} for m, a, __ in active],
        )
        out.append(s)
    return out

def suggest_negotiate_utilities(rows: List[Tuple]) -> List[Suggestion]:
    out: List[Suggestion] = []
    for cat in ("telco", "utilities", "insurance"):
        cat_rows = [r for r in rows if (r.category or "").lower() == cat]
        if not cat_rows:
            continue
        amt = _avg_abs_amount(cat_rows)
        if amt <= 0:
            continue
        save = amt * 0.15
        s = Suggestion(
            id=f"negotiate:{cat}",
            title=f"Negotiate {cat}",
            summary=f"Try negotiating your {cat} bill for ~15% savings (~${save:.2f}/mo).",
            estimated_monthly_saving=save,
            estimated_annual_saving=save * 12,
            confidence=0.6,
            tags=[cat, "negotiation"],
            evidence=[{"samples": min(3, len(cat_rows))}],
        )
        out.append(s)
    return out

def suggest_reduce_dining(rows: List[Tuple]) -> List[Suggestion]:
    last_30 = [r for r in rows if r.date is not None and (func.current_date() - 30) is not None]
    dining = [r for r in rows if (r.category or "").lower() == "dining"]
    if not dining:
        return []
    total = sum(abs(float(r.amount or 0)) for r in dining)
    if total < 300:
        return []
    save = total * 0.15
    return [Suggestion(
        id="dining:reduce",
        title="Reduce dining spend",
        summary=f"Dining spend in the recent period is ~${total:.2f}. Aim to reduce by ~15% (~${save:.2f}/mo).",
        estimated_monthly_saving=save,
        estimated_annual_saving=save * 12,
        confidence=0.5,
        tags=["dining", "budget"],
        evidence=[{"total": total}],
    )]

def generate_suggestions(db: Session) -> List[Dict[str, Any]]:
    rows = _recent_joined(db, days=90)
    suggestions: List[Suggestion] = []
    for fn in (
        suggest_recurring_subscriptions,
        suggest_streaming_consolidation,
        suggest_negotiate_utilities,
        suggest_reduce_dining,
    ):
        suggestions.extend(fn(rows))
    seen = set()
    uniq: List[Suggestion] = []
    for s in suggestions:
        if s.id in seen:
            continue
        seen.add(s.id)
        uniq.append(s)
    return [s.__dict__ for s in uniq]
