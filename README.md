# Social Media Automation

Niche-agnostic AI content automation: discover topics, generate vertical videos (story → images → voiceover → music → captions → thumbnail), and post to Instagram, Facebook, YouTube Shorts, and TikTok on a schedule.

Ships in two modes from one codebase:

- **`DEPLOYMENT_MODE=single_tenant`** — white-label deploy (one admin user, BYOK, no billing).
- **`DEPLOYMENT_MODE=multi_tenant`** — SaaS deploy (signup, 7-day trial, Stripe subscription, master OAuth apps).

## Status

**Phase 1 in progress** — generalizing the engine. CLI-only for now. Backend (FastAPI) and frontend (Next.js) come in Phases 2-3.

## Quick start (Phase 1 dev)

```bash
# Install (using uv, recommended)
uv venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # macOS/Linux
uv pip install -e ".[dev]"

# Configure
cp .env.example .env
# Fill in at minimum: OPENAI_API_KEY, PEXELS_API_KEY, ELEVENLABS_API_KEY

# Try a non-tourism niche
sma run-once examples/fitness_niche.yaml --max-topics 1
```

## Architecture

See [`../COMMERCIAL_PRODUCT_PLAN.md`](../COMMERCIAL_PRODUCT_PLAN.md) for the full architecture and dual-mode design.
See [`../PHASE_1_TASKS.md`](../PHASE_1_TASKS.md) for the current phase task breakdown.

## Repository layout

```
src/sma/
├── core/          # niche, topics, content, media, pipeline, scheduling
├── providers/     # LLM, image, voice, music, social abstractions + impls
├── usage/         # cost tracking
└── cli/           # Typer-based CLI
templates/         # Jinja2 prompt templates
examples/          # example niche.yaml configs
tests/
```
