"""End-to-end Phase 2 smoke against the full backend surface.

Verifies that all routers register, all routes respond as expected, OAuth
endpoints produce valid redirect URLs (without actually completing the
external dance), and the worker module imports cleanly.

Real OAuth flows + actual pipeline runs are tested separately because they
need real external API keys + registered OAuth apps.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

# Load .env
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip())

# Use an isolated test DB
test_db = Path("data/sma_phase2_test.db")
test_db.parent.mkdir(parents=True, exist_ok=True)
test_db.unlink(missing_ok=True)
os.environ["SMA_DATABASE_URL"] = f"sqlite:///{test_db.as_posix()}"

# Provide stub OAuth credentials so the /connect endpoints can build redirect URLs.
# Force-set OAuth stub creds (override any empty values from .env).
for k, v in {
    "META_APP_ID": "stub_meta_id",
    "META_APP_SECRET": "stub_meta_secret",
    "GOOGLE_CLIENT_ID": "stub_google_id",
    "GOOGLE_CLIENT_SECRET": "stub_google_secret",
    "TIKTOK_CLIENT_KEY": "stub_tiktok_key",
    "TIKTOK_CLIENT_SECRET": "stub_tiktok_secret",
    "LINKEDIN_CLIENT_ID": "stub_linkedin_id",
    "LINKEDIN_CLIENT_SECRET": "stub_linkedin_secret",
}.items():
    if not os.environ.get(k):
        os.environ[k] = v

sys.path.insert(0, "src")

subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    env={**os.environ}, check=True, capture_output=True,
)

from fastapi.testclient import TestClient
from sma.web.app import create_app

PASS = "[PASS]"
FAIL = "[FAIL]"


def expect(label: str, cond: bool, detail: str = "") -> bool:
    print(f"  {PASS if cond else FAIL} {label}{(' — ' + detail) if detail else ''}")
    return cond


def main() -> int:
    failures = 0

    # 1. Worker module imports cleanly (catches import-time issues)
    print("=== WORKER IMPORT CHECK ===")
    try:
        from sma.worker import main as worker_main  # noqa: F401
        from sma.worker.jobs import (  # noqa: F401
            discover_topics,
            process_schedules,
            refresh_tokens,
        )
        failures += not expect("worker modules importable", True)
    except Exception as e:
        failures += not expect("worker modules importable", False, str(e))

    # 2. Pipeline → DB modules importable
    print("\n=== PIPELINE→DB IMPORT CHECK ===")
    try:
        from sma.core.pipeline import db_runner, factory_db  # noqa: F401
        failures += not expect("pipeline DB modules importable", True)
    except Exception as e:
        failures += not expect("pipeline DB modules importable", False, str(e))

    # 3. CLI migrate command registered
    print("\n=== CLI MIGRATE COMMAND ===")
    try:
        from sma.cli.migrate import cmd_migrate_from_json  # noqa: F401
        failures += not expect("migrate-from-json import", True)
    except Exception as e:
        failures += not expect("migrate-from-json import", False, str(e))

    # 4. App + all routes
    print("\n=== APP BOOT + ROUTES ===")
    with TestClient(create_app()) as client:
        r = client.post("/api/auth/login",
                        json={"email": "admin@example.com", "password": "devpassword"})
        failures += not expect("login", r.status_code == 200)
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        # All CRUD endpoints still respond
        for path in [
            "/api/me", "/api/niches", "/api/credentials", "/api/social-accounts",
            "/api/topic-sources", "/api/topics", "/api/posts", "/api/schedules",
            "/api/posting-rules", "/api/prompt-templates", "/api/usage/summary",
        ]:
            r = client.get(path, headers=h)
            failures += not expect(f"GET {path}", r.status_code == 200, f"status={r.status_code}")

        # Action routes exist (even without real data, they should return 4xx not 404)
        print("\n=== ACTION ROUTES PRESENT ===")
        r = client.post("/api/posts/run", headers=h, json={"niche_id": 999})
        # Expect 400 (validation error) or 422 — anything other than 404 means the route exists.
        failures += not expect(
            "POST /api/posts/run route exists",
            r.status_code != 404,
            f"got {r.status_code}",
        )

        # OAuth /connect routes — should 302 to platform's auth URL
        print("\n=== OAUTH /connect REDIRECTS ===")
        for platform, expected_host in [
            ("meta", "facebook.com"),
            ("youtube", "accounts.google.com"),
            ("tiktok", "tiktok.com"),
            ("linkedin", "linkedin.com"),
        ]:
            r = client.get(f"/api/oauth/{platform}/connect", headers=h, follow_redirects=False)
            ok = r.status_code in (302, 307) and expected_host in r.headers.get("location", "")
            failures += not expect(
                f"OAuth /{platform}/connect → redirect to {expected_host}",
                ok,
                f"status={r.status_code}, loc={r.headers.get('location', '')[:80]}",
            )

        # Unauth on OAuth = 401
        r = client.get("/api/oauth/meta/connect", follow_redirects=False)
        failures += not expect("OAuth requires auth", r.status_code == 401)

    print()
    if failures:
        print(f"FAILED: {failures} expectation(s) did not pass")
        return 1
    print("PHASE 2 SMOKE: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
