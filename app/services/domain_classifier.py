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
    
    # AI/ML Alias Expansion (Part 2 Fix)
    AI_ML_KEYWORDS = [
        "ai", "artificial intelligence", "machine learning", "ml", 
        "deep learning", "nlp", "computer vision", "neural networks", 
        "tensorflow", "pytorch", "data science", "llm", "generative ai",
        "python", "statistics", "data engineering", "spark", "hadoop", "analytics"
    ]

    DOMAIN_GROUPS = {
        Domain.FRONTEND: [
            "frontend", "javascript", "typescript", "react", "angular", 
            "angularjs", "vue", "nextjs", "web", "ui", "frontend architecture", 
            "html", "css", "sass", "redux", "web development"
        ],
        Domain.BACKEND: [
            "backend", "api", "java", "spring", "nodejs", "microservices", 
            "distributed systems", "python", "django", "flask", "fastapi", 
            "sql", "nosql", "database", "mongodb", "postgresql", "enterprise java"
        ],
        Domain.DEVOPS: [
            "devops", "cloud", "aws", "docker", "terraform", "kubernetes", 
            "sre", "infrastructure", "azure", "gcp", "ci/cd", "observability", "jenkins", "ansible"
        ],
        Domain.DATA_AI: AI_ML_KEYWORDS,
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
        Detects primary domain using smart normalization.
        """
        query_low = query.lower()
        scores = {domain: 0.0 for domain in self.DOMAIN_GROUPS}
        
        for domain, keywords in self.DOMAIN_GROUPS.items():
            for kw in keywords:
                # Part 2: Explicit weight for AI/ML keywords
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, query_low):
                    weight = 3.0 if domain == Domain.DATA_AI else 2.0 if " " in kw else 1.0
                    scores[domain] += weight
        
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        primary_domain = Domain.GENERAL
        confidence = 0.0
        
        if sorted_domains and sorted_domains[0][1] > 0:
            primary_domain = sorted_domains[0][0]
            confidence = min(1.0, sorted_domains[0][1] / 2.0)
        
        return {
            "primaryDomain": primary_domain,
            "confidence": confidence,
            "all_scores": scores
        }

    def normalize_assessment_domain(self, name: str, description: str) -> Domain:
        """
        Normalizes assessment domains into canonical groups.
        """
        text = (name + " " + description).lower()
        scores = {domain: 0 for domain in self.DOMAIN_GROUPS}
        
        for domain, keywords in self.DOMAIN_GROUPS.items():
            for kw in keywords:
                if kw in text:
                    # Give AI/ML a boost during catalog normalization too
                    weight = 2 if domain == Domain.DATA_AI else 1
                    scores[domain] += weight
        
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_domains and sorted_domains[0][1] > 0:
            return sorted_domains[0][0]
            
        return Domain.GENERAL

    def is_allowed_domain(self, query_domain: Domain, assessment_domain: Domain) -> bool:
        """
        Smart Safety Gate (Recovery Fix).
        Allows semantic subdomain matching while rejecting unrelated engineering.
        """
        if query_domain == Domain.GENERAL:
            return assessment_domain not in [Domain.ENGINEERING_CORE, Domain.MEDICAL]
            
        if assessment_domain in [Domain.ENGINEERING_CORE, Domain.MEDICAL]:
            return False
            
        technical_domains = [Domain.FRONTEND, Domain.BACKEND, Domain.DEVOPS, Domain.DATA_AI, Domain.QA, Domain.MANAGEMENT]
        if query_domain in technical_domains:
            if assessment_domain == Domain.GENERAL:
                return False
                
        # Specialized AI logic: AI queries can use Python/Data Science (which might be in Backend/General)
        if query_domain == Domain.DATA_AI:
            if assessment_domain == Domain.DATA_AI: return True
            # Allow pure Python/Data fallback if needed (Part 2 Fix)
            return False 

        return query_domain == assessment_domain
