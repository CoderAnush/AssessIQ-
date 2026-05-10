"""
Evaluation metrics and analytics for system optimization.
Tracks performance against evaluator scoring criteria.
"""

import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConversationMetrics:
    """Metrics for a single conversation."""

    conversation_id: str
    timestamp: str
    total_turns: int
    total_messages: int

    # Retrieval metrics
    retrieval_attempts: int
    retrieval_confidence_avg: float  # 0-1
    retrieval_precision: float  # % of recommendations used by evaluator

    # Recommendation metrics
    recommendations_count: int
    recommendations_quality_score: float  # 0-1
    hallucination_detected: int  # count of hallucinations
    schema_violations: int  # count

    # Clarification metrics
    clarification_turns: int
    clarification_efficiency: float  # (useful info gained) / (turns spent)

    # Refinement metrics
    refinement_turns: int
    refinement_success_rate: float  # % of refinements that improved ranking

    # Response quality
    avg_response_latency_ms: float
    avg_explanation_quality: float  # 0-1 (how clear/actionable)

    # Evaluator satisfaction (if available)
    evaluator_score: Optional[float] = None  # 0-100
    evaluator_feedback: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dict for storage."""
        return asdict(self)


class EvaluationAnalytics:
    """Tracks and analyzes system performance."""

    def __init__(self):
        """Initialize analytics."""
        self.conversations: List[ConversationMetrics] = []
        self.metrics_log_path = "logs/evaluation_metrics.jsonl"

    def start_conversation(self, conversation_id: str) -> None:
        """Mark conversation start."""
        logger.info(f"Started conversation: {conversation_id}")

    def log_retrieval_event(
        self,
        conversation_id: str,
        confidence: float,
        retrieved_count: int,
        precision: float,
    ) -> None:
        """Log retrieval event."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "retrieval",
            "conversation_id": conversation_id,
            "confidence": confidence,
            "retrieved_count": retrieved_count,
            "precision": precision,
        }

        self._log_metric(event)

    def log_recommendation_event(
        self,
        conversation_id: str,
        count: int,
        quality_score: float,
        hallucination_count: int = 0,
    ) -> None:
        """Log recommendation event."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "recommendation",
            "conversation_id": conversation_id,
            "recommendation_count": count,
            "quality_score": quality_score,
            "hallucinations": hallucination_count,
        }

        self._log_metric(event)

    def log_clarification_event(
        self,
        conversation_id: str,
        question: str,
        efficiency_score: float,
    ) -> None:
        """Log clarification question event."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "clarification",
            "conversation_id": conversation_id,
            "question_preview": question[:100],
            "efficiency_score": efficiency_score,
        }

        self._log_metric(event)

    def log_refinement_event(
        self,
        conversation_id: str,
        refinement_type: str,
        success: bool,
    ) -> None:
        """Log refinement event."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "refinement",
            "conversation_id": conversation_id,
            "refinement_type": refinement_type,
            "success": success,
        }

        self._log_metric(event)

    def log_hallucination_event(
        self,
        conversation_id: str,
        hallucination_type: str,
        details: str,
    ) -> None:
        """Log hallucination detection."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "hallucination_detected",
            "conversation_id": conversation_id,
            "type": hallucination_type,
            "details": details,
        }

        self._log_metric(event)

    def _log_metric(self, event: Dict) -> None:
        """Log metric event to file."""
        try:
            with open(self.metrics_log_path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error(f"Error logging metric: {e}")

    def get_summary_statistics(self) -> Dict:
        """Get summary statistics from logged events."""

        try:
            events = []

            with open(self.metrics_log_path, "r") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))

            if not events:
                return {"conversations": 0, "total_events": 0}

            # Group by conversation
            conversations = {}
            for event in events:
                conv_id = event.get("conversation_id", "unknown")
                if conv_id not in conversations:
                    conversations[conv_id] = {"events": [], "types": {}}

                conversations[conv_id]["events"].append(event)
                event_type = event.get("event_type", "unknown")
                conversations[conv_id]["types"][event_type] = (
                    conversations[conv_id]["types"].get(event_type, 0) + 1
                )

            # Calculate statistics
            stats = {
                "total_conversations": len(conversations),
                "total_events": len(events),
                "event_types": {},
                "hallucinations_detected": sum(
                    1 for e in events if e.get("event_type") == "hallucination_detected"
                ),
                "avg_retrieval_confidence": self._calc_avg_confidence(events),
                "avg_recommendation_quality": self._calc_avg_quality(events),
                "conversation_lengths": {
                    "avg": sum(
                        len(c["events"]) for c in conversations.values()
                    ) / len(conversations) if conversations else 0,
                    "min": min(
                        (len(c["events"]) for c in conversations.values()), default=0
                    ),
                    "max": max(
                        (len(c["events"]) for c in conversations.values()), default=0
                    ),
                },
            }

            # Event type counts
            for event_type in set(e.get("event_type") for e in events):
                count = sum(1 for e in events if e.get("event_type") == event_type)
                stats["event_types"][event_type] = count

            return stats

        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {"error": str(e)}

    @staticmethod
    def _calc_avg_confidence(events: List[Dict]) -> float:
        """Calculate average retrieval confidence."""
        retrieval_events = [e for e in events if e.get("event_type") == "retrieval"]

        if not retrieval_events:
            return 0.0

        total = sum(e.get("confidence", 0) for e in retrieval_events)
        return total / len(retrieval_events)

    @staticmethod
    def _calc_avg_quality(events: List[Dict]) -> float:
        """Calculate average recommendation quality."""
        recommendation_events = [
            e for e in events if e.get("event_type") == "recommendation"
        ]

        if not recommendation_events:
            return 0.0

        total = sum(e.get("quality_score", 0) for e in recommendation_events)
        return total / len(recommendation_events)

    def get_evaluator_summary(self) -> str:
        """Get summary for evaluator optimization."""

        stats = self.get_summary_statistics()

        if "error" in stats:
            return "No metrics available yet."

        summary = f"""
EVALUATION ANALYTICS SUMMARY
============================

Conversations: {stats.get('total_conversations', 0)}
Total Events: {stats.get('total_events', 0)}

Retrieval Performance:
  Average Confidence: {stats.get('avg_retrieval_confidence', 0):.2%}
  Retrieval Events: {stats.get('event_types', {}).get('retrieval', 0)}

Recommendation Quality:
  Average Quality Score: {stats.get('avg_recommendation_quality', 0):.2f}/1.0
  Hallucinations Detected: {stats.get('hallucinations_detected', 0)}

Conversation Efficiency:
  Average Turns: {stats.get('conversation_lengths', {}).get('avg', 0):.1f}
  Min Turns: {stats.get('conversation_lengths', {}).get('min', 0)}
  Max Turns: {stats.get('conversation_lengths', {}).get('max', 0)}

Event Breakdown:
"""

        for event_type, count in stats.get("event_types", {}).items():
            summary += f"  {event_type}: {count}\n"

        return summary
