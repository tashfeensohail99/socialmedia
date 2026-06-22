"""Apply the avatar_mode migration directly to the production DB.

Adds 5 columns (3 to niches, 2 to posts) with safe defaults, then bumps the
alembic_version table to c3d4e5f6a7b8 so future `alembic upgrade head` runs
treat it as already-applied.

Backward-compat: niches.avatar_mode defaults to 'off' for ALL existing rows, so
the deployed app keeps using the slideshow pipeline until the seed SQL flips a
specific niche to 'talking_head'.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import psycopg

url = open("/tmp/heygen_pg_url.txt").read().strip()
# Migration uses raw SQL — psycopg driver handles postgresql:// directly.

EXPECTED_FROM = "b2c3d4e5f6a7"
NEW_REVISION = "c3d4e5f6a7b8"

with psycopg.connect(url, connect_timeout=30) as conn:
    with conn.cursor() as cur:
        # 1) Confirm current alembic revision
        cur.execute("SELECT version_num FROM alembic_version")
        row = cur.fetchone()
        if not row:
            print("ERROR: alembic_version table is empty — refusing to migrate")
            sys.exit(1)
        current = row[0]
        print(f"Current alembic_version: {current}")
        if current == NEW_REVISION:
            print("Migration already applied — nothing to do.")
            sys.exit(0)
        if current != EXPECTED_FROM:
            print(f"ERROR: expected {EXPECTED_FROM!r} as current, got {current!r}")
            print("Refusing to migrate (manual intervention needed).")
            sys.exit(1)

        # 2) Add columns (idempotent via IF NOT EXISTS)
        statements = [
            "ALTER TABLE niches ADD COLUMN IF NOT EXISTS avatar_mode VARCHAR(16) NOT NULL DEFAULT 'off'",
            "ALTER TABLE niches ADD COLUMN IF NOT EXISTS avatar_library_ids JSON",
            "ALTER TABLE niches ADD COLUMN IF NOT EXISTS heygen_voice_id VARCHAR(64)",
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS avatar_id VARCHAR(128)",
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS avatar_cost_usd DOUBLE PRECISION",
        ]
        for s in statements:
            print(f"  → {s}")
            cur.execute(s)

        # 3) Bump alembic_version
        cur.execute("UPDATE alembic_version SET version_num = %s", (NEW_REVISION,))
        print(f"alembic_version → {NEW_REVISION}")

        # 4) Sanity: re-read to confirm
        cur.execute("SELECT version_num FROM alembic_version")
        print(f"Confirmed alembic_version: {cur.fetchone()[0]}")

        # 5) Show the new columns
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name IN ('niches','posts')
              AND column_name IN ('avatar_mode','avatar_library_ids','heygen_voice_id','avatar_id','avatar_cost_usd')
            ORDER BY table_name, column_name
        """)
        print("\nNew columns:")
        for c in cur.fetchall():
            print(f"  {c[0]:<22} {c[1]:<20} nullable={c[2]}  default={c[3]}")
    conn.commit()

print("\n✔ Migration applied successfully.")
