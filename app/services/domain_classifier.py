"""
Domain Classifier for AssessIQ.
Implements smart domain normalization and strict safety gates.
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
    Handles smart domain normalization and precise safety gates (Recovery Fix).
    """
    
    DOMAIN_GROUPS = {
        Domain.FRONTEND: [
            "frontend", "javascript", "typescript", "react", "angular", 
            "angularjs", "vue", "nextjs", "web", "ui", "frontend architecture", 
            "html", "css", "sass", "redux"
        ],
        Domain.BACKEND: [
            "backend", "api", "java", "spring", "nodejs", "microservices", 
            "distributed systems", "python", "django", "flask", "fastapi", 
            "sql", "nosql", "database", "mongodb", "postgresql"
        ],
        Domain.DEVOPS: [
            "devops", "cloud", "aws", "docker", "terraform", "kubernetes", 
            "sre", "infrastructure", "azure", "gcp", "ci/cd", "observability"
        ],
        Domain.DATA_AI: [
            "ai", "ml", "machine learning", "data science", "deep learning", 
            "nlp", "pytorch", "tensorflow", "data engineering", "analytics"
        ],
        Domain.MANAGEMENT: [
            "management", "leadership", "behavioral", "stakeholder", 
            "engineering manager", "people management", "scrum", "agile"
        ],
        Domain.QA: [
            "testing", "qa", "sdet", "automation testing", "selenium", "cypress"
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
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, query_low):
                    weight = 2.0 if " " in kw else 1.0
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
                    scores[domain] += 1
        
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_domains and sorted_domains[0][1] > 0:
            return sorted_domains[0][0]
            
        return Domain.GENERAL

    def is_allowed_domain(self, query_domain: Domain, assessment_domain: Domain) -> bool:
        """
        Smart Safety Gate (Recovery Fix).
        Allows semantic subdomain matching while rejecting unrelated engineering.
        """
        # Generic queries allow general assessments but reject specialized medical/core-engineering
        if query_domain == Domain.GENERAL:
            return assessment_domain not in [Domain.ENGINEERING_CORE, Domain.MEDICAL]
            
        # Hard safety: Never allow core engineering/medical for TECHNICAL queries
        # Technical domains: FRONTEND, BACKEND, DEVOPS, DATA_AI, QA, MANAGEMENT
        technical_domains = [Domain.FRONTEND, Domain.BACKEND, Domain.DEVOPS, Domain.DATA_AI, Domain.QA, Domain.MANAGEMENT]
        if query_domain in technical_domains:
            if assessment_domain in [Domain.ENGINEERING_CORE, Domain.MEDICAL, Domain.GENERAL]:
                return False
                
        # If query is for engineering/medical, allow exact match
        return query_domain == assessment_domain
