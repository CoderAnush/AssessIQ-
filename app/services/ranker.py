"""
REBUILT Ranking Engine - Phase 2 Architectural Refinement.

RECRUITER-STYLE SCORING MODEL:
FinalScore = 
    0.25 Domain Match (Taxonomy)
    0.15 Seniority Alignment
    0.15 Assessment Type Alignment (Focus)
    0.15 Explicit Skill Overlap (Tech Stack)
    0.10 Soft-Skill Alignment
    0.10 Role Completeness (Requirement coverage)
    0.10 Semantic/Contextual Relevance
    - Diversity Penalty (Negative modifier)

Key Improvements:
1. Integrates with AssessmentTaxonomy for domain classification
2. Normalizes scores against candidate pool for natural spread
3. Enforces category diversity (no 5 personality tests)
4. Technical roles prioritize technical assessments
5. Leadership roles prioritize leadership/personality assessments
6. Natural score decay: 96, 92, 89, 84, 79, 73
"""

from typing import List, Dict, Set, Optional, Tuple, Any
import re
import time
from app.models.assessment import AssessmentWithMetadata
from app.models.ranking import RankingFactors, RankedAssessment
from app.services.conversation_analyzer import HiringContext
from app.services.recruiter_reasoning import RecruiterExplanationEngine
from app.core.assessment_taxonomy import AssessmentTaxonomy, AssessmentDomain, RoleDomain, AssessmentClassification
from app.logger_config.logger import get_logger
import numpy as np

logger = get_logger("ranker_v2")


# RankingFactors and RankedAssessment moved to app.models.ranking


class DiversityBalancer:
    """Enforces category diversity in recommendations."""
    
    def __init__(self, max_per_category: int = 2, max_per_domain: int = 3):
        self.max_per_category = max_per_category
        self.max_per_domain = max_per_domain
        self.category_counts: Dict[str, int] = {}
        self.domain_counts: Dict[AssessmentDomain, int] = {}
    
    def calculate_penalty(
        self, 
        assessment: AssessmentWithMetadata, 
        domain: AssessmentDomain,
        category: str
    ) -> float:
        """Calculate diversity penalty (0 = no penalty, negative = penalty)."""
        penalty = 0.0
        
        # Check category overflow
        current_category = self.category_counts.get(category, 0)
        if current_category >= self.max_per_category:
            penalty -= 0.15 * (current_category - self.max_per_category + 1)
        
        # Check domain overflow
        current_domain = self.domain_counts.get(domain, 0)
        if current_domain >= self.max_per_domain:
            penalty -= 0.10 * (current_domain - self.max_per_domain + 1)
        
        return penalty
    
    def record_selection(self, domain: AssessmentDomain, category: str) -> None:
        """Record that an assessment from this domain/category was selected."""
        self.category_counts[category] = self.category_counts.get(category, 0) + 1
        self.domain_counts[domain] = self.domain_counts.get(domain, 0) + 1


class RecruiterRanker:
    """
    Recruiter-style ranking engine with taxonomy integration.
    
    Produces natural score spreads and enforces category diversity.
    """
    
    DOMAIN_MISMATCH_PENALTY = -0.40  # -40% penalty for wrong domain
    MINIMUM_RECOMMENDATION_SCORE = 0.75  # 75% threshold
    
    def __init__(self, taxonomy: Optional[AssessmentTaxonomy] = None):
        self.taxonomy = taxonomy or AssessmentTaxonomy()
        self.diversity_balancer = DiversityBalancer()
        self.explanation_engine = RecruiterExplanationEngine(self.taxonomy)

    def _build_context_terms(self, context: HiringContext) -> Set[str]:
        terms: Set[str] = set()

        def add_text(text: Optional[str]) -> None:
            if not text:
                return
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                if len(token) > 1:
                    terms.add(token)

        add_text(context.role)
        add_text(context.domain)
        add_text(context.seniority)

        for skill in context.tech_stack:
            add_text(skill)
        for skill in context.soft_skills:
            add_text(skill)
        for skill in getattr(context, "technical_skills", set()):
            add_text(skill)
        for filt in context.refinement_filters:
            add_text(filt)

        return terms
    
    async def rank(
        self,
        retrieved_results: List[Dict],
        context: HiringContext,
        catalog_assessments: Dict[str, AssessmentWithMetadata],
        top_k: int = 10
    ) -> Tuple[List[RankedAssessment], List[Tuple[AssessmentWithMetadata, RankingFactors, float]]]:
        """
        Rank assessments using recruiter-style scoring (Async).
        """
        start_time = time.time()
        try:
            logger.info(f"Ranking {len(retrieved_results)} assessments for role: {context.role}")
            
            # Build/refresh taxonomy
            if not self.taxonomy._classifications:
                self.taxonomy.build_taxonomy(list(catalog_assessments.values()))
            
            # Classify role
            role_domain = self.taxonomy.classify_role(
                context.role or "",
                list(context.tech_stack or [])
            )
            logger.info(f"Role classified as: {role_domain.value}")
            role_profile = self.taxonomy.get_role_intelligence_profile(role_domain)
            
            # PRE-FILTERING (Priority 1 Optimization)
            # Shortlist only the strongest 20 retrieval candidates before deep scoring.
            candidate_pool = retrieved_results[:20]
            logger.info(f"Shortlisted {len(candidate_pool)} candidates for deep scoring")
            
            # Score shortlisted assessments
            scored_assessments: List[Tuple[AssessmentWithMetadata, RankingFactors, float]] = []
            
            for result in candidate_pool:
                assessment_id = result.get("id")
                if not assessment_id:
                    continue
                    
                assessment = catalog_assessments.get(assessment_id)
                
                if not assessment:
                    continue
                
                factors = self._calculate_factors(assessment, context, role_domain, result)
                raw_score = factors.calculate_final()
                
                scored_assessments.append((assessment, factors, raw_score))
            
            # Sort by raw score
            scored_assessments.sort(key=lambda x: x[2], reverse=True)
            
            # Apply diversity balancing during selection
            ranked_results = self._apply_diversity_and_finalize(scored_assessments, role_domain, top_k, role_profile)
            
            # Normalize to natural spread
            final_results = self._normalize_to_natural_spread(ranked_results)
            
            # Deterministic explanation generation for the final shortlist.
            for result in final_results:
                result.explanation = await self.explanation_engine.generate_explanation(
                    result.assessment,
                    context,
                    result.factors,
                )

            self._log_quality_diagnostics(final_results, context, role_profile)
            
            latency = time.time() - start_time
            logger.info(f"Completed async ranking in {latency:.3f}s")
            return final_results, scored_assessments
        except Exception as e:
            logger.error(f"Ranking error: {e}", exc_info=True)
            # Return minimal safe results instead of crashing
            return [], []
    
    def _calculate_factors(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext,
        role_domain: RoleDomain,
        retrieval_result: Dict
    ) -> RankingFactors:
        """Calculate all ranking factors for an assessment."""
        factors = RankingFactors()
        context_terms = self._build_context_terms(context)
        
        # Determine Recruiter Domains for hard penalties
        TECH_DOMAINS = {
            "java": ["java", "spring", "j2ee", "hibernate"],
            "python": ["python", "django", "flask", "asyncio"],
            "frontend": ["react", "javascript", "typescript", "frontend"],
            "data_science": ["machine learning", "ml", "ai", "sql", "data science", "analytics"],
            "devops": ["docker", "kubernetes", "aws", "devops"],
            "sales": ["sales", "account executive", "business development"],
            "support": ["customer support", "support", "service desk"],
            "leadership": ["manager", "leadership", "director", "vp"]
        }
        
        # Identify the Recruiter Domain from context
        recruiter_domain = str(context.domain or "").lower()
        candidate_text = " ".join(
            [
                assessment.name,
                assessment.description,
                " ".join(assessment.skills or []),
                " ".join(assessment.ideal_roles or []),
                " ".join(assessment.skill_tags or []),
            ]
        ).lower()
        
        # 1. Semantic Relevance (10%)
        factors.semantic_relevance = retrieval_result.get("hybrid_score", 0.5)

        if context_terms:
            hits = sum(1 for term in context_terms if term in candidate_text)
            overlap = hits / max(1, min(len(context_terms), 8))
            factors.semantic_relevance = max(factors.semantic_relevance, min(1.0, 0.35 + overlap * 0.65))
        
        # 2. Domain Match (30% - Boosted)
        alignment_score, _ = self.taxonomy.calculate_domain_alignment(
            assessment.id, role_domain
        )
        factors.domain_match = alignment_score
        
        # Phase 5: HARD DOMAIN PENALTIES & BOOSTS
        classification = self.taxonomy.get_assessment_classification(assessment.id)
        if classification:
            # A. CROSS-DOMAIN MISMATCH PENALTY
            # If recruiter domain is explicitly set and doesn't match the assessment domain/keywords
            if recruiter_domain:
                is_match = False
                # If we know the domain keywords, check if the assessment matches ANY of them
                if recruiter_domain in TECH_DOMAINS:
                    domain_keywords = TECH_DOMAINS[recruiter_domain]
                    if any(kw in candidate_text for kw in domain_keywords):
                        is_match = True
                        factors.domain_match = min(1.0, factors.domain_match + 0.40) # BOOST Exact Match
                
                # B. SPECIFIC CROSS-PENALTIES
                if recruiter_domain == "python" and ("java" in candidate_text or "j2ee" in candidate_text):
                    factors.domain_match -= 0.70 # Severe Java penalty for Python
                
                if recruiter_domain == "java" and ("python" in candidate_text or "django" in candidate_text):
                    factors.domain_match -= 0.70 # Severe Python penalty for Java

                # If it's a known domain but the assessment is for a DIFFERENT known domain
                if recruiter_domain and not is_match:
                    for other_domain, other_kws in TECH_DOMAINS.items():
                        if other_domain != recruiter_domain and any(kw in candidate_text for kw in other_kws):
                            # This is a different domain assessment!
                            factors.domain_match -= 0.60 # HUGE PENALTY
                            break
                
                # If no match found for a specific tech domain, penalize "Generic" knowledge tests
                if not is_match and recruiter_domain in ["java", "python", "data_science", "devops", "frontend"]:
                    if classification.primary_domain in [AssessmentDomain.GENERAL, AssessmentDomain.PERSONALITY] and role_domain != RoleDomain.GENERAL:
                         factors.domain_match -= 0.25 # Technical roles want technical tests

            # C. SPECIFIC ROLE-BASED PENALTIES
            if role_domain in [RoleDomain.DATA_SCIENTIST, RoleDomain.DATA_ANALYST]:
                if "java" in candidate_text or "spring" in candidate_text:
                    factors.domain_match -= 0.50 # Java is irrelevant for DS/Analytics
                if any(kw in candidate_text for kw in ["sql", "analytics", "machine learning", "data science", "statistics"]):
                    factors.domain_match += 0.35
            
            if role_domain in [RoleDomain.SALES_REP, RoleDomain.CUSTOMER_SUPPORT, RoleDomain.HR_PROFESSIONAL]:
                if classification.primary_domain == AssessmentDomain.TECHNICAL:
                    factors.domain_match -= 0.80 # No coding tests for sales/HR
            
            if role_domain == RoleDomain.ENGINEERING_MANAGER:
                if classification.primary_domain == AssessmentDomain.TECHNICAL and "management" not in candidate_text:
                    factors.domain_match -= 0.20 # EM needs less focus on syntax
                if classification.primary_domain in [AssessmentDomain.LEADERSHIP, AssessmentDomain.BEHAVIORAL]:
                    factors.domain_match += 0.30

        # Natural Score Normalization
        factors.domain_match = max(0.0, min(1.0, factors.domain_match))

        role_profile = self.taxonomy.get_role_intelligence_profile(role_domain)
        preferred_domains = set(role_profile.get("preferred_domains", []))
        support_domains = set(role_profile.get("support_domains", []))
        discouraged_domains = set(role_profile.get("discouraged_domains", []))
        anchor_terms = [term.lower() for term in role_profile.get("anchor_terms", [])]

        if classification:
            if classification.primary_domain in preferred_domains:
                factors.domain_match = min(1.0, factors.domain_match + 0.18)
            elif classification.primary_domain in support_domains:
                factors.domain_match = min(1.0, factors.domain_match + 0.05)
            elif classification.primary_domain in discouraged_domains:
                factors.domain_match *= 0.18
            elif classification.primary_domain == AssessmentDomain.GENERAL and role_domain != RoleDomain.GENERAL:
                factors.domain_match *= 0.12

            if classification.category == "General Assessment" and role_domain != RoleDomain.GENERAL:
                factors.domain_match *= 0.2

        if self._is_generic_assessment(assessment):
            if role_domain == RoleDomain.GENERAL:
                factors.semantic_relevance = max(0.0, factors.semantic_relevance - 0.05)
            else:
                factors.semantic_relevance = max(0.0, factors.semantic_relevance - 0.35)
                factors.role_completeness = max(0.0, factors.role_completeness - 0.20)

        if anchor_terms:
            anchor_hits = sum(1 for term in anchor_terms if term in candidate_text)
            if anchor_hits:
                factors.semantic_relevance = min(1.0, factors.semantic_relevance + 0.15 + min(0.15, anchor_hits * 0.05))
                factors.role_completeness = min(1.0, factors.role_completeness + 0.10)
            elif role_domain != RoleDomain.GENERAL:
                factors.semantic_relevance = max(0.0, factors.semantic_relevance - 0.18)
                factors.domain_match *= 0.85

        # Explicit relevance boosts for exact keyword matches
        if context.tech_stack:
            tech_hits = sum(1 for tech in context.tech_stack if tech.lower() in candidate_text)
            if tech_hits:
                factors.skill_overlap = min(1.0, 0.4 + (tech_hits * 0.3))
                factors.semantic_relevance = min(1.0, factors.semantic_relevance + 0.2)

        # DEBUG RANKING LOG
        score = factors.calculate_final()
        print(f"[RANK] {assessment.name} | domain={recruiter_domain} | role={role_domain.value} | score={score:.3f}")
        

        # --- RECRUITER WORKFLOW INTELLIGENCE (Priority 2 & 4) ---
        
        # A. Workflow Modes Bias
        if context.workflow_mode == "leadership":
            if classification and classification.primary_domain in [AssessmentDomain.LEADERSHIP, AssessmentDomain.PERSONALITY]:
                factors.role_completeness = min(1.0, factors.role_completeness + 0.2)
                factors.domain_match = min(1.0, factors.domain_match + 0.1)
        elif context.workflow_mode == "graduate":
            if classification and classification.primary_domain in [AssessmentDomain.COGNITIVE, AssessmentDomain.ANALYTICAL]:
                factors.type_alignment = min(1.0, factors.type_alignment + 0.2)
        elif context.workflow_mode == "quick":
            # Prefer shorter assessments
            duration = getattr(assessment, 'duration_minutes', 30)
            if duration <= 20:
                factors.role_completeness = min(1.0, factors.role_completeness + 0.15)
        
        # B. Smart Refinement Filters
        if "technical+" in context.refinement_filters:
            if classification and classification.primary_domain == AssessmentDomain.TECHNICAL:
                factors.domain_match = min(1.0, factors.domain_match + 0.2)
        if "personality-" in context.refinement_filters:
            if classification and classification.primary_domain == AssessmentDomain.PERSONALITY:
                factors.domain_match = max(0.0, factors.domain_match - 0.4)
        if "shorter" in context.refinement_filters:
            duration = getattr(assessment, 'duration_minutes', 30)
            if duration > 45:
                factors.type_alignment = max(0.0, factors.type_alignment - 0.3)
        if "cognitive-only" in context.refinement_filters:
            if classification and classification.primary_domain != AssessmentDomain.COGNITIVE:
                factors.domain_match = max(0.0, factors.domain_match - 0.5)
        
        return factors

    def _is_generic_assessment(self, assessment: AssessmentWithMetadata) -> bool:
        name = assessment.name.lower()
        generic_markers = [
            "global skills",
            "general skills",
            "general assessment",
            "skills development report",
            "skills assessment",
            "report",
            "inventory",
            "basic",
            "general ability",
        ]
        return any(marker in name for marker in generic_markers)

    def _calculate_soft_skill_match(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext
    ) -> float:
        """Calculate alignment with soft-skill requirements."""
        if not context.soft_skills:
            return 0.5
            
        soft_skills_lower = {s.lower() for s in context.soft_skills}
        assess_skills = {s.lower() for s in (assessment.skills or [])}
        
        matches = len(soft_skills_lower.intersection(assess_skills))
        if matches > 0:
            return 0.7 + (0.3 * (matches / len(soft_skills_lower)))
            
        # Check domain for soft skill relevance
        classification = self.taxonomy.get_assessment_classification(assessment.id)
        if classification:
            if "communication" in soft_skills_lower and classification.primary_domain == AssessmentDomain.COMMUNICATION:
                return 0.9
            if "leadership" in soft_skills_lower and classification.primary_domain == AssessmentDomain.LEADERSHIP:
                return 0.9
            if "teamwork" in soft_skills_lower and classification.primary_domain == AssessmentDomain.PERSONALITY:
                return 0.8
                
        return 0.4

    def _calculate_role_completeness(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext,
        factors: RankingFactors
    ) -> float:
        """Calculate how many distinct recruiter requirements this assessment covers."""
        score = 0.0
        requirements_covered = 0
        total_requirements = 0
        
        # Count requirements
        if context.tech_stack: total_requirements += 1
        if context.soft_skills: total_requirements += 1
        if context.seniority: total_requirements += 1
        if context.leadership_needs: total_requirements += 1
        
        if total_requirements == 0:
            return 0.8
            
        # Check coverage
        if factors.skill_overlap > 0.7: requirements_covered += 1
        if factors.soft_skill_match > 0.7: requirements_covered += 1
        if factors.seniority_fit > 0.8: requirements_covered += 1
        if context.leadership_needs and factors.type_alignment > 0.8: requirements_covered += 1
        
        return requirements_covered / total_requirements
    
    def _calculate_skill_overlap(
        self, 
        assessment: AssessmentWithMetadata, 
        context: HiringContext
    ) -> float:
        """Calculate explicit skill overlap score."""
        all_context_skills = (
            context.technical_skills | 
            context.soft_skills | 
            context.tech_stack
        )
        
        if not all_context_skills:
            return 0.5  # Neutral
        
        if not hasattr(assessment, 'skills') or not assessment.skills:
            return 0.3  # Low - no skills listed
        
        assess_skills = {s.lower() for s in assessment.skills}
        matches = 0
        
        for skill in all_context_skills:
            skill_lower = skill.lower()
            if any(skill_lower in a or a in skill_lower for a in assess_skills):
                matches += 1
        
        # Normalize
        overlap_ratio = matches / len(all_context_skills)
        return 0.3 + (overlap_ratio * 0.7)  # Scale 0.3-1.0
    
    def _calculate_seniority_alignment(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext
    ) -> float:
        """Calculate seniority alignment with penalties for mismatch."""
        if not context.seniority:
            return 0.7  # Default
        
        target = context.seniority.lower()
        
        if not hasattr(assessment, 'seniority_levels'):
            return 0.6
        
        supported = {s.lower() for s in assessment.seniority_levels}
        
        if target in supported:
            return 1.0
        
        # Severe penalty: junior test for senior role
        if "senior" in target and "junior" in supported and "senior" not in supported:
            return 0.15
        
        # Moderate penalty
        if "junior" in target and "senior" in supported and "junior" not in supported:
            return 0.6
        
        return 0.4
    
    def _calculate_category_fit(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext
    ) -> float:
        """Calculate category fit based on context needs."""
        test_type = assessment.test_type.value
        
        # Leadership roles need leadership focus
        if context.leadership_needs:
            if hasattr(assessment, 'leadership_focus') and assessment.leadership_focus:
                return 1.0
            if test_type == "P":  # Personality helps with leadership
                return 0.7
        
        # Technical roles need technical focus
        if context.tech_stack and len(context.tech_stack) > 0:
            if test_type == "K":  # Knowledge tests
                return 0.9
            if hasattr(assessment, 'technical_focus') and assessment.technical_focus:
                return 0.95
        
        # Communication needs
        if "communication" in [s.lower() for s in context.soft_skills]:
            if hasattr(assessment, 'communication_focus') and assessment.communication_focus:
                return 0.9
        
        return 0.6  # Neutral
    
    def _calculate_intent_modifiers(
        self,
        assessment: AssessmentWithMetadata,
        context: HiringContext
    ) -> float:
        """Calculate recruiter intent modifier bonuses/penalties."""
        modifier = 0.5  # Neutral
        
        # Exact tech match bonus
        if context.tech_stack:
            for tech in context.tech_stack:
                if tech.lower() in assessment.name.lower():
                    modifier += 0.3  # Strong bonus for exact match
                    break
                elif tech.lower() in assessment.description.lower():
                    modifier += 0.15
                    break
        
        # Leadership bonus
        if context.leadership_needs:
            if hasattr(assessment, 'leadership_focus') and assessment.leadership_focus:
                modifier += 0.2

        if getattr(context, "preferred_test_types", None) and assessment.test_type.value in context.preferred_test_types:
            modifier += 0.15
        
        return min(modifier, 1.0)
    
    def _apply_diversity_and_finalize(
        self,
        scored_assessments: List[Tuple[AssessmentWithMetadata, RankingFactors, float]],
        role_domain: RoleDomain,
        top_k: int,
        role_profile: Optional[Dict[str, object]] = None,
    ) -> List[RankedAssessment]:
        """
        Apply diversity balancing and create ranked results.
        Enforces a balanced mix: (e.g. 1 Tech, 1 Cognitive, 1 Personality).
        """
        results = []
        diversity_balancer = DiversityBalancer(max_per_category=1, max_per_domain=2)
        
        # 1. First pass: Select the absolute top candidate (anchoring)
        if scored_assessments:
            assessment, factors, raw_score = scored_assessments[0]
            classification = self.taxonomy.get_assessment_classification(assessment.id)
            if classification:
                diversity_balancer.record_selection(classification.primary_domain, classification.category)
                results.append(self._create_ranked_assessment(assessment, factors, raw_score, classification))

        # 2. Subsequent passes: Prioritize unrepresented domains
        preferred_domains = list(role_profile.get("preferred_domains", [])) if role_profile else []
        support_domains = list(role_profile.get("support_domains", [])) if role_profile else []
        target_domains = preferred_domains + [domain for domain in support_domains if domain not in preferred_domains]
        if not target_domains:
            target_domains = [AssessmentDomain.TECHNICAL, AssessmentDomain.COGNITIVE, AssessmentDomain.PERSONALITY, AssessmentDomain.LEADERSHIP, AssessmentDomain.ANALYTICAL]
        
        # Try to fill slots with diverse domains
        for _ in range(top_k - 1):
            best_candidate = None
            best_candidate_idx = -1
            max_adjusted_score = -1.0
            
            for i, (assessment, factors, raw_score) in enumerate(scored_assessments):
                if any(r.assessment.id == assessment.id for r in results):
                    continue
                    
                classification = self.taxonomy.get_assessment_classification(assessment.id)
                if not classification: continue
                
                # Boost if domain is not yet in results
                domain_penalty = diversity_balancer.calculate_penalty(
                    assessment, classification.primary_domain, classification.category
                )
                
                # Active diversity boost
                domain_already_present = any(r.domain == classification.primary_domain for r in results)
                diversity_boost = 0.15 if not domain_already_present else 0.0

                if classification.primary_domain in target_domains:
                    target_index = target_domains.index(classification.primary_domain)
                    diversity_boost += max(0.18 - (target_index * 0.03), 0.05)

                if role_profile and classification.primary_domain == AssessmentDomain.GENERAL and role_domain != RoleDomain.GENERAL:
                    diversity_boost -= 0.25

                if role_profile:
                    anchor_terms = [term.lower() for term in role_profile.get("anchor_terms", [])]
                    candidate_text = f"{assessment.name} {assessment.description}".lower()
                    if anchor_terms and any(term in candidate_text for term in anchor_terms):
                        diversity_boost += 0.10
                    elif anchor_terms and role_domain != RoleDomain.GENERAL:
                        diversity_boost -= 0.12
                
                adjusted_score = factors.calculate_final() + domain_penalty + diversity_boost
                
                if adjusted_score > max_adjusted_score:
                    max_adjusted_score = adjusted_score
                    best_candidate = (assessment, factors, raw_score, classification)
                    best_candidate_idx = i
            
            if best_candidate:
                assessment, factors, raw_score, classification = best_candidate
                diversity_balancer.record_selection(classification.primary_domain, classification.category)
                results.append(self._create_ranked_assessment(assessment, factors, raw_score, classification))
            else:
                break
                
        return results

    def _score_quality(
        self,
        result: RankedAssessment,
        context: HiringContext,
        role_profile: Optional[Dict[str, object]] = None,
    ) -> float:
        explanation_text = " ".join(result.explanation.values()).lower() if result.explanation else ""
        explanation_quality = 0.0
        if explanation_text:
            required_fragments = ["role", "measures", "ranks", "stage"]
            explanation_quality = sum(1 for fragment in required_fragments if fragment in explanation_text) / len(required_fragments)

        preferred_domains = set(role_profile.get("preferred_domains", [])) if role_profile else set()
        support_domains = set(role_profile.get("support_domains", [])) if role_profile else set()
        domain_score = 1.0 if result.domain in preferred_domains else 0.75 if result.domain in support_domains else 0.4

        seniority_score = result.factors.seniority_fit
        relevance_score = max(result.factors.domain_match, result.factors.semantic_relevance, result.factors.skill_overlap)

        diversity_score = 1.0
        if result.category == "General Assessment" and result.domain != AssessmentDomain.GENERAL:
            diversity_score = 0.7

        return round(
            (relevance_score * 0.35)
            + (diversity_score * 0.15)
            + (domain_score * 0.25)
            + (seniority_score * 0.15)
            + (explanation_quality * 0.10),
            3,
        )

    def _log_quality_diagnostics(
        self,
        ranked_results: List[RankedAssessment],
        context: HiringContext,
        role_profile: Optional[Dict[str, object]] = None,
    ) -> None:
        if not ranked_results:
            return

        scores = [self._score_quality(result, context, role_profile) for result in ranked_results]
        average_quality = sum(scores) / len(scores)
        top_names = ", ".join(result.assessment.name for result in ranked_results[:3])
        logger.info(
            f"Quality diagnostics: avg={average_quality:.3f} top={top_names} "
            f"domains={[result.domain.value for result in ranked_results[:3]]}"
        )

    def _create_ranked_assessment(self, assessment, factors, raw_score, classification) -> RankedAssessment:
        """Helper to create RankedAssessment object."""
        return RankedAssessment(
            assessment=assessment,
            final_score=factors.calculate_final(),
            raw_score=raw_score,
            confidence_label="",
            factors=factors,
            explanation={}, # Will be populated by engine
            rank_position=0,
            domain=classification.primary_domain,
            category=classification.category
        )
    
    def _normalize_to_natural_spread(
        self, 
        ranked_results: List[RankedAssessment]
    ) -> List[RankedAssessment]:
        """
        Normalize scores to create natural recruiter-style spread.
        
        Target distribution: 96, 92, 89, 84, 79, 73, 70...
        """
        if not ranked_results:
            return []
        
        # Get raw scores
        raw_scores = [r.raw_score for r in ranked_results]
        
        if len(raw_scores) == 1:
            ranked_results[0].final_score = 0.94
            ranked_results[0].confidence_label = "Exceptional Match"
            ranked_results[0].rank_position = 1
            return ranked_results
        
        # Calculate statistics
        max_score = max(raw_scores)
        min_score = min(raw_scores)
        mean_score = np.mean(raw_scores)
        std_score = np.std(raw_scores) if len(raw_scores) > 1 else 0.1
        
        # Normalize with natural spread transformation
        normalized = []
        for i, result in enumerate(ranked_results):
            # Apply position-based decay (6% per position for natural recruiter spread)
            position_factor = 1.0 - (i * 0.06)  
            
            # Apply score-based transformation
            if result.raw_score >= max_score * 0.95:
                # Top tier: 94-96%
                normalized_score = 0.94 + (0.02 * (result.raw_score - min_score) / (max_score - min_score + 0.001))
            elif result.raw_score >= mean_score:
                # Above average: 84-94%
                normalized_score = 0.84 + (0.10 * (result.raw_score - mean_score) / (max_score - mean_score + 0.001))
            else:
                # Below average: 70-84%
                normalized_score = 0.70 + (0.14 * (result.raw_score - min_score) / (mean_score - min_score + 0.001))
            
            # Apply position decay
            final_score = normalized_score * position_factor
            
            # Apply hard threshold
            if final_score < self.MINIMUM_RECOMMENDATION_SCORE:
                continue

            final_score = max(0.70, min(0.97, final_score))  # Clamp to 70-97%
            
            # Round to avoid artificial precision
            final_score = round(final_score, 2)
            
            result.final_score = final_score
            result.rank_position = len(normalized) + 1
            result.confidence_label = self._get_confidence_label(final_score)
            
            normalized.append(result)
        
        return normalized
    
    def _get_confidence_label(self, score: float) -> str:
        """Get confidence label based on score."""
        if score >= 0.94:
            return "Exceptional Match"
        elif score >= 0.89:
            return "Strong Match"
        elif score >= 0.84:
            return "Good Match"
        elif score >= 0.78:
            return "Moderate Match"
        else:
            return "Partial Match"
    
    def _generate_recruiter_explanation(
        self,
        assessment: AssessmentWithMetadata,
        factors: RankingFactors,
        role_domain: RoleDomain,
        classification: Optional[AssessmentClassification] = None
    ) -> str:
        """Generate high-fidelity recruiter-grade contextual explanation."""
        parts = []
        stage = "screening"
        
        if classification is None:
            classification = self.taxonomy.get_assessment_classification(assessment.id)
        
        role_name = role_domain.value.replace('_', ' ')
        role_profile = self.taxonomy.get_role_intelligence_profile(role_domain)
        preferred_domains = set(role_profile.get("preferred_domains", []))
        support_domains = set(role_profile.get("support_domains", []))
        
        # 1. Role/Domain Alignment
        if classification and classification.primary_domain in preferred_domains:
            parts.append(f"Directly fits {role_name} hiring because it evaluates {classification.primary_domain.value} capabilities relevant to the role")
            stage = "shortlist"
        elif classification and classification.primary_domain in support_domains:
            parts.append(f"Provides supporting evidence for {role_name} selection by measuring {classification.primary_domain.value} capabilities")
        
        # 2. Technical Depth (Recruiter-Grade)
        if classification and classification.technical_depth > 7:
            parts.append("Measures advanced problem solving and technical depth needed to differentiate stronger candidates")
        elif classification and classification.technical_depth > 4:
            parts.append("Measures practical capability that is useful for screening before deeper interviews")
            
        # 3. Behavioral/Soft Skills
        if classification and classification.behavioral_relevance > 7:
            parts.append("Captures behavioral signals that matter for team fit and day-to-day working style")
        
        # 4. Seniority match
        if factors.seniority_fit > 0.9:
            parts.append(f"Matches the expected seniority level for this role and is best used in {stage} screening")
        else:
            parts.append(f"Best used during {stage} screening to compare candidates against the core role requirements")

        # Combine
        if len(parts) >= 2:
            explanation = ". ".join(parts[:4]) + "."
        else:
            explanation = f"Recommended assessment for {role_name} based on grounded role taxonomy and catalog metadata."
            
        return explanation
    
    def _extract_technical_focus(self, assessment: AssessmentWithMetadata) -> str:
        """Extract technical focus from assessment metadata."""
        # Check name for technology
        tech_keywords = {
            "java": "Java programming proficiency",
            "python": "Python programming capabilities",
            "react": "React frontend development",
            "javascript": "JavaScript development skills",
            "data science": "data science and ML workflows",
            "machine learning": "machine learning competency",
        }
        
        name_lower = assessment.name.lower()
        for tech, description in tech_keywords.items():
            if tech in name_lower:
                return description
        
        return ""
    
    def _extract_assessment_purpose(self, assessment: AssessmentWithMetadata) -> str:
        """Extract purpose from assessment description."""
        desc = assessment.description
        
        # Extract first meaningful sentence
        sentences = desc.split(".")
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20 and len(sent) < 120:
                # Clean up
                sent = sent.lower()
                sent = sent[0].upper() + sent[1:]
                return sent
        
        return ""
    
    def get_top_recommendations(
        self,
        ranked_results: List[RankedAssessment],
        top_k: int = 5
    ) -> List[Dict]:
        """
        Backward compatible method to get top recommendations.
        Calls get_recommendations_for_api internally.
        """
        return self.get_recommendations_for_api(ranked_results, top_k)

    async def get_recommendations_for_api(
        self, 
        ranked_results: List[RankedAssessment],
        context: Optional[Any] = None,
        top_k: int = 5
    ) -> Dict:
        """
        STRICT COMPLIANCE VERSION (Phase 1 & 5).
        Returns fully structured recommendations as required by the recruiter UI.
        """
        recommendations = []
        
        # Limit to 1-10 (Phase 1)
        count = min(10, max(1, len(ranked_results)))
        if not ranked_results: count = 0

        for result in ranked_results[:count]:
            # Generate reasoning if context provided
            insight = "Catalog-grounded assessment for recruiter screening."
            ideal_use_case = "Grounded catalog recommendation."
            stage = "Screening"
            
            if context and self.explanation_engine:
                explanation = await self.explanation_engine.generate_explanation(
                    result.assessment, 
                    context, 
                    result.factors
                )
                insight = explanation.get("why_it_matches", insight)
                ideal_use_case = explanation.get("ideal_use_case", ideal_use_case)
                stage = explanation.get("best_hiring_stage", "Screening").title()

            rec = {
                "name": str(result.assessment.name),
                "url": str(result.assessment.url),
                "test_type": str(result.assessment.test_type.value) if hasattr(result.assessment.test_type, 'value') else "K",
                "subtitle": f"{result.category} assessment",
                "confidence": int(result.final_score * 100),
                "category": str(result.category),
                "stage": stage,
                "duration": f"{getattr(result.assessment, 'duration_minutes', 30)} min",
                "recruiter_insight": insight,
                "ideal_use_case": ideal_use_case
            }
            recommendations.append(rec)
            
        return {
            "recommendations": recommendations,
            "reply": "Based on your requirements, here are the most relevant SHL assessments from our grounded catalog:"
        }

    def _determine_exclusion_reason(self, assessment, factors) -> Optional[str]:
        """Strategic reason why a high-quality test was not selected (Priority 6)."""
        if factors.domain_match < 0.4:
            return "Excluded due to domain misalignment."
        if factors.seniority_fit < 0.5:
            return "Lower seniority alignment for this role level."
        if factors.type_alignment < 0.5:
            return "Assessment type did not match requested focus."
        return "Ranked lower than the top selections for this specific query."


# Backward compatibility - maintain existing interface
class RecommendationRanker(RecruiterRanker):
    """Backward compatible wrapper for existing code."""
    pass
