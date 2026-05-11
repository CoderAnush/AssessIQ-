"""
Hiring Pipeline Orchestrator.
Generates multi-stage assessment pipelines from ranked results.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from app.models.assessment import AssessmentWithMetadata
from app.services.competency_engine import CompetencyEngine
from app.services.conversation_analyzer import HiringContext

@dataclass
class PipelineStage:
    name: str
    description: str
    assessments: List[Dict[str, Any]] = field(default_factory=list)
    estimated_duration: int = 0
    competencies_covered: List[str] = field(default_factory=list)

@dataclass
class HiringPipeline:
    stages: List[PipelineStage] = field(default_factory=list)
    total_duration: int = 0
    competency_coverage: Dict[str, float] = field(default_factory=dict)
    gaps: List[str] = field(default_factory=list)
    strategic_guidance: str = ""

class PipelineOrchestrator:
    """
    Orchestrates multi-stage hiring evaluations.
    """
    
    def __init__(self, competency_engine: Optional[CompetencyEngine] = None):
        self.competency_engine = competency_engine or CompetencyEngine()

    def generate_pipeline(self, ranked_assessments: List[Any], context: HiringContext) -> HiringPipeline:
        """
        Generate a multi-stage pipeline from ranked assessments.
        """
        pipeline = HiringPipeline()
        
        # 1. Define Stages based on role and mode
        stages = self._define_stages(context)
        
        # 2. Assign assessments to stages based on type and competencies
        used_ids = set()
        for stage in stages:
            for res in ranked_assessments:
                assess = res.assessment
                if assess.id in used_ids: continue
                
                # Logic to match assessment to stage
                if self._matches_stage(assess, stage.name):
                    # Check for redundancy (Phase 7)
                    if self._is_redundant(assess, stage.assessments):
                        continue
                        
                    comp_scores = self.competency_engine.map_assessment(assess)
                    
                    stage.assessments.append({
                        "id": assess.id,
                        "name": assess.name,
                        "url": assess.url,
                        "test_type": assess.test_type.value,
                        "competencies": list(comp_scores.keys())
                    })
                    stage.estimated_duration += getattr(assess, "duration_minutes", 30)
                    stage.competencies_covered.extend(list(comp_scores.keys()))
                    used_ids.add(assess.id)
                    
                    # Limit assessments per stage to avoid fatigue (Phase 4)
                    if len(stage.assessments) >= 2: break
            
            pipeline.stages.append(stage)
            pipeline.total_duration += stage.estimated_duration

        # 3. Calculate Global Coverage & Gaps
        all_comp_scores = []
        for stage in pipeline.stages:
            for assess_dict in stage.assessments:
                # Mocking scores for coverage calculation
                all_comp_scores.append({c: 0.8 for c in assess_dict["competencies"]})
        
        pipeline.competency_coverage = self.competency_engine.get_cluster_coverage(all_comp_scores)
        
        role_type = "technical" if "backend" in (context.role or "").lower() or "frontend" in (context.role or "").lower() else "general"
        if context.leadership_needs: role_type = "management"
        
        pipeline.gaps = self.competency_engine.identify_gaps(pipeline.competency_coverage, role_type)
        
        # 4. Strategic Guidance (Phase 9)
        pipeline.strategic_guidance = self._generate_guidance(pipeline, context)
        
        return pipeline

    def _define_stages(self, context: HiringContext) -> List[PipelineStage]:
        mode = context.workflow_mode
        if mode == "quick_screening":
            return [
                PipelineStage("Initial Screening", "Fast assessment of core aptitude and communication."),
                PipelineStage("Technical/Role Fit", "Evaluation of essential technical or domain skills.")
            ]
        elif mode == "technical_deep_dive":
            return [
                PipelineStage("Screening", "Quick cognitive and language check."),
                PipelineStage("Core Technical", "Deep dive into language and frameworks."),
                PipelineStage("System & Architecture", "Evaluation of senior-level technical reasoning.")
            ]
        elif mode == "leadership_hiring":
            return [
                PipelineStage("Behavioral Screening", "Personality and work-style evaluation."),
                PipelineStage("Leadership & Strategy", "Management readiness and strategic thinking."),
                PipelineStage("Final Fit", "Comprehensive behavioral and communication assessment.")
            ]
        else:
            # Default Balanced Pipeline
            return [
                PipelineStage("Stage 1: Screening", "Aptitude and basic skills."),
                PipelineStage("Stage 2: Technical", "Core role requirements."),
                PipelineStage("Stage 3: Behavioral", "Team fit and soft skills.")
            ]

    def _matches_stage(self, assess: AssessmentWithMetadata, stage_name: str) -> bool:
        name = stage_name.lower()
        t_type = assess.test_type.value
        
        if "screening" in name:
            return t_type in ["A", "P"] or any(kw in assess.name.lower() for kw in ["aptitude", "basic", "screening"])
        if "technical" in name or "core" in name:
            return t_type == "K" or "coding" in assess.name.lower()
        if "behavioral" in name or "fit" in name or "leadership" in name:
            return t_type == "P" or assess.leadership_focus or assess.communication_focus
            
        return True

    def _is_redundant(self, assess: AssessmentWithMetadata, existing: List[Dict]) -> bool:
        # Phase 7: Redundancy detection
        if not existing: return False
        
        current_skills = set(assess.skills)
        for other in existing:
            # Simple overlap check (could be improved with competency scores)
            other_skills = set(other.get("competencies", []))
            overlap = len(current_skills.intersection(other_skills))
            if overlap >= 3: return True
            
        return False

    def _generate_guidance(self, pipeline: HiringPipeline, context: HiringContext) -> str:
        if pipeline.gaps:
            clusters = ", ".join(pipeline.gaps)
            return f"Your current pipeline has gaps in: {clusters}. For a {context.seniority or 'mid'}-level {context.role}, adding a behavioral or leadership component is recommended to ensure long-term fit."
        return f"This pipeline provides comprehensive coverage for the {context.role} role, balancing technical rigor with cognitive ability."
