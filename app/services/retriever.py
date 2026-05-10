"""
LIGHTWEIGHT Retrieval Engine - Rebuilt for maximum Recall@10.
Uses keyword overlap, synonym expansion, and strategic scoring.
"""

from typing import List, Dict, Optional, Tuple
from app.models.assessment import AssessmentWithMetadata
from app.services.catalog_loader import CatalogLoader
from app.services.conversation_analyzer import HiringContext
from app.core.assessment_taxonomy import AssessmentTaxonomy, AssessmentDomain, RoleDomain
from app.logger_config.logger import get_logger

logger = get_logger("retriever")


class HybridRetriever:
    """
    Lightweight keyword-based retrieval optimized for SHL catalog (Phase 4).
    """

    def __init__(self, catalog_loader: CatalogLoader):
        self.catalog_loader = catalog_loader
        self.taxonomy = AssessmentTaxonomy()
        logger.info("Initializing Recall-Optimized Hybrid Retriever")

    def retrieve(self, query: str, context: HiringContext, top_k: int = 15) -> List[Dict]:
        """
        Recall@10 Optimization: Hybrid keyword matching with synonym expansion.
        """
        all_assessments = self.catalog_loader.get_all()
        query_low = query.lower()
        query_terms = set(query_low.split())
        
        # 1. Synonym Expansion (Phase 4: Maximize Recall)
        expanded_terms = set(query_terms)
        synonyms = {
            "test": ["assessment", "evaluation", "exam", "inventory"],
            "coding": ["technical", "knowledge", "programming", "software", "development"],
            "java": ["programming", "backend", "developer", "spring", "j2ee"],
            "python": ["programming", "backend", "developer", "django", "flask"],
            "cognitive": ["ability", "aptitude", "reasoning", "intelligence", "logic"],
            "personality": ["behavioral", "style", "trait", "work", "behavior"],
            "sales": ["commercial", "revenue", "account", "business", "growth", "quota", "pipeline"],
            "leadership": ["manager", "executive", "director", "strategy", "management", "supervisor"],
            "graduate": ["junior", "entry", "trainee", "fresh", "early", "entry-level"],
            "support": ["customer", "service", "client", "care", "helpdesk", "contact center"],
            "operations": ["process", "workflow", "logistics", "coordination", "delivery"],
            "data": ["analyst", "science", "ml", "ai", "statistics", "analytics"],
            "finance": ["accounting", "tax", "banking", "audit", "compliance"]
        }
        for term, syns in synonyms.items():
            if term in query_terms: expanded_terms.update(syns)

        role_domain = self.taxonomy.classify_role(context.role or "", list(context.tech_stack or []))
        role_profile = self.taxonomy.get_role_intelligence_profile(role_domain)
        anchor_terms = [term.lower() for term in role_profile.get("anchor_terms", [])]
        role_boosts = {
            RoleDomain.BACKEND_ENGINEER: {AssessmentDomain.TECHNICAL, AssessmentDomain.COGNITIVE, AssessmentDomain.ANALYTICAL},
            RoleDomain.FRONTEND_ENGINEER: {AssessmentDomain.TECHNICAL, AssessmentDomain.COMMUNICATION, AssessmentDomain.COGNITIVE},
            RoleDomain.FULLSTACK_ENGINEER: {AssessmentDomain.TECHNICAL, AssessmentDomain.COGNITIVE, AssessmentDomain.ANALYTICAL},
            RoleDomain.DATA_SCIENTIST: {AssessmentDomain.ANALYTICAL, AssessmentDomain.COGNITIVE, AssessmentDomain.TECHNICAL},
            RoleDomain.DATA_ANALYST: {AssessmentDomain.ANALYTICAL, AssessmentDomain.COGNITIVE, AssessmentDomain.TECHNICAL},
            RoleDomain.DEVOPS_ENGINEER: {AssessmentDomain.TECHNICAL, AssessmentDomain.COGNITIVE, AssessmentDomain.ANALYTICAL},
            RoleDomain.MOBILE_DEVELOPER: {AssessmentDomain.TECHNICAL, AssessmentDomain.COGNITIVE},
            RoleDomain.QA_ENGINEER: {AssessmentDomain.TECHNICAL, AssessmentDomain.ANALYTICAL, AssessmentDomain.COGNITIVE},
            RoleDomain.ENGINEERING_MANAGER: {AssessmentDomain.LEADERSHIP, AssessmentDomain.BEHAVIORAL, AssessmentDomain.COMMUNICATION},
            RoleDomain.PRODUCT_MANAGER: {AssessmentDomain.COMMUNICATION, AssessmentDomain.ANALYTICAL, AssessmentDomain.LEADERSHIP},
            RoleDomain.SALES_REP: {AssessmentDomain.SALES, AssessmentDomain.COMMUNICATION, AssessmentDomain.PERSONALITY},
            RoleDomain.SALES_MANAGER: {AssessmentDomain.SALES, AssessmentDomain.LEADERSHIP, AssessmentDomain.COMMUNICATION},
            RoleDomain.EXECUTIVE: {AssessmentDomain.LEADERSHIP, AssessmentDomain.PERSONALITY, AssessmentDomain.COMMUNICATION},
            RoleDomain.HR_PROFESSIONAL: {AssessmentDomain.PERSONALITY, AssessmentDomain.BEHAVIORAL, AssessmentDomain.COMMUNICATION},
            RoleDomain.GENERAL: {AssessmentDomain.COGNITIVE, AssessmentDomain.BEHAVIORAL, AssessmentDomain.COMMUNICATION},
        }

        scored_results = []
        for assessment in all_assessments:
            score = 0.0
            name_low = assessment.name.lower()
            desc_low = assessment.description.lower()
            classification = self.taxonomy.get_assessment_classification(assessment.id) or self.taxonomy._classify_assessment(assessment)
            
            # A. Name exact/partial match (Highest weight)
            if any(term in name_low for term in query_terms): score += 0.6
            elif any(term in name_low for term in expanded_terms): score += 0.4
            
            # B. Skill/Role Alignment
            skills = {s.lower() for s in (assessment.skills or [])}
            roles = {r.lower() for r in (assessment.ideal_roles or [])}
            tags = {t.lower() for t in (assessment.skill_tags or [])}
            all_metadata = skills | roles | tags
            
            matches = len(expanded_terms.intersection(all_metadata))
            score += 0.25 * matches
            
            # C. Description Grounding
            if any(term in desc_low for term in query_terms): score += 0.15

            # E. Taxonomy-aware role boost.
            if classification and classification.primary_domain in role_boosts.get(role_domain, set()):
                score += 0.45
            elif classification and role_domain != RoleDomain.GENERAL:
                score -= 0.20

            preferred_domains = set(role_profile.get("preferred_domains", []))
            support_domains = set(role_profile.get("support_domains", []))
            discouraged_domains = set(role_profile.get("discouraged_domains", []))
            if classification:
                if classification.primary_domain in preferred_domains:
                    score += 0.35
                elif classification.primary_domain in support_domains:
                    score += 0.12
                elif classification.primary_domain in discouraged_domains:
                    score -= 0.35

                if classification.category == "General Assessment" and role_domain != RoleDomain.GENERAL:
                    score -= 0.45

            if anchor_terms:
                anchor_hits = sum(1 for term in anchor_terms if term in name_low or term in desc_low)
                if anchor_hits:
                    score += 0.20 + min(0.25, anchor_hits * 0.08)
                elif role_domain != RoleDomain.GENERAL:
                    score -= 0.50

            if any(marker in name_low for marker in ["global skills", "general skills", "skills assessment", "skills development report", "report", "inventory"]):
                score -= 0.70
            if role_domain != RoleDomain.GENERAL and name_low.startswith("global"):
                score -= 0.40

            # F. Explicit tech-stack matching should dominate for engineering roles.
            if context.tech_stack:
                tech_matches = [tech for tech in context.tech_stack if tech.lower() in (name_low + " " + desc_low)]
                if tech_matches:
                    score += 0.35 + (0.1 * len(tech_matches))
                elif role_domain in {
                    RoleDomain.BACKEND_ENGINEER,
                    RoleDomain.FRONTEND_ENGINEER,
                    RoleDomain.FULLSTACK_ENGINEER,
                    RoleDomain.DATA_SCIENTIST,
                    RoleDomain.DATA_ANALYST,
                    RoleDomain.DEVOPS_ENGINEER,
                    RoleDomain.MOBILE_DEVELOPER,
                    RoleDomain.QA_ENGINEER,
                }:
                    score -= 0.25
            
            # D. Category Match
            if context.preferred_test_types and assessment.test_type.value in context.preferred_test_types:
                score += 0.3
            
            if score > 0:
                scored_results.append({
                    "id": assessment.id,
                    "name": assessment.name,
                    "url": assessment.url,
                    "test_type": assessment.test_type.value,
                    "description": assessment.description,
                    "hybrid_score": min(score, 1.0)
                })
        
        # Sort by score
        scored_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return scored_results[:top_k]
