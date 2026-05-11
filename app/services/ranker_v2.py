"""
Enterprise-grade Ranking Engine for AssessIQ.
Implements strict domain gating, diversity boosting, and absolute domain locking.
"""

from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field
from app.logger_config.logger import get_logger
from app.services.skill_graph import SkillGraph
from app.services.domain_classifier import DomainClassifier, Domain

logger = get_logger("enterprise_ranker")

@dataclass
class RankingFactors:
    semantic_similarity: float = 0.0
    domain_match_score: float = 0.0
    skill_overlap_score: float = 0.0
    diversity_bonus: float = 0.0

@dataclass
class RankedAssessment:
    assessment: Any
    factors: RankingFactors
    final_score: float
    explanation: str
    matched_skills: List[str] = field(default_factory=list)
    recruiter_signal: str = "Core Technical Signal"

class EnterpriseRanker:
    """
    UPGRADED Enterprise Ranking Engine (Absolute Domain Locking).
    """
    
    def __init__(self, embedding_service=None, skill_graph: Optional[SkillGraph] = None):
        self.embedding_service = embedding_service
        self.skill_graph = skill_graph or SkillGraph()
        self.domain_classifier = DomainClassifier()

    def rank(self, retrieved: List[Dict], context: Any, catalog: Dict[str, Any], top_k: int = 10) -> List[RankedAssessment]:
        """
        STRICT DOMAIN GATING PASS with SMART Fallback Handling.
        Prevents cross-domain leakage while keeping expanded candidates visible with lower confidence.
        """
        query_domain = getattr(context, "domain", Domain.GENERAL)
        query_classification = {"primaryDomain": query_domain}
        
        logger.info(f"RANKER: Using Context Domain: {query_domain}")

        # 1. INITIAL STRICT FILTERING (precision + safety gates)
        candidates = []
        for res in retrieved[:40]:
            assess = catalog.get(res["id"])
            if not assess:
                continue

            # DYNAMIC RE-TAGGING
            assess_domain = self.domain_classifier.normalize_assessment_domain(assess.name, assess.description)

            assess_text = (assess.name + " " + assess.description).lower()

            # HARD FILTER: Physical Engineering Domains
            engineering_blacklist = [
                "civil", "mechanical", "electrical", "chemical", "aeronautical", 
                "aerospace", "ceramic", "automotive", "electronics", "fire engineering", "geoinformatics", "general engineering"
            ]
            if query_domain in [Domain.FRONTEND, Domain.BACKEND, Domain.DEVOPS, Domain.DATA_AI]:
                if any(kw in assess_text for kw in engineering_blacklist) or assess_domain == Domain.ENGINEERING_CORE:
                    continue

            is_expansion = res.get("expansion_matched", False)
            # ABSOLUTE GATE (prevents cross-domain leakage)
            if not self.domain_classifier.is_strictly_allowed(query_domain, assess_domain):
                if not is_expansion:
                    continue

                # DATA_AI sparse catalogs may normalize NLP/ML assessments into GENERAL.
                if query_domain == Domain.DATA_AI and is_expansion and assess_domain == Domain.GENERAL:
                    pass
                else:
                    continue

            assess_text = (assess.name + " " + assess.description).lower()

            # Precision negative filters (keep as safety)
            if query_domain == Domain.FRONTEND:
                devops_cloud = ["aws", "cloud", "kubernetes", "docker", "terraform", "infrastructure", "devops", "networking", "azure", "gcp"]
                if any(kw in assess_text for kw in devops_cloud):
                    # Keep domain safety via is_allowed_domain gate above.
                    # Do not hard-drop expanded candidates (they will be confidence-decayed later).
                    pass
            if query_domain == Domain.BACKEND:
                frontend_tech = ["angular", "react", "vue", "ui ", "frontend", "css", "html", "nextjs", "ux "]
                if any(kw in assess_text for kw in frontend_tech):
                    # Keep domain safety: is_allowed_domain already enforced above.
                    pass
            if query_domain == Domain.DATA_AI:
                generic_tech = ["java developer", "frontend engineer", "sales representative"]
                if any(kw in assess_text for kw in generic_tech):
                    pass

            semantic_sim = res.get("hybrid_score", 0.0)

            expansion_label = res.get("expansion_label", None)

            # Domain match score:
            # - exact domain => 1.0
            # - adjacent domain => 0.6 (still allowed by domain gate)
            # - for expansion items, keep them eligible even when normalization differs,
            #   but never allow domain_match to reach "exact" confidence.
            if assess_domain == query_domain:
                domain_match = 1.0
            else:
                domain_match = 0.55 if is_expansion else 0.0

            tech_stack = {str(t).lower() for t in (getattr(context, "tech_stack", set()) or set())}
            assess_skills = {s.lower() for s in getattr(assess, "skills", [])}
            matched = tech_stack.intersection(assess_skills)
            skill_overlap = len(matched) / max(1, len(tech_stack)) if tech_stack else 0.5

            candidates.append({
                "assess": assess,
                "semantic": semantic_sim,
                "domain": domain_match,
                "overlap": skill_overlap,
                "matched": matched,
                "is_expansion": is_expansion,
                "expansion_label": expansion_label,
            })

        # 2. DIVERSITY BOOST WITHIN SAME DOMAIN (Part 3 Fix)
        # We only work with the filtered candidates.
        # Optimization: Use pre-calculated weights
        candidates.sort(key=lambda x: (x["semantic"] * 0.5 + x["domain"] * 0.3 + x["overlap"] * 0.2), reverse=True)
        
        final_ranked = []
        global_skill_frequencies = {}
        
        # Optimization: Early exit if we have enough high-quality candidates
        for cand in candidates:
            assess = cand["assess"]
            
            diversity_bonus = 0.0
            assess_skills = getattr(assess, "skills", [])
            for skill in assess_skills:
                freq = global_skill_frequencies.get(skill, 0)
                diversity_bonus -= (freq * 0.1) # Increased penalty to force diversity
            
            final_score = (0.50 * cand["semantic"]) + (0.30 * cand["domain"]) + (0.20 * cand["overlap"]) + diversity_bonus
            
            for skill in assess_skills:
                global_skill_frequencies[skill] = global_skill_frequencies.get(skill, 0) + 1
            
            factors = RankingFactors(
                semantic_similarity=cand["semantic"],
                domain_match_score=cand["domain"],
                skill_overlap_score=cand["overlap"],
                diversity_bonus=diversity_bonus
            )

            explanation = self._generate_grounded_insight(assess, query_classification, cand["matched"], is_expansion)
            recruiter_signal = self._determine_recruiter_signal(assess, query_domain, is_expansion)
            
            # Phase 4: Handle Fallback/Expansion confidence decay (larger decay, keep visible)
            if is_expansion:
                # Expanded/related items should remain visible but clearly lower confidence.
                final_score = final_score * 0.60
                # Note: _generate_grounded_insight already prefixes CATALOG-LIMITED MATCH:
                # Do NOT add another prefix here to avoid double-labeling.

            final_ranked.append(RankedAssessment(
                assessment=assess,
                factors=factors,
                final_score=final_score,
                explanation=explanation,
                matched_skills=list(cand["matched"]),
                recruiter_signal=recruiter_signal
            ))
            
            # Optimization: Stop once we have 15 good candidates to process for orchestration
            if len(final_ranked) >= 15: break
            
        # 3. PRECISION OVER QUANTITY (Part 5 Fix)
        # Sort and return only the top K.
        return sorted(final_ranked, key=lambda x: x.final_score, reverse=True)[:top_k]

    def _generate_grounded_insight(self, assess: Any, query_class: Dict, matched_skills: Set[str], is_expansion: bool) -> str:
        primary_domain = getattr(assess, "primary_domain", Domain.GENERAL)
        query_domain = query_class.get("primaryDomain", Domain.GENERAL)
        assess_text = (assess.name + " " + assess.description).lower()

        if query_domain == Domain.BACKEND:
            # Technology-specific backend insights
            if any(t in assess_text for t in ["distributed", "microservice", "systems design", "architecture"]):
                base = "Evaluates distributed systems architecture, microservices reliability, and scalable backend design."
            elif any(t in assess_text for t in ["api", "rest", "graphql", "endpoint"]):
                base = "Measures API design, REST architecture, and backend service contract competency."
            elif any(t in assess_text for t in ["java", "spring", "j2ee", "hibernate"]):
                base = "Evaluates Java enterprise architecture, Spring framework, and backend service design."
            elif any(t in assess_text for t in ["python", "fastapi", "django", "flask"]):
                base = "Validates Python backend development, API frameworks, and service engineering."
            elif any(t in assess_text for t in ["database", "sql", "postgresql", "nosql", "redis"]):
                base = "Assesses database design, query optimization, and data persistence architecture."
            elif any(t in assess_text for t in ["cloud", "aws", "azure", "infrastructure"]):
                base = "Measures cloud infrastructure design and backend deployment competency."
            else:
                base = "Evaluates API architecture, distributed systems reliability, and backend service design."
        elif query_domain == Domain.FRONTEND:
            base = "Validates component architecture, frontend scalability, and modern UI engineering workflows."
        elif query_domain == Domain.DATA_AI:
            base = "Assesses machine learning foundations, NLP reasoning, and applied AI competency."
        elif query_domain == Domain.DEVOPS:
            base = "Measures infrastructure automation, deployment reliability, and cloud operations competency."
        else:
            base = f"Evaluates core {primary_domain.value.lower().replace('_', ' ')} principles essential for this role."

        if is_expansion:
            base = f"CATALOG-LIMITED MATCH: {base}"
        elif len(matched_skills) > 0:
            base = f"EXACT MATCH: {base}"
        else:
            base = f"RELEVANT MATCH: {base}"

        if matched_skills:
            skills_str = ", ".join(list(matched_skills)[:3])
            return f"{base}, specifically overlapping with: {skills_str}."
        return f"{base}."

    def _determine_recruiter_signal(self, assess: Any, query_domain: Domain, is_expansion: bool) -> str:
        assess_text = (assess.name + " " + assess.description).lower()
        if query_domain == Domain.BACKEND:
            return "Enterprise Backend Signal" if "api" in assess_text or "microservice" in assess_text else "Distributed Systems Signal"
        elif query_domain == Domain.FRONTEND:
            if "react" in assess_text or "next" in assess_text:
                return "Modern Frontend Signal"
            elif "angular" in assess_text:
                return "Angular Architecture Signal"
            else:
                return "UI Engineering Signal"
        elif query_domain == Domain.DATA_AI:
            return "ML Research Signal" if "research" in assess_text or "nlp" in assess_text else "Enterprise Data Signal"
        elif query_domain == Domain.DEVOPS:
            return "Infrastructure Reliability Signal" if "sre" in assess_text or "kubernetes" in assess_text else "Cloud Operations Signal"
        return "Core Technical Signal"
