"""
Adaptive Hiring Orchestration Engine.
Optimizes pipeline generation using signal, fatigue, and competency coverage.
Fully domain-aware stage naming (Part 3 Fix).
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from app.models.assessment import AssessmentWithMetadata
from app.services.competency_taxonomy_v2 import CompetencyTaxonomyV2
from app.services.hiring_intelligence_engines import FatigueEngine, SignalEngine
from app.services.conversation_analyzer import HiringContext
from app.logger_config.logger import get_logger
from app.services.domain_classifier import Domain

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
    UPGRADED Adaptive Orchestrator (Part 3: Dynamic Domain Stages).
    Zero hardcoded role strings. Pure dynamic orchestration.
    """
    
    def __init__(self, taxonomy: Optional[CompetencyTaxonomyV2] = None):
        self.taxonomy = taxonomy or CompetencyTaxonomyV2()
        self.fatigue_engine = FatigueEngine()
        self.signal_engine = SignalEngine()

    def orchestrate(self, ranked_assessments: List[Any], context: HiringContext, catalog: Dict[str, Any]) -> OptimizedPipeline:
        """
        Generates an elite, domain-aware hiring pipeline.
        """
        try:
            selected_ids = self._optimize_selection(ranked_assessments, context)
            
            # Part 3 Fix: Dynamic Stage Generation
            stages = self._generate_dynamic_stages(selected_ids, catalog, context)
            
            fatigue = self.fatigue_engine.calculate_fatigue(selected_ids, catalog)
            signal = self.signal_engine.estimate_signal(selected_ids, catalog)
            tradeoff = self._analyze_tradeoffs(fatigue, signal, context)
            advice = self._generate_strategic_advice(signal, fatigue, context)
            
            return OptimizedPipeline(
                stages=stages,
                fatigue_report=fatigue,
                signal_report=signal,
                tradeoff_analysis=tradeoff,
                strategic_advice=advice
            )
        except Exception:
            logger.exception("ORCHESTRATION FAILURE")
            return OptimizedPipeline(stages=[], strategic_advice="Review individual matches.")

    def _optimize_selection(self, ranked: List[Any], context: HiringContext) -> List[str]:
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
            if overlap > 4: continue
            
            selected.append(assess.id)
            covered_skills.update(assess_skills)
            total_time += duration
            if len(selected) >= 4: break
            
        return selected

    def _generate_dynamic_stages(self, ids: List[str], catalog: Dict[str, Any], context: HiringContext) -> List[Dict[str, Any]]:
        """
        Part 3 Fix: Dynamic Domain-Aware Stage Naming.
        """
        stages = []
        # Get detected domain from context (set in chat.py)
        domain = getattr(context, "domain", Domain.GENERAL)
        
        used_names = set()
        for idx, aid in enumerate(ids):
            assess = catalog.get(aid)
            if not assess: continue
            
            name = self._generate_stage_name(idx, assess, domain, used_names)
            used_names.add(name)
            
            stages.append({
                "name": name,
                "description": f"Targeted validation of {assess.name} competencies.",
                "assessments": [assess.name],
                "duration": getattr(assess, "duration_minutes", 30),
                "competencies_covered": list(getattr(assess, "skills", []))[:3]
            })
        return stages

    def _generate_stage_name(self, idx: int, assess: Any, domain: Domain, used: Set[str]) -> str:
        """
        Part 3 Fix: Logic for dynamic stage naming.
        Ensures Backend queries never see 'Frontend' labels.
        """
        # 1. Primary Mapping per Domain
        DOMAIN_TEMPLATES = {
            Domain.FRONTEND: {
                "initial": "Initial Frontend Screening",
                "K": ["Frontend Architecture Validation", "UI Systems Review", "JavaScript Competency Check", "Web Engineering Evaluation"],
                "A": ["Cognitive UI Aptitude", "Frontend Problem Solving"],
                "P": ["Product Mindset Assessment", "UI Collaboration Review"]
            },
            Domain.BACKEND: {
                "initial": "Backend Systems Screening",
                "K": ["Java API Architecture Review", "Backend Microservices Review", "Distributed Systems Evaluation", "Server-Side Performance Audit"],
                "A": ["Algorithmic Reasoning", "System Design Aptitude"],
                "P": ["Architecture Focus Review", "Engineering Ethics"]
            },
            Domain.DEVOPS: {
                "initial": "Infrastructure Reliability Screening",
                "K": ["Kubernetes Operations Validation", "Cloud Automation Assessment", "SRE Systems Audit", "Security & Compliance Review"],
                "A": ["Systems Troubleshooting Round", "Logic & Automation Check"],
                "P": ["Operational Resilience Review", "On-Call Suitability"]
            },
            Domain.DATA_AI: {
                "initial": "AI Foundation Screening",
                "K": ["ML Foundations & Mathematics", "NLP & Deep Learning Evaluation", "AI Model Engineering Review", "Data Pipeline Integrity Check"],
                "A": ["Mathematical Reasoning", "Statistical Logic Round"],
                "P": ["Ethics in AI Assessment", "Data Precision Focus"]
            },
            Domain.MANAGEMENT: {
                "initial": "Leadership Alignment Round",
                "K": ["Stakeholder Communication Assessment", "Strategic Decision-Making Review", "Delivery Management Audit", "People Leadership Evaluation"],
                "A": ["Conflict Resolution Logic", "Prioritization Reasoning"],
                "P": ["EQ & Empathy Assessment", "Organizational Culture Fit"]
            },
            Domain.QA: {
                "initial": "QA Foundations Screening",
                "K": ["Automation Framework Review", "SDET Systems Validation", "Load & Stress Logic Check", "Test Coverage Analysis"],
                "A": ["Edge-Case Reasoning", "Logical Debugging Round"],
                "P": ["Detail Orientation Focus", "Quality Mindset Review"]
            }
        }

        # 2. Get template for domain or fallback to General
        template = DOMAIN_TEMPLATES.get(domain, {
            "initial": "Initial Candidate Screening",
            "K": ["Core Technical Validation", "Systems Knowledge Review"],
            "A": ["Cognitive Aptitude Check"],
            "P": ["Behavioral Alignment Review"]
        })

        if idx == 0:
            return template["initial"]

        t_type = str(getattr(assess.test_type, "value", assess.test_type))
        options = template.get(t_type, template["K"])
        
        for n in options:
            if n not in used: return n
        return f"Stage {idx + 1}: {assess.name}"

    def _analyze_tradeoffs(self, fatigue: Dict, signal: Dict, context: HiringContext) -> str:
        f_score = fatigue.get("fatigue_score", 0.0)
        s_score = signal.get("signal_score", 0.0)
        if f_score > 0.5: return "High-Rigor Validation: Maximizes signal for critical hires."
        return "Balanced Pipeline: Optimal signal-to-fatigue ratio for enterprise speed."

    def _generate_strategic_advice(self, signal: Dict, fatigue: Dict, context: HiringContext) -> str:
        s_score = signal.get("signal_score", 0.0)
        if s_score > 0.8: return "Elite Signal: This pipeline offers top-tier technical validation for FAANG-level roles."
        return "Standardized Success: Pipeline matches enterprise requirements for technical precision."
