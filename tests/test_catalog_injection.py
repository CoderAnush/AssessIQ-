"""Unit tests for catalog_injection must-include resolution."""

import pytest

from app.services.catalog_injection import (
    find_assessment_by_substring,
    inject_must_include_recommendations,
    resolve_must_include_ids,
)
from app.services.catalog_loader import CatalogLoader
from app.services.conversation_analyzer import HiringContext
from app.services.domain_classifier import Domain


@pytest.fixture(scope="module")
def catalog():
    loader = CatalogLoader("data/processed/catalog_processed.json")
    return {a.id: a for a in loader.get_all()}


def test_find_by_substring_rust_proxies(catalog):
    live = find_assessment_by_substring(catalog, "smart interview live coding")
    linux = find_assessment_by_substring(catalog, "linux programming")
    assert live is not None
    assert linux is not None
    assert "smart interview" in live.name.lower()
    assert "linux" in linux.name.lower()


def test_resolve_rust_must_includes(catalog):
    ctx = HiringContext(role="senior rust engineer", seniority="senior")
    ids = resolve_must_include_ids(
        catalog,
        ctx,
        "senior Rust engineer for networking infrastructure",
        Domain.BACKEND,
    )
    names = {catalog[i].name.lower() for i in ids if i in catalog}
    assert any("smart interview" in n for n in names)
    assert any("linux" in n for n in names)


def test_resolve_healthcare_must_includes(catalog):
    ctx = HiringContext(role="healthcare admin", seniority="mid")
    ids = resolve_must_include_ids(
        catalog,
        ctx,
        "healthcare admin HIPAA patient records bilingual",
        Domain.MEDICAL,
    )
    names = {catalog[i].name.lower() for i in ids if i in catalog}
    assert any("hipaa" in n for n in names)


def test_inject_prepends_missing(catalog):
    ctx = HiringContext(role="plant operator", seniority="mid")
    must_ids = resolve_must_include_ids(
        catalog,
        ctx,
        "plant operator chemical facility safety dependability",
        Domain.GENERAL,
    )
    injected = inject_must_include_recommendations([], catalog, must_ids, max_total=5)
    assert len(injected) >= 1
    assert any("safety" in r.name.lower() or "dependability" in r.name.lower() for r in injected)
