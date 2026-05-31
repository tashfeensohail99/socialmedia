# Writing a niche.yaml

A `NicheConfig` defines the personality, audience, content guardrails, and
provider preferences for one content stream. In Phase 1 you write it as YAML.
In Phase 2+ you'll edit it through the admin panel.

## Minimal example

```yaml
name: "Daily Plant Care Tips"
description: |
  One actionable houseplant tip per day. Focus on troubleshooting common
  problems (yellow leaves, root rot, pests) over generic advice.
target_audience: "Houseplant beginners who already killed at least one plant"
tone: "warm, knowledgeable, mildly self-deprecating"

content_pillars:
  - "diagnosing common plant problems"
  - "watering myth-busting"
  - "light requirements explained simply"
  - "propagation success stories"

voice_id: "EXAVITQu4vr4xnSDxMaL"
```

That's the bare minimum. Everything else has sensible defaults.

## Full schema

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | str | **required** | Short label, shown in dashboards |
| `description` | str | **required** | Multi-paragraph context for the LLM |
| `target_audience` | str | **required** | Who the content is for |
| `tone` | str | `friendly, informative` | Voice instruction |
| `language` | str | `en` | ISO code |
| `content_pillars` | list[str] | `[]` | Recommended topics |
| `forbidden_topics` | list[str] | `[]` | Topics to actively avoid |
| `cta` | str | `""` | Call-to-action included in captions |
| `hashtag_seeds` | list[str] | `[]` | Always-included hashtags |
| `video_length_default` | `short` \| `long` | `short` | `short` = ≤60s, `long` = 3-8 min |
| `llm_provider` | str | `openai` | One of registered LLMs |
| `llm_model` | str | `gpt-4o-mini` | Model identifier |
| `image_provider` | str | `pexels` | Free default; set `nano_banana` for AI-generated |
| `image_aspect_default` | str | `9:16` | `9:16`, `4:5`, `1:1`, or `16:9` |
| `image_count_short` | int | `10` | Hint to the story analyzer |
| `image_count_long` | int | `20` | Hint for long videos |
| `voice_provider` | str | `elevenlabs` | `openai_tts` is 12× cheaper |
| `voice_id` | str | `""` | **Required** — your ElevenLabs voice ID or OpenAI voice name |
| `voice_model` | str \| null | `null` | Provider-specific (`eleven_turbo_v2_5`, `tts-1-hd`) |
| `music_provider` | str | `elevenlabs` | |
| `music_enabled` | bool | `true` | Set false to skip background music |
| `topic_score_threshold` | float | `7.0` | Topics scored below this are dropped |

## Writing a good description

The `description` field is the single most important driver of output quality.
It's prepended to every LLM prompt. Aim for **3-5 sentences** that:

1. State what the niche covers
2. State what it explicitly does NOT cover (boundaries)
3. State the angle / point of view
4. State any consistency rules (e.g. "every post must include a citation")

Bad:
```
description: "Fitness content"
```

Good:
```
description: |
  Quick, science-backed fitness and nutrition advice for busy professionals.
  Each post focuses on one actionable habit they can apply today — not extreme
  regimens, not supplement promotion. Cite the underlying mechanism in plain
  language so viewers understand the WHY, not just the WHAT.
```

## Writing good content pillars

Pillars constrain what topics the AI will generate or score highly. They should
be **specific phrases**, not generic categories.

Bad: `["fitness", "nutrition", "lifestyle"]`
Good: `["5-minute desk-friendly workouts", "myth-busting common fitness advice", "habit-stacking for consistency"]`

## Forbidden topics

Use these to enforce hard rules. The LLM is explicitly told to never produce
topics matching these strings, and the topic scorer caps scores at ≤3 for
matches.

```yaml
forbidden_topics:
  - "specific stock or coin recommendations"
  - "anything that could be construed as financial advice"
  - "leverage / margin trading"
```

## Provider preferences cheat sheet

| You want... | Set... |
|---|---|
| Cheapest LLM | `llm_model: gpt-4o-mini` |
| Best LLM | `llm_model: gpt-5` |
| Free images | `image_provider: pexels` (or `unsplash`) |
| AI-generated images | `image_provider: nano_banana` |
| Premium voice | `voice_provider: elevenlabs` |
| Cheapest voice | `voice_provider: openai_tts`, `voice_id: nova` |
| No background music | `music_enabled: false` |
| Longer-form video | `video_length_default: long` |

## Three reference niches

See `examples/`:
- [`fitness_niche.yaml`](../examples/fitness_niche.yaml) — short videos, free stock images
- [`recipes_niche.yaml`](../examples/recipes_niche.yaml) — long videos for step-by-step format
- [`crypto_niche.yaml`](../examples/crypto_niche.yaml) — strict forbidden topics (no financial advice)
