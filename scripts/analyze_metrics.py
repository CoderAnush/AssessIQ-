#!/usr/bin/env python3
"""
Analytics dashboard generator - creates reports from evaluation metrics.
Tracks performance over time and identifies optimization opportunities.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import numpy as np


class MetricsAnalyzer:
    """Analyzes evaluation metrics and generates insights."""

    def __init__(self, metrics_file: str = "logs/evaluation_metrics.jsonl"):
        self.metrics_file = metrics_file
        self.events = self._load_events()

    def _load_events(self) -> List[Dict]:
        """Load all metrics events from JSONL file."""
        events = []
        try:
            with open(self.metrics_file, "r") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        except FileNotFoundError:
            pass
        return events

    def get_retrieval_metrics(self) -> Dict:
        """Analyze retrieval performance."""
        retrieval_events = [e for e in self.events if e.get("event_type") == "retrieval"]

        if not retrieval_events:
            return {"error": "No retrieval events found"}

        confidences = [e.get("confidence", 0) for e in retrieval_events]
        precisions = [e.get("precision", 0) for e in retrieval_events]

        return {
            "total_retrievals": len(retrieval_events),
            "avg_confidence": np.mean(confidences),
            "median_confidence": np.median(confidences),
            "min_confidence": np.min(confidences),
            "max_confidence": np.max(confidences),
            "std_confidence": np.std(confidences),
            "avg_precision": np.mean(precisions),
            "median_precision": np.median(precisions),
        }

    def get_recommendation_metrics(self) -> Dict:
        """Analyze recommendation quality."""
        rec_events = [e for e in self.events if e.get("event_type") == "recommendation"]

        if not rec_events:
            return {"error": "No recommendation events found"}

        quality_scores = [e.get("quality_score", 0) for e in rec_events]
        rec_counts = [e.get("recommendation_count", 0) for e in rec_events]
        hallucinations = [e.get("hallucinations", 0) for e in rec_events]

        total_hallucinations = sum(hallucinations)

        return {
            "total_recommendations": len(rec_events),
            "avg_quality_score": np.mean(quality_scores),
            "median_quality_score": np.median(quality_scores),
            "min_quality_score": np.min(quality_scores),
            "max_quality_score": np.max(quality_scores),
            "avg_rec_count": np.mean(rec_counts),
            "median_rec_count": np.median(rec_counts),
            "total_hallucinations": total_hallucinations,
            "hallucination_rate": total_hallucinations / len(rec_events) if rec_events else 0,
        }

    def get_clarification_metrics(self) -> Dict:
        """Analyze clarification efficiency."""
        clarif_events = [e for e in self.events if e.get("event_type") == "clarification"]

        if not clarif_events:
            return {"error": "No clarification events found"}

        efficiency_scores = [e.get("efficiency_score", 0) for e in clarif_events]

        return {
            "total_clarifications": len(clarif_events),
            "avg_efficiency": np.mean(efficiency_scores),
            "median_efficiency": np.median(efficiency_scores),
            "min_efficiency": np.min(efficiency_scores),
            "max_efficiency": np.max(efficiency_scores),
        }

    def get_refinement_metrics(self) -> Dict:
        """Analyze refinement success rate."""
        refine_events = [e for e in self.events if e.get("event_type") == "refinement"]

        if not refine_events:
            return {"error": "No refinement events found"}

        successes = sum(1 for e in refine_events if e.get("success", False))

        # Group by refinement type
        by_type = {}
        for event in refine_events:
            rtype = event.get("refinement_type", "unknown")
            if rtype not in by_type:
                by_type[rtype] = {"total": 0, "successful": 0}
            by_type[rtype]["total"] += 1
            if event.get("success", False):
                by_type[rtype]["successful"] += 1

        return {
            "total_refinements": len(refine_events),
            "successful_refinements": successes,
            "success_rate": successes / len(refine_events) if refine_events else 0,
            "by_type": by_type,
        }

    def get_conversation_metrics(self) -> Dict:
        """Analyze conversation patterns."""
        conversation_ids = set(e.get("conversation_id") for e in self.events)

        if not conversation_ids:
            return {"error": "No conversations found"}

        conv_lengths = {}
        for conv_id in conversation_ids:
            conv_events = [e for e in self.events if e.get("conversation_id") == conv_id]
            conv_lengths[conv_id] = len(conv_events)

        lengths = list(conv_lengths.values())

        return {
            "total_conversations": len(conversation_ids),
            "avg_conversation_length": np.mean(lengths),
            "median_conversation_length": np.median(lengths),
            "min_conversation_length": np.min(lengths),
            "max_conversation_length": np.max(lengths),
            "total_events": len(self.events),
        }

    def get_hallucination_metrics(self) -> Dict:
        """Analyze hallucination detection."""
        halluc_events = [e for e in self.events if e.get("event_type") == "hallucination_detected"]

        if not halluc_events:
            return {"total_hallucinations_detected": 0, "hallucination_types": {}}

        by_type = {}
        for event in halluc_events:
            htype = event.get("type", "unknown")
            by_type[htype] = by_type.get(htype, 0) + 1

        return {
            "total_hallucinations_detected": len(halluc_events),
            "hallucination_types": by_type,
        }

    def generate_summary_report(self) -> str:
        """Generate comprehensive metrics summary report."""
        report = f"""
╔════════════════════════════════════════════════════════════════════╗
║           ASSESSIQ ANALYTICS & METRICS REPORT                      ║
╚════════════════════════════════════════════════════════════════════╝

Generated: {datetime.now().isoformat()}
Metrics File: {self.metrics_file}
Total Events: {len(self.events)}

CONVERSATION OVERVIEW
=====================
"""
        conv_metrics = self.get_conversation_metrics()
        if "error" not in conv_metrics:
            report += f"""
  Total Conversations: {conv_metrics['total_conversations']}
  Total Events: {conv_metrics['total_events']}

  Conversation Length:
    Average: {conv_metrics['avg_conversation_length']:.1f} turns
    Median:  {conv_metrics['median_conversation_length']:.1f} turns
    Min:     {conv_metrics['min_conversation_length']} turns
    Max:     {conv_metrics['max_conversation_length']} turns
"""

        report += "\nRETRIEVAL PERFORMANCE\n=====================\n"
        ret_metrics = self.get_retrieval_metrics()
        if "error" not in ret_metrics:
            report += f"""
  Total Retrievals: {ret_metrics['total_retrievals']}

  Confidence Scores:
    Average:  {ret_metrics['avg_confidence']:.1%}
    Median:   {ret_metrics['median_confidence']:.1%}
    Min:      {ret_metrics['min_confidence']:.1%}
    Max:      {ret_metrics['max_confidence']:.1%}
    Std Dev:  {ret_metrics['std_confidence']:.1%}

  Precision Scores:
    Average:  {ret_metrics['avg_precision']:.1%}
    Median:   {ret_metrics['median_precision']:.1%}
"""

        report += "\nRECOMMENDATION QUALITY\n======================\n"
        rec_metrics = self.get_recommendation_metrics()
        if "error" not in rec_metrics:
            report += f"""
  Total Recommendations: {rec_metrics['total_recommendations']}

  Quality Scores:
    Average:  {rec_metrics['avg_quality_score']:.2f}/1.0
    Median:   {rec_metrics['median_quality_score']:.2f}/1.0
    Min:      {rec_metrics['min_quality_score']:.2f}/1.0
    Max:      {rec_metrics['max_quality_score']:.2f}/1.0

  Recommendation Counts:
    Average:  {rec_metrics['avg_rec_count']:.1f} per turn
    Median:   {rec_metrics['median_rec_count']:.1f} per turn

  Hallucinations:
    Total Detected: {rec_metrics['total_hallucinations']}
    Detection Rate: {rec_metrics['hallucination_rate']:.2%}
"""

        report += "\nCLARIFICATION EFFICIENCY\n=======================\n"
        clarif_metrics = self.get_clarification_metrics()
        if "error" not in clarif_metrics:
            report += f"""
  Total Clarifications: {clarif_metrics['total_clarifications']}

  Efficiency Scores:
    Average:  {clarif_metrics['avg_efficiency']:.2f}/1.0
    Median:   {clarif_metrics['median_efficiency']:.2f}/1.0
    Min:      {clarif_metrics['min_efficiency']:.2f}/1.0
    Max:      {clarif_metrics['max_efficiency']:.2f}/1.0
"""

        report += "\nREFINEMENT SUCCESS\n==================\n"
        refine_metrics = self.get_refinement_metrics()
        if "error" not in refine_metrics:
            report += f"""
  Total Refinements: {refine_metrics['total_refinements']}
  Successful: {refine_metrics['successful_refinements']}
  Success Rate: {refine_metrics['success_rate']:.1%}

  By Type:
"""
            for rtype, stats in refine_metrics.get("by_type", {}).items():
                rate = stats["successful"] / stats["total"] * 100 if stats["total"] > 0 else 0
                report += f"    {rtype}: {stats['successful']}/{stats['total']} ({rate:.0f}%)\n"

        report += "\nHALLUCINATION DETECTION\n=======================\n"
        halluc_metrics = self.get_hallucination_metrics()
        report += f"""
  Total Hallucinations Detected: {halluc_metrics['total_hallucinations_detected']}
"""
        if halluc_metrics['hallucination_types']:
            report += "  By Type:\n"
            for htype, count in halluc_metrics['hallucination_types'].items():
                report += f"    {htype}: {count}\n"

        report += "\n" + "=" * 70 + "\n"
        return report

    @staticmethod
    def format_metrics_json(metrics: Dict) -> str:
        """Format metrics as pretty JSON."""
        return json.dumps(metrics, indent=2, default=str)


def main():
    """Main CLI for metrics analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze AssessIQ evaluation metrics")
    parser.add_argument(
        "--metrics",
        "-m",
        default="logs/evaluation_metrics.jsonl",
        help="Path to metrics JSONL file"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Save report to file"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted report"
    )
    args = parser.parse_args()

    analyzer = MetricsAnalyzer(args.metrics)

    if args.json:
        # Output all metrics as JSON
        all_metrics = {
            "retrieval": analyzer.get_retrieval_metrics(),
            "recommendations": analyzer.get_recommendation_metrics(),
            "clarifications": analyzer.get_clarification_metrics(),
            "refinements": analyzer.get_refinement_metrics(),
            "conversations": analyzer.get_conversation_metrics(),
            "hallucinations": analyzer.get_hallucination_metrics(),
        }
        output = MetricsAnalyzer.format_metrics_json(all_metrics)
    else:
        # Output formatted report
        output = analyzer.generate_summary_report()

    print(output)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(output)
        print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
