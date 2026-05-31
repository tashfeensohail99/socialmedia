# Providers

Every external service Posty talks to is wrapped in a provider class implementing
one of five protocols.

## The five protocols

| Kind | Protocol file | Purpose |
|---|---|---|
| `llm` | `providers/llm/base.py` | Chat / completion. Returns text + token counts. |
| `image` | `providers/image/base.py` | Generate or fetch images for a list of prompts. |
| `voice` | `providers/voice/base.py` | Text-to-speech. Returns mp3 path + char count. |
| `music` | `providers/music/base.py` | Generate background music from a prompt. |
| `social` | `providers/social/base.py` | Post a video to a social platform. |

## Currently registered

| Kind | Name | Status | Pricing notes |
|---|---|---|---|
| llm | `openai` | ✅ working | gpt-4o-mini default; gpt-5 / gpt-5-mini supported |
| llm | `anthropic` | 🚧 stub (v1.1) | Schema present, raises NotImplementedError |
| llm | `gemini` | 🚧 stub (v1.1) | Schema present, raises NotImplementedError |
| image | `pexels` | ✅ working, **free** | dev API key, ~3000 req/hr |
| image | `unsplash` | ✅ working, **free** | dev API key, 50 req/hr (production tier higher) |
| image | `nano_banana` | ✅ working | gemini-2.5-flash-image, ~$0.039/image |
| image | `dalle` | ✅ working | gpt-image-1, ~$0.04/image |
| voice | `elevenlabs` | ✅ working | turbo_v2 ~$0.18/1k chars |
| voice | `openai_tts` | ✅ working | tts-1 ~$0.015/1k chars (12× cheaper) |
| music | `elevenlabs` | ✅ working | music-v1, 20s max per track (we loop in mix) |
| social | `instagram` | ✅ working* | * needs MediaUploader (R2/S3) for public URL |
| social | `facebook` | ✅ working | direct file upload via Graph API |
| social | `youtube` | ✅ working | OAuth refresh-token flow, Shorts upload |
| social | `tiktok` | ✅ working | Content Posting API, FILE_UPLOAD chunked |

## Adding a new provider (recipe)

Say you want to add **Suno** as a music provider.

1. Create `src/sma/providers/music/suno.py`:
   ```python
   from sma.providers.music.base import MusicResult
   from sma.usage import pricing
   from sma.usage.events import UsageEvent
   from sma.usage.recorder import record

   class SunoMusic:
       name = "suno"

       def __init__(self, api_key: str) -> None:
           if not api_key:
               raise ValueError("Suno API key required")
           self._client = SunoClient(api_key)

       def generate(self, prompt, duration_sec, output_path, model=None):
           # ... call API, save to output_path ...
           record(UsageEvent(provider=self.name, model=model or "v3.5",
                             operation="compose", units=int(duration_sec),
                             cost_usd=pricing.cost_for_units(self.name, model or "v3.5", int(duration_sec))))
           return MusicResult(path=output_path, duration_sec=duration_sec, ...)
   ```

2. Register it in `src/sma/providers/registry.py`:
   ```python
   "music": {
       "elevenlabs": "sma.providers.music.elevenlabs:ElevenLabsMusic",
       "suno": "sma.providers.music.suno:SunoMusic",   # ← add
   },
   ```

3. Add pricing in `src/sma/usage/pricing.yaml`:
   ```yaml
   suno:
     v3.5:
       per_unit_cost: 0.015
       unit_label: second
   ```

4. Wire credentials in `src/sma/core/pipeline/factory.py::_music_creds`:
   ```python
   return {
       "elevenlabs": {"api_key": s.elevenlabs_api_key},
       "suno": {"api_key": s.suno_api_key},   # ← add
   }[name]
   ```

5. Add the env var to `src/sma/config.py::Settings` and `.env.example`.

6. (Optional) Add the new provider to a niche YAML to test:
   `music_provider: suno`.

## Usage tracking contract

Every provider implementation MUST call `usage.recorder.record(UsageEvent(...))`
exactly once per external API call, with:

- `provider` = your provider's `name`
- `model` = the specific model identifier used
- `operation` = a verb like `complete`, `generate`, `synthesize`, `tts`
- one of `tokens_in`/`tokens_out` (LLMs) or `units` (everything else)
- `cost_usd` from `pricing.cost_for_*()` — pass 0.0 for free providers

If the API call fails, do **not** record an event. Wrap the recording in the
success path only.

## Free vs paid image providers

Image providers expose `is_free: bool`. The registry constant `FREE_IMAGE_PROVIDERS`
is used by SaaS UI to default new tenants to free providers (so they don't see
surprise image bills). Free providers also get a different prompting branch in the
image orchestrator (`templates/image_scene.j2` `for_stock_search=True`) — they
receive search keywords, not detailed scene descriptions.
