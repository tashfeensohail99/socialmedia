"""APScheduler-based worker process.

Run locally:
    python -m sma.worker.main

On Railway / Render this is the entry-point for the `worker` service.
Four jobs run in-process:
  - process_scheduled_posts:  every 60 seconds
  - auto_generate_videos:     every 15 minutes
  - discover_topics:          every 30 minutes
  - refresh_oauth_tokens:     every hour
"""

from __future__ import annotations

import signal
import sys
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from sma import __version__
from sma.config import get_settings
from sma.worker.jobs.auto_generate import auto_generate_for_all_tenants
from sma.worker.jobs.auto_generate_cinematic import auto_generate_cinematic_for_all_tenants
from sma.worker.jobs.discover_topics import discover_topics_for_all_tenants
from sma.worker.jobs.process_schedules import process_due_schedules
from sma.worker.jobs.refresh_tokens import refresh_due_tokens


def _build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        process_due_schedules,
        IntervalTrigger(seconds=60),
        id="process_scheduled_posts",
        max_instances=1,         # never overlap with itself
        coalesce=True,           # if we fall behind, just run once when we catch up
        misfire_grace_time=300,
    )
    scheduler.add_job(
        discover_topics_for_all_tenants,
        IntervalTrigger(hours=4),
        id="discover_topics",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )
    scheduler.add_job(
        auto_generate_for_all_tenants,
        IntervalTrigger(minutes=15),
        id="auto_generate_videos",
        max_instances=1,         # video gen is heavy — never overlap
        coalesce=True,
        misfire_grace_time=600,
    )
    scheduler.add_job(
        auto_generate_cinematic_for_all_tenants,
        IntervalTrigger(hours=6),
        id="auto_generate_cinematic",
        max_instances=1,         # Seedance renders run 5-10 min — never overlap
        coalesce=True,
        misfire_grace_time=1800,
    )
    scheduler.add_job(
        refresh_due_tokens,
        IntervalTrigger(hours=1),
        id="refresh_oauth_tokens",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )
    return scheduler


def main() -> int:
    settings = get_settings()
    logger.info(
        f"Starting Social Media Automation worker v{__version__} "
        f"(mode={settings.deployment_mode.value})"
    )

    scheduler = _build_scheduler()

    def _graceful_shutdown(signum, frame):  # type: ignore[no-untyped-def]
        logger.info(f"Received signal {signum}; shutting down scheduler")
        scheduler.shutdown(wait=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, _graceful_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _graceful_shutdown)

    # Run jobs once at startup so a fresh deploy doesn't wait up to 30 min
    # for the first topic discovery cycle.
    logger.info("Running initial jobs at startup...")
    try:
        process_due_schedules()
    except Exception as e:
        logger.error(f"initial process_due_schedules failed: {e}")
    # Discover topics once at startup so a freshly deployed worker has a topic
    # pool to draw from immediately (RSS is free; news/AI cost is tiny). The
    # 4-hourly schedule then keeps it fresh.
    try:
        discover_topics_for_all_tenants()
    except Exception as e:
        logger.error(f"initial discover_topics failed: {e}")
    # Then run one generation pass at startup. This is SAFE to do on every
    # restart because auto_generate is bounded by the per-day limit AND the
    # inter-post spacing gate — if today's quota is met or a post was made
    # recently, it no-ops. This makes a fresh deploy productive immediately
    # instead of waiting up to 15 min for the first timed cycle.
    try:
        auto_generate_for_all_tenants()
    except Exception as e:
        logger.error(f"initial auto_generate failed: {e}")

    logger.info("Scheduler started. Jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  {job.id} → {job.trigger}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
