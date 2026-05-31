"""Social Media Automation CLI.

  sma run-once <niche.yaml>            Discover topics, score, generate top 1
  sma run-once <niche.yaml> --topic "..." [--length short|long]
                                       Generate from a manually-supplied topic title
  sma post <post_dir> --platform ...   Post a generated post
  sma usage [--month YYYY-MM]          Print usage summary
  sma test-provider <kind> <name>      Verify an API key works
  sma list-providers <kind>            Show registered providers for a kind
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from sma.config import get_settings
from sma.core.niche.loader import load_from_yaml
from sma.core.pipeline.factory import build_context
from sma.core.pipeline.orchestrator import run_pipeline
from sma.core.topics.base import Topic
from sma.core.topics.scorer import score_and_filter
from sma.core.topics.sources.ai_generated import AIGeneratedTopicSource
from sma.cli.migrate import cmd_migrate_from_json
from sma.providers.registry import ProviderKind, get_provider, list_providers

app = typer.Typer(
    add_completion=False,
    help="Social Media Automation — niche-agnostic AI content pipeline.",
    no_args_is_help=True,
)


@app.command("run-once")
def run_once(
    niche_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    topic_title: Optional[str] = typer.Option(None, "--topic", help="Skip discovery; use this topic title"),
    topic_content: str = typer.Option("", "--topic-content"),
    length: Optional[str] = typer.Option(None, "--length", help="short or long; overrides niche default"),
    output_dir: Path = typer.Option(Path("data/posts"), "--out", help="Where to save posts"),
    max_topics_to_consider: int = typer.Option(10, "--max-discover"),
) -> None:
    """Run the pipeline end-to-end for one topic."""
    settings = get_settings()
    niche = load_from_yaml(niche_path)
    ctx = build_context(niche, settings)
    logger.info(f"Loaded niche: {niche.name!r}")

    if topic_title:
        topic = Topic(title=topic_title, content=topic_content, source="cli")
    else:
        source = AIGeneratedTopicSource(count=max_topics_to_consider)
        candidates = source.discover(niche, ctx.llm)
        if not candidates:
            typer.echo("No topics discovered.", err=True)
            raise typer.Exit(1)
        kept = score_and_filter(candidates, niche, ctx.llm)
        if not kept:
            typer.echo(
                f"No topics scored above threshold {niche.topic_score_threshold}. "
                "Lower the threshold or try again.",
                err=True,
            )
            raise typer.Exit(2)
        topic = kept[0]
        typer.echo(f"Top topic ({topic.score}/10): {topic.title}")

    result = run_pipeline(
        topic=topic,
        ctx=ctx,
        output_root=output_dir,
        video_length=length,  # type: ignore[arg-type]
    )
    typer.echo(f"\n✔ Post ready at: {result.output_dir}")
    typer.echo(f"  Video: {result.video_path}")
    typer.echo(f"  Duration: {result.duration_sec:.1f}s")
    typer.echo(f"  Cost: ${result.cost_usd:.4f}")


@app.command("post")
def post_command(
    post_dir: Path = typer.Argument(..., exists=True, file_okay=False),
    platform: str = typer.Option(..., "--platform", "-p"),
) -> None:
    """Post a previously-generated post directory to a platform."""
    metadata_path = post_dir / "metadata.json"
    if not metadata_path.exists():
        typer.echo(f"No metadata.json in {post_dir}", err=True)
        raise typer.Exit(1)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    video_path = post_dir / metadata["video_path"]
    thumbnail_path = post_dir / metadata.get("thumbnail_path", "thumbnail.jpg")

    settings = get_settings()
    poster = _build_poster(platform, settings)
    if poster is None:
        raise typer.Exit(2)

    result = poster.post_video(
        video_path=video_path,
        caption=metadata["caption"],
        hashtags=metadata["hashtags"],
        thumbnail_path=thumbnail_path if thumbnail_path.exists() else None,
        is_short=True,
    )

    if result.success:
        typer.echo(f"✔ Posted to {platform}: {result.url or result.external_post_id}")
    else:
        typer.echo(f"✗ Failed to post to {platform}: {result.error}", err=True)
        raise typer.Exit(3)


@app.command("usage")
def usage_command(
    month: Optional[str] = typer.Option(None, "--month", help="YYYY-MM filter; default = current month"),
) -> None:
    """Summarize logged usage events."""
    settings = get_settings()
    path = settings.usage_log_path
    if not path.exists():
        typer.echo("No usage events logged yet.")
        return

    target_month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    by_provider: dict[str, dict[str, float]] = {}
    total_cost = 0.0
    total_events = 0

    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not str(ev.get("timestamp", "")).startswith(target_month):
                continue
            total_events += 1
            cost = float(ev.get("cost_usd", 0.0))
            total_cost += cost
            key = f"{ev['provider']}/{ev.get('model', '?')}"
            entry = by_provider.setdefault(key, {"calls": 0.0, "cost_usd": 0.0})
            entry["calls"] += 1
            entry["cost_usd"] += cost

    typer.echo(f"\nUsage for {target_month}:")
    typer.echo(f"  Total events: {total_events}")
    typer.echo(f"  Total cost:   ${total_cost:.4f}")
    typer.echo("\n  By provider/model:")
    for key, entry in sorted(by_provider.items(), key=lambda kv: -kv[1]["cost_usd"]):
        typer.echo(f"    {key:<35} {int(entry['calls']):>5} calls   ${entry['cost_usd']:.4f}")


@app.command("test-provider")
def test_provider(
    kind: str = typer.Argument(..., help="llm | image | voice | music | social"),
    name: str = typer.Argument(..., help="Provider name (e.g. openai, pexels)"),
) -> None:
    """Smoke-test a provider with a tiny request to verify the API key works."""
    settings = get_settings()
    try:
        if kind == "llm":
            creds = {
                "openai": {"api_key": settings.openai_api_key},
                "anthropic": {"api_key": settings.anthropic_api_key},
                "gemini": {"api_key": settings.gemini_api_key},
            }[name]
            provider = get_provider("llm", name, **creds)
            resp = provider.complete(
                system="You are a test responder.", user="Reply with the single word: ok",
                model="gpt-4o-mini" if name == "openai" else name,
                temperature=0,
            )
            typer.echo(f"✔ {name} replied: {resp.text[:80]}")
        elif kind == "image":
            creds = {
                "pexels": {"api_key": settings.pexels_api_key},
                "unsplash": {"access_key": settings.unsplash_access_key},
                "nano_banana": {"api_key": settings.gemini_api_key},
                "dalle": {"api_key": settings.openai_api_key},
            }[name]
            provider = get_provider("image", name, **creds)
            tmp = Path("data/usage/_test")
            tmp.mkdir(parents=True, exist_ok=True)
            result = provider.generate(prompts=["sunrise over mountains"], aspect_ratio="9:16", output_dir=tmp, count=1)
            if result.paths:
                typer.echo(f"✔ {name} produced {result.paths[0]}")
            else:
                typer.echo(f"✗ {name} returned no images", err=True)
                raise typer.Exit(1)
        else:
            typer.echo(f"test-provider for kind {kind!r} not yet wired (try llm or image).", err=True)
            raise typer.Exit(2)
    except Exception as e:
        typer.echo(f"✗ {name} test failed: {e}", err=True)
        raise typer.Exit(1)


@app.command("list-providers")
def list_providers_command(kind: str = typer.Argument(...)) -> None:
    try:
        names = list_providers(kind)  # type: ignore[arg-type]
    except KeyError:
        typer.echo(f"Unknown provider kind: {kind}", err=True)
        raise typer.Exit(1)
    typer.echo(f"\nProviders for kind={kind!r}:")
    for n in names:
        typer.echo(f"  - {n}")


def _build_poster(platform: str, settings):
    if platform == "youtube":
        return get_provider(
            "social", "youtube",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            refresh_token=_load_youtube_refresh_token(),
        )
    elif platform == "facebook":
        return get_provider(
            "social", "facebook",
            page_token=settings.meta_page_token,
            page_id=_env_or_die("FACEBOOK_PAGE_ID"),
        )
    elif platform == "tiktok":
        return get_provider(
            "social", "tiktok",
            access_token=_env_or_die("TIKTOK_ACCESS_TOKEN"),
        )
    elif platform == "instagram":
        typer.echo(
            "Instagram posting requires a configured MediaUploader (R2/S3/Dropbox). "
            "Wire one up in your settings before using the CLI for IG.",
            err=True,
        )
        return None
    typer.echo(f"Unknown platform: {platform}", err=True)
    return None


def _env_or_die(var: str) -> str:
    import os
    val = os.environ.get(var, "").strip()
    if not val:
        typer.echo(f"Environment variable {var} is required.", err=True)
        sys.exit(1)
    return val


def _load_youtube_refresh_token() -> str:
    import os
    return os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip() or _env_or_die("YOUTUBE_REFRESH_TOKEN")


# Register the migration command.
app.command("migrate-from-json")(cmd_migrate_from_json)


if __name__ == "__main__":
    app()
