# Architecture

> Phase 1 = the engine. Backend (FastAPI) and frontend (Next.js) come in Phases 2-3.

## High-level flow

```
              ┌─────────────────────────────────────┐
              │          NicheConfig                │
              │  (loaded from YAML in Phase 1,      │
              │   from Postgres per-tenant in P2)   │
              └────────────────┬────────────────────┘
                               │
                               ▼
              ┌─────────────────────────────────────┐
              │     TopicSource.discover()          │
              │  (AI-generated / RSS / manual /     │
              │   news — all return list[Topic])    │
              └────────────────┬────────────────────┘
                               │
                               ▼  Topic
              ┌─────────────────────────────────────┐
              │     scorer.score_and_filter()       │
              │  (LLM scores each, threshold cut)   │
              └────────────────┬────────────────────┘
                               │
                               ▼  Topic with score ≥ threshold
              ┌─────────────────────────────────────┐
              │     pipeline.run_pipeline()         │
              │  ────────────────────────────────   │
              │  1. analyze_story()  → StoryPlan    │
              │  2. generate_scene_images()         │
              │  3. build_audio_bundle()            │
              │       (voiceover + music + mix)     │
              │  4. assemble_video()  (or _long)    │
              │  5. generate_thumbnail()            │
              │  6. generate_caption_and_hashtags() │
              │  7. write metadata.json             │
              └────────────────┬────────────────────┘
                               │
                               ▼
              ┌─────────────────────────────────────┐
              │     SocialPoster.post_video()       │
              │  (instagram / facebook / youtube /  │
              │   tiktok — Phase 1: manual via CLI) │
              └─────────────────────────────────────┘
```

Every external API call goes through a **provider abstraction** and writes a
`UsageEvent` to `data/usage/events.jsonl`. This powers the cost dashboard.

## Module map

```
src/sma/
├── config.py                Settings (pydantic-settings, .env)
├── core/
│   ├── niche/               NicheConfig + YAML loader
│   ├── topics/              Topic, TopicSource protocol, scorer
│   │   └── sources/         ai_generated, manual, rss, news
│   ├── content/             story_analyzer, caption_generator
│   ├── media/
│   │   ├── images/          orchestrator, thumbnail (text overlay)
│   │   ├── audio/           orchestrator (voice + music + ffmpeg mix)
│   │   └── video/           assembler (ffmpeg slideshow), long_video
│   ├── pipeline/            context, factory, orchestrator
│   ├── scheduling/          (Phase 2)
│   └── templates.py         Jinja2 prompt loader
├── providers/
│   ├── registry.py          (kind, name) → class via lazy import
│   ├── llm/                 base, openai, anthropic (stub), gemini (stub)
│   ├── image/               base, pexels, unsplash, nano_banana, dalle
│   ├── voice/               base, elevenlabs, openai_tts
│   ├── music/               base, elevenlabs
│   └── social/              base, instagram, facebook, youtube, tiktok
├── usage/
│   ├── events.py            UsageEvent dataclass
│   ├── pricing.yaml         per-provider per-model rates
│   ├── pricing.py           cost_for_tokens / cost_for_units
│   └── recorder.py          JsonlSink (P1) / DB sink (P2)
└── cli/
    └── main.py              `sma` Typer app
```

## Key design rules (don't break these)

1. **No globals reach into the pipeline.** Everything flows in via `PipelineContext`.
   Tests construct a context and pass it; the orchestrator never reads `os.environ`.

2. **Every external API call goes through a provider.** Direct `openai.OpenAI(...)`
   in `core/` is a bug. The provider records usage; the call site stays clean.

3. **Every domain table will have `tenant_id`** (Phase 2). Today it's an int=1 in
   `PipelineContext`. Don't add code that assumes single-tenant — propagate the id.

4. **Templates own the prompts**, not Python files. Edit `templates/*.j2`, not
   string literals in `core/content/*.py`.

5. **Free image providers = SaaS defaults.** Pexels/Unsplash are tagged `is_free=True`
   and surfaced via `FREE_IMAGE_PROVIDERS` so multi-tenant mode can default to them.

## Data flow per pipeline run

For one Topic, `run_pipeline()` produces a directory `data/posts/post_<id>/`:

```
post_<id>/
├── metadata.json           caption, hashtags, narrative, beats, costs, status
├── thumbnail.jpg           1080x1920 with overlaid hook text
├── images/
│   ├── pexels_000_*.jpg    one per story beat, normalized to target dims
│   └── ...
├── audio/
│   ├── voiceover.mp3       full narrative TTS (chunked + concat for long)
│   ├── music.mp3           background track (looped during mix)
│   └── audio_mixed.mp3     voiceover + ducked music
└── video/
    └── final.mp4           1080x1920 H.264 + AAC, faststart enabled
```

## Mode awareness (Phase 2 preview)

Phase 1 is single-tenant (`tenant_id=1` always). Phase 2 introduces
`DEPLOYMENT_MODE=single_tenant|multi_tenant` env var:

- single-tenant: one admin user, no signup, no billing → for license customers
- multi-tenant: signup, Stripe subscription, master OAuth apps → for the SaaS

Both modes run the same engine. The difference is the auth/billing wrapper that
sits between HTTP requests and `run_pipeline()`.
