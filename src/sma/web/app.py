"""FastAPI app factory.

Run locally with:
    uvicorn sma.web.app:app --reload

On Railway / Render this is the entry-point for the `web` service.
"""

from __future__ import annotations

# Load .env into os.environ BEFORE any module that reads os.environ.get(...) runs.
# uvicorn doesn't do this automatically; without it, JWT_SECRET / MASTER_KEY etc.
# raise on first use.
from dotenv import load_dotenv as _load_dotenv  # noqa: E402

_load_dotenv()

from contextlib import asynccontextmanager  # noqa: E402
from typing import AsyncIterator  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from loguru import logger  # noqa: E402

from sma import __version__
from sma.config import get_settings
from sma.web.auth.bootstrap import bootstrap_single_admin
from sma.web.oauth import google as google_oauth
from sma.web.oauth import linkedin as linkedin_oauth
from sma.web.oauth import meta as meta_oauth
from sma.web.oauth import tiktok as tiktok_oauth
from sma.web.routers import (
    actions as actions_routes,
    auth as auth_routes,
    credentials as credentials_routes,
    health as health_routes,
    me as me_routes,
    niches as niches_routes,
    posting_rules as posting_rules_routes,
    posts as posts_routes,
    prompt_templates as prompt_templates_routes,
    schedules as schedules_routes,
    social_accounts as social_accounts_routes,
    topic_sources as topic_sources_routes,
    topics as topics_routes,
    usage as usage_routes,
    whop_webhook as whop_webhook_routes,
)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Startup + shutdown hooks."""
    settings = get_settings()
    logger.info(
        f"Starting Social Media Automation v{__version__} "
        f"(mode={settings.deployment_mode.value})"
    )
    # In Mode A, ensure the admin tenant + user exist on first boot.
    try:
        bootstrap_single_admin()
    except Exception as e:
        # Don't crash the whole app — first request will surface a clearer error.
        logger.error(f"Admin bootstrap failed (non-fatal): {e}")
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Social Media Automation",
        version=__version__,
        description="Niche-agnostic AI content automation — generate + post videos to IG, FB, YouTube, TikTok, LinkedIn.",
        lifespan=_lifespan,
    )

    # CORS:
    #   - In dev (CORS_ALLOWED_ORIGINS unset) we allow any origin so the
    #     localhost:3100 Next.js dev server can hit localhost:8000.
    #   - In production set CORS_ALLOWED_ORIGINS to a comma-separated list
    #     (e.g. "https://app.summitautomates.com,https://summitautomates.com").
    import os as _os
    cors_origins_env = _os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
    cors_origins = (
        [o.strip() for o in cors_origins_env.split(",") if o.strip()]
        if cors_origins_env
        else ["*"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        # `allow_credentials=True` + wildcard origin is rejected by browsers.
        # Toggle credentials off when wildcarding (dev only).
        allow_credentials=(cors_origins != ["*"]),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers — unauthenticated
    app.include_router(health_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(whop_webhook_routes.router)

    # Routers — authenticated (each route depends on CurrentUser)
    app.include_router(me_routes.router)
    app.include_router(niches_routes.router)
    app.include_router(credentials_routes.router)
    app.include_router(social_accounts_routes.router)
    app.include_router(topic_sources_routes.router)
    app.include_router(topics_routes.router)
    app.include_router(posts_routes.router)
    app.include_router(schedules_routes.router)
    app.include_router(posting_rules_routes.router)
    app.include_router(prompt_templates_routes.router)
    app.include_router(usage_routes.router)
    app.include_router(actions_routes.router)

    # OAuth — connect + callback per platform
    app.include_router(meta_oauth.router)
    app.include_router(google_oauth.router)
    app.include_router(tiktok_oauth.router)
    app.include_router(linkedin_oauth.router)

    return app


app = create_app()
