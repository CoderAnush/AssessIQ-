"""
Domain Classifier for AssessIQ.
Implements smart domain normalization, precise safety gates, and AI/ML expansion.
"""

from enum import Enum
from typing import List, Dict, Set, Optional
import re

class Domain(str, Enum):
    FRONTEND = "FRONTEND"
    BACKEND = "BACKEND"
    DEVOPS = "DEVOPS"
    DATA_AI = "DATA_AI"
    MANAGEMENT = "MANAGEMENT"
    QA = "QA"
    ENGINEERING_CORE = "ENGINEERING_CORE"
    MEDICAL = "MEDICAL"
    GENERAL = "GENERAL"

class DomainClassifier:
    """
    Handles smart domain normalization and precise safety gates (Final Intelligence Refinement).
    """
    
    # Contextual Indicators for Disambiguation
    BACKEND_INDICATORS = {
        "backend", "api", "rest api", "flask", "django", "fastapi", "microservice",
        "server", "web app", "postgres", "redis", "celery", "sqlalchemy", "distributed systems",
        "sql", "nosql", "database", "mongodb", "postgresql", "enterprise java", "spring", "j2ee",
        "java", "c++", "c programming", "c#", "dotnet", "software", "coding", "programming", "developer",
        "development", "engineering", "technical", "distributed"
    }

    AI_ML_INDICATORS = {
        "ai", "ml", "machine learning", "deep learning", "tensorflow", "pytorch",
        "nlp", "llm", "generative ai", "data science", "computer vision", "statistics",
        "data engineering", "spark", "hadoop", "analytics", "neural networks", "data", "mathematics",
        "modeling", "algorithms"
    }

    FRONTEND_INDICATORS = {
        "frontend", "javascript", "typescript", "react", "angular", "vue", "nextjs",
        "ui", "ux", "frontend architecture", "html", "css", "sass", "redux",
        "interface", "styling", "ui design", "user interface"
    }

    DEVOPS_INDICATORS = {
        "devops", "cloud", "aws", "docker", "terraform", "kubernetes", "sre",
        "site reliability", "infrastructure", "azure", "gcp", "ci/cd", "observability",
        "jenkins", "ansible", "helm", "argocd", "linux", "monitoring", "prometheus",
        "grafana", "deployment", "platform engineer", "container", "orchestration"
    }

    ADJACENCY_MAP = {
        Domain.BACKEND: [],
        Domain.FRONTEND: [],
        Domain.DATA_AI: [],
        Domain.DEVOPS: [],
        Domain.QA: [],
        Domain.MANAGEMENT: [Domain.GENERAL]
    }

    DOMAIN_GROUPS = {
        Domain.FRONTEND: list(FRONTEND_INDICATORS),
        Domain.BACKEND: list(BACKEND_INDICATORS),
        Domain.DEVOPS: list(DEVOPS_INDICATORS),
        Domain.DATA_AI: list(AI_ML_INDICATORS),
        Domain.MANAGEMENT: [
            "management", "leadership", "behavioral", "stakeholder", 
            "engineering manager", "people management", "scrum", "agile", "strategic"
        ],
        Domain.QA: [
            "testing", "qa", "sdet", "automation testing", "selenium", "cypress", "unit testing", "integration testing"
        ],
        Domain.ENGINEERING_CORE: [
            "civil", "mechanical", "electrical", "chemical", "aeronautical", 
            "aerospace", "ceramic", "fire engineering", "geoinformatics", "electronics"
        ],
        Domain.MEDICAL: [
            "cardiology", "medical", "healthcare", "nursing", "pharmacology", "diabetes"
        ]
    }

    def detect_query_domain(self, query: str) -> Dict:
        """
        Detects primary domain using Contextual Python Disambiguation.
        """
        query_low = query.lower()
        
        # 1. EXPLICIT OVERRIDES (Highest Priority)
        if any(kw in query_low for kw in ["backend", "api", "fastapi", "django", "flask", "server"]):
            if not any(kw in query_low for kw in ["machine learning", "deep learning", "nlp", "llm"]):
                 return {"primaryDomain": Domain.BACKEND, "confidence": 1.0, "reason": "Explicit Backend Keywords"}

        if any(kw in query_low for kw in ["devops", "kubernetes", "terraform", "docker", "ci/cd",
                                           "sre", "site reliability", "helm", "argocd",
                                           "linux", "monitoring", "infrastructure", "platform engineer"]):
            if not any(kw in query_low for kw in ["machine learning", "deep learning", "nlp", "react", "frontend"]):
                return {"primaryDomain": Domain.DEVOPS, "confidence": 1.0, "reason": "Explicit DevOps Keywords"}

        if any(kw in query_low for kw in ["civil", "mechanical", "electrical", "aeronautical", "aerospace", "chemical", "ceramic", "cad ", "bim "]):
             if not any(kw in query_low for kw in ["software", "coding", "developer", "backend", "frontend"]):
                return {"primaryDomain": Domain.ENGINEERING_CORE, "confidence": 1.0, "reason": "Explicit Physical Engineering"}

        if any(kw in query_low for kw in ["medical", "cardiology", "healthcare", "nursing", "pharmacology"]):
            return {"primaryDomain": Domain.MEDICAL, "confidence": 1.0, "reason": "Explicit Medical Keywords"}

        if any(kw in query_low for kw in ["frontend", "react", "angular", "ui ", "ux ", "css"]):
            return {"primaryDomain": Domain.FRONTEND, "confidence": 1.0, "reason": "Explicit Frontend Keywords"}

        # 2. Check for Python Ambiguity
        has_python = "python" in query_low
        has_backend = any(kw in query_low for kw in self.BACKEND_INDICATORS)
        has_ai = any(kw in query_low for kw in self.AI_ML_INDICATORS)

        if has_python:
            if has_backend and not has_ai:
                return {"primaryDomain": Domain.BACKEND, "confidence": 0.95, "reason": "Python Backend Context"}
            if has_ai:
                return {"primaryDomain": Domain.DATA_AI, "confidence": 0.95, "reason": "Python AI/ML Context"}

        # 3. Standard Weighted Scoring
        scores = {domain: 0.0 for domain in self.DOMAIN_GROUPS}
        for domain, keywords in self.DOMAIN_GROUPS.items():
            for kw in keywords:
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, query_low):
                    weight = 3.0 if " " in kw else 1.5
                    scores[domain] += weight
        
        # Add CRITICAL boost for direct domain mentions
        if "backend" in query_low: scores[Domain.BACKEND] += 10.0
        if "frontend" in query_low: scores[Domain.FRONTEND] += 10.0
        if "devops" in query_low: scores[Domain.DEVOPS] += 10.0
        if "data science" in query_low or "machine learning" in query_low: scores[Domain.DATA_AI] += 10.0

        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        primary_domain = Domain.GENERAL
        confidence = 0.0
        
        if sorted_domains and sorted_domains[0][1] > 0:
            primary_domain = sorted_domains[0][0]
            confidence = min(1.0, sorted_domains[0][1] / 10.0)
        
        # 4. Tech Stack Extraction (For Expansion)
        tech_stack = set()
        for domain, keywords in self.DOMAIN_GROUPS.items():
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", query_low):
                    tech_stack.add(kw.title())

        return {
            "primaryDomain": primary_domain,
            "confidence": confidence,
            "all_scores": scores,
            "techStack": tech_stack
        }

    def normalize_assessment_domain(self, name: str, description: str) -> Domain:
        """
        Normalizes assessment domains into canonical groups.
        """
        text = (name + " " + description).lower()
        
        # Hard Negative Checks for Assessment Tagging
        if any(kw in text for kw in ["aws", "cloud", "kubernetes", "docker", "terraform", "infrastructure", "devops"]):
            return Domain.DEVOPS
        if any(kw in text for kw in ["react", "frontend", "ui ", "ux ", "angular", "javascript", "typescript", "css"]):
             # Re-verify it's not a backend test for frontend developers
             if "java" in text or "python" in text or "backend" in text:
                 return Domain.BACKEND
             return Domain.FRONTEND
        if any(re.search(rf"\b{re.escape(kw)}\b", text) for kw in ["machine learning", "data science", "nlp", "llm"]):
            return Domain.DATA_AI
        scores = {domain: 0 for domain in self.DOMAIN_GROUPS}
        for domain, keywords in self.DOMAIN_GROUPS.items():
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", text):
                    scores[domain] += 1
        
        # Add a heavy bias for backend if java is present
        if re.search(r"\bjava\b", text) and not re.search(r"\bjavascript\b", text):
            scores[Domain.BACKEND] += 5
        
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_domains and sorted_domains[0][1] > 0:
            return sorted_domains[0][0]

        # Core Engineering Check
        if any(kw in text for kw in ["software", "programming", "coding", "algorithm", "data structure", "computer science", "technical"]):
            # If it didn't match a specific domain above, call it CORE
            return Domain.ENGINEERING_CORE

        return Domain.GENERAL

    def is_strictly_allowed(self, query_domain: Domain, assessment_domain: Domain) -> bool:
        """
        Absolute Domain Hard Lock.
        NO ENGINEERING_CORE. NO partial overlap.
        """
        strict_domains = {Domain.FRONTEND, Domain.BACKEND, Domain.DEVOPS, Domain.DATA_AI}
        if query_domain in strict_domains:
            return query_domain == assessment_domain
            
        if query_domain == Domain.GENERAL:
            return assessment_domain != Domain.MEDICAL
            
        return query_domain == assessment_domain
