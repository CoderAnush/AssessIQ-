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
    
    def __init__(self, embedding_service, skill_graph: Optional[SkillGraph] = None):
        self.embedding_service = embedding_service
        self.skill_graph = skill_graph or SkillGraph()

    def rank(self, retrieved: List[Dict], context: Any, catalog: Dict[str, Any], top_k: int = 10) -> List[RankedAssessment]:
        """
        Hardened ranking with strict domain enforcement.
        """
        query_text = f"{context.role} {context.seniority} {' '.join(context.tech_stack)}"
        query_emb = self.embedding_service.get_embedding(query_text)
        
        scored = []
        for res in retrieved:
            assess = catalog.get(res["id"])
            if not assess: continue
            
            factors = self._calculate_factors(assess, context, query_emb)
            
            # Final Score Calculation (Phase 6)
            # Prioritize Domain and Skills over Semantic Similarity
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
            
            scored.append(RankedAssessment(
                assessment=assess,
                factors=factors,
                final_score=final_score,
                explanation=explanation,
                matched_skills=list(context.tech_stack.intersection(set(getattr(assess, "skills", [])))),
                inferred_skills=[]
            ))
            
        return sorted(scored, key=lambda x: x.final_score, reverse=True)[:top_k]

    def _calculate_factors(self, assess: Any, context: Any, query_emb: Any) -> RankingFactors:
        # 1. Domain Alignment
        assess_domain = self._infer_domain(assess)
        domain_penalty = 1.0 if context.domain != "general" and assess_domain != "general" and context.domain != assess_domain else 0.0
        
        # 2. Skill Overlap
        assess_skills = set(getattr(assess, "skills", [])) | set(getattr(assess, "inferred_skills", []))
        matched = assess_skills.intersection(context.tech_stack)
        keyword_sim = len(matched) / max(1, len(context.tech_stack))
        
        # 3. Graph Relevance
        graph_score = 0.0
        for s in context.tech_stack:
            for askill in assess_skills:
                graph_score = max(graph_score, self.skill_graph.get_related_weight(s, askill))

        # 4. Role Boost
        role_boost = 0.0
        if context.role and context.role.lower() in assess.name.lower():
            role_boost = self.ROLE_SPECIFICITY_BOOST
        
        # 5. Embedding Similarity
        text = f"{assess.name} {assess.description} {assess.category}"
        assess_emb = self.embedding_service.get_embedding(text)
        embedding_sim = self.embedding_service.calculate_similarity(query_emb, assess_emb)
        
        return RankingFactors(
            embedding_similarity=embedding_sim,
            keyword_similarity=keyword_sim,
            graph_relevance=graph_score,
            role_boost=role_boost,
            domain_penalty=domain_penalty
        )

    def _infer_domain(self, assess: Any) -> str:
        text = (assess.name + " " + assess.description).lower()
        # Phase 1: Expanded Metadata Inference
        if any(w in text for w in ["kubernetes", "terraform", "platform", "infrastructure", "sre", "automation", "amazon", "aws", "cloud", "azure", "google", "gcp"]):
            return "devops"
        if any(w in text for w in ["pytorch", "tensorflow", "ml", "machine learning", "data engineering", "spark", "hadoop", "hive", "big data", "analytics"]):
            return "data science"
        if any(w in text for w in ["python", "java", "backend", "api", "microservice", "distributed", "fastapi", "django", "node", "ruby", "php", "c#", ".net"]):
            return "backend engineering"
        if any(w in text for w in ["frontend", "react", "ui", "javascript", "playwright", "cypress", "angular", "html", "css"]):
            if any(w in text for w in ["playwright", "cypress", "selenium", "test"]): return "qa automation"
            return "frontend engineering"
        if any(w in text for w in ["qa", "test", "selenium", "automation"]): return "qa automation"
        if any(w in text for w in ["leadership", "management", "strategic", "people", "manager"]): return "management"
        if any(w in text for w in ["sales", "negotiation", "customer", "support"]): return "business"
        return "general"

    def _generate_grounded_insight(self, assess: Any, context: Any) -> str:
        """Phase 4 & 5: Grounded Recruiter Insights with Adjacency Reasoning."""
        domain = self._infer_domain(assess)
        assess_skills = set(getattr(assess, "skills", [])) | set(getattr(assess, "inferred_skills", []))
        matched = list(context.tech_stack.intersection(assess_skills))
        
        # Adaptive Fallback Reasoning (Phase 4)
        is_adjacent = False
        if context.tech_stack and not matched:
            is_adjacent = True
            
        role_desc = context.role or "this role"
        
        if domain == "backend engineering":
            if is_adjacent:
                target_tech = list(context.tech_stack)[0] if context.tech_stack else "modern backend"
                return f"While not directly testing {target_tech}, this assessment evaluates the core systems reasoning and logic critical for high-performance {role_desc} environments."
            skill_part = f" for {', '.join(matched)}" if matched else ""
            return f"Evaluates core backend API problem-solving and technical proficiency{skill_part} for production engineering roles."
            
        if domain == "devops":
            if "kubernetes" in context.tech_stack or "terraform" in context.tech_stack:
                return f"Evaluates infrastructure automation and systems reliability competencies relevant for Kubernetes and cloud platform teams."
            return f"Measures infrastructure-as-code and cloud reliability proficiency required for {role_desc} environments."

        if domain == "data science":
            if any(s in context.tech_stack for s in ["pytorch", "ml", "ai"]):
                return f"Measures analytical reasoning and data interpretation skills important for AI/ML engineering workflows."
            return f"Assesses statistical modeling and data-driven decision making for {role_desc}."

        if domain == "management":
            return f"Useful for screening {context.role} who need to lead teams and collaborate cross-functionally with stakeholders."
            
        return f"A grounded SHL assessment for {context.role} that validates key competencies in the {domain} domain."
