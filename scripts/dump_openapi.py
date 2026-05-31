"""Dump the FastAPI app's OpenAPI spec to frontend/openapi.json.

Used by the frontend build to regenerate TypeScript types via openapi-typescript:

    python scripts/dump_openapi.py
    cd frontend && npm run gen:types
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Provide minimal env so app boot doesn't fail (real values are not needed
# for the OpenAPI dump — none of these are read during schema generation).
os.environ.setdefault("JWT_SECRET", "ephemeral-for-openapi-dump")
os.environ.setdefault("MASTER_KEY", "Y2hhbmdlbWUtZm9yLW9wZW5hcGktZHVtcC1jaGFuZ2VtZQ==")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sma.web.app import create_app

app = create_app()
spec = app.openapi()
out = ROOT / "frontend" / "openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(spec, indent=2), encoding="utf-8")
print(f"Wrote OpenAPI spec ({len(spec.get('paths', {}))} paths) -> {out.relative_to(ROOT)}")
