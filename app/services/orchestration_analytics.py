"""
Orchestration Analytics and Training Data Foundation.
Logs recruiter interactions to prepare for future ML-driven orchestration.
"""

import json
import os
import time
from typing import Dict, Any, List
from pathlib import Path

LOG_DIR = Path("data/logs/orchestration")

class OrchestrationAnalytics:
    """
    Tracks recruiter behavior and generates training data for ML orchestration.
    """
    
    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def log_interaction(self, session_id: str, action: str, data: Dict[str, Any]):
        """Log a recruiter action with metadata."""
        log_entry = {
            "timestamp": time.time(),
            "session_id": session_id,
            "action": action,
            "data": data
        }
        
        log_file = LOG_DIR / f"session_{session_id}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Generate a summary of recruiter behavior in a session."""
        log_file = LOG_DIR / f"session_{session_id}.jsonl"
        if not log_file.exists(): return {}
        
        actions = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                actions.append(json.loads(line))
                
        return {
            "total_actions": len(actions),
            "selected_assessments": [a["data"]["id"] for a in actions if a["action"] == "select"],
            "last_action_time": actions[-1]["timestamp"] if actions else 0
        }

    def generate_training_dataset(self) -> str:
        """Consolidates logs into a structured JSON dataset for future ML."""
        dataset = []
        for log_file in LOG_DIR.glob("*.jsonl"):
            with open(log_file, "r", encoding="utf-8") as f:
                session_data = [json.loads(line) for line in f]
                dataset.append({
                    "session_id": log_file.stem.split("_")[1],
                    "interactions": session_data
                })
        
        output_file = LOG_DIR / "orchestration_training_data_v1.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2)
            
        return str(output_file)
