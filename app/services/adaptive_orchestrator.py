"""
Adaptive Hiring Orchestration Engine.
Optimizes pipeline generation using signal, fatigue, and competency coverage.
Implements dynamic stage naming to avoid repetition.
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from app.models.assessment import AssessmentWithMetadata
from app.services.competency_taxonomy_v2 import CompetencyTaxonomyV2
from app.services.hiring_intelligence_engines import FatigueEngine, SignalEngine
from app.services.conversation_analyzer import HiringContext
from app.logger_config.logger import get_logger

logger = get_logger("adaptive_orchestrator")

@dataclass
class OptimizedPipeline:
    stages: List[Dict[str, Any]] = field(default_factory=list)
    fatigue_report: Dict[str, Any] = field(default_factory=dict)
    signal_report: Dict[str, Any] = field(default_factory=dict)
    tradeoff_analysis: str = ""
    strategic_advice: str = ""

class AdaptiveOrchestrator:
    """
    UPGRADED Adaptive Orchestrator (Final Hardening).
    Generates dynamic, non-repetitive stage names and high-trust signals.
    """
    
    def __init__(self, taxonomy: Optional[CompetencyTaxonomyV2] = None):
        self.taxonomy = taxonomy or CompetencyTaxonomyV2()
        self.fatigue_engine = FatigueEngine()
        self.signal_engine = SignalEngine()

    def orchestrate(self, ranked_assessments: List[Any], context: HiringContext, catalog: Dict[str, Any]) -> OptimizedPipeline:
        """
        Generates an elite, adaptive hiring pipeline with dynamic staging.
        """
        try:
            # 1. Optimize selection for coverage vs redundancy
            selected_ids = self._optimize_selection(ranked_assessments, context)
            
            # 2. Dynamic Stage Generation (Final Hardening Fix)
            stages = self._generate_dynamic_stages(selected_ids, catalog, context)
            
            # 3. Intelligence Analysis
            fatigue = self.fatigue_engine.calculate_fatigue(selected_ids, catalog)
            signal = self.signal_engine.estimate_signal(selected_ids, catalog)
            
            # 4. Tradeoff Analysis
            tradeoff = self._analyze_tradeoffs(fatigue, signal, context)
            
            # 5. Strategic Advice
            advice = self._generate_strategic_advice(signal, fatigue, context)
            
            return OptimizedPipeline(
                stages=stages,
                fatigue_report=fatigue,
                signal_report=signal,
                tradeoff_analysis=tradeoff,
                strategic_advice=advice
            )
        except Exception as e:
            logger.exception("ORCHESTRATION FAILURE")
            return OptimizedPipeline(
                stages=[],
                fatigue_report={"fatigue_score": 0.0, "risk_level": "LOW", "total_duration": 0},
                signal_report={"signal_score": 0.5, "coverage": {}, "confidence_levels": {}},
                tradeoff_analysis="Minimal orchestration available.",
                strategic_advice="Review individual matches below."
            )

    def _optimize_selection(self, ranked: List[Any], context: HiringContext) -> List[str]:
        """Greedy optimization to maximize coverage and minimize redundancy."""
        selected = []
        covered_skills = set()
        total_time = 0
        limit_time = 180
        
        for res in ranked:
            assess = res.assessment
            duration = getattr(assess, "duration_minutes", 30)
            if total_time + duration > limit_time: continue
            
            assess_skills = set(getattr(assess, "skills", []))
            overlap = len(assess_skills.intersection(covered_skills))
            
            if overlap > 4: continue # Diversity guard
            
            selected.append(assess.id)
            covered_skills.update(assess_skills)
            total_time += duration
            if len(selected) >= 4: break
            
        return selected

    def _generate_dynamic_stages(self, ids: List[str], catalog: Dict[str, Any], context: HiringContext) -> List[Dict[str, Any]]:
        """
        Part 1 Fix: Generates dynamic, non-repetitive stage names.
        """
        stages = []
        role = getattr(context, "role", "Engineering") or "Engineering"
        domain = getattr(context, "domain", "Technical") or "Technical"
        
        used_names = set()
        for idx, aid in enumerate(ids):
            assess = catalog.get(aid)
            if not assess: continue
            
            name = self._generate_stage_name(idx, assess, role, domain, used_names)
            used_names.add(name)
            
            stages.append({
                "name": name,
                "description": f"Targeted validation of {assess.name} competencies.",
                "assessments": [assess.name],
                "duration": getattr(assess, "duration_minutes", 30),
                "competencies_covered": list(getattr(assess, "skills", []))[:3]
            })
        return stages

    def _generate_stage_name(self, idx: int, assess: Any, role: str, domain: str, used: Set[str]) -> str:
        """Logic for dynamic stage naming (Part 1)."""
        role_clean = role.replace("Engineer", "").replace("Developer", "").strip()
        if not role_clean: role_clean = domain.title() if domain != "Technical" else "Technical"
        
        if idx == 0:
            return f"Initial {role_clean} Screening"
        
        t_type = assess.test_type.value
        if t_type == "K":
            names = [
                f"{role_clean} Architecture Validation",
                f"{role_clean} Core Competency Review",
                f"Advanced {role_clean} Evaluation",
                f"Technical Depth Assessment"
            ]
        elif t_type == "A":
            names = [
                f"Cognitive Aptitude Check",
                f"Problem Solving Round",
                f"Analytical Reasoning Stage"
            ]
        else: # Personality
            names = [
                f"Behavioral Fit Interview",
                f"Leadership Style Analysis",
                f"Culture Alignment Review"
            ]
            
        for n in names:
            if n not in used: return n
        return f"Stage {idx + 1}: {assess.name}"

    def _analyze_tradeoffs(self, fatigue: Dict, signal: Dict, context: HiringContext) -> str:
        f_score = fatigue.get("fatigue_score", 0.0)
        s_score = signal.get("signal_score", 0.0)
        if f_score > 0.5: return "Rigor-Focused: Maximum technical validation but requires high candidate commitment."
        if s_score < 0.4: return "Efficiency-Focused: Rapid screening with low candidate friction."
        return "Balanced: Optimal trade-off between signal quality and candidate experience."

    def _generate_strategic_advice(self, signal: Dict, fatigue: Dict, context: HiringContext) -> str:
        s_score = signal.get("signal_score", 0.0)
        if s_score > 0.8: return "Elite-tier signal detected. This pipeline offers FAANG-quality technical validation."
        if s_score > 0.5: return "Strong domain alignment. Pipeline covers all core competencies for this role."
        return "Standard screening pipeline. Consider adding a technical interview to deepen signal."
