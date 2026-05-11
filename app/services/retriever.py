"""
LIGHTWEIGHT Retrieval Engine - Rebuilt for maximum Recall@10.
Uses keyword overlap, synonym expansion, and strategic scoring.
ENHANCED: Role normalization with strong domain filtering.
"""

from typing import List, Dict, Optional, Tuple
from app.models.assessment import AssessmentWithMetadata
from app.services.catalog_loader import CatalogLoader
from app.services.conversation_analyzer import HiringContext
from app.services.role_normalizer import RoleNormalizer, NormalizedRole
from app.core.assessment_taxonomy import AssessmentTaxonomy, AssessmentDomain, RoleDomain
from app.logger_config.logger import get_logger

logger = get_logger("retriever")


class HybridRetriever:
    """
    Lightweight keyword-based retrieval optimized for SHL catalog (Phase 4).
    ENHANCED: Role normalization with strong domain filtering.
    """

    def __init__(self, catalog_loader: CatalogLoader):
        self.catalog_loader = catalog_loader
        self.taxonomy = AssessmentTaxonomy()
        self.role_normalizer = RoleNormalizer()
        from app.services.skill_graph import SkillGraph
        self.skill_graph = SkillGraph()
        logger.info("Initializing Enterprise Hybrid Retriever with Skill Graph integration")

    def retrieve(self, query: str, context: HiringContext, top_k: int = 20) -> List[Dict]:
        """
        Recall Optimization with Knowledge Graph propagation and Intent Inference.
        """
        all_assessments = self.catalog_loader.get_all()
        query_low = query.lower()

        # 1. GRAPH-BASED INTENT INFERENCE (Phase 2)
        intents = self.skill_graph.infer_intent(query)
        expanded_query_skills = self.skill_graph.expand_skills(set(intents.keys()), depth=1)
        
        # Filter out common stopwords
        stopwords = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he",
                     "in", "is", "it", "its", "of", "on", "or", "the", "to", "was", "will", "with",
                     "need", "have", "looking", "seek", "hiring", "want", "find", "need", "experience"}
        query_terms = set(term for term in query_low.split() if term not in stopwords)
        
        # Add tech stack and expanded skills
        if context.tech_stack:
            query_terms.update(t.lower() for t in context.tech_stack)
        query_terms.update(expanded_query_skills)

        # 2. ROLE NORMALIZATION (Phase 4)
        n_role = getattr(context, "normalized_role", None)
        if n_role:
            role_domain_keywords = self.role_normalizer.get_domain_keywords(n_role)
            query_terms.update(role_domain_keywords)

        role_domain = self.taxonomy.classify_role(context.role or "", list(context.tech_stack or []))
        role_profile = self.taxonomy.get_role_intelligence_profile(role_domain)
        anchor_terms = [term.lower() for term in role_profile.get("anchor_terms", [])]

        scored_results = []
        for assessment in all_assessments:
            score = 0.0
            name_low = assessment.name.lower()
            desc_low = assessment.description.lower()
            metadata_str = (name_low + " " + desc_low).lower()
            
            # A. Name exact/partial match
            name_words = set(name_low.split())
            if any(term in name_words for term in query_terms):
                score += 0.5
            
            # B. Graph Skill Match (Propagation)
            assess_skills = set(getattr(assessment, "inferred_skills", []))
            skill_hits = len(query_terms.intersection(assess_skills))
            if skill_hits:
                score += 0.1 * min(skill_hits, 5)
            
            # C. Intent Weighting
            for intent, weight in intents.items():
                if intent in metadata_str:
                    score += 0.2 * weight

            # D. Taxonomy-aware role boost.
            classification = self.taxonomy.get_assessment_classification(assessment.id) or self.taxonomy._classify_assessment(assessment)
            if classification:
                if classification.primary_domain in role_profile.get("preferred_domains", []):
                    score += 0.3
                elif classification.primary_domain in role_profile.get("discouraged_domains", []):
                    score -= 0.3

            # E. Explicit tech-stack matching
            if context.tech_stack:
                tech_matches = [tech for tech in context.tech_stack if tech.lower() in metadata_str]
                if tech_matches:
                    score += 0.4 + (0.1 * len(tech_matches))

            if score > 0.15:
                scored_results.append({
                    "id": assessment.id,
                    "name": assessment.name,
                    "url": assessment.url,
                    "test_type": assessment.test_type.value,
                    "description": assessment.description,
                    "hybrid_score": min(max(score, 0.0), 1.0)
                })

        # Sort by score
        scored_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return scored_results[:top_k]


    def _is_domain_mismatch(
        self,
        normalized_role: NormalizedRole,
        name_low: str,
        desc_low: str,
        classification: Optional[object]
    ) -> bool:
        """Check if assessment domain strongly mismatches the normalized role."""
        # Map normalized roles to forbidden domain keywords
        forbidden_domains = {
            NormalizedRole.BACKEND_ENGINEER: ["sales", "customer service", "personality only", "communication only"],
            NormalizedRole.FRONTEND_ENGINEER: ["java backend", "sales", "customer service"],
            NormalizedRole.QA_ENGINEER: ["sales", "customer service", "leadership", "personality only"],
            NormalizedRole.DATA_SCIENTIST: ["java developer", "frontend", "react", "customer service"],
            NormalizedRole.SALES_REP: ["java", "python", "coding", "programming", "backend", "frontend"],
            NormalizedRole.CUSTOMER_SUPPORT: ["advanced programming", "deep learning", "backend engineering"],
            NormalizedRole.PRODUCT_MANAGER: ["java backend", "react coding"],
            NormalizedRole.ENGINEERING_MANAGER: ["pure coding", "java 8", "react framework"],
        }

        if normalized_role not in forbidden_domains:
            return False

        forbidden = forbidden_domains[normalized_role]
        combined_text = name_low + " " + desc_low

        # Check if forbidden keywords appear in assessment
        for keyword in forbidden:
            if keyword in combined_text:
                logger.debug(f"Forbidden domain '{keyword}' found in {name_low} for role {normalized_role.value}")
                return True

        return False
