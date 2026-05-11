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
        from app.services.domain_classifier import DomainClassifier
        self.domain_classifier = DomainClassifier()

    def retrieve(self, query: str, context: Any, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval with strict domain enforcement and domain-safe SMART fallback expansion.
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
        
        # Phase 2: DOMAIN-SAFE FALLBACK EXPANSION (SMART + constrained)
        # Goal: when exact matches are sparse, expand ONLY within detected domain competency chains.
        from app.services.domain_classifier import Domain
        query_domain = getattr(context, "domain", Domain.GENERAL)

        # Count "exact" domain matches in the current scored results
        # (we treat items with domain keyword alignment as exact enough for the fallback threshold)
        scored_results_by_domain = 0
        for r in scored_results:
            assess_text = (r.get("name", "") + " " + r.get("description", "")).lower()
            inferred = self.domain_classifier.normalize_assessment_domain(assess_text, assess_text)
            if inferred == query_domain:
                scored_results_by_domain += 1

        # Expansion should trigger when exact matches are too low.
        # DATA_AI catalogs tend to be sparser around NLP-specific phrasing; use a lower threshold there.
        if query_domain == Domain.DATA_AI:
            exact_match_threshold = 3
        else:
            exact_match_threshold = 3

        if scored_results_by_domain < exact_match_threshold:
            logger.info(
                "RETRIEVER: Low exact domain matches (%s < %s). Triggering domain-safe expansion.",
                scored_results_by_domain, exact_match_threshold
            )

            # Build domain-constrained expansion keywords from the competency chain.
            # Map Domain -> internal chain key.
            chain_key_map = {
                Domain.BACKEND: "backend",
                Domain.FRONTEND: "frontend",
                Domain.DATA_AI: "data_ai",
            }
            chain_key = chain_key_map.get(query_domain, None)

            # Use existing tech_stack seeds (if any), but constrain expansions by domain keywords.
            tech_stack = getattr(context, "tech_stack", set()) or set()
            seed_skills = {s.lower() for s in tech_stack if isinstance(s, str)}

            expansion_pool = set()
            if chain_key:
                domain_keywords = self.skill_graph.get_domain_competency_chain_keywords(chain_key)
                # Expand seed skills, then constrain strictly by domain chain keywords.
                expansion_pool.update(self.skill_graph.get_domain_adjacent_skills(seed_skills, chain_key, depth=2))
                # If tech_stack is empty, fall back to chain keywords themselves.
                if not expansion_pool:
                    expansion_pool.update(domain_keywords)

            # Additional hard foundations (still domain-constrained; no cross-domain leakage).
            domain_foundations = {
                Domain.BACKEND: ["backend", "api", "rest", "microservice", "distributed systems", "databases", "software architecture", "server-side engineering"],
                Domain.FRONTEND: ["frontend", "ui engineering", "web", "javascript", "typescript", "frontend architecture", "design"],
                # Expanded to improve recall for sparse DATA_AI catalogs (TensorFlow + NLP heavy).
                Domain.DATA_AI: [
                    "machine learning", "deep learning", "neural networks", "nlp", "transformers", "language models",
                    "data science", "python for ai",
                    "tensorflow", "keras", "pytorch",
                    "transformer", "bert", "gpt",
                    "natural language", "natural language processing",
                    "word embeddings", "tokenization", "sequence modeling",
                    "text generation", "sequence-to-sequence"
                ],
            }
            if query_domain in domain_foundations:
                # Keep precision: still constrain by competency chain keywords when possible,
                # but for DATA_AI allow broader NLP/TensorFlow recall terms.
                for term in domain_foundations[query_domain]:
                    expansion_pool.add(term.lower())

            logger.info("RETRIEVER: SMART Expansion Pool Final: %s | Domain: %s", list(expansion_pool)[:30], query_domain)

            existing_ids = {r["id"] for r in scored_results}
            fallbacks = []

            # UI transparency label expected by ranker/chat
            if query_domain == Domain.BACKEND:
                expansion_label = "Expanded Match"
            elif query_domain == Domain.FRONTEND:
                expansion_label = "Related Competency Match"
            elif query_domain == Domain.DATA_AI:
                expansion_label = "Expanded Match"
            else:
                expansion_label = "Related Competency Match"

            for a in all_assessments:
                if a.id in existing_ids:
                    continue

                # Check for domain mismatch first
                if self._is_domain_mismatch(context.normalized_role, a.name.lower(), a.description.lower(), None):
                    continue

                # Domain-safe gating: allow only within the detected domain OR its adjacency.
                # This prevents leakage while still enabling richer DATA_AI sparse-catalog expansions.
                a_text = (a.name + " " + a.description).lower()
                assess_domain = self.domain_classifier.normalize_assessment_domain(a.name, a.description)

                adjacent_domains = set(self.domain_classifier.ADJACENCY_MAP.get(query_domain, []))

                allowed = (
                    assess_domain == query_domain
                    or assess_domain in adjacent_domains
                    or (query_domain == Domain.DATA_AI and assess_domain == Domain.GENERAL)
                )

                if not allowed:
                    continue

                m_str = a_text
                # SMART: match using domain expansion keywords, with robust phrase/token matching.
                # - If keyword looks like a multiword phrase, require substring match.
                # - Otherwise, allow token presence to improve recall (e.g., 'nlp', 'tensorflow', 'transformers').
                def _keyword_hits(keyword: str) -> bool:
                    k = (keyword or "").strip().lower()
                    if not k:
                        return False
                    if len(k.split()) >= 2:
                        return k in m_str
                    return k in m_str

                is_match = any(_keyword_hits(t) for t in expansion_pool if t)

                if is_match:
                    logger.info("RETRIEVER: SMART Expansion Match Found: %s | label=%s", a.name, expansion_label)
                    fallbacks.append({
                        "id": a.id,
                        "name": a.name,
                        "url": a.url,
                        "test_type": a.test_type.value,
                        "description": a.description,
                        # Expanded matches are lower-confidence by design
                        "hybrid_score": 0.38,
                        "is_fallback": True,
                        "expansion_matched": True,
                        "expansion_label": expansion_label,
                        "expanded_domain": str(query_domain),
                    })

                # Ensure we have enough candidates to support a richer pipeline.
                if len(scored_results) + len(fallbacks) >= max(15, top_k * 2):
                    break

            scored_results.extend(fallbacks)

        # Phase 3: MINIMUM GUARANTEE (General Technical)
        if len(scored_results) < 5:
            for a in all_assessments:
                if len(scored_results) >= 5:
                    break
                
                if a.id in {r["id"] for r in scored_results}:
                    continue
                    
                assess_domain = self.domain_classifier.normalize_assessment_domain(a.name, a.description)
                adjacent_domains = set(self.domain_classifier.ADJACENCY_MAP.get(query_domain, []))
                
                allowed = (
                    assess_domain == query_domain
                    or assess_domain in adjacent_domains
                    or (query_domain == Domain.DATA_AI and assess_domain == Domain.GENERAL)
                )
                
                if allowed:
                    scored_results.append({
                        "id": a.id, "name": a.name, "url": a.url,
                        "test_type": a.test_type.value, "description": a.description,
                        "hybrid_score": 0.1, "is_fallback": True,
                        "expansion_matched": True,
                        "expansion_label": "Related Competency Match"
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
