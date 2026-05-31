"""Niches CRUD — the personality + provider config for a content stream.

All routes auto-scope by tenant via the JWT dependency. The tenant scoping
middleware in db.session enforces this at the query level too — even if a
route forgot the manual filter, queries would still return only the current
tenant's rows.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from sma.db.crypto import decrypt_blob
from sma.db.models.credentials import Credentials
from sma.db.models.niche import Niche
from sma.db.models.topic import TopicSource
from sma.db.session import get_db_session
from sma.providers.registry import get_provider
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.common import Page, PageMeta
from sma.web.schemas.niche import NicheCreate, NicheRead, NicheUpdate

router = APIRouter(prefix="/api/niches", tags=["niches"])

# Google News RSS is free + unlimited. We build a search query from the niche
# so every new niche gets an autonomous news source with zero manual setup.
_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


def _build_news_query(niche: Niche) -> str:
    """Derive a Google News search query from the niche's pillars (or name)."""
    import urllib.parse

    pillars = [p.split("(")[0].strip() for p in (niche.content_pillars or []) if p.strip()]
    terms = pillars[:4] if pillars else [niche.name]
    # OR the pillars together so the feed is broad but on-topic.
    raw = " OR ".join(f'"{t}"' for t in terms)
    return urllib.parse.quote(raw)


def _seed_rss_source(session, niche: Niche) -> None:
    """Auto-create an enabled RSS topic source for a new niche (idempotent)."""
    existing = session.execute(
        select(TopicSource).where(
            TopicSource.niche_id == niche.id, TopicSource.kind == "rss"
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    feed_url = _GOOGLE_NEWS_RSS.format(query=_build_news_query(niche))
    session.add(
        TopicSource(
            tenant_id=niche.tenant_id,
            niche_id=niche.id,
            kind="rss",
            config_json={"feed_urls": [feed_url], "items_per_feed": 10},
            enabled=True,
        )
    )


@router.get("", response_model=Page[NicheRead])
def list_niches(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[NicheRead]:
    with get_db_session() as session:
        total = session.scalar(select(func.count(Niche.id))) or 0
        rows = session.scalars(
            select(Niche).order_by(Niche.id.desc()).limit(limit).offset(offset)
        ).all()
        return Page[NicheRead](
            items=[NicheRead.model_validate(r) for r in rows],
            meta=PageMeta(total=total, limit=limit, offset=offset),
        )


class DraftNicheRequest(BaseModel):
    business_description: str = Field(
        ..., min_length=200,
        description="Free-text description of the client's business (≥ ~250 words recommended).",
    )


class DraftNicheResponse(BaseModel):
    name: str
    description: str
    target_audience: str
    tone: str
    content_pillars: list[str]
    forbidden_topics: list[str]
    hashtag_seeds: list[str]
    cta: str
    news_search_query: str = Field(
        "", description="Suggested Google-News-style search query for the worker."
    )


_DRAFT_SYSTEM = (
    "You are a social-media strategist. Given a business description, you design a "
    "complete content NICHE for an automated short-video bot that turns NEWS into posts. "
    "Return ONLY valid JSON, no markdown."
)


def _draft_prompt(business_description: str) -> str:
    return f"""A client described their business below. Design a content niche for an
automated bot that monitors NEWS and turns relevant articles into short social videos
that always tie back to this client's business.

CLIENT'S BUSINESS
=================
{business_description}

YOUR TASK
=========
Produce a JSON object with EXACTLY these keys:
- "name": short label (≤ 60 chars) for this content stream
- "description": 3-5 sentences describing what the niche covers, the angle, and how
  every post should connect back to the client's business
- "target_audience": one sentence on who the content is for
- "tone": short style instruction (e.g. "informative, trustworthy, simple Urdu/English mix")
- "content_pillars": 4-7 SHORT news topics/keywords the bot should search for. These drive
  the news feed — make them concrete search terms, not sentences.
- "forbidden_topics": 2-5 things to avoid (politics, religion, anything off-brand or risky)
- "hashtag_seeds": 5-8 hashtags WITHOUT the # symbol
- "cta": one short call-to-action line pointing back to the client's business
- "news_search_query": a single search query (terms joined with OR) the bot can paste into
  a news search to find articles for this niche

Output strictly as JSON, no commentary."""


@router.post("/draft-from-description", response_model=DraftNicheResponse)
def draft_niche_from_description(
    payload: DraftNicheRequest, user: CurrentUser
) -> DraftNicheResponse:
    """Use the tenant's own OpenAI key to turn a free-text business description into a
    structured niche draft. Does NOT persist anything — the frontend shows the draft for
    review, then calls POST /api/niches to save it."""
    # Load the tenant's OpenAI credential.
    with get_db_session() as session:
        cred = session.execute(
            select(Credentials).where(
                Credentials.provider_kind == "llm",
                Credentials.provider_name == "openai",
            )
        ).scalar_one_or_none()
        if cred is None:
            raise HTTPException(
                status_code=412,
                detail="Add your OpenAI API key on the API Keys page first.",
            )
        creds = decrypt_blob(cred.encrypted_blob)

    try:
        llm = get_provider("llm", "openai", **creds)
        resp = llm.complete(
            system=_DRAFT_SYSTEM,
            user=_draft_prompt(payload.business_description),
            model="gpt-4o-mini",
            temperature=0.7,
            json_mode=True,
        )
        data = json.loads(resp.text)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"AI returned invalid JSON: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI niche generation failed: {e}") from e

    def _as_list(v: object) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [s.strip() for s in v.split(",") if s.strip()]
        return []

    return DraftNicheResponse(
        name=str(data.get("name", "")).strip()[:120] or "My Niche",
        description=str(data.get("description", "")).strip(),
        target_audience=str(data.get("target_audience", "")).strip(),
        tone=str(data.get("tone", "informative, trustworthy")).strip(),
        content_pillars=_as_list(data.get("content_pillars")),
        forbidden_topics=_as_list(data.get("forbidden_topics")),
        hashtag_seeds=_as_list(data.get("hashtag_seeds")),
        cta=str(data.get("cta", "")).strip(),
        news_search_query=str(data.get("news_search_query", "")).strip(),
    )


@router.post("", response_model=NicheRead, status_code=status.HTTP_201_CREATED)
def create_niche(payload: NicheCreate, user: CurrentUser) -> NicheRead:
    with get_db_session() as session:
        niche = Niche(tenant_id=user.tenant_id, **payload.model_dump())
        session.add(niche)
        session.flush()
        # Auto-seed a free Google News RSS source so the niche is autonomous
        # immediately — no manual Topic Source setup needed.
        _seed_rss_source(session, niche)
        session.flush()
        session.refresh(niche)
        return NicheRead.model_validate(niche)


@router.get("/{niche_id}", response_model=NicheRead)
def get_niche(niche_id: int, user: CurrentUser) -> NicheRead:
    with get_db_session() as session:
        niche = session.get(Niche, niche_id)
        if niche is None or niche.tenant_id != user.tenant_id:
            # Don't leak existence across tenants — same 404 for both cases.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="niche not found")
        return NicheRead.model_validate(niche)


@router.patch("/{niche_id}", response_model=NicheRead)
def update_niche(niche_id: int, payload: NicheUpdate, user: CurrentUser) -> NicheRead:
    with get_db_session() as session:
        niche = session.get(Niche, niche_id)
        if niche is None or niche.tenant_id != user.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="niche not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(niche, field, value)
        session.flush()
        session.refresh(niche)
        return NicheRead.model_validate(niche)


@router.delete("/{niche_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_niche(niche_id: int, user: CurrentUser) -> None:
    with get_db_session() as session:
        niche = session.get(Niche, niche_id)
        if niche is None or niche.tenant_id != user.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="niche not found")
        session.delete(niche)
