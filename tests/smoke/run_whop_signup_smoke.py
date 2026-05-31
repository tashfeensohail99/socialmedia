"""Simulates the full Whop signup flow:

  1. POST /api/webhooks/whop with a `membership.went_valid` payload
  2. Verify a tenant + user were created
  3. Capture the magic-link URL from the email sender (LoggingSender logs it)
  4. POST /api/auth/magic-login with the token from the URL
  5. Verify the returned session JWT can hit /api/me

Runs in multi_tenant mode against an isolated SQLite DB so it doesn't touch
the dev one.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from pathlib import Path

# Force UTF-8 stdout for Windows.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

# Load .env defaults
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip())

# Isolated test DB
test_db = Path("data/sma_whop_smoke.db")
test_db.parent.mkdir(parents=True, exist_ok=True)
test_db.unlink(missing_ok=True)
os.environ["SMA_DATABASE_URL"] = f"sqlite:///{test_db.as_posix()}"
os.environ["DEPLOYMENT_MODE"] = "multi_tenant"
os.environ["PUBLIC_BASE_URL"] = "http://localhost:8000"
# Leave WHOP_WEBHOOK_SECRET unset → falls back to dev "no-signature" mode
# (multi_tenant mode requires it, so set a stub):
os.environ["WHOP_WEBHOOK_SECRET"] = "smoke-test-secret"

sys.path.insert(0, "src")

# Apply migrations
subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    env={**os.environ}, check=True, capture_output=True,
)

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from sma.web.app import create_app
from sma.web.email.sender import EmailMessage, EmailSender, set_sender

PASS = "[PASS]"
FAIL = "[FAIL]"


def expect(label: str, cond: bool, detail: str = "") -> bool:
    print(f"  {PASS if cond else FAIL} {label}{(' — ' + detail) if detail else ''}")
    return cond


class CapturingSender:
    """Captures sent emails so the smoke can extract magic-link URLs."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, msg: EmailMessage) -> None:
        self.sent.append(msg)


def whop_signature(body: bytes) -> str:
    return hmac.new(b"smoke-test-secret", body, hashlib.sha256).hexdigest()


def main() -> int:
    failures = 0
    capture = CapturingSender()
    set_sender(capture)

    with TestClient(create_app()) as client:
        # 1. Send the Whop webhook payload (membership.went_valid)
        print("=== 1. Webhook → tenant creation ===")
        payload = {
            "event": "membership.went_valid",
            "data": {
                "id": "mem_smoke_001",
                "status": "valid",
                "expires_at": "2027-05-19T00:00:00Z",
                "user": {
                    "id": "user_smoke_001",
                    "email": "newbuyer@summitautomates.com",
                },
                "product": {"id": "prod_summit_starter"},
            },
        }
        body = json.dumps(payload).encode("utf-8")
        r = client.post(
            "/api/webhooks/whop",
            content=body,
            headers={
                "Content-Type": "application/json",
                "Whop-Signature": whop_signature(body),
            },
        )
        failures += not expect(f"POST /api/webhooks/whop", r.status_code == 200, f"body={r.json()}")
        resp = r.json()
        failures += not expect("is_new == True (first time)", bool(resp.get("is_new")))
        tenant_id = resp.get("tenant_id")
        failures += not expect("got tenant_id", tenant_id is not None)

        # 2. Verify a magic-link email was sent
        print("\n=== 2. Magic-link email captured ===")
        failures += not expect("1 email captured", len(capture.sent) == 1, f"got {len(capture.sent)}")
        if capture.sent:
            email = capture.sent[0]
            failures += not expect("to=newbuyer", email.to == "newbuyer@summitautomates.com")
            match = re.search(r"http://[^\s]+/auth/magic\?token=([A-Za-z0-9._-]+)", email.text)
            failures += not expect("URL with token in email body", match is not None)
            token = match.group(1) if match else ""

            # 3. Exchange the magic token for a session JWT
            print("\n=== 3. Magic-link login ===")
            r = client.post("/api/auth/magic-login", json={"token": token})
            failures += not expect("POST /api/auth/magic-login", r.status_code == 200, f"status={r.status_code}")
            jwt_resp = r.json()
            failures += not expect(
                f"tenant_id matches webhook ({tenant_id})",
                jwt_resp.get("tenant_id") == tenant_id,
            )

            # 4. Use that session JWT to hit /api/me
            print("\n=== 4. Authed /api/me with session JWT ===")
            session_token = jwt_resp.get("access_token")
            r = client.get("/api/me", headers={"Authorization": f"Bearer {session_token}"})
            failures += not expect("GET /api/me", r.status_code == 200, f"status={r.status_code}")
            me = r.json()
            failures += not expect("email correct", me.get("email") == "newbuyer@summitautomates.com")
            failures += not expect("subscription_status=active", me.get("subscription_status") == "active")

        # 5. Re-send same webhook → should be idempotent (no new tenant)
        print("\n=== 5. Idempotency (re-send same membership.went_valid) ===")
        capture.sent.clear()
        r = client.post(
            "/api/webhooks/whop",
            content=body,
            headers={
                "Content-Type": "application/json",
                "Whop-Signature": whop_signature(body),
            },
        )
        failures += not expect("re-send returns 200", r.status_code == 200)
        failures += not expect(
            "no new tenant created (is_new=False)", r.json().get("is_new") is False
        )

        # 6. Cancellation webhook
        print("\n=== 6. membership.cancelled → status=cancelled ===")
        capture.sent.clear()
        cancel_payload = {
            "event": "membership.cancelled",
            "data": {"id": "mem_smoke_001", "status": "canceled"},
        }
        cancel_body = json.dumps(cancel_payload).encode("utf-8")
        r = client.post(
            "/api/webhooks/whop",
            content=cancel_body,
            headers={
                "Content-Type": "application/json",
                "Whop-Signature": whop_signature(cancel_body),
            },
        )
        failures += not expect("cancellation webhook → 200", r.status_code == 200)
        # Confirm DB updated
        from sqlalchemy import select
        from sma.db.models.tenant import Tenant
        from sma.db.session import get_session_factory

        with get_session_factory()() as session:
            t = session.execute(
                select(Tenant)
                .where(Tenant.whop_membership_id == "mem_smoke_001")
                .execution_options(skip_tenant_filter=True)
            ).scalar_one()
            failures += not expect("DB tenant.subscription_status=cancelled", t.subscription_status == "cancelled")

        # 7. Invalid signature is rejected
        print("\n=== 7. Invalid signature rejected (401) ===")
        r = client.post(
            "/api/webhooks/whop",
            content=body,
            headers={
                "Content-Type": "application/json",
                "Whop-Signature": "wrong" * 10,
            },
        )
        failures += not expect("bad signature → 401", r.status_code == 401)

    print()
    if failures:
        print(f"FAILED: {failures} expectation(s) did not pass")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
