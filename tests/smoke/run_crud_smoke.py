"""End-to-end CRUD smoke against the backend.

Drives every router through realistic scenarios with the TestClient. No real
external API calls — credentials are fake; we only verify the storage + auth +
tenant scoping behavior.

Run:
    python tests/smoke/run_crud_smoke.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Force UTF-8 stdout for Windows.
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

# Use an isolated test DB so we don't trash the dev one
test_db = Path("data/sma_crud_test.db")
test_db.parent.mkdir(parents=True, exist_ok=True)
test_db.unlink(missing_ok=True)
os.environ["SMA_DATABASE_URL"] = f"sqlite:///{test_db.as_posix()}"

sys.path.insert(0, "src")

# Apply migrations to the fresh DB.
import subprocess

subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    env={**os.environ}, check=True, capture_output=True,
)

from fastapi.testclient import TestClient
from sma.web.app import create_app

PASS = "[PASS]"
FAIL = "[FAIL]"


def expect(label: str, condition: bool, detail: str = "") -> bool:
    """Print pass/fail and return the condition."""
    mark = PASS if condition else FAIL
    print(f"  {mark} {label}{(' — ' + detail) if detail else ''}")
    return condition


def main() -> int:
    failures = 0

    with TestClient(create_app()) as client:
        # 1. Login as the admin bootstrapped on startup
        print("\n=== AUTH ===")
        r = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "devpassword"},
        )
        failures += not expect("login", r.status_code == 200)
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        # 2. /api/me
        r = client.get("/api/me", headers=h)
        failures += not expect("GET /api/me", r.status_code == 200,
                               f"user={r.json().get('email')} tenant={r.json().get('tenant_id')}")

        # 3. Niches CRUD
        print("\n=== NICHES ===")
        r = client.post("/api/niches", headers=h, json={
            "name": "Test Niche",
            "description": "A niche for smoke testing.",
            "target_audience": "test users",
            "voice_id": "EXAVITQu4vr4xnSDxMaL",
        })
        failures += not expect("POST /api/niches", r.status_code == 201)
        niche_id = r.json()["id"]

        r = client.get(f"/api/niches/{niche_id}", headers=h)
        failures += not expect(f"GET /api/niches/{niche_id}", r.status_code == 200)

        r = client.patch(f"/api/niches/{niche_id}", headers=h, json={"tone": "playful"})
        failures += not expect("PATCH niche.tone", r.status_code == 200 and r.json()["tone"] == "playful")

        r = client.get("/api/niches", headers=h)
        failures += not expect("LIST /api/niches", r.status_code == 200 and r.json()["meta"]["total"] == 1)

        # 4. Credentials — store, list (masked), test (will likely fail without real key, but should respond), delete
        print("\n=== CREDENTIALS ===")
        r = client.post("/api/credentials", headers=h, json={
            "provider_kind": "llm",
            "provider_name": "openai",
            "label": "default",
            "payload": {"api_key": "sk-fake-key-1234567890"},
        })
        failures += not expect("POST /api/credentials", r.status_code == 201)
        cred_id = r.json()["id"]
        failures += not expect("secret_preview is masked", r.json()["secret_preview"] == "...7890")

        r = client.get("/api/credentials", headers=h)
        failures += not expect("LIST credentials", r.status_code == 200 and len(r.json()["items"]) == 1)
        # Ensure the encrypted blob is NEVER leaked
        body = r.json()
        for item in body["items"]:
            failures += not expect("no encrypted_blob in response", "encrypted_blob" not in item)

        r = client.delete(f"/api/credentials/{cred_id}", headers=h)
        failures += not expect("DELETE credentials", r.status_code == 204)

        # 5. Topic sources
        print("\n=== TOPIC SOURCES ===")
        r = client.post("/api/topic-sources", headers=h, json={
            "niche_id": niche_id,
            "kind": "ai_generated",
            "config_json": {"count": 5},
        })
        failures += not expect("POST topic-source", r.status_code == 201)
        src_id = r.json()["id"]

        r = client.get("/api/topic-sources", headers=h, params={"niche_id": niche_id})
        failures += not expect("LIST topic-sources by niche", r.status_code == 200 and r.json()["meta"]["total"] == 1)

        # 6. Topics — create manual, list, reject, delete
        print("\n=== TOPICS ===")
        r = client.post("/api/topics", headers=h, json={"title": "Test topic", "content": "context"})
        failures += not expect("POST manual topic", r.status_code == 201)
        topic_id = r.json()["id"]

        r = client.post(f"/api/topics/{topic_id}/promote", headers=h)
        failures += not expect("promote topic", r.status_code == 200)

        r = client.get("/api/topics", headers=h, params={"min_score": 5})
        failures += not expect("LIST topics min_score=5", r.status_code == 200 and r.json()["meta"]["total"] == 1)

        # 7. Posting rules
        print("\n=== POSTING RULES ===")
        r = client.post("/api/posting-rules", headers=h, json={
            "name": "weekday peak",
            "type": "peak_hours",
            "params_json": {"hours": [18, 20, 21], "tz": "UTC"},
        })
        failures += not expect("POST posting-rule", r.status_code == 201)

        r = client.post("/api/posting-rules", headers=h, json={
            "name": "bad type",
            "type": "INVALID",
            "params_json": {},
        })
        failures += not expect("POST invalid type rejected", r.status_code == 400)

        # 8. Prompt templates
        print("\n=== PROMPT TEMPLATES ===")
        r = client.put("/api/prompt-templates/caption", headers=h, json={
            "slug": "caption", "body": "tenant override of caption template"
        })
        failures += not expect("PUT prompt-template upsert", r.status_code == 200)

        r = client.get("/api/prompt-templates/story_analysis/default", headers=h)
        failures += not expect("GET default body", r.status_code == 200 and "LONG-FORMAT" in r.json()["message"])

        # 9. Usage summary (no events yet)
        print("\n=== USAGE ===")
        r = client.get("/api/usage/summary", headers=h)
        failures += not expect(
            "usage summary current month", r.status_code == 200 and r.json()["total_events"] == 0
        )

        # 10. Schedules — requires a Post; we can't create a Post via CRUD (only via action endpoints),
        # but we can at least verify the empty list works.
        r = client.get("/api/schedules", headers=h)
        failures += not expect("LIST schedules (empty)", r.status_code == 200 and r.json()["meta"]["total"] == 0)

        # 11. Social accounts — empty list (creation goes through OAuth)
        r = client.get("/api/social-accounts", headers=h)
        failures += not expect(
            "LIST social-accounts (empty)", r.status_code == 200 and r.json()["meta"]["total"] == 0
        )

        # 12. Auth enforcement — no header = 401
        print("\n=== AUTH ENFORCEMENT ===")
        r = client.get("/api/niches")
        failures += not expect("unauthenticated → 401", r.status_code == 401)

        # 13. Cleanup — delete the niche (cascade should drop the topic_source)
        r = client.delete(f"/api/niches/{niche_id}", headers=h)
        failures += not expect("DELETE niche", r.status_code == 204)

    print()
    if failures:
        print(f"FAILED: {failures} expectation(s) did not pass")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
