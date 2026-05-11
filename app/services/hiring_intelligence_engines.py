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
            
            t_type = str(getattr(assess.test_type, "value", assess.test_type))
            type_counts[t_type] = type_counts.get(t_type, 0) + 1
            
            if t_type == "A": cognitive_load += 0.8
            elif t_type == "K": cognitive_load += 0.6
            else: cognitive_load += 0.3
            
        duration_factor = min(1.0, total_duration / 240.0)
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
            
            t_type = str(getattr(assess.test_type, "value", assess.test_type))
            if t_type == "K": coverage["technical"] += 0.4
            elif t_type == "P": coverage["behavioral"] += 0.4
            elif t_type == "A": coverage["cognitive"] += 0.5
            
            if getattr(assess, "leadership_focus", False): coverage["leadership"] += 0.5
            
        for k in coverage:
            coverage[k] = min(1.0, coverage[k])
            
        # Hardening: Overall signal should be weighted by active clusters
        active_clusters = [v for v in coverage.values() if v > 0]
        if active_clusters:
            overall_signal = sum(active_clusters) / len(active_clusters)
            # Boost if multiple clusters covered
            if len(active_clusters) > 1: overall_signal = min(1.0, overall_signal * 1.1)
        else:
            overall_signal = 0.0
        
        confidence_mapping = {k: ("High" if v > 0.7 else "Moderate" if v > 0.3 else "Low") for k, v in coverage.items()}
        
        return {
            "signal_score": round(overall_signal, 2),
            "coverage": coverage,
            "confidence_levels": confidence_mapping
        }
