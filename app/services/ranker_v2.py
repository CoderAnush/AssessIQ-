"""
Enterprise-grade Ranking Engine for AssessIQ.
Implements strict domain filtering, role specificity boosts, and grounded insights.
"""

from typing import List, Dict, Set, Optional, Any
import numpy as np
from dataclasses import dataclass, field
from app.logger_config.logger import get_logger
from app.services.skill_graph import SkillGraph

logger = get_logger("enterprise_ranker")

@dataclass
class RankingFactors:
    embedding_similarity: float = 0.0
    keyword_similarity: float = 0.0
    graph_relevance: float = 0.0
    role_boost: float = 0.0
    domain_penalty: float = 0.0
    mode_adjustment: float = 0.0
    diversity_bonus: float = 0.0

@dataclass
class RankedAssessment:
    assessment: Any
    factors: RankingFactors
    final_score: float
    explanation: str
    matched_skills: List[str] = field(default_factory=list)
    inferred_skills: List[str] = field(default_factory=list)

class EnterpriseRanker:
    """
    UPGRADED Enterprise Ranking Engine (Phase 2, 5, 6).
    """
    
    DOMAIN_MISMATCH_PENALTY = 0.85
    ROLE_SPECIFICITY_BOOST = 0.3
    TECH_STACK_BOOST = 0.4
    FRONTEND_MIN_RESULTS = 3
    
    def __init__(self, embedding_service=None, skill_graph: Optional[SkillGraph] = None):
        self.embedding_service = embedding_service
        self.skill_graph = skill_graph or SkillGraph()

    def rank(self, retrieved: List[Dict], context: Any, catalog: Dict[str, Any], top_k: int = 10) -> List[RankedAssessment]:
        """
        Hardened ranking with strict domain enforcement.
        """
        # Phase 8: Semantic similarity skipped in hotfix
        query_emb = None
        if self.embedding_service and hasattr(self.embedding_service, "get_embedding"):
            try:
                query_text = f"{context.role} {context.seniority} {' '.join(context.tech_stack)}"
                query_emb = self.embedding_service.get_embedding(query_text)
            except Exception:
                query_emb = None
        
        scored = []
        is_frontend_query = self._is_frontend_context(context)
        is_technical_query = self._is_technical_context(context)
        is_fastapi_query = self._is_fastapi_context(context)

        for res in retrieved:
            assess = catalog.get(res["id"])
            if not assess: continue

            if is_technical_query and self._is_suppressed_for_technical(assess):
                continue

            if is_fastapi_query and self._is_fastapi_mismatch(assess):
                continue
            
            factors = self._calculate_factors(assess, context, query_emb)
            
            # Final Score Calculation (Phase 6)
            # Prioritize Domain and Skills over Semantic Similarity
            # In HOTFIX mode, embedding_similarity will be 0.0
            final_score = (
                factors.graph_relevance * 0.5 +
                factors.keyword_similarity * 0.35 +
                factors.embedding_similarity * 0.05 +
                factors.role_boost * 0.1
            )
            
            # Apply Hard Penalty (Phase 2)
            if factors.domain_penalty > 0.5:
                final_score *= (1.0 - self.DOMAIN_MISMATCH_PENALTY)

            explanation = self._generate_grounded_insight(assess, context)
            
            tech_stack = {str(t).lower() for t in (getattr(context, "tech_stack", set()) or set())}
            assess_skills = set(getattr(assess, "skills", []))
            matched_skills = list(tech_stack.intersection(assess_skills)) if tech_stack else []

            scored.append(RankedAssessment(
                assessment=assess,
                factors=factors,
                final_score=final_score,
                explanation=explanation,
                matched_skills=matched_skills,
                inferred_skills=[]
            ))
            
        ranked = sorted(scored, key=lambda x: x.final_score, reverse=True)[:top_k]

        # Guarantee frontend coverage for explicit frontend requests.
        if is_frontend_query and len(ranked) < self.FRONTEND_MIN_RESULTS and catalog:
            existing_ids = {item.assessment.id for item in ranked}
            supplemental = []
            for assess in catalog.values():
                if assess.id in existing_ids:
                    continue
                if self._is_suppressed_for_technical(assess):
                    continue
                if not self._is_frontend_assessment(assess):
                    continue
                supplemental.append(RankedAssessment(
                    assessment=assess,
                    factors=RankingFactors(graph_relevance=0.8, keyword_similarity=0.6, role_boost=0.25),
                    final_score=0.75,
                    explanation=self._generate_grounded_insight(assess, context),
                    matched_skills=[],
                    inferred_skills=[],
                ))
                if len(ranked) + len(supplemental) >= self.FRONTEND_MIN_RESULTS:
                    break

            ranked = sorted(ranked + supplemental, key=lambda x: x.final_score, reverse=True)[:max(top_k, self.FRONTEND_MIN_RESULTS)]
        
        # 6. GUARANTEE MINIMUM RESULTS (Phase 11)
        if not ranked and catalog:
            logger.info("RANKER: No results, returning top technical catalog items")
            role_text = getattr(context, "role", "").lower()
            is_tech = any(w in role_text for w in ["python", "java", "backend", "engineer", "developer", "devops", "cloud", "data", "software", "stack", "frontend", "qa", "test", "sdet", "architect", "fastapi"])
            is_fastapi = "fastapi" in role_text or any(str(t).lower() == "fastapi" for t in (getattr(context, "tech_stack", set()) or set()))
            
            fallback_candidates = []
            blacklist = ["account manager", "sales", "collections", "reservation agent", "cashier", "clerk", "bilingual", "bank collections", "agency manager", "job focused assessment", "global skills", "hipo unlocking potential", "bank operations supervisor", "branch manager"]
            
            for assess in catalog.values():
                name_low = assess.name.lower()
                text_low = (assess.name + " " + assess.description).lower()
                if any(bw in name_low for bw in blacklist): continue
                
                score = 0.5
                if is_tech:
                    if self._is_suppressed_for_technical(assess):
                        continue

                    matches_technical = False
                    if is_fastapi:
                        if any(w in text_low for w in ["python", "backend", "fastapi", "django", "flask", "microservice", "api ", " api"]):
                            matches_technical = True
                            score = 0.85
                    else:
                        if any(w in name_low for w in ["java", "python", "software", "coding", "technical", "algorithm", "logic", "programming", "developer"]):
                            matches_technical = True
                            score = 0.7

                    if not matches_technical:
                        continue
                
                fallback_candidates.append(RankedAssessment(
                    assessment=assess,
                    factors=RankingFactors(),
                    final_score=score,
                    explanation="Catalog-grounded recommendation for general recruiter screening."
                ))
                if len(fallback_candidates) >= 5: break
            
            ranked = sorted(fallback_candidates, key=lambda x: x.final_score, reverse=True)[:3]
        
        return ranked

    def _calculate_factors(self, assess: Any, context: Any, query_emb: Any) -> RankingFactors:
        # 1. Domain Alignment
        assess_domain = self._infer_domain(assess)
        context_domain = getattr(context, "domain", "general")
        domain_penalty = 1.0 if context_domain != "general" and assess_domain != "general" and context_domain != assess_domain else 0.0
        
        # 2. Skill Overlap
        assess_skills = {str(s).lower() for s in (set(getattr(assess, "skills", [])) | set(getattr(assess, "inferred_skills", [])))}
        tech_stack = {str(t).lower() for t in (getattr(context, "tech_stack", set()) or set())}
        matched = assess_skills.intersection(tech_stack)
        keyword_sim = len(matched) / max(1, len(tech_stack))
        
        # 3. Graph Relevance
        graph_score = 0.0
        for s in tech_stack:
            for askill in assess_skills:
                graph_score = max(graph_score, self.skill_graph.get_related_weight(s, askill))

        # 4. Role Boost
        role_boost = 0.0
        role = getattr(context, "role", "") or ""
        if role and role.lower() in assess.name.lower():
            role_boost = self.ROLE_SPECIFICITY_BOOST

        if self._is_frontend_context(context) and self._is_frontend_assessment(assess):
            role_boost += 0.35

        if self._is_frontend_context(context) and self._is_java_backend_assessment(assess):
            domain_penalty = 1.0

        if self._is_fastapi_context(context) and self._is_fastapi_assessment(assess):
            graph_score = max(graph_score, 0.9)
            role_boost += 0.25
        
        # 5. Embedding Similarity (SKIPPED in Hotfix)
        embedding_sim = 0.0
        if query_emb is not None and self.embedding_service:
            try:
                text = f"{assess.name} {assess.description} {assess.category}"
                assess_emb = self.embedding_service.get_embedding(text)
                embedding_sim = self.embedding_service.calculate_similarity(query_emb, assess_emb)
            except Exception:
                embedding_sim = 0.0
        
        return RankingFactors(
            embedding_similarity=embedding_sim,
            keyword_similarity=keyword_sim,
            graph_relevance=graph_score,
            role_boost=role_boost,
            domain_penalty=domain_penalty
        )

    def _infer_domain(self, assess: Any) -> str:
        text = (assess.name + " " + assess.description).lower()
        
        # Priority 1: Core Backend Languages (Avoid DevOps leakage)
        if any(w in text for w in ["python", "java", "fastapi", "django", "spring", "microservice"]):
            return "backend engineering"
            
        # Priority 2: Infrastructure & DevOps
        if any(w in text for w in ["kubernetes", "terraform", "infrastructure", "sre", "amazon", "aws", "cloud", "azure", "gcp"]):
            return "devops"
            
        # Priority 3: Data Science
        if any(w in text for w in ["pytorch", "tensorflow", "ml", "machine learning", "data engineering", "big data", "analytics"]):
            return "data science"
            
        # Priority 4: Other Technical Domains
        if any(w in text for w in ["backend", "api", "distributed", "node", "ruby", "php", "c#", ".net"]):
            return "backend engineering"
        if any(w in text for w in ["frontend", "react", "ui", "javascript", "playwright", "cypress", "angular", "html", "css"]):
            return "frontend engineering"
        if any(w in text for w in ["manager", "lead", "leadership", "stakeholder", "strategy"]):
            return "management"
        if any(w in text for w in ["qa", "test", "selenium", "automation", "playwright", "cypress"]):
            return "qa automation"
        if any(w in text for w in ["sales", "negotiation", "customer", "support", "business"]):
            return "business"
            
        return "general"

    def _generate_grounded_insight(self, assess: Any, context: Any) -> str:
        """Phase 4 & 5: Grounded Recruiter Insights with Adjacency Reasoning."""
        domain = self._infer_domain(assess)
        assess_skills = {str(s).lower() for s in (set(getattr(assess, "skills", [])) | set(getattr(assess, "inferred_skills", [])))}
        tech_stack = {str(t).lower() for t in (getattr(context, "tech_stack", set()) or set())}
        matched = list(tech_stack.intersection(assess_skills))
        
        # Adaptive Fallback Reasoning (Phase 4)
        is_adjacent = False
        if tech_stack and not matched:
            is_adjacent = True
            
        role_desc = getattr(context, "role", "this role") or "this role"
        
        if domain == "backend engineering":
            if is_adjacent:
                target_tech = list(tech_stack)[0] if tech_stack else "modern backend"
                return f"While not directly testing {target_tech}, this assessment evaluates the core systems reasoning and logic critical for high-performance {role_desc} environments."
            skill_part = f" for {', '.join(matched)}" if matched else ""
            return f"Evaluates core backend API problem-solving and technical proficiency{skill_part} for production engineering roles."
            
        if domain == "devops":
            if "kubernetes" in tech_stack or "terraform" in tech_stack:
                return f"Evaluates infrastructure automation and systems reliability competencies relevant for Kubernetes and cloud platform teams."
            return f"Measures infrastructure-as-code and cloud reliability proficiency required for {role_desc} environments."
 
        if domain == "data science":
            if any(s in tech_stack for s in ["pytorch", "ml", "ai"]):
                return f"Measures analytical reasoning and data interpretation skills important for AI/ML engineering workflows."
            return f"Assesses statistical modeling and data-driven decision making for {role_desc}."
 
        if domain == "management":
            return f"Useful for screening {role_desc} who need to lead teams and collaborate cross-functionally with stakeholders."
            
        return f"A grounded SHL assessment for {role_desc} that validates key competencies in the {domain} domain."

    def _is_technical_context(self, context: Any) -> bool:
        role = (getattr(context, "role", "") or "").lower()
        domain = (getattr(context, "domain", "") or "").lower()
        tech_stack = {str(t).lower() for t in (getattr(context, "tech_stack", set()) or set())}
        technical_terms = {
            "backend", "frontend", "engineer", "developer", "software", "python", "java", "javascript",
            "typescript", "react", "angular", "vue", "fastapi", "devops", "sre", "qa", "sdet", "data", "ml", "ai",
        }
        return any(term in role for term in technical_terms) or "engineering" in domain or bool(tech_stack.intersection(technical_terms))

    def _is_frontend_context(self, context: Any) -> bool:
        role = (getattr(context, "role", "") or "").lower()
        domain = (getattr(context, "domain", "") or "").lower()
        tech_stack = " ".join(str(t).lower() for t in (getattr(context, "tech_stack", set()) or set()))
        frontend_terms = ["frontend", "react", "angular", "vue", "javascript", "typescript", "nextjs", "ui", "web"]
        return any(term in role for term in frontend_terms) or "frontend" in domain or any(term in tech_stack for term in frontend_terms)

    def _is_fastapi_context(self, context: Any) -> bool:
        role = (getattr(context, "role", "") or "").lower()
        tech_stack = " ".join(str(t).lower() for t in (getattr(context, "tech_stack", set()) or set()))
        return "fastapi" in role or "fastapi" in tech_stack

    def _is_frontend_assessment(self, assess: Any) -> bool:
        text = (assess.name + " " + assess.description).lower()
        frontend_terms = ["frontend", "front-end", "ui", "web", "javascript", "typescript", "react", "angular", "vue", "html", "css"]
        return any(term in text for term in frontend_terms)

    def _is_java_backend_assessment(self, assess: Any) -> bool:
        text = (assess.name + " " + assess.description).lower()
        backend_terms = ["java", "spring", "backend", "j2ee", "hibernate"]
        return any(term in text for term in backend_terms)

    def _is_fastapi_assessment(self, assess: Any) -> bool:
        text = (assess.name + " " + assess.description).lower()
        return any(term in text for term in ["fastapi", "python", "backend", "microservice", "django", "flask"])

    def _is_fastapi_mismatch(self, assess: Any) -> bool:
        text = (assess.name + " " + assess.description).lower()
        return not any(term in text for term in ["fastapi", "python", "backend", "microservice", "django", "flask"])

    def _is_suppressed_for_technical(self, assess: Any) -> bool:
        text = (assess.name + " " + assess.description).lower()
        if any(term in text for term in ["sales", "account manager", "customer service", "reservation agent", "cashier", "clerk", "support representative", "bank operations supervisor", "branch manager"]):
            return True

        if any(term in text for term in ["global skills", "hipo unlocking potential", "job focused assessment", "agency manager"]):
            return True

        has_personality = any(term in text for term in ["personality", "behavioral"]) 
        has_technical = any(term in text for term in ["java", "python", "backend", "frontend", "react", "angular", "typescript", "javascript", "api", "devops", "data", "ml", "qa", "automation"])
        if has_personality and not has_technical:
            return True

        return False
