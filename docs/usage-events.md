# Usage tracking

Posty records every external API call as a `UsageEvent`. This drives the cost
dashboard (especially important for Mode B SaaS, where subscribers see "you
spent $X on OpenAI this month").

## Event schema

Each row in `data/usage/events.jsonl`:

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "operation": "complete",
  "tokens_in": 850,
  "tokens_out": 412,
  "units": 0,
  "cost_usd": 0.000375,
  "tenant_id": 1,
  "post_id": null,
  "timestamp": "2026-05-16T14:23:11.421Z",
  "metadata": {}
}
```

Field meanings:

| Field | Notes |
|---|---|
| `provider` | The provider's `name` attribute (`openai`, `pexels`, `nano_banana`...) |
| `model` | Specific model identifier — what the cost calculation keys off |
| `operation` | Verb: `complete` / `generate` / `synthesize` / `tts` / `compose` / `image_generate` / `search_download` |
| `tokens_in` / `tokens_out` | For LLMs only |
| `units` | For everything else (chars for TTS, images for image gen, seconds for music) |
| `cost_usd` | Computed from `pricing.yaml` at record time |
| `tenant_id` | Always 1 in single-tenant mode; per-subscriber in Mode B |
| `post_id` | Optional — set when the call is part of a pipeline run |
| `timestamp` | ISO 8601 UTC |
| `metadata` | Provider-specific extras (voice_id, prompt snippets, etc.) |

## Pricing table

`src/sma/usage/pricing.yaml` is the source of truth for what each call costs.
Two formats:

```yaml
# Token-priced (LLMs)
openai:
  gpt-4o-mini:
    input_per_1m: 0.15      # USD per 1M input tokens
    output_per_1m: 0.60     # USD per 1M output tokens

# Unit-priced (images, TTS, music)
nano_banana:
  gemini-2.5-flash-image:
    per_unit_cost: 0.039
    unit_label: image
```

When a provider's price changes, edit this file. There is no DB cache — Phase 2
loads pricing on demand. Free providers should be listed with `per_unit_cost: 0.0`
so operations are still tracked even though cost is zero.

## Querying usage

The CLI prints a month-to-date summary:

```bash
sma usage                        # current month
sma usage --month 2026-04        # specific month
```

Output:
```
Usage for 2026-05:
  Total events: 1247
  Total cost:   $4.2871

  By provider/model:
    openai/gpt-4o-mini                    412 calls   $0.1853
    elevenlabs/eleven_turbo_v2_5           48 calls   $2.4192
    nano_banana/gemini-2.5-flash-image    480 calls   $1.6320
    pexels/stock                          307 calls   $0.0000
```

## Phase 2 migration

In Phase 2 the JSONL sink is replaced with a Postgres `usage_events` table.
The schema is identical (just relational). The dashboard will:

- show MTD spend per provider per tenant
- project monthly cost based on first N days
- alert when a tenant exceeds a configurable cap
- export CSV for the user's records

## Why we record on the success path only

Failed API calls don't get recorded. Reasoning: providers usually charge only
for successful responses, and if you record before the call you'll inflate the
displayed cost when retries happen. The provider class is responsible for
calling `record(...)` only after parsing a successful response.

If a provider does charge for failed attempts (rare), record at the boundary
where you know the charge is committed.
