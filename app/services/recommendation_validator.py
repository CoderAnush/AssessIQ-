import re
from typing import List, Set, Union, Optional
from app.models.response import Recommendation
from app.services.domain_classifier import Domain, DomainClassifier
from app.services.tech_families import card_matches_any_excluded_family

class RecommendationCompletenessValidator:
    """Validate and augment recommendation list to guarantee required assessment categories."""

    def __init__(self):
        self.min_fallback_confidence = 40
        self.max_fallback_confidence = 60

    def _fallback_confidence(self, lowest_conf: int) -> int:
        return min(self.max_fallback_confidence, max(self.min_fallback_confidence, lowest_conf - 2))

    def _score_candidate(
        self,
        assessment,
        target_type: str,
        tech_stack: set,
        user_query_tokens: set,
        query_domain: Optional[Domain] = None,
        user_query: str = "",
    ) -> float:
        score = 0.0
        name_lower = assessment.name.lower()
        desc_lower = assessment.description.lower()
        keys_lower = [k.lower() for k in getattr(assessment, "keys", [])]
        test_type = getattr(assessment, "test_type", "K")
        if hasattr(test_type, "value"):
            test_type = test_type.value
        test_type = str(test_type).upper()

        if not DomainClassifier.query_requests_java(user_query):
            if DomainClassifier.is_java_spring_assessment(name_lower, desc_lower):
                return -1.0

        if target_type == "technical":
            if test_type != "K" and "knowledge & skills" not in keys_lower and "simulations" not in keys_lower:
                return -1.0
            score += 10.0
            if query_domain == Domain.DATA_AI:
                for sig in ("ai skills", "data science", "automata data science", "machine learning"):
                    if sig in name_lower:
                        score += 80.0
            elif query_domain == Domain.QA:
                for sig in ("selenium", "automata selenium", "agile testing", "manual testing"):
                    if sig in name_lower:
                        score += 80.0
            elif query_domain == Domain.GENERAL and any(t in user_query.lower() for t in ("sales", "b2b")):
                if "sales" in name_lower:
                    score += 80.0
            for tech in tech_stack | user_query_tokens:
                if tech in name_lower:
                    score += 50.0
                if tech in desc_lower:
                    score += 15.0

        elif target_type == "cognitive":
            if test_type != "A" and "ability & aptitude" not in keys_lower:
                return -1.0
            score += 10.0
            if "verify" in name_lower:
                score += 20.0
            if "reasoning" in name_lower:
                score += 30.0
            if "g+" in name_lower:
                score += 40.0
            if "numerical" in name_lower or "deductive" in name_lower or "inductive" in name_lower:
                score += 20.0

        elif target_type == "personality":
            if test_type != "P" and "personality & behavior" not in keys_lower:
                return -1.0
            score += 10.0
            if "opq" in name_lower and "leadership" not in name_lower:
                score += 20.0
            if "workplace" in name_lower or "behavioral" in name_lower:
                score += 20.0

        elif target_type == "leadership_report":
            if query_domain != Domain.MANAGEMENT:
                return -1.0
            if "opq" not in name_lower and "leadership" not in name_lower and "development & 360" not in keys_lower:
                return -1.0
            score += 10.0
            if "leadership report" in name_lower:
                score += 50.0
            if "competency report" in name_lower:
                score += 40.0
            if "development" in name_lower:
                score += 30.0

        elif target_type == "learning":
            if "learning" in name_lower or "ability" in name_lower:
                score += 30.0
            if "verify" in name_lower:
                score += 20.0

        elif target_type == "behaviour":
            if "scenarios" in name_lower or "situational" in name_lower or "competency" in name_lower:
                score += 30.0
            if "graduate scenarios" in name_lower:
                score += 50.0

        return score

    def ensure_completeness(
        self,
        recommendations: List[Recommendation],
        required_categories: Union[Set[str], Domain, str],
        catalog: dict,
        user_query: str = "",
        remove_coding: bool = False,
        context=None,
        excluded_families: Optional[Set[str]] = None,
    ) -> List[Recommendation]:
        if isinstance(required_categories, (str, Domain)):
            from app.services.requirement_resolver import RequirementResolver
            from app.services.conversation_analyzer import HiringContext
            resolver = RequirementResolver()
            dummy_ctx = HiringContext(domain=required_categories)
            required_categories = resolver.resolve(required_categories, dummy_ctx)

        query_domain = getattr(context, "domain_enum", None) if context is not None else None
        lowest_conf = min([rec.confidence for rec in recommendations] or [self.max_fallback_confidence])
        fallback_conf = self._fallback_confidence(lowest_conf)

        existing_ids = set()
        for rec in recommendations:
            matched_id = None
            rec_url_slug = rec.url.split('/')[-1].strip().lower() if rec.url else ""
            for a in catalog.values():
                if a.id.lower() == rec_url_slug or a.name.lower() == rec.name.lower():
                    matched_id = a.id
                    break
            if matched_id:
                existing_ids.add(matched_id)

        def make_rec(a, reason: str, f_type: str) -> Recommendation:
            a_test_type = getattr(a.test_type, "value", str(a.test_type))
            return Recommendation(
                name=str(a.name),
                url=str(a.url),
                test_type=str(a_test_type),
                subtitle=f"{a.category.title()} Assessment",
                confidence=fallback_conf,
                category=str(a.category),
                stage="Screening",
                duration=f"{getattr(a, 'duration_minutes', 30)} min",
                recruiter_insight=reason,
                ideal_use_case=str(a.description[:120]) + "...",
                domain=str(getattr(a, "primary_domain", "general")).upper(),
                matched_skills=list(getattr(a, "skills", [])[:5]),
                recruiter_signal="Fallback Completeness",
                is_fallback=True,
                fallback_reason=reason,
                fallback_type=f_type,
            )

        user_query_tokens = set(re.findall(r'\b[a-z0-9.]+\b', user_query.lower()))
        tech_stack = set()
        if context is not None:
            tech_stack.update(t.lower() for t in getattr(context, "tech_stack", set()) or set())
        for rec in recommendations:
            tech_stack.update([s.lower() for s in rec.matched_skills])

        has_tech = False
        has_cognitive = False
        has_personality = False
        has_leadership = False
        has_learning = False
        has_behaviour = False

        for rec in recommendations:
            rec_name_lower = rec.name.lower()
            rec_cat_lower = rec.category.lower()
            rec_test_type = getattr(rec.test_type, "value", str(rec.test_type)).upper()

            if rec_test_type == "K" or rec_cat_lower == "knowledge" or any(kw in rec_name_lower for kw in ["java", "spring", "python", "react", "javascript", "c++", "c#", "linux", "cloud", "docker", "kubernetes", "selenium", "sales", "ai skills", "data science"]):
                has_tech = True
            if rec_test_type == "A" or rec_cat_lower in ["cognitive", "ability"] or any(kw in rec_name_lower for kw in ["reasoning", "g+", "verify", "aptitude", "cognitive", "ability"]):
                has_cognitive = True
            if rec_test_type == "P" or rec_cat_lower in ["personality", "behavior"] or any(kw in rec_name_lower for kw in ["personality", "opq", "behavior", "trait"]):
                has_personality = True
            if DomainClassifier.is_leadership_assessment(rec_name_lower):
                has_leadership = True
            if "learning" in rec_name_lower or "agile" in rec_name_lower:
                has_learning = True
            if any(kw in rec_name_lower for kw in ["scenario", "situational", "competency"]):
                has_behaviour = True

        augmented_recs = list(recommendations)
        added_personality_fallback = False
        excluded = excluded_families or getattr(context, "excluded_families", None) or set()

        def add_best_fallback(target_type: str, reason: str, fallback_type: str):
            nonlocal added_personality_fallback
            best_a = None
            best_score = -999.0
            for a in catalog.values():
                if a.id in existing_ids:
                    continue
                if excluded and card_matches_any_excluded_family(
                    a.name, excluded, getattr(a, "description", "")
                ):
                    continue
                score = self._score_candidate(
                    a, target_type, tech_stack, user_query_tokens, query_domain, user_query
                )
                if score > best_score:
                    best_score = score
                    best_a = a
            if best_a:
                augmented_recs.append(make_rec(best_a, reason, fallback_type))
                existing_ids.add(best_a.id)
                if target_type == "personality":
                    added_personality_fallback = True

        if "technical" in required_categories and not remove_coding and not has_tech:
            add_best_fallback("technical", "Fallback Technical Assessment matching core role requirements", "Completeness")

        if "cognitive" in required_categories and not has_cognitive:
            add_best_fallback("cognitive", "Verify cognitive reasoning capability for engineering role", "Completeness")

        if "personality" in required_categories and not has_personality:
            add_best_fallback("personality", "OPQ behavioral style assessment for general workplace competencies", "Completeness")

        if "leadership_report" in required_categories and not has_leadership:
            add_best_fallback("leadership_report", "OPQ leadership style assessment for strategic talent management", "Completeness")

        if "learning" in required_categories and not has_learning:
            add_best_fallback("learning", "Verify learning aptitude and agile capabilities", "Completeness")

        if "behaviour" in required_categories and not has_behaviour:
            add_best_fallback("behaviour", "Graduate scenarios situational judgment assessment", "Completeness")

        role_lower = ""
        if context is not None:
            role_lower = str(getattr(context, "role", "") or "").lower()
        if not role_lower:
            role_lower = user_query.lower()
        technical_role = (
            any(t in role_lower for t in ["engineer", "developer", "backend", "frontend", "devops", "qa", "data", "ml", "ai"])
            and not any(t in role_lower for t in ["engineering manager", "tech lead", "executive", "director", "leadership"])
        )
        if added_personality_fallback and technical_role:
            def _is_personality_fallback(rec: Recommendation) -> bool:
                test_type = getattr(rec.test_type, "value", rec.test_type)
                test_type = str(test_type).upper()
                return rec.is_fallback and (test_type == "P" or "opq" in rec.name.lower())
            augmented_recs = sorted(augmented_recs, key=_is_personality_fallback)

        if excluded:
            augmented_recs = [
                rec for rec in augmented_recs
                if not card_matches_any_excluded_family(
                    rec.name, excluded, rec.ideal_use_case or ""
                )
            ]

        return augmented_recs
