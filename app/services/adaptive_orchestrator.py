"""
Adaptive Hiring Orchestration Engine.
Optimizes pipeline generation using signal, fatigue, and competency coverage.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from app.models.assessment import AssessmentWithMetadata
from app.services.competency_taxonomy_v2 import CompetencyTaxonomyV2
from app.services.hiring_intelligence_engines import FatigueEngine, SignalEngine
from app.services.conversation_analyzer import HiringContext

@dataclass
class OptimizedPipeline:
    stages: List[Dict[str, Any]] = field(default_factory=list)
    fatigue_report: Dict[str, Any] = field(default_factory=dict)
    signal_report: Dict[str, Any] = field(default_factory=dict)
    tradeoff_analysis: str = ""
    strategic_advice: str = ""

class AdaptiveOrchestrator:
    """
    Orchestrates adaptive hiring pipelines with optimization-driven logic.
    """
    
    def __init__(self, taxonomy: Optional[CompetencyTaxonomyV2] = None):
        self.taxonomy = taxonomy or CompetencyTaxonomyV2()
        self.fatigue_engine = FatigueEngine()
        self.signal_engine = SignalEngine()

    def orchestrate(self, ranked_assessments: List[Any], context: HiringContext, catalog: Dict[str, Any]) -> OptimizedPipeline:
        """
        Generates an optimized, adaptive hiring pipeline (Phase 2 & 6).
        """
        # 1. Greedy Optimization for Coverage vs Fatigue (Phase 2)
        selected_ids = self._optimize_selection(ranked_assessments, context)
        
        # 2. Adaptive Stage Distribution (Phase 6)
        stages = self._distribute_stages(selected_ids, catalog, context)
        
        # 3. Intelligence Analysis (Phase 3 & 4)
        fatigue = self.fatigue_engine.calculate_fatigue(selected_ids, catalog)
        signal = self.signal_engine.estimate_signal(selected_ids, catalog)
        
        # 4. Tradeoff Analysis (Phase 5)
        tradeoff = self._analyze_tradeoffs(fatigue, signal, context)
        
        # 5. Strategic Advice (Phase 10)
        advice = self._generate_strategic_advice(signal, fatigue, context)
        
        return OptimizedPipeline(
            stages=stages,
            fatigue_report=fatigue,
            signal_report=signal,
            tradeoff_analysis=tradeoff,
            strategic_advice=advice
        )

    def _optimize_selection(self, ranked: List[Any], context: HiringContext) -> List[str]:
        """Greedy optimization to maximize coverage and minimize redundancy/fatigue."""
        selected = []
        covered_skills = set()
        total_time = 0
        limit_time = 180 if context.workflow_mode == "quick_screening" else 300
        
        for res in ranked:
            assess = res.assessment
            duration = getattr(assess, "duration_minutes", 30)
            
            if total_time + duration > limit_time: continue
            
            # Competency overlap check (Redundancy Suppression)
            assess_skills = set(assess.skills) | set(getattr(assess, "inferred_skills", []))
            overlap = len(assess_skills.intersection(covered_skills))
            
            if overlap > 5: continue # Too redundant
            
            selected.append(assess.id)
            covered_skills.update(assess_skills)
            total_time += duration
            
            if len(selected) >= 5: break
            
        return selected

    def _distribute_stages(self, ids: List[str], catalog: Dict[str, Any], context: HiringContext) -> List[Dict[str, Any]]:
        stages = []
        
        # Simplified adaptive stage logic
        for idx, aid in enumerate(ids):
            assess = catalog.get(aid)
            if not assess: continue
            
            # Group into stages based on type/order
            stage_name = "Initial Screening" if idx == 0 else "Technical Deep Dive" if assess.test_type.value == "K" else "Behavioral Fit"
            
            stages.append({
                "name": stage_name,
                "assessments": [assess.name],
                "duration": getattr(assess, "duration_minutes", 30),
                "type": assess.test_type.value
            })
            
        return stages

    def _analyze_tradeoffs(self, fatigue: Dict, signal: Dict, context: HiringContext) -> str:
        if fatigue["fatigue_score"] > 0.6 and signal["signal_score"] > 0.7:
            return "High rigor vs High fatigue: This pipeline provides maximum validation but carries a dropout risk of 30%."
        if fatigue["fatigue_score"] < 0.3 and signal["signal_score"] < 0.4:
            return "Speed vs Coverage: Fast screening with minimal burden, but technical depth is limited."
        return "Balanced approach: Moderate duration with good cross-domain coverage."

    def _generate_strategic_advice(self, signal: Dict, fatigue: Dict, context: HiringContext) -> str:
        advice = []
        if signal["coverage"]["leadership"] < 0.3 and context.leadership_needs:
            advice.append("⚠️ Strategic risk: Current pipeline lacks leadership signal.")
        if fatigue["risk_level"] == "HIGH":
            advice.append("💡 Tip: Consider splitting the technical evaluations to reduce candidate dropout.")
        if not advice:
            advice.append("✅ Strategy aligned: Pipeline matches enterprise standards for this role.")
            
        return " ".join(advice)
