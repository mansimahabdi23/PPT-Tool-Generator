"""Analyze & Plan step — thin wrapper around the active LLMProvider.

The provider is initialised in app lifespan (StubProvider by default;
AzureOpenAIProvider when LLM_PROVIDER=azure_openai + credentials are set).
All classification logic lives in the provider, not here.
"""

from __future__ import annotations

from app.models.job import SlidePlan
from app.services.llm_provider import get_provider
from app.services.parser import ParsedDeck


def build_plan(parsed: ParsedDeck, allow_restructure: bool) -> list[SlidePlan]:
    """Produce one SlidePlan per parsed slide via the active LLMProvider."""
    return get_provider().analyze_deck(parsed, allow_restructure)
