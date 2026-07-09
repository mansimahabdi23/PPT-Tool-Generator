"""Tests for LLMProvider interface, StubProvider, and AzureOpenAIProvider."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from app.models.enums import AssetType, SlideType
from app.services import llm_provider as _lp
from app.services.llm_provider import (
    AzureOpenAIProvider,
    LLMProvider,
    StubProvider,
    get_provider,
    init_provider,
)
from app.services.parser import AtomicClaim, ParsedDeck, ParsedSlide, SourceRef


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deck(n_slides: int = 3) -> ParsedDeck:
    """Minimal ParsedDeck for testing."""
    type_cycle = [SlideType.title, SlideType.content, SlideType.closing, SlideType.data]
    slides = [
        ParsedSlide(
            index=i,
            slide_type=type_cycle[i % len(type_cycle)],
            text_blocks=[],
            tables=[],
            images=[],
            claims=[
                AtomicClaim(
                    text=f"Claim {i}",
                    claim_type="bullet",
                    source=SourceRef(slide_index=i, shape_id=1, shape_name="body"),
                )
            ],
            title=f"Slide {i + 1} Title",
            body_items=[f"Bullet {i}a", f"Bullet {i}b"],
        )
        for i in range(n_slides)
    ]
    return ParsedDeck(name="test_deck", slide_count=n_slides, slides=slides)


def _make_azure_response(plans: list[dict]) -> MagicMock:
    """Mock openai ChatCompletion response wrapping the given plans."""
    msg = MagicMock()
    msg.content = json.dumps({"slides": plans})
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


def _stub_entry(index: int, slide_type: str = "content") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "index": index,
        "slideType": slide_type,
        "plannedLayout": "Two-column layout with icon accents",
        "assetTypes": ["icon", "template"],
        "restructureNote": None,
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_provider_raises_before_init(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_lp, "_provider", None)
    with pytest.raises(RuntimeError, match="not initialised"):
        get_provider()


def test_init_and_get_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_lp, "_provider", None)
    stub = StubProvider()
    init_provider(stub)
    assert get_provider() is stub


def test_init_provider_replaces_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_lp, "_provider", None)
    init_provider(StubProvider())
    second = StubProvider()
    init_provider(second)
    assert get_provider() is second


# ---------------------------------------------------------------------------
# Protocol check
# ---------------------------------------------------------------------------


def test_stub_satisfies_protocol() -> None:
    assert isinstance(StubProvider(), LLMProvider)


# ---------------------------------------------------------------------------
# StubProvider
# ---------------------------------------------------------------------------


def test_stub_one_plan_per_slide() -> None:
    deck = _make_deck(4)
    plans = StubProvider().analyze_deck(deck, allow_restructure=False)
    assert len(plans) == 4
    for i, plan in enumerate(plans):
        assert plan.index == i


def test_stub_slide_types_match_parser_heuristic() -> None:
    deck = _make_deck(4)
    plans = StubProvider().analyze_deck(deck, allow_restructure=False)
    for plan, slide in zip(plans, deck.slides):
        assert plan.slide_type == slide.slide_type


def test_stub_no_restructure_note_when_disabled() -> None:
    plans = StubProvider().analyze_deck(_make_deck(3), allow_restructure=False)
    assert all(p.restructure_note is None for p in plans)


def test_stub_has_restructure_note_when_enabled() -> None:
    plans = StubProvider().analyze_deck(_make_deck(3), allow_restructure=True)
    assert all(p.restructure_note is not None for p in plans)


def test_stub_all_asset_types_are_valid() -> None:
    valid = set(AssetType)
    plans = StubProvider().analyze_deck(_make_deck(6), allow_restructure=False)
    for plan in plans:
        assert all(a in valid for a in plan.asset_types)


def test_stub_planned_layout_is_non_empty() -> None:
    plans = StubProvider().analyze_deck(_make_deck(3), allow_restructure=False)
    assert all(len(p.planned_layout) > 0 for p in plans)


def test_stub_title_slide_gets_logo() -> None:
    deck = _make_deck(1)
    deck.slides[0].slide_type = SlideType.title
    plans = StubProvider().analyze_deck(deck, allow_restructure=False)
    assert AssetType.logo in plans[0].asset_types


def test_stub_empty_deck_returns_empty_list() -> None:
    deck = ParsedDeck(name="empty", slide_count=0, slides=[])
    plans = StubProvider().analyze_deck(deck, allow_restructure=False)
    assert plans == []


# ---------------------------------------------------------------------------
# AzureOpenAIProvider — mocked client
# ---------------------------------------------------------------------------


def test_azure_uses_llm_response() -> None:
    deck = _make_deck(2)
    mock_plans = [
        {
            "id": str(uuid.uuid4()),
            "index": 0,
            "slideType": "title",
            "plannedLayout": "Full-bleed cover with brand orange gradient and logo",
            "assetTypes": ["logo", "template"],
            "restructureNote": None,
        },
        {
            "id": str(uuid.uuid4()),
            "index": 1,
            "slideType": "data",
            "plannedLayout": "Data table with callout statistics and chart accent",
            "assetTypes": ["chart", "template"],
            "restructureNote": None,
        },
    ]
    client = MagicMock()
    client.chat.completions.create.return_value = _make_azure_response(mock_plans)

    plans = AzureOpenAIProvider(client, "gpt-4o").analyze_deck(deck, allow_restructure=False)

    assert len(plans) == 2
    assert plans[0].slide_type == SlideType.title
    assert plans[0].planned_layout == "Full-bleed cover with brand orange gradient and logo"
    assert plans[1].slide_type == SlideType.data
    assert AssetType.chart in plans[1].asset_types


def test_azure_passes_both_roles_to_api() -> None:
    deck = _make_deck(1)
    client = MagicMock()
    client.chat.completions.create.return_value = _make_azure_response(
        [_stub_entry(0, "content")]
    )
    AzureOpenAIProvider(client, "gpt-4o").analyze_deck(deck, allow_restructure=False)

    call_kwargs = client.chat.completions.create.call_args
    messages = call_kwargs.kwargs["messages"]
    roles = [m["role"] for m in messages]
    assert "system" in roles
    assert "user" in roles


def test_azure_temperature_zero() -> None:
    deck = _make_deck(1)
    client = MagicMock()
    client.chat.completions.create.return_value = _make_azure_response(
        [_stub_entry(0, "content")]
    )
    AzureOpenAIProvider(client, "gpt-4o").analyze_deck(deck, allow_restructure=False)

    call_kwargs = client.chat.completions.create.call_args
    assert call_kwargs.kwargs.get("temperature") == 0


def test_azure_pads_missing_slides_with_stub() -> None:
    """When LLM returns fewer plans than slides, stub fills the gap."""
    deck = _make_deck(3)
    client = MagicMock()
    client.chat.completions.create.return_value = _make_azure_response(
        [_stub_entry(0, "title")]  # only 1 plan for 3 slides
    )

    plans = AzureOpenAIProvider(client, "gpt-4o").analyze_deck(deck, allow_restructure=False)

    assert len(plans) == 3
    assert plans[0].slide_type == SlideType.title  # from LLM
    assert plans[1].index == 1                     # stub fill
    assert plans[2].index == 2                     # stub fill


def test_azure_falls_back_on_invalid_slide_type() -> None:
    """Bad slideType from LLM → entry falls back to stub for that slide."""
    deck = _make_deck(1)
    deck.slides[0].slide_type = SlideType.title
    bad_entry = {
        "id": str(uuid.uuid4()),
        "index": 0,
        "slideType": "not_a_real_type",
        "plannedLayout": "Imaginary layout",
        "assetTypes": ["template"],
        "restructureNote": None,
    }
    client = MagicMock()
    client.chat.completions.create.return_value = _make_azure_response([bad_entry])

    plans = AzureOpenAIProvider(client, "gpt-4o").analyze_deck(deck, allow_restructure=False)

    assert len(plans) == 1
    # Falls back to stub which uses the parser heuristic (title for slide 0)
    assert plans[0].slide_type == SlideType.title


def test_azure_preserves_restructure_note_when_enabled() -> None:
    deck = _make_deck(1)
    entry = {
        "id": str(uuid.uuid4()),
        "index": 0,
        "slideType": "content",
        "plannedLayout": "Single-column with header accent",
        "assetTypes": ["icon", "template"],
        "restructureNote": "Consider merging with next slide for flow.",
    }
    client = MagicMock()
    client.chat.completions.create.return_value = _make_azure_response([entry])

    plans = AzureOpenAIProvider(client, "gpt-4o").analyze_deck(deck, allow_restructure=True)

    assert plans[0].restructure_note == "Consider merging with next slide for flow."


def test_azure_uses_configured_deployment_name() -> None:
    deck = _make_deck(1)
    client = MagicMock()
    client.chat.completions.create.return_value = _make_azure_response(
        [_stub_entry(0, "content")]
    )
    AzureOpenAIProvider(client, "my-custom-deployment").analyze_deck(deck, allow_restructure=False)

    call_kwargs = client.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == "my-custom-deployment"
