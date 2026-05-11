"""
Hybrid Retriever for AssessIQ.
Combines role-based filtering, keyword expansion, and strict domain isolation.
"""

from typing import List, Dict, Set, Optional, Any
from app.models.assessment import AssessmentWithMetadata
from app.services.skill_graph import SkillGraph
from app.services.role_normalizer import NormalizedRole
from app.logger_config.logger import get_logger

logger = get_logger("retriever")

class HybridRetriever:
    """
    UPGRADED Hybrid Retriever (Phase 2, 4, 6, 8).
    Supports adjacency expansion and guaranteed technical fallback.
    """
    
    def __init__(self, catalog_loader, skill_graph: Optional[SkillGraph] = None):
        self.catalog_loader = catalog_loader
        self.skill_graph = skill_graph or SkillGraph()

    def retrieve(self, query: str, context: Any, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval with strict domain enforcement and technical fallback.
        """
        all_assessments = self.catalog_loader.get_all()
        query_low = query.lower()
        
        # Determine technical context
        role_text = (getattr(context, "role", "") or "").lower()
        is_tech = any(w in role_text or w in query_low for w in ["python", "java", "backend", "engineer", "developer", "devops", "cloud", "data", "software", "stack", "frontend", "qa", "test", "sdet", "architect", "fastapi", "react", "angular"])

        # Detect explicit tech keywords
        explicit_python = "python" in query_low
        explicit_java = "java" in query_low and "javascript" not in query_low
        explicit_fastapi = "fastapi" in query_low
        explicit_devops = any(w in query_low for w in ["devops", "kubernetes", "terraform", "sre"])
        explicit_frontend = any(w in query_low for w in ["frontend", "react", "angular", "vue", "javascript", "typescript", "ui", "web"])
        
        scored_results = []
        for assessment in all_assessments:
            name_low = assessment.name.lower()
            desc_low = assessment.description.lower()
            metadata_str = name_low + " " + desc_low
            
            # Phase 4: Domain Mismatch Filter
            if self._is_domain_mismatch(context.normalized_role, name_low, desc_low, None):
                continue
                
            score = 0.0
            
            # Base Keyword Matching
            if any(term in metadata_str for term in query_low.split()):
                score += 0.2
            
            # Explicit tech boosts
            if explicit_python and "python" in metadata_str: score += 0.5
            if explicit_java and "java" in metadata_str: score += 0.5
            if explicit_frontend and any(w in metadata_str for w in ["frontend", "react", "angular", "vue", "javascript", "typescript", "ui", "web"]):
                score += 0.5
            if explicit_devops and any(w in metadata_str for w in ["devops", "kubernetes", "terraform", "cloud"]):
                score += 0.5
            
            # Skill Graph Expansion
            tech_stack = getattr(context, "tech_stack", set())
            for skill in tech_stack:
                if skill.lower() in metadata_str:
                    score += 0.3
                else:
                    # Check graph relations
                    related = self.skill_graph.get_related_skills(skill)
                    if any(r.lower() in metadata_str for r in related):
                        score += 0.15

            # Role Mappings (FastAPI etc)
            if explicit_fastapi:
                if any(term in metadata_str for term in ["fastapi", "python", "backend", "microservice", "django", "flask"]):
                    score += 0.7
                else:
                    # Phase 1: Don't continue/skip yet, let score accumulate
                    pass

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
        
        # Phase 1: GUARANTEED TECHNICAL FALLBACK
        if not scored_results or (is_tech and len(scored_results) < 3):
            logger.info("RETRIEVER: Low results (%s), triggering technical fallback", len(scored_results))
            
            ADJACENCY = {
                "fastapi": ["python", "backend", "api", "microservice", "distributed", "web"],
                "terraform": ["devops", "infrastructure", "cloud", "automation", "aws", "azure", "gcp"],
                "kubernetes": ["devops", "infrastructure", "cloud", "orchestration", "docker"],
                "react": ["frontend", "javascript", "typescript", "ui", "web", "angular", "vue"],
                "python": ["backend", "software", "developer", "coding"],
            }
            
            expansion = set()
            for tech, adj in ADJACENCY.items():
                if tech in query_low: expansion.update(adj)
            
            if is_tech and not expansion:
                expansion.update(["software", "coding", "technical", "algorithm", "programming", "developer"])

            existing = {r["id"] for r in scored_results}
            fallbacks = []
            for a in all_assessments:
                if a.id in existing: continue
                m_str = (a.name + " " + a.description).lower()
                if any(t in m_str for t in expansion):
                    fallbacks.append({
                        "id": a.id, "name": a.name, "url": a.url,
                        "test_type": a.test_type.value, "description": a.description,
                        "hybrid_score": 0.4, "is_fallback": True
                    })
                if len(scored_results) + len(fallbacks) >= 5: break
            scored_results.extend(fallbacks)

        if not scored_results:
            for a in all_assessments[:3]:
                 scored_results.append({
                    "id": a.id, "name": a.name, "url": a.url,
                    "test_type": a.test_type.value, "description": a.description,
                    "hybrid_score": 0.1, "is_fallback": True
                })

        return scored_results[:top_k]

    def _is_domain_mismatch(self, normalized_role: NormalizedRole, name_low: str, desc_low: str, classification: Optional[object]) -> bool:
        forbidden = {
            NormalizedRole.BACKEND_ENGINEER: ["sales", "customer service", "personality only"],
            NormalizedRole.FRONTEND_ENGINEER: ["java backend", "sales", "customer service"],
            NormalizedRole.QA_ENGINEER: ["sales", "customer service", "leadership"],
            NormalizedRole.DATA_SCIENTIST: ["java developer", "frontend", "react"],
        }
        if normalized_role not in forbidden: return False
        combined = name_low + " " + desc_low
        for keyword in forbidden[normalized_role]:
            if keyword in combined: return True
        return False
