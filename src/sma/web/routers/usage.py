"""Usage / cost dashboard — read-only summary of UsageEvent rows.

This is the data source for the cost panel in the admin dashboard.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from sma.db.models.usage_event import UsageEvent
from sma.db.session import get_db_session
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.rules_and_templates import UsageByProviderModel, UsageSummary

router = APIRouter(prefix="/api/usage", tags=["usage"])


def _month_bounds(month: str | None) -> tuple[str, datetime, datetime]:
    """Return (display_month, starting_at, ending_at) for the given YYYY-MM or current month."""
    now = datetime.now(timezone.utc)
    display = month or now.strftime("%Y-%m")
    try:
        year, mo = (int(p) for p in display.split("-"))
    except ValueError as e:
        raise ValueError(f"month must be YYYY-MM, got {display!r}") from e
    starting = datetime(year, mo, 1, tzinfo=timezone.utc)
    # End-of-month = first of next month
    if mo == 12:
        ending = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        ending = datetime(year, mo + 1, 1, tzinfo=timezone.utc)
    return display, starting, ending


@router.get("/summary", response_model=UsageSummary)
def usage_summary(
    user: CurrentUser,
    month: str | None = Query(None, description="YYYY-MM; defaults to current month"),
) -> UsageSummary:
    display, starting, ending = _month_bounds(month)
    with get_db_session() as session:
        total_events = session.scalar(
            select(func.count(UsageEvent.id)).where(
                UsageEvent.occurred_at >= starting,
                UsageEvent.occurred_at < ending,
            )
        ) or 0
        total_cost = session.scalar(
            select(func.coalesce(func.sum(UsageEvent.cost_usd), 0.0)).where(
                UsageEvent.occurred_at >= starting,
                UsageEvent.occurred_at < ending,
            )
        ) or 0.0

        rows = session.execute(
            select(
                UsageEvent.provider,
                UsageEvent.model,
                func.count(UsageEvent.id).label("calls"),
                func.coalesce(func.sum(UsageEvent.tokens_in), 0).label("tokens_in"),
                func.coalesce(func.sum(UsageEvent.tokens_out), 0).label("tokens_out"),
                func.coalesce(func.sum(UsageEvent.units), 0).label("units"),
                func.coalesce(func.sum(UsageEvent.cost_usd), 0.0).label("cost_usd"),
            )
            .where(
                UsageEvent.occurred_at >= starting,
                UsageEvent.occurred_at < ending,
            )
            .group_by(UsageEvent.provider, UsageEvent.model)
            .order_by(func.sum(UsageEvent.cost_usd).desc().nulls_last())
        ).all()

    by_pm = [
        UsageByProviderModel(
            provider=r.provider,
            model=r.model,
            calls=int(r.calls),
            tokens_in=int(r.tokens_in),
            tokens_out=int(r.tokens_out),
            units=int(r.units),
            cost_usd=float(r.cost_usd),
        )
        for r in rows
    ]
    return UsageSummary(
        month=display,
        total_events=int(total_events),
        total_cost_usd=float(total_cost),
        by_provider_model=by_pm,
        starting_at=starting,
        ending_at=ending,
    )
