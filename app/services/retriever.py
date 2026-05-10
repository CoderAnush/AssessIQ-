"""
LIGHTWEIGHT Retrieval Engine - Replaced Semantic Search with Keyword Matching.
Designed for low-resource environments (Render Free Tier).
"""

from typing import List, Dict, Optional, Tuple
from app.models.assessment import AssessmentWithMetadata
from app.services.catalog_loader import CatalogLoader
from app.services.conversation_analyzer import HiringContext
from app.logging.logger import get_logger

logger = get_logger("retriever_lightweight")


class HybridRetriever:
    """
    Lightweight keyword-based retrieval.
    Replaces heavy FAISS/Sentence-Transformers with simple Python matching.
    """

    def __init__(
        self,
        catalog_loader: CatalogLoader,
        embeddings_model=None,
        faiss_index=None,
        semantic_weight: float = 0.0, # Semantic search disabled
        bm25_weight: float = 1.0,
    ):
        """Initialize lightweight retriever."""
        self.catalog_loader = catalog_loader
        logger.info("Initializing LIGHTWEIGHT retriever (Keyword Matching Only)")

    def retrieve(
        self,
        query: str,
        context: HiringContext,
        top_k: int = 10,
    ) -> List[Dict]:
        """
        Retrieve relevant assessments using simple keyword matching.
        """
        logger.info(f"LIGHTWEIGHT RETRIEVAL for query: {query}")
        
        all_assessments = self.catalog_loader.get_all()
        scored_results = []
        
        query_terms = set(query.lower().split())
        
        for assessment in all_assessments:
            score = 0.0
            
            # 1. Name match (high weight)
            name_lower = assessment.name.lower()
            if any(term in name_lower for term in query_terms):
                score += 0.5
                
            # 2. Skill match
            assess_skills = {s.lower() for s in assessment.skills}
            skill_matches = len(query_terms.intersection(assess_skills))
            score += 0.1 * skill_matches
            
            # 3. Description match
            desc_lower = assessment.description.lower()
            if any(term in desc_lower for term in query_terms):
                score += 0.2
                
            if score > 0:
                scored_results.append({
                    "id": assessment.id,
                    "name": assessment.name,
                    "url": assessment.url,
                    "test_type": assessment.test_type.value,
                    "description": assessment.description,
                    "hybrid_score": min(score, 1.0),
                    "semantic_score": 0.0, # Disabled
                    "bm25_score": score
                })
        
        # Sort and return top_k
        final_results = sorted(
            scored_results, key=lambda x: x["hybrid_score"], reverse=True
        )[:top_k]
        
        logger.info(f"Lightweight retrieval returned {len(final_results)} results")
        return final_results

    def get_assessment_by_name(self, name: str) -> Optional[AssessmentWithMetadata]:
        """Get assessment by name for comparisons."""
        return self.catalog_loader.get_by_name(name)

    def get_assessment_by_id(self, assessment_id: str) -> Optional[AssessmentWithMetadata]:
        """Get assessment by ID."""
        return self.catalog_loader.get_by_id(assessment_id)
