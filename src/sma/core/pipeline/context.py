"""PipelineContext — bundles everything a pipeline run needs.

Built once per run from a NicheConfig + factory-resolved providers.
Threaded through every step so nothing reaches into globals.
"""

from __future__ import annotations

from dataclasses import dataclass

from sma.core.niche.config import NicheConfig
from sma.providers.image.base import ImageProvider
from sma.providers.llm.base import LLMProvider
from sma.providers.music.base import MusicProvider
from sma.providers.voice.base import VoiceProvider


@dataclass
class PipelineContext:
    niche: NicheConfig
    llm: LLMProvider
    image: ImageProvider
    voice: VoiceProvider
    music: MusicProvider | None  # None when music is disabled
    tenant_id: int = 1  # always 1 in single-tenant mode
