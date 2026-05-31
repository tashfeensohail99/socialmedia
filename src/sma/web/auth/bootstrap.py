"""First-boot bootstrap: in Mode A, ensure a single admin tenant + user exists.

Reads ADMIN_EMAIL and ADMIN_PASSWORD from env. If a user already exists with
that email, it's a no-op. If not, creates tenant id=1 and the admin user.

Called by the FastAPI app on startup. Idempotent.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import select

from sma.config import get_settings
from sma.db.models.tenant import SubscriptionStatus, Tenant
from sma.db.models.user import User, UserRole
from sma.db.session import get_db_session, get_session_factory, set_current_tenant
from sma.web.auth.passwords import hash_password


def bootstrap_single_admin() -> None:
    """Create tenant + admin user on first boot in single-tenant mode."""
    settings = get_settings()
    if settings.deployment_mode.value != "single_tenant":
        logger.debug("Skipping admin bootstrap (multi-tenant mode)")
        return

    email = settings.admin_email.strip().lower()
    password = settings.admin_password
    if not password:
        logger.warning(
            "ADMIN_PASSWORD env var not set — single-tenant admin user not created. "
            "Set it in .env and restart, or use the setup wizard."
        )
        return

    # Bootstrap runs outside any tenant context — go raw via session factory.
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        # Check if the admin already exists (idempotent on restart).
        existing = session.execute(
            select(User).where(User.email == email).execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        if existing is not None:
            logger.info(f"Single-tenant admin already exists: {email}")
            return

        # Ensure tenant id=1 exists.
        tenant = session.get(Tenant, 1)
        if tenant is None:
            tenant = Tenant(
                id=1,
                name="Default Workspace",
                subscription_status=SubscriptionStatus.NONE.value,
            )
            session.add(tenant)
            session.flush()  # populate id without ending the txn

        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            email_verified=True,
        )
        session.add(user)
        session.commit()
        logger.info(f"✓ Bootstrapped single-tenant admin: {email} (tenant_id={tenant.id})")
