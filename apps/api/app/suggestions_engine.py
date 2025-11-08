from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .models import Transactions, TransactionsRaw
import httpx
import re
import hashlib

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

def _stable_index(key: str, n: int) -> int:
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % max(1, n)

def _try_fetch_prices(urls: List[str]) -> Tuple[float | None, List[str]]:
    found: List[float] = []
    ok_links: List[str] = []
    for u in urls:
        try:
            r = httpx.get(u, timeout=2.0)
            if r.status_code >= 200 and r.status_code < 300 and r.text:
                ok_links.append(u)
                m = re.findall(r"\$\s*(\d{1,3}(?:\.\d{1,2})?)\s*/?\s*(?:mo|month)?", r.text, re.I)
                vals = [float(x) for x in m if x]
                if vals:
                    found.append(sorted(vals)[0])
        except Exception:
            continue
    if found:
        vals = sorted(found)
        mid = vals[len(vals)//2]
        return mid, ok_links
    return None, ok_links

def _online_benchmarks(category: str, merchant: str | None = None) -> Tuple[float | None, List[str]]:
    urls: List[str] = []
    cat = (category or "").lower()
    m = (merchant or "").lower()
    if cat == "telco":
        urls = [
            "https://www.spectrum.com/internet/plans",
            "https://www.xfinity.com/learn/internet-service",
            "https://www.att.com/internet/",
        ]
    elif cat == "subscriptions" or any(x in m for x in ("netflix","hulu","disney","spotify","apple tv","youtube")):
        urls = [
            "https://www.netflix.com/signup/planform",
            "https://www.spotify.com/us/premium/",
            "https://www.hulu.com/welcome",
            "https://www.disneyplus.com/subscribe",
        ]
    if not urls:
        return None, []
    price, links = _try_fetch_prices(urls)
    if price is None:
        if cat == "telco":
            return 60.0, urls
        if cat == "subscriptions":
            return 12.0, urls
    return price, links

def _text_blob(r: Tuple) -> str:
    """Lowercased combined merchant/description for keyword heuristics."""
    return f"{(r.merchant_norm or '').lower()} {(r.description or '').lower()}".strip()

def _guess_category(r: Tuple) -> str | None:
    t = _text_blob(r)
    if not t:
        return None
    # transport first to avoid misclassifying "gas station" as utilities
    if any(k in t for k in ("fuel", "gas station", "rideshare", "ride share", "uber", "lyft", "metro", "bus", "train", "parking", "taxi")):
        return "transport"
    # telco / internet / mobile
    if any(k in t for k in ("internet", "isp", "mobile", "telco", "phone")):
        return "telco"
    # utilities (explicit gas utility terms, not gas station)
    if any(k in t for k in ("utilit", "electric", "water", "power", "sewer", "energy", "natural gas", "gas bill", "gas utility", "gas company", "gas co")):
        return "utilities"
    if "insurance" in t:
        return "insurance"
    if any(k in t for k in ("rent", "landlord")):
        return "housing"
    if any(k in t for k in ("grocery", "market")):
        return "grocery"
    if any(k in t for k in ("dining", "restaurant", "sushi", "pizza", "burger", "cafe")):
        return "dining"
    if any(k in t for k in ("stream", "subscription", "netflix", "hulu", "disney", "spotify", "apple tv", "youtube premium")):
        return "subscriptions"
    if any(k in t for k in ("gym", "fitness")):
        return "personal"
    return None

def _recent_joined(db: Session, days: int = 90, user_id: int | None = None) -> List[Tuple]:
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
    if user_id is not None:
        stmt = stmt.where(Transactions.user_id == user_id)
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
            bench, links = _online_benchmarks("subscriptions", merchant)
            templates = [
                "You spend about ${amt:.2f}/mo on {merchant}. Consider canceling or downgrading.",
                "Recurring charge to {merchant} is ~${amt:.2f}/mo. Review plan options and usage.",
                "{merchant} costs ~${amt:.2f}/mo. If value is low, pause or switch to a lower tier.",
            ]
            if bench is not None:
                templates = [
                    "You pay ~${amt:.2f}/mo to {merchant}. Comparable plans are ~${bench:.2f}/mo.",
                    "{merchant} runs ~${amt:.2f}/mo; typical pricing is ~${bench:.2f}/mo per sources.",
                    "{merchant} averages ~${amt:.2f}/mo for you; benchmarks suggest ~${bench:.2f}/mo.",
                ]
            idx = _stable_index(merchant, len(templates))
            summary = templates[idx].format(amt=amt, merchant=merchant, bench=(bench or 0))
            s = Suggestion(
                id=f"sub:{merchant}",
                title=f"Review {merchant} subscription",
                summary=summary,
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
                    "reference_links": links,
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
        if (any(m in key for m in STREAMING_MERCHANTS) or "stream" in key) and _is_monthly_like([r.date for r in items]):
            active.append((merchant, _avg_abs_amount(items), items))
    if len(active) >= 2:
        total = sum(a for _, a, __ in active)
        save = total * 0.3
        templates = [
            "Multiple streaming services detected; trimming could save ~${save:.2f}/mo.",
            "Overlapping streaming subscriptions found; pausing extras could free ~${save:.2f}/mo.",
            "Streamline streaming: reducing overlap may save about ${save:.2f}/mo.",
        ]
        idx = _stable_index("streaming", len(templates))
        summary = templates[idx].format(save=save)
        bench, links = _online_benchmarks("subscriptions", None)
        s = Suggestion(
            id="streaming:consolidate",
            title="Consolidate streaming services",
            summary=summary,
            estimated_monthly_saving=save,
            estimated_annual_saving=save * 12,
            confidence=0.7,
            tags=["subscriptions", "streaming"],
            evidence=[{"merchant": m, "amount": a} for m, a, __ in active] + ([{"reference_links": links}] if links else []),
        )
        out.append(s)
    return out

def suggest_negotiate_utilities(rows: List[Tuple]) -> List[Suggestion]:
    out: List[Suggestion] = []
    for cat in ("telco", "utilities", "insurance"):
        cat_rows = [r for r in rows if ((r.category or _guess_category(r) or "").lower() == cat)]
        # For telco suggestions, require a monthly-like pattern per merchant to avoid single, ad-hoc charges
        if cat == "telco" and cat_rows:
            groups = _group_by_merchant(cat_rows)
            monthly_like_rows: List[Tuple] = []
            for merchant, items in groups.items():
                dates = [r.date for r in items]
                if _is_monthly_like(dates):
                    monthly_like_rows.extend(items)
            cat_rows = monthly_like_rows
        if not cat_rows:
            continue
        amt = _avg_abs_amount(cat_rows)
        if amt <= 0:
            continue
        save = amt * 0.15
        # Deduplicate and take the latest up to 3 samples
        samples = []
        seen = set()
        for it in sorted(cat_rows, key=lambda x: x.date or date.today(), reverse=True):
            key = (it.date, float(abs(it.amount or 0)), (it.description or ""), (it.merchant_norm or ""))
            if key in seen:
                continue
            seen.add(key)
            samples.append({
                "date": (it.date.isoformat() if it.date else None),
                "amount": float(abs(it.amount)) if it.amount is not None else None,
                "description": it.description,
                "merchant": (it.merchant_norm or ""),
            })
            if len(samples) >= 3:
                break
        tpls_no_bench = [
            "Your {cat} average is ~${amt:.2f}/mo; negotiating could save ~${save:.2f}/mo.",
            "You pay about ${amt:.2f}/mo for {cat}. Target a ~15% cut (~${save:.2f}/mo).",
            "{cat.capitalize()} spend is ~${amt:.2f}/mo. Shop or negotiate to save ~${save:.2f}/mo.",
        ]
        tpls_with_bench = [
            "You pay ~${amt:.2f}/mo for {cat}; comparable plans are ~${bench:.2f}/mo.",
            "{cat.capitalize()} runs ~${amt:.2f}/mo; typical offers are near ${bench:.2f}/mo.",
            "Market rates for {cat} average ~${bench:.2f}/mo; yours is ~${amt:.2f}/mo.",
        ]
        bench = None
        links: List[str] = []
        if cat == "telco":
            b, lks = _online_benchmarks("telco")
            bench = b
            links = lks
        idx = _stable_index(cat, len(tpls_with_bench if bench is not None else tpls_no_bench))
        chosen = (tpls_with_bench if bench is not None else tpls_no_bench)[idx]
        summary = chosen.format(cat=cat, amt=amt, save=save, bench=(bench or 0))
        s = Suggestion(
            id=f"negotiate:{cat}",
            title=f"Negotiate {cat}",
            summary=summary,
            estimated_monthly_saving=save,
            estimated_annual_saving=save * 12,
            confidence=0.6,
            tags=[cat, "negotiation"],
            evidence=[{"samples": samples}] + ([{"reference_links": links}] if links else []),
        )
        out.append(s)
    return out

def suggest_reduce_dining(rows: List[Tuple]) -> List[Suggestion]:
    dining = [r for r in rows if ((r.category or _guess_category(r) or "").lower() == "dining")]
    if not dining:
        return []
    total = sum(abs(float(r.amount or 0)) for r in dining)
    if total < 300:
        return []
    save = total * 0.15
    tpls = [
        "Dining totals ~${total:.2f} recently; trimming ~15% saves ~${save:.2f}/mo.",
        "Recent dining is ~${total:.2f}. Set a goal to cut ~15% (~${save:.2f}/mo).",
        "Eating out cost ~${total:.2f} in the period; a modest 15% trim saves ~${save:.2f}/mo.",
    ]
    idx = _stable_index("dining", len(tpls))
    summary = tpls[idx].format(total=total, save=save)
    return [Suggestion(
        id="dining:reduce",
        title="Reduce dining spend",
        summary=summary,
        estimated_monthly_saving=save,
        estimated_annual_saving=save * 12,
        confidence=0.5,
        tags=["dining", "budget"],
        evidence=[{"total": total}],
    )]

def generate_suggestions(db: Session, user_id: int | None = None) -> List[Dict[str, Any]]:
    rows = _recent_joined(db, days=90, user_id=user_id)
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
