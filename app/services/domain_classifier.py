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
            "typescript", "html", "css", "ui", "frontend", "web frontend", "sass", "less"
        },
        Domain.BACKEND: {
            "java", "spring", "nodejs", "express", "python", "django", "flask", 
            "fastapi", "backend", "api", "microservices", "sql", "nosql", "database", "mongodb", "postgresql"
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
            "people management", "delivery management", "scrum", "agile", "project manager", "product manager"
        },
        Domain.QA: {
            "testing", "automation testing", "selenium", "playwright", 
            "cypress", "qa", "sdet", "unit testing", "integration testing"
        },
        Domain.ENGINEERING_CORE: {
            "civil engineering", "mechanical engineering", "electrical engineering", 
            "chemical engineering", "aeronautical engineering", "aerospace", "automotive"
        },
        Domain.MEDICAL: {
            "cardiology", "diabetes", "medical", "healthcare", "nursing", "pharmacology"
        }
    }
    
    ADJACENCY_MAP = {
        Domain.FRONTEND: [Domain.FRONTEND],
        Domain.BACKEND: [Domain.BACKEND],
        Domain.DEVOPS: [Domain.DEVOPS, Domain.BACKEND],
        Domain.DATA_AI: [Domain.DATA_AI, Domain.BACKEND],
        Domain.MANAGEMENT: [Domain.MANAGEMENT],
        Domain.QA: [Domain.QA, Domain.BACKEND, Domain.FRONTEND]
    }

    def detect_query_domain(self, query: str) -> Dict:
        """
        Detects primary and secondary domains for a query.
        """
        query_low = query.lower()
        scores = {domain: 0 for domain in self.TAXONOMY}
        matched_keywords = {domain: [] for domain in self.TAXONOMY}
        
        # Weighted keyword matching
        for domain, keywords in self.TAXONOMY.items():
            for kw in keywords:
                # Use regex to find whole words to avoid partial matches like "ai" in "chair"
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, query_low):
                    # Multi-word keywords get higher weight
                    weight = 2.0 if " " in kw else 1.0
                    scores[domain] += weight
                    matched_keywords[domain].append(kw)
        
        # Sort domains by score
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        primary_domain = Domain.GENERAL
        confidence = 0.0
        secondary_domains = []
        
        if sorted_domains and sorted_domains[0][1] > 0:
            primary_domain = sorted_domains[0][0]
            confidence = min(1.0, sorted_domains[0][1] / 3.0) # Simple confidence normalization
            
            # Find secondary domains (those with > 50% of primary score)
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

    def infer_assessment_domain(self, name: str, description: str) -> Domain:
        """
        Infers the primary domain for an assessment based on its name and description.
        """
        text = (name + " " + description).lower()
        scores = {domain: 0 for domain in self.TAXONOMY}
        
        for domain, keywords in self.TAXONOMY.items():
            for kw in keywords:
                if kw in text:
                    scores[domain] += 1
        
        sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_domains and sorted_domains[0][1] > 0:
            return sorted_domains[0][0]
            
        return Domain.GENERAL

    def is_allowed_domain(self, query_domain: Domain, assessment_domain: Domain) -> bool:
        """
        Implements the hard domain filtering logic.
        """
        if query_domain == Domain.GENERAL:
            return True # Allow everything if query is general
            
        # Hard reject unrelated engineering/medical domains
        if assessment_domain in [Domain.ENGINEERING_CORE, Domain.MEDICAL]:
            return False
            
        allowed = self.ADJACENCY_MAP.get(query_domain, [query_domain])
        return assessment_domain in allowed or assessment_domain == Domain.GENERAL
