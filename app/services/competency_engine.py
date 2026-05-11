"""
Competency Mapping Engine for Hiring Orchestration.
Maps skills, traits, and assessments to core hiring competencies.
"""

from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field
from app.models.assessment import AssessmentWithMetadata

@dataclass
class Competency:
    name: str
    description: str
    cluster: str # technical, behavioral, cognitive, leadership
    related_skills: Set[str] = field(default_factory=set)
    weight: float = 1.0

class CompetencyEngine:
    """
    Engine for mapping recruiter needs to high-level competencies.
    """
    
    def __init__(self):
        self.competencies: Dict[str, Competency] = {}
        self._initialize_competencies()

    def _initialize_competencies(self):
        # Technical Cluster
        self._add_competency("Programming Proficiency", "Core coding skills and language knowledge.", "technical", 
                            {"python", "java", "javascript", "c#", "c++", "go", "coding", "programming"})
        self._add_competency("System Architecture", "Design and scalability of complex systems.", "technical", 
                            {"architecture", "distributed systems", "microservices", "system design", "cloud architecture"})
        self._add_competency("Technical Depth", "Deep knowledge of frameworks and tools.", "technical", 
                            {"django", "spring", "react", "fastapi", "aws", "kubernetes", "database"})
        self._add_competency("Quality Assurance", "Testing and reliability skills.", "technical", 
                            {"testing", "qa", "automation", "selenium", "cypress", "unit test", "regression"})

        # Behavioral Cluster
        self._add_competency("Communication", "Clarity and effectiveness of information exchange.", "behavioral", 
                            {"communication", "writing", "presentation", "verbal", "influence"})
        self._add_competency("Collaboration", "Working effectively in teams.", "behavioral", 
                            {"teamwork", "collaboration", "empathy", "relationship", "stakeholder"})
        self._add_competency("Problem Solving", "Analytical thinking and complexity management.", "behavioral", 
                            {"problem solving", "judgment", "logic", "reasoning", "critical thinking"})

        # Leadership Cluster
        self._add_competency("People Management", "Leading and developing individuals.", "leadership", 
                            {"management", "mentoring", "coaching", "talent", "leadership"})
        self._add_competency("Strategic Thinking", "Long-term planning and business alignment.", "leadership", 
                            {"strategy", "planning", "vision", "executive", "business alignment"})

        # Cognitive Cluster
        self._add_competency("Cognitive Ability", "General mental ability and learning speed.", "cognitive", 
                            {"aptitude", "intelligence", "logic", "reasoning", "cognitive", "learning agility"})

    def _add_competency(self, name: str, desc: str, cluster: str, skills: Set[str]):
        self.competencies[name.lower()] = Competency(name=name, description=desc, cluster=cluster, related_skills=skills)

    def map_assessment(self, assess: AssessmentWithMetadata) -> Dict[str, float]:
        """Map an assessment to competencies based on its metadata."""
        scores = {}
        combined_text = (assess.name + " " + assess.description).lower()
        skills = set(s.lower() for s in getattr(assess, "inferred_skills", []))
        skills.update(s.lower() for s in assess.skills)

        for comp_name, comp in self.competencies.items():
            # Calculate match score
            skill_match = len(comp.related_skills.intersection(skills))
            keyword_match = sum(1 for kw in comp.related_skills if kw in combined_text)
            
            score = (skill_match * 0.3) + (keyword_match * 0.1)
            
            # Type-based overrides
            if comp.cluster == "technical" and assess.test_type.value == "K": score += 0.4
            if comp.cluster == "cognitive" and assess.test_type.value == "A": score += 0.5
            if comp.cluster == "behavioral" and assess.test_type.value == "P": score += 0.4
            if comp.cluster == "leadership" and assess.leadership_focus: score += 0.5

            if score > 0.2:
                scores[comp.name] = min(1.0, score)
                
        return scores

    def get_cluster_coverage(self, assessment_scores: List[Dict[str, float]]) -> Dict[str, float]:
        """Calculate coverage across competency clusters."""
        coverage = {"technical": 0.0, "behavioral": 0.0, "leadership": 0.0, "cognitive": 0.0}
        
        for scores in assessment_scores:
            for comp_name, score in scores.items():
                comp = self.competencies.get(comp_name.lower())
                if comp:
                    coverage[comp.cluster] = max(coverage[comp.cluster], score)
                    
        return coverage

    def identify_gaps(self, coverage: Dict[str, float], role_type: str) -> List[str]:
        """Identify missing competencies based on role expectations."""
        gaps = []
        threshold = 0.5
        
        expectations = {
            "technical": ["technical", "cognitive"],
            "management": ["leadership", "behavioral", "cognitive"],
            "sales": ["behavioral", "cognitive"],
            "general": ["cognitive", "behavioral"]
        }
        
        required = expectations.get(role_type.lower(), expectations["general"])
        for cluster in required:
            if coverage.get(cluster, 0.0) < threshold:
                gaps.append(cluster)
                
        return gaps
