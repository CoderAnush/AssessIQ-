"""Unit tests for DomainClassifier overrides and strict domain gates."""

import pytest

from app.services.domain_classifier import Domain, DomainClassifier


@pytest.fixture
def classifier():
    return DomainClassifier()


def test_sdet_routes_to_qa(classifier):
    result = classifier.detect_query_domain("Hiring an SDET for automation testing with Selenium")
    assert result["primaryDomain"] == Domain.QA


def test_cto_routes_to_management(classifier):
    result = classifier.detect_query_domain("We need assessments for our new CTO / Chief Technology Officer")
    assert result["primaryDomain"] == Domain.MANAGEMENT


def test_plant_operator_routes_general_with_safety(classifier):
    result = classifier.detect_query_domain(
        "We're hiring plant operators for a chemical facility. Safety is top priority."
    )
    assert result["primaryDomain"] == Domain.GENERAL
    assert "safety" in {t.lower() for t in result.get("techStack", [])}


def test_admin_assistant_routes_office_general(classifier):
    result = classifier.detect_query_domain("Screen admin assistants for Excel and Word daily")
    assert result["primaryDomain"] == Domain.GENERAL


def test_healthcare_hipaa_routes_medical(classifier):
    result = classifier.detect_query_domain(
        "Bilingual healthcare admin staff — HIPAA compliance and patient records"
    )
    assert result["primaryDomain"] == Domain.MEDICAL


def test_platform_engineer_routes_devops(classifier):
    result = classifier.detect_query_domain("Senior platform engineer for Kubernetes and Terraform")
    assert result["primaryDomain"] == Domain.DEVOPS


def test_strict_domain_blocks_management_flooding(classifier):
    assert classifier.is_strictly_allowed(
        Domain.BACKEND,
        Domain.MANAGEMENT,
        "Occupational Personality Questionnaire OPQ32r",
    ) is False


def test_strict_domain_blocks_leadership_general(classifier):
    assert classifier.is_strictly_allowed(
        Domain.DATA_AI,
        Domain.GENERAL,
        "Global Skills Development Report leadership",
    ) is False


def test_strict_domain_allows_verify_general(classifier):
    assert classifier.is_strictly_allowed(
        Domain.BACKEND,
        Domain.GENERAL,
        "Verify General Ability Screen",
    ) is True


def test_qa_domain_strict_match(classifier):
    assert classifier.is_strictly_allowed(Domain.QA, Domain.QA, "Automata Selenium") is True
    assert classifier.is_strictly_allowed(Domain.QA, Domain.BACKEND, "Core Java") is False


def test_devops_indicators_exclude_bare_admin(classifier):
    assert "admin" not in classifier.DEVOPS_INDICATORS
    assert "system admin" in classifier.DEVOPS_INDICATORS
