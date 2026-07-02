"""Unit tests for tech family resolution and vague request detection."""

import pytest

from app.services.tech_families import (
    TECH_FAMILIES,
    card_matches_family,
    families_for_text,
    families_for_tokens,
    family_for_token,
)
from app.utils.intent_tokens import is_vague_request, normalize_tokens


def test_family_for_token_java_ecosystem():
    assert family_for_token("java") == "JAVA"
    assert family_for_token("spring") == "JAVA"
    assert family_for_token("jvm") == "JAVA"


def test_family_for_token_python_ecosystem():
    assert family_for_token("python") == "PYTHON"
    assert family_for_token("django") == "PYTHON"
    assert family_for_token("fastapi") == "PYTHON"


def test_families_for_text_full_stack_java():
    fams = families_for_text("Full Stack Java Spring React")
    assert "JAVA" in fams
    assert "JS" in fams


def test_card_matches_java_family():
    assert card_matches_family("Spring (New)", "JAVA")
    assert card_matches_family("Core Java (Advanced Level)", "JAVA")
    assert not card_matches_family("ReactJS", "JAVA")


def test_card_matches_any_target_family():
    from app.services.tech_families import card_matches_any_target_family

    assert card_matches_any_target_family("Python (New)", {"PYTHON"})
    assert card_matches_any_target_family("Django", {"PYTHON"})
    assert not card_matches_any_target_family("Spring (New)", {"PYTHON"})
    assert card_matches_any_target_family(
        "ReactJS",
        {"JS", "PYTHON"},
    )


def test_is_vague_request_paraphrases():
    assert is_vague_request("I need an assessment.")
    assert is_vague_request("Need a test")
    assert is_vague_request("Suggest an assessment")
    assert is_vague_request("Recommend assessment help")


def test_is_vague_request_not_vague_when_specific():
    assert not is_vague_request("Senior Java Backend Engineer")
    assert not is_vague_request("Hiring a React frontend developer")


def test_normalize_tokens_synonyms():
    tokens = normalize_tokens("Looking for assessments and recommendations")
    assert "assessment" in tokens
    assert "recommend" in tokens
