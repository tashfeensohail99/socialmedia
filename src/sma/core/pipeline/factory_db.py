"""DB-driven PipelineContext factory.

Replaces the .env-driven `factory.build_context` for the web/worker code paths.
Reads the niche + credentials from Postgres (already tenant-scoped via the
session middleware), maps DB columns → in-memory NicheConfig, instantiates
the provider classes, returns a ready-to-run PipelineContext.

The original `factory.py` (env-driven) is still used by the CLI and Phase 1
smoke runner; this is the addition, not a replacement.
"""

from __future__ import annotations

from sqlalchemy import select

from sma.core.niche.config import NicheConfig
from sma.core.pipeline.context import PipelineContext
from sma.db.crypto import decrypt_blob
from sma.db.models.credentials import Credentials
from sma.db.models.niche import Niche as NicheRow
from sma.db.session import get_db_session, require_current_tenant
from sma.providers.image.base import ImageProvider
from sma.providers.llm.base import LLMProvider
from sma.providers.music.base import MusicProvider
from sma.providers.registry import get_provider
from sma.providers.voice.base import VoiceProvider


class MissingCredentialsError(RuntimeError):
    """Tenant tried to run the pipeline without credentials for a required provider."""


def _row_to_niche_config(row: NicheRow) -> NicheConfig:
    """ORM row → NicheConfig (mirror fields 1:1)."""
    return NicheConfig(
        name=row.name,
        description=row.description,
        target_audience=row.target_audience,
        tone=row.tone,
        language=row.language,
        content_pillars=list(row.content_pillars or []),
        forbidden_topics=list(row.forbidden_topics or []),
        cta=row.cta,
        hashtag_seeds=list(row.hashtag_seeds or []),
        video_length_default=row.video_length_default,  # type: ignore[arg-type]
        llm_provider=row.llm_provider,
        llm_model=row.llm_model,
        image_provider=row.image_provider,
        image_aspect_default=row.image_aspect_default,
        image_count_short=row.image_count_short,
        image_count_long=row.image_count_long,
        voice_provider=row.voice_provider,
        voice_id=row.voice_id,
        voice_model=row.voice_model,
        music_provider=row.music_provider,
        music_enabled=row.music_enabled,
        topic_score_threshold=row.topic_score_threshold,
    )


def _load_credentials(
    session, provider_kind: str, provider_name: str, label: str = "default"
) -> dict:
    """Load + decrypt the credentials row for (kind, name, label) in the current tenant."""
    row = session.execute(
        select(Credentials).where(
            Credentials.provider_kind == provider_kind,
            Credentials.provider_name == provider_name,
            Credentials.label == label,
        )
    ).scalar_one_or_none()
    if row is None:
        raise MissingCredentialsError(
            f"No credentials for {provider_kind}/{provider_name} (label={label!r}). "
            f"POST /api/credentials with the API key first."
        )
    return decrypt_blob(row.encrypted_blob)


def build_context_for_niche(niche_id: int) -> tuple[PipelineContext, NicheRow]:
    """Load niche + all required credentials, return an instantiated PipelineContext.

    Caller must have set the tenant context (via JWT auth dependency or
    `tenant_scope(...)`) before calling this. Raises if niche or any required
    credentials aren't present.
    """
    tenant_id = require_current_tenant()
    with get_db_session() as session:
        niche_row = session.get(NicheRow, niche_id)
        if niche_row is None or niche_row.tenant_id != tenant_id:
            raise ValueError(f"niche {niche_id} not found in tenant {tenant_id}")

        niche_cfg = _row_to_niche_config(niche_row)

        # Detach the row with all attributes loaded so callers can safely read
        # niche_row.* after this session closes (avoids DetachedInstanceError).
        session.refresh(niche_row)
        session.expunge(niche_row)

        # Load credentials for every provider the niche references.
        llm_creds = _load_credentials(session, "llm", niche_cfg.llm_provider)
        image_creds = _load_credentials(session, "image", niche_cfg.image_provider)

        # Voice: openai_tts / dalle-style providers reuse the OpenAI LLM key, so
        # if a dedicated voice credential isn't stored, fall back to the OpenAI
        # key the tenant already has. Same for music providers that piggyback.
        try:
            voice_creds = _load_credentials(session, "voice", niche_cfg.voice_provider)
        except MissingCredentialsError:
            if niche_cfg.voice_provider == "openai_tts":
                voice_creds = _load_credentials(session, "llm", "openai")
            else:
                raise

        music_creds: dict | None = None
        if niche_cfg.music_enabled:
            if niche_cfg.music_provider == "local":
                # Bundled local tracks need no credentials.
                music_creds = {}
            else:
                try:
                    music_creds = _load_credentials(session, "music", niche_cfg.music_provider)
                except MissingCredentialsError:
                    # Music is optional — if not configured, run with music disabled.
                    music_creds = None

    llm: LLMProvider = get_provider("llm", niche_cfg.llm_provider, **llm_creds)
    image: ImageProvider = get_provider("image", niche_cfg.image_provider, **image_creds)
    voice: VoiceProvider = get_provider("voice", niche_cfg.voice_provider, **voice_creds)
    music: MusicProvider | None = None
    if music_creds is not None:
        music = get_provider("music", niche_cfg.music_provider, **music_creds)

    ctx = PipelineContext(
        niche=niche_cfg,
        llm=llm,
        image=image,
        voice=voice,
        music=music,
        tenant_id=tenant_id,
    )
    return ctx, niche_row
