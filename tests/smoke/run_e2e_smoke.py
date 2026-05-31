"""End-to-end smoke runner for Phase 1.

Requires real API keys in `.env`:
  - OPENAI_API_KEY  (LLM + topic generation)
  - PEXELS_API_KEY  (free image source — default for example niches)
  - ELEVENLABS_API_KEY  (voiceover + music)

Run from the repo root:
  python tests/smoke/run_e2e_smoke.py
  python tests/smoke/run_e2e_smoke.py --niche fitness
  python tests/smoke/run_e2e_smoke.py --niche recipes --topic "30-min one-pan chicken"

Costs roughly $0.05-$0.20 per run depending on the niche/length.
Outputs to data/smoke/post_*/ so you can inspect the result without polluting data/posts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr so the script's output (and loguru logs that bubble
# through it) work on Windows consoles defaulting to cp1252.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, Exception):
        pass

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from sma.config import get_settings  # noqa: E402
from sma.core.niche.loader import load_from_yaml  # noqa: E402
from sma.core.pipeline.factory import build_context  # noqa: E402
from sma.core.pipeline.orchestrator import run_pipeline  # noqa: E402
from sma.core.topics.base import Topic  # noqa: E402
from sma.core.topics.scorer import score_and_filter  # noqa: E402
from sma.core.topics.sources.ai_generated import AIGeneratedTopicSource  # noqa: E402

NICHES = {
    "fitness": "examples/fitness_niche.yaml",
    "recipes": "examples/recipes_niche.yaml",
    "crypto": "examples/crypto_niche.yaml",
}


def main() -> int:
    p = argparse.ArgumentParser(description="Phase 1 end-to-end smoke test")
    p.add_argument("--niche", choices=list(NICHES), default="fitness")
    p.add_argument("--topic", help="Skip discovery; use this manual topic title")
    p.add_argument("--length", choices=["short", "long"], default=None)
    args = p.parse_args()

    settings = get_settings()
    _check_keys(settings)

    niche = load_from_yaml(REPO / NICHES[args.niche])
    print(f"\n==> niche: {niche.name!r}")
    print(f"  llm:    {niche.llm_provider}/{niche.llm_model}")
    print(f"  image:  {niche.image_provider}")
    print(f"  voice:  {niche.voice_provider} (id={niche.voice_id!r})")

    ctx = build_context(niche, settings)

    if args.topic:
        topic = Topic(title=args.topic, content="", source="smoke_cli")
    else:
        print("\n==> discovering topics via AI...")
        candidates = AIGeneratedTopicSource(count=8).discover(niche, ctx.llm)
        if not candidates:
            print("✗ AI returned no topics", file=sys.stderr)
            return 1
        kept = score_and_filter(candidates, niche, ctx.llm)
        if not kept:
            print(
                f"✗ no topics scored above {niche.topic_score_threshold}; lower the threshold",
                file=sys.stderr,
            )
            return 2
        topic = kept[0]
        print(f"  top topic ({topic.score}/10): {topic.title}")

    print("\n==> running pipeline...")
    out_root = REPO / "data" / "smoke"
    result = run_pipeline(topic, ctx, output_root=out_root, video_length=args.length)

    print("\n✔ DONE")
    print(f"  post dir:  {result.output_dir}")
    print(f"  video:     {result.video_path}")
    print(f"  thumbnail: {result.thumbnail_path}")
    print(f"  duration:  {result.duration_sec:.1f}s")
    print(f"  images:    {result.image_count}")
    print(f"  cost:      ${result.cost_usd:.4f}")
    print(f"\n  Caption preview:")
    for line in result.caption.splitlines()[:3]:
        print(f"    {line}")
    print(f"\n  Hashtags ({len(result.hashtags)}): {' '.join('#' + t for t in result.hashtags[:8])}...")
    return 0


def _check_keys(settings) -> None:
    missing = []
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.pexels_api_key:
        missing.append("PEXELS_API_KEY")
    if not settings.elevenlabs_api_key:
        missing.append("ELEVENLABS_API_KEY")
    if missing:
        print(f"✗ missing env vars: {', '.join(missing)}", file=sys.stderr)
        print("  copy .env.example → .env and fill in your keys", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    sys.exit(main())
