"""
Tests for FitFindr tools — run with: pytest tests/
"""

from unittest.mock import MagicMock, patch

from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_case_insensitive():
    # "M" should match listings with size "S/M" or "M"
    results = search_listings("tee shirt top", size="M", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_returns_at_most_three():
    results = search_listings("vintage", size=None, max_price=None)
    assert len(results) <= 3


def test_search_sorted_by_relevance():
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    # All returned items should mention at least one keyword
    assert len(results) > 0
    for item in results:
        combined = (
            item["title"].lower()
            + " "
            + item["description"].lower()
            + " "
            + " ".join(item["style_tags"]).lower()
        )
        assert any(kw in combined for kw in ["vintage", "graphic", "tee"])


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

EXAMPLE_ITEM = {
    "id": "lst_002",
    "title": "Y2K Baby Tee — Butterfly Print",
    "description": "Super cute early 2000s baby tee with butterfly graphic.",
    "category": "tops",
    "style_tags": ["y2k", "vintage", "graphic tee"],
    "size": "S/M",
    "condition": "excellent",
    "price": 18.00,
    "colors": ["white", "pink", "purple"],
    "brand": None,
    "platform": "depop",
}

MOCK_LLM_RESPONSE = MagicMock()
MOCK_LLM_RESPONSE.choices[0].message.content = "Pair it with straight-leg jeans and chunky sneakers."


def test_suggest_outfit_with_wardrobe():
    wardrobe = get_example_wardrobe()
    with patch("tools._get_groq_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = MOCK_LLM_RESPONSE
        result = suggest_outfit(EXAMPLE_ITEM, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe_does_not_crash():
    wardrobe = get_empty_wardrobe()
    with patch("tools._get_groq_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = MOCK_LLM_RESPONSE
        result = suggest_outfit(EXAMPLE_ITEM, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_fallback_on_api_error():
    wardrobe = get_empty_wardrobe()
    with patch("tools._get_groq_client") as mock_client:
        mock_client.return_value.chat.completions.create.side_effect = Exception("API down")
        result = suggest_outfit(EXAMPLE_ITEM, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Y2K Baby Tee" in result


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

OUTFIT_STR = "Pair it with baggy dark wash jeans and chunky white sneakers."


def test_create_fit_card_returns_string():
    with patch("tools._get_groq_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = MOCK_LLM_RESPONSE
        result = create_fit_card(OUTFIT_STR, EXAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit_returns_error():
    result = create_fit_card("", EXAMPLE_ITEM)
    assert result == "Could not generate a fit card: no outfit suggestion was provided."


def test_create_fit_card_whitespace_outfit_returns_error():
    result = create_fit_card("   ", EXAMPLE_ITEM)
    assert result == "Could not generate a fit card: no outfit suggestion was provided."


def test_create_fit_card_fallback_on_api_error():
    with patch("tools._get_groq_client") as mock_client:
        mock_client.return_value.chat.completions.create.side_effect = Exception("API down")
        result = create_fit_card(OUTFIT_STR, EXAMPLE_ITEM)
    assert result == "Could not generate fit card due to a service error."
