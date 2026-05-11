"""
Domain Classifier for AssessIQ.
Implements strict domain taxonomy and query domain detection.
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
    Handles domain taxonomy and intelligent query classification.
    """
    
    TAXONOMY = {
        Domain.FRONTEND: {
            "react", "angular", "angularjs", "vue", "nextjs", "javascript", 
            "typescript", "html", "css", "ui", "frontend", "web frontend", "sass", "less", "redux"
        },
        Domain.BACKEND: {
            "java", "spring", "nodejs", "express", "python", "django", "flask", 
            "fastapi", "backend", "api", "microservices", "sql", "nosql", "database", "mongodb", "postgresql", "distributed systems"
        },
        Domain.DEVOPS: {
            "kubernetes", "terraform", "docker", "aws", "gcp", "azure", 
            "ci/cd", "sre", "infrastructure", "devops", "observability", "jenkins", "ansible", "cloud"
        },
        Domain.DATA_AI: {
            "ai", "ml", "llm", "deep learning", "nlp", "machine learning", 
            "analytics", "data science", "pytorch", "tensorflow", "spark", "hadoop", "data engineering"
        },
        Domain.MANAGEMENT: {
            "engineering manager", "stakeholder management", "leadership", 
            "people management", "delivery management", "scrum", "agile", "project manager", "product manager", "behavioral"
        },
        Domain.QA: {
            "testing", "automation testing", "selenium", "playwright", 
            "cypress", "qa", "sdet", "unit testing", "integration testing"
        },
        Domain.ENGINEERING_CORE: {
            "civil engineering", "mechanical engineering", "electrical engineering", 
            "chemical engineering", "aeronautical engineering", "aerospace", "automotive", 
            "ceramic engineering", "fire engineering", "geoinformatics", "electronics engineering"
        },
        Domain.MEDICAL: {
            "cardiology", "diabetes", "medical", "healthcare", "nursing", "pharmacology"
        }
    }
    
    # STRICT ADJACENCY MAP (Part 1 Fix)
    ADJACENCY_MAP = {
        Domain.FRONTEND: [Domain.FRONTEND],
        Domain.BACKEND: [Domain.BACKEND],
        Domain.DEVOPS: [Domain.DEVOPS],
        Domain.DATA_AI: [Domain.DATA_AI],
        Domain.MANAGEMENT: [Domain.MANAGEMENT],
        Domain.QA: [Domain.QA]
    }

    def detect_query_domain(self, query: str) -> Dict:
        """
        Detects primary and secondary domains for a query.
        """
        query_low = query.lower()
        scores = {domain: 0 for domain in self.TAXONOMY}
        matched_keywords = {domain: [] for domain in self.TAXONOMY}
        
        for domain, keywords in self.TAXONOMY.items():
            for kw in keywords:
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, query_low):
                    weight = 2.0 if " " in kw else 1.0
                    scores[domain] += weight
                    matched_keywords[domain].append(kw)
        
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        primary_domain = Domain.GENERAL
        confidence = 0.0
        secondary_domains = []
        
        if sorted_domains and sorted_domains[0][1] > 0:
            primary_domain = sorted_domains[0][0]
            confidence = min(1.0, sorted_domains[0][1] / 2.0) # Lowered threshold for technical detection
            
            for dom, score in sorted_domains[1:]:
                if score > 0 and score >= sorted_domains[0][1] * 0.5:
                    secondary_domains.append(dom)
        
        return {
            "primaryDomain": primary_domain,
            "secondaryDomains": secondary_domains,
            "matchedKeywords": matched_keywords.get(primary_domain, []) if primary_domain != Domain.GENERAL else [],
            "confidence": confidence,
            "all_scores": scores
        }

    def is_allowed_domain(self, query_domain: Domain, assessment_domain: Domain) -> bool:
        """
        ABSOLUTE DOMAIN LOCKING (Part 1 & 2 Fix).
        """
        # If query is generic, allow anything except medical/core-engineering unless requested
        if query_domain == Domain.GENERAL:
            return assessment_domain not in [Domain.ENGINEERING_CORE, Domain.MEDICAL]
            
        # Hard reject unrelated engineering/medical domains always
        if assessment_domain in [Domain.ENGINEERING_CORE, Domain.MEDICAL]:
            return False
            
        # If technical domain detected (FRONTEND, BACKEND, etc), reject GENERAL fallback (Part 2 Fix)
        if query_domain in [Domain.FRONTEND, Domain.BACKEND, Domain.DEVOPS, Domain.DATA_AI, Domain.QA]:
            if assessment_domain == Domain.GENERAL:
                return False
                
        allowed = self.ADJACENCY_MAP.get(query_domain, [query_domain])
        return assessment_domain in allowed
