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

        # 2b. Global Technical Filter (Phase 11)
        role_text = (context.role or "").lower()
        query_text = query_low
        is_tech = any(w in role_text for w in ["python", "java", "backend", "engineer", "devops", "cloud", "data", "software", "stack", "frontend", "qa", "test", "sdet", "architect", "graduate", "intern"])
        blacklist = ["account manager", "sales", "collections", "reservation agent", "cashier", "clerk", "bilingual", "bank collections", "agency manager", "hotel", "front desk", "receptionist", "hospitality", "store manager", "global skills", "hipo unlocking potential", "job focused assessment"]
        
        # Language-specific filtering (NEW: prevent Java/Python cross-contamination)
        explicit_python = "python" in query_text or "django" in query_text or "flask" in query_text
        explicit_java = "java" in query_text and "javascript" not in query_text  # Exclude JavaScript false positives
        explicit_devops = any(w in query_text for w in ["devops", "sre", "kubernetes", "terraform", "docker", "aws", "azure", "gcp", "cloud"])
        explicit_frontend = any(w in query_text for w in ["frontend", "react", "angular", "vue", "javascript", "typescript", "ui", "web", "nextjs"])
        explicit_fastapi = "fastapi" in query_text
        
        if explicit_python:
            # Exclude ANY Java assessment when Python is requested
            language_penalty_keywords = ["java"]  # Simple and effective - catches all Java
            if explicit_fastapi:
                language_penalty_keywords.extend(["sales", "account manager", "customer service"])
        elif explicit_java:
            # Exclude Python assessments when Java is requested
            language_penalty_keywords = ["python"]  # Simple and effective - catches all Python
        elif explicit_frontend:
            # Frontend roles should not leak Java backend recommendations.
            language_penalty_keywords = ["java", "spring", "backend", "sales", "account manager", "customer service"]
        elif explicit_devops:
            # For DevOps, exclude pure language programming assessments
            language_penalty_keywords = ["java programming", "python programming", "java coding", "python coding", "core java", "python developer"]
        else:
            language_penalty_keywords = []

        scored_results = []
        for assessment in all_assessments:
            name_low = assessment.name.lower()
            if is_tech and any(bw in name_low for bw in blacklist):
                continue
                
            score = 0.0
            desc_low = assessment.description.lower()
            metadata_str = (name_low + " " + desc_low).lower()

            if is_tech and any(term in metadata_str for term in ["sales", "account manager", "customer service", "global skills", "hipo unlocking potential", "job focused assessment"]):
                continue

            if is_tech and "personality" in metadata_str and not any(term in metadata_str for term in ["java", "python", "backend", "frontend", "devops", "data", "qa", "react", "angular", "api", "automation"]):
                continue
            
            # Language filtering (NEW: completely exclude wrong language for explicit queries)
            if language_penalty_keywords and any(kw in name_low for kw in language_penalty_keywords):
                continue  # Skip this assessment entirely - wrong language
            
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

            if explicit_frontend and any(term in metadata_str for term in ["frontend", "react", "angular", "vue", "javascript", "typescript", "ui", "web", "nextjs"]):
                score += 0.5

            if explicit_fastapi:
                if any(term in metadata_str for term in ["fastapi", "python", "backend", "microservice", "django", "flask"]):
                    score += 0.7
                else:
                    continue

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
        
        # 4. EMPTY RESULT FALLBACK (Phase 11)
        if not scored_results:
            logger.info("RETRIEVER: No results found, triggered technical fallback")
            role_text = (context.role or "").lower()
            is_tech = any(w in role_text for w in ["python", "java", "backend", "engineer", "devops", "cloud", "data", "software", "stack", "frontend", "qa", "test", "sdet", "architect"])
            
            # Blacklist for technical fallbacks
            blacklist = ["account manager", "sales", "collections", "reservation agent", "cashier", "clerk", "bilingual", "bank collections"]
            
            if is_tech:
                # Fallback to top technical assessments (respecting language preference)
                for a in all_assessments:
                    name_low = a.name.lower()
                    
                    # STRICT language filtering: Skip if wrong language for explicit queries
                    if explicit_python and "java" in name_low:
                        continue
                    if explicit_java and "python" in name_low:
                        continue
                    
                    # Check if matches language preference
                    matches_language = False
                    if explicit_python:
                        matches_language = "python" in name_low or "django" in name_low or "flask" in name_low
                    elif explicit_java:
                        matches_language = "java" in name_low and "javascript" not in name_low
                    elif explicit_fastapi:
                        matches_language = any(w in name_low for w in ["fastapi", "python", "backend", "django", "flask", "microservice"])
                    elif explicit_devops:
                        # For DevOps, look for cloud/DevOps keywords
                        matches_language = any(w in name_low for w in ["cloud", "devops", "kubernetes", "docker", "aws", "azure", "infrastructure", "terraform"])
                    elif explicit_frontend:
                        matches_language = any(w in name_low for w in ["frontend", "react", "angular", "vue", "javascript", "typescript", "ui", "web"])
                    else:
                        # No explicit language - accept any technical
                        matches_language = any(w in name_low for w in ["java", "python", "software", "coding", "technical", "algorithm", "logic", "programming", "developer"])
                    
                    if matches_language and not any(bw in name_low for bw in blacklist):
                        if explicit_frontend and any(w in name_low for w in ["java", "spring", "backend"]):
                            continue
                        scored_results.append({
                            "id": a.id,
                            "name": a.name,
                            "url": a.url,
                            "test_type": a.test_type.value,
                            "description": a.description,
                            "hybrid_score": 0.5
                        })
                        if len(scored_results) >= top_k: break
            
            # Only use generic fallback if NO explicit language was requested
            if not scored_results and not explicit_python and not explicit_java and not explicit_devops and not explicit_fastapi and not explicit_frontend:
                for a in all_assessments:
                    name_low = a.name.lower()
                    if not any(bw in name_low for bw in blacklist):
                        scored_results.append({
                            "id": a.id,
                            "name": a.name,
                            "url": a.url,
                            "test_type": a.test_type.value,
                            "description": a.description,
                            "hybrid_score": 0.1
                        })
                        if len(scored_results) >= top_k: break

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
