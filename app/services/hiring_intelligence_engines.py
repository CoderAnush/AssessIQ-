"""
Hiring Intelligence Engines: Fatigue and Signal Quality.
Models candidate burden and validation confidence.
"""

from typing import List, Dict, Any, Optional
from app.models.assessment import AssessmentWithMetadata

class FatigueEngine:
    """
    Models candidate fatigue risk and dropout probability.
    """
    
    def calculate_fatigue(self, assessment_ids: List[str], catalog: Dict[str, Any]) -> Dict[str, Any]:
        total_duration = 0
        cognitive_load = 0.0
        type_counts = {}
        
        for aid in assessment_ids:
            assess = catalog.get(aid)
            if not assess: continue
            
            duration = getattr(assess, "duration_minutes", 30)
            total_duration += duration
            
            # Type weighting for cognitive load
            t_type = assess.test_type.value
            type_counts[t_type] = type_counts.get(t_type, 0) + 1
            
            if t_type == "A": cognitive_load += 0.8
            elif t_type == "K": cognitive_load += 0.6
            else: cognitive_load += 0.3
            
        # Fatigue Score Logic (0.0 to 1.0)
        # 120 mins = 0.5 fatigue
        # 240 mins = 1.0 fatigue
        duration_factor = min(1.0, total_duration / 240.0)
        
        # Repetitive burden
        max_repeats = max(type_counts.values()) if type_counts else 0
        repetition_factor = min(1.0, max_repeats / 4.0)
        
        overall_score = (duration_factor * 0.7) + (repetition_factor * 0.3)
        
        risk_level = "LOW"
        if overall_score > 0.7: risk_level = "HIGH"
        elif overall_score > 0.4: risk_level = "MODERATE"
        
        return {
            "fatigue_score": round(overall_score, 2),
            "risk_level": risk_level,
            "total_duration": total_duration,
            "cognitive_overload": round(cognitive_load / max(1, len(assessment_ids)), 2),
            "dropout_probability": round(overall_score * 0.5, 2)
        }

class SignalEngine:
    """
    Estimates hiring signal quality and validation confidence.
    """
    
    def estimate_signal(self, assessment_ids: List[str], catalog: Dict[str, Any]) -> Dict[str, Any]:
        coverage = {"technical": 0.0, "behavioral": 0.0, "leadership": 0.0, "cognitive": 0.0}
        
        for aid in assessment_ids:
            assess = catalog.get(aid)
            if not assess: continue
            
            t_type = assess.test_type.value
            if t_type == "K": coverage["technical"] += 0.4
            elif t_type == "P": coverage["behavioral"] += 0.4
            elif t_type == "A": coverage["cognitive"] += 0.5
            
            if getattr(assess, "leadership_focus", False): coverage["leadership"] += 0.5
            
        # Normalize and cap
        for k in coverage:
            coverage[k] = min(1.0, coverage[k])
            
        overall_signal = sum(coverage.values()) / 4.0
        
        confidence_mapping = {
            "technical": "High" if coverage["technical"] > 0.7 else "Moderate" if coverage["technical"] > 0.3 else "Low",
            "behavioral": "High" if coverage["behavioral"] > 0.7 else "Moderate" if coverage["behavioral"] > 0.3 else "Low",
            "leadership": "High" if coverage["leadership"] > 0.7 else "Moderate" if coverage["leadership"] > 0.3 else "Low",
            "cognitive": "High" if coverage["cognitive"] > 0.7 else "Moderate" if coverage["cognitive"] > 0.3 else "Low",
        }
        
        return {
            "signal_score": round(overall_signal, 2),
            "coverage": coverage,
            "confidence_levels": confidence_mapping
        }
