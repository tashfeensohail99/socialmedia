"""All ORM models — imported here so Alembic autogenerate sees every table."""

from sma.db.base import Base  # noqa: F401

# Tenant + users
from sma.db.models.tenant import Tenant  # noqa: F401
from sma.db.models.user import User  # noqa: F401

# Provider configs + credentials
from sma.db.models.credentials import Credentials  # noqa: F401
from sma.db.models.prompt_template import PromptTemplate  # noqa: F401

# Niche / topic / pipeline
from sma.db.models.niche import Niche  # noqa: F401
from sma.db.models.topic import Topic, TopicSource  # noqa: F401
from sma.db.models.post import Post, MediaAsset, PostStatus  # noqa: F401
from sma.db.models.schedule import Schedule, PostingAttempt, ScheduleStatus  # noqa: F401

# Social accounts (OAuth tokens) + in-flight OAuth state
from sma.db.models.oauth_state import OAuthState  # noqa: F401
from sma.db.models.social_account import SocialAccount  # noqa: F401

# Usage tracking + posting rules + provider pricing
from sma.db.models.usage_event import UsageEvent  # noqa: F401
from sma.db.models.posting_rule import PostingRule  # noqa: F401
