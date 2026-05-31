"""initial_schema

Revision ID: 39c6e5aae1ea
Revises:
Create Date: 2026-05-19 20:02:33.215418

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39c6e5aae1ea'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: Order of create_table matters on Postgres (FK targets must
    # already exist). The auto-generated alphabetical-ish order works on
    # SQLite but breaks Postgres with "relation does not exist". We
    # hand-ordered this into dependency layers. The circular FK between
    # `topics` and `posts` (each references the other) is broken by
    # creating `topics` without `used_for_post_id`'s FK, then adding it
    # via ALTER TABLE at the end with `op.create_foreign_key`.

    # ─── Layer 0: independent tables ──────────────────────────────────
    op.create_table('tenants',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('subscription_status', sa.String(length=32), nullable=False),
    sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('stripe_customer_id', sa.String(length=64), nullable=True),
    sa.Column('stripe_subscription_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('stripe_customer_id'),
    sa.UniqueConstraint('stripe_subscription_id')
    )

    # ─── Layer 1: tables depending only on tenants ────────────────────
    op.create_table('niches',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('target_audience', sa.Text(), nullable=False),
    sa.Column('tone', sa.String(length=255), nullable=False),
    sa.Column('language', sa.String(length=8), nullable=False),
    sa.Column('content_pillars', sa.JSON(), nullable=False),
    sa.Column('forbidden_topics', sa.JSON(), nullable=False),
    sa.Column('cta', sa.Text(), nullable=False),
    sa.Column('hashtag_seeds', sa.JSON(), nullable=False),
    sa.Column('video_length_default', sa.String(length=16), nullable=False),
    sa.Column('image_aspect_default', sa.String(length=8), nullable=False),
    sa.Column('image_count_short', sa.Integer(), nullable=False),
    sa.Column('image_count_long', sa.Integer(), nullable=False),
    sa.Column('llm_provider', sa.String(length=32), nullable=False),
    sa.Column('llm_model', sa.String(length=64), nullable=False),
    sa.Column('image_provider', sa.String(length=32), nullable=False),
    sa.Column('voice_provider', sa.String(length=32), nullable=False),
    sa.Column('voice_id', sa.String(length=64), nullable=False),
    sa.Column('voice_model', sa.String(length=64), nullable=True),
    sa.Column('music_provider', sa.String(length=32), nullable=False),
    sa.Column('music_enabled', sa.Boolean(), nullable=False),
    sa.Column('topic_score_threshold', sa.Float(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('niches', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_niches_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('credentials',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('provider_kind', sa.String(length=32), nullable=False),
    sa.Column('provider_name', sa.String(length=64), nullable=False),
    sa.Column('label', sa.String(length=64), nullable=False),
    sa.Column('encrypted_blob', sa.LargeBinary(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'provider_kind', 'provider_name', 'label', name='uq_credentials_tenant_provider_label')
    )
    with op.batch_alter_table('credentials', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_credentials_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('posting_rules',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('type', sa.String(length=32), nullable=False),
    sa.Column('params_json', sa.JSON(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('posting_rules', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_posting_rules_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('prompt_templates',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('slug', sa.String(length=64), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'slug', name='uq_prompt_template_tenant_slug')
    )
    with op.batch_alter_table('prompt_templates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_prompt_templates_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('social_accounts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('platform', sa.String(length=32), nullable=False),
    sa.Column('account_handle', sa.String(length=255), nullable=False),
    sa.Column('encrypted_oauth_blob', sa.LargeBinary(), nullable=False),
    sa.Column('refresh_token_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'platform', 'account_handle', name='uq_social_account_tenant_platform_handle')
    )
    with op.batch_alter_table('social_accounts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_social_accounts_platform'), ['platform'], unique=False)
        batch_op.create_index(batch_op.f('ix_social_accounts_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('email_verified', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_tenant_id'), ['tenant_id'], unique=False)

    # ─── Layer 2: tables depending on niches ──────────────────────────
    op.create_table('topic_sources',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('niche_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('config_json', sa.JSON(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['niche_id'], ['niches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('topic_sources', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_topic_sources_niche_id'), ['niche_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_topic_sources_tenant_id'), ['tenant_id'], unique=False)

    # ─── Layer 3: topics + posts (circular) ───────────────────────────
    # `topics` is created WITHOUT the FK on used_for_post_id; that FK is
    # added at the bottom with op.create_foreign_key once `posts` exists.
    op.create_table('topics',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=True),
    sa.Column('content_hash', sa.String(length=32), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('score_reason', sa.Text(), nullable=False),
    sa.Column('suggested_angle', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('used_for_post_id', sa.Integer(), nullable=True),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['topic_sources.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    # used_for_post_id FK added via op.create_foreign_key below
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('topics', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_topics_content_hash'), ['content_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_topics_source_id'), ['source_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_topics_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_topics_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('posts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('niche_id', sa.Integer(), nullable=False),
    sa.Column('topic_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('video_length', sa.String(length=16), nullable=False),
    sa.Column('video_format', sa.String(length=32), nullable=False),
    sa.Column('caption', sa.Text(), nullable=False),
    sa.Column('hashtags', sa.JSON(), nullable=False),
    sa.Column('narrative_script', sa.Text(), nullable=False),
    sa.Column('hook_text', sa.String(length=255), nullable=False),
    sa.Column('story_beats_json', sa.JSON(), nullable=False),
    sa.Column('llm_model', sa.String(length=64), nullable=False),
    sa.Column('image_provider', sa.String(length=32), nullable=False),
    sa.Column('voice_provider', sa.String(length=32), nullable=False),
    sa.Column('music_provider', sa.String(length=32), nullable=True),
    sa.Column('duration_sec', sa.Float(), nullable=False),
    sa.Column('image_count', sa.Integer(), nullable=False),
    sa.Column('media_cost_usd', sa.Float(), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_log', sa.Text(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['niche_id'], ['niches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_posts_niche_id'), ['niche_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_posts_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_posts_tenant_id'), ['tenant_id'], unique=False)

    # Now close the circular reference: topics.used_for_post_id → posts.id
    op.create_foreign_key(
        'fk_topics_used_for_post_id',
        'topics', 'posts',
        ['used_for_post_id'], ['id'],
        ondelete='SET NULL',
    )

    # ─── Layer 4: tables depending on posts ───────────────────────────
    op.create_table('media_assets',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('path_or_url', sa.String(length=1024), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=True),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('media_assets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_media_assets_post_id'), ['post_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_media_assets_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('schedules',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('scheduled_for_utc', sa.DateTime(timezone=True), nullable=False),
    sa.Column('platforms_json', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('attempts_count', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_schedules_post_id'), ['post_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_schedules_scheduled_for_utc'), ['scheduled_for_utc'], unique=False)
        batch_op.create_index(batch_op.f('ix_schedules_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_schedules_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('usage_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('model', sa.String(length=64), nullable=False),
    sa.Column('operation', sa.String(length=32), nullable=False),
    sa.Column('tokens_in', sa.Integer(), nullable=False),
    sa.Column('tokens_out', sa.Integer(), nullable=False),
    sa.Column('units', sa.Integer(), nullable=False),
    sa.Column('cost_usd', sa.Float(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('usage_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usage_events_occurred_at'), ['occurred_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_usage_events_post_id'), ['post_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_usage_events_provider'), ['provider'], unique=False)
        batch_op.create_index(batch_op.f('ix_usage_events_tenant_id'), ['tenant_id'], unique=False)

    # ─── Layer 5: tables depending on schedules ───────────────────────
    op.create_table('posting_attempts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('schedule_id', sa.Integer(), nullable=False),
    sa.Column('platform', sa.String(length=32), nullable=False),
    sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('external_post_id', sa.String(length=255), nullable=True),
    sa.Column('response_log', sa.JSON(), nullable=False),
    sa.Column('error', sa.Text(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('posting_attempts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_posting_attempts_schedule_id'), ['schedule_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_posting_attempts_tenant_id'), ['tenant_id'], unique=False)


def downgrade() -> None:
    # Drop in reverse dependency order. Break the topics↔posts circle by
    # dropping the deferred FK first, then dropping both tables.
    with op.batch_alter_table('posting_attempts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_posting_attempts_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_posting_attempts_schedule_id'))
    op.drop_table('posting_attempts')

    with op.batch_alter_table('usage_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usage_events_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_usage_events_provider'))
        batch_op.drop_index(batch_op.f('ix_usage_events_post_id'))
        batch_op.drop_index(batch_op.f('ix_usage_events_occurred_at'))
    op.drop_table('usage_events')

    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_schedules_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_schedules_status'))
        batch_op.drop_index(batch_op.f('ix_schedules_scheduled_for_utc'))
        batch_op.drop_index(batch_op.f('ix_schedules_post_id'))
    op.drop_table('schedules')

    with op.batch_alter_table('media_assets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_media_assets_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_media_assets_post_id'))
    op.drop_table('media_assets')

    # Drop the circular FK before dropping either table.
    op.drop_constraint('fk_topics_used_for_post_id', 'topics', type_='foreignkey')

    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_posts_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_posts_status'))
        batch_op.drop_index(batch_op.f('ix_posts_niche_id'))
    op.drop_table('posts')

    with op.batch_alter_table('topics', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_topics_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_topics_status'))
        batch_op.drop_index(batch_op.f('ix_topics_source_id'))
        batch_op.drop_index(batch_op.f('ix_topics_content_hash'))
    op.drop_table('topics')

    with op.batch_alter_table('topic_sources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_topic_sources_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_topic_sources_niche_id'))
    op.drop_table('topic_sources')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_users_email'))
    op.drop_table('users')

    with op.batch_alter_table('social_accounts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_social_accounts_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_social_accounts_platform'))
    op.drop_table('social_accounts')

    with op.batch_alter_table('prompt_templates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_prompt_templates_tenant_id'))
    op.drop_table('prompt_templates')

    with op.batch_alter_table('posting_rules', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_posting_rules_tenant_id'))
    op.drop_table('posting_rules')

    with op.batch_alter_table('credentials', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_credentials_tenant_id'))
    op.drop_table('credentials')

    with op.batch_alter_table('niches', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_niches_tenant_id'))
    op.drop_table('niches')

    op.drop_table('tenants')
