"""
Assessment Taxonomy Engine for AssessIQ AI.

Provides centralized classification system for:
- Assessment domains (technical, cognitive, personality, etc.)
- Role domain priorities (what matters for each role type)
- Assessment-to-domain mapping based on grounded catalog metadata
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum
from app.models.assessment import AssessmentWithMetadata
from app.logging.logger import get_logger

logger = get_logger("assessment_taxonomy")


class AssessmentDomain(str, Enum):
    """Primary assessment classification domains."""
    TECHNICAL = "technical"           # Programming, specific tech skills
    COGNITIVE = "cognitive"           # Reasoning, problem-solving, general ability
    PERSONALITY = "personality"     # Behavioral styles, traits
    LEADERSHIP = "leadership"       # Management, executive capabilities
    BEHAVIORAL = "behavioral"         # Workplace behavior, teamwork
    COMMUNICATION = "communication" # Verbal, written, presentation skills
    ANALYTICAL = "analytical"         # Data analysis, quantitative reasoning
    SALES = "sales"                   # Sales aptitude, customer-facing
    GENERAL = "general"               # Cross-domain assessments


class RoleDomain(str, Enum):
    """Role classification for priority weighting."""
    BACKEND_ENGINEER = "backend_engineer"
    FRONTEND_ENGINEER = "frontend_engineer"
    FULLSTACK_ENGINEER = "fullstack_engineer"
    DATA_SCIENTIST = "data_scientist"
    DATA_ANALYST = "data_analyst"
    DEVOPS_ENGINEER = "devops_engineer"
    MOBILE_DEVELOPER = "mobile_developer"
    QA_ENGINEER = "qa_engineer"
    ENGINEERING_MANAGER = "engineering_manager"
    PRODUCT_MANAGER = "product_manager"
    SALES_REP = "sales_rep"
    SALES_MANAGER = "sales_manager"
    EXECUTIVE = "executive"
    HR_PROFESSIONAL = "hr_professional"
    GENERAL = "general"


@dataclass
class DomainScore:
    """Score for a specific domain alignment."""
    domain: AssessmentDomain
    score: float  # 0-1 alignment score
    reasoning: str


@dataclass
class AssessmentClassification:
    """Complete classification for an assessment."""
    assessment_id: str
    primary_domain: AssessmentDomain
    secondary_domains: List[AssessmentDomain]
    domain_scores: Dict[AssessmentDomain, float]
    technical_depth: int  # 0-10 scale
    behavioral_relevance: int  # 0-10 scale
    seniority_suitability: Set[str]  # junior, mid, senior, executive
    category: str
    key_capabilities: List[str]
    ideal_use_cases: List[str]


class AssessmentTaxonomy:
    """
    Centralized taxonomy engine for assessment classification.
    
    Maps assessments to domains based on grounded catalog metadata.
    Provides role-to-domain priority weightings.
    """
    
    # Role domain priority mappings
    # Format: {role_domain: {assessment_domain: priority_weight (0-1)}}
    ROLE_DOMAIN_PRIORITIES: Dict[RoleDomain, Dict[AssessmentDomain, float]] = {
        RoleDomain.BACKEND_ENGINEER: {
            AssessmentDomain.TECHNICAL: 1.0,
            AssessmentDomain.COGNITIVE: 0.85,
            AssessmentDomain.ANALYTICAL: 0.75,
            AssessmentDomain.COMMUNICATION: 0.50,
            AssessmentDomain.LEADERSHIP: 0.35,
            AssessmentDomain.BEHAVIORAL: 0.40,
            AssessmentDomain.PERSONALITY: 0.25,
        },
        RoleDomain.FRONTEND_ENGINEER: {
            AssessmentDomain.TECHNICAL: 1.0,
            AssessmentDomain.COGNITIVE: 0.75,
            AssessmentDomain.COMMUNICATION: 0.60,
            AssessmentDomain.BEHAVIORAL: 0.50,
            AssessmentDomain.ANALYTICAL: 0.50,
            AssessmentDomain.LEADERSHIP: 0.30,
            AssessmentDomain.PERSONALITY: 0.25,
        },
        RoleDomain.FULLSTACK_ENGINEER: {
            AssessmentDomain.TECHNICAL: 1.0,
            AssessmentDomain.COGNITIVE: 0.80,
            AssessmentDomain.ANALYTICAL: 0.70,
            AssessmentDomain.COMMUNICATION: 0.55,
            AssessmentDomain.BEHAVIORAL: 0.45,
            AssessmentDomain.LEADERSHIP: 0.35,
            AssessmentDomain.PERSONALITY: 0.30,
        },
        RoleDomain.DATA_SCIENTIST: {
            AssessmentDomain.ANALYTICAL: 1.0,
            AssessmentDomain.TECHNICAL: 0.90,
            AssessmentDomain.COGNITIVE: 0.85,
            AssessmentDomain.COMMUNICATION: 0.45,
            AssessmentDomain.BEHAVIORAL: 0.35,
            AssessmentDomain.PERSONALITY: 0.25,
            AssessmentDomain.LEADERSHIP: 0.20,
        },
        RoleDomain.DATA_ANALYST: {
            AssessmentDomain.ANALYTICAL: 1.0,
            AssessmentDomain.COGNITIVE: 0.80,
            AssessmentDomain.TECHNICAL: 0.60,
            AssessmentDomain.COMMUNICATION: 0.50,
            AssessmentDomain.BEHAVIORAL: 0.40,
            AssessmentDomain.PERSONALITY: 0.30,
            AssessmentDomain.LEADERSHIP: 0.25,
        },
        RoleDomain.DEVOPS_ENGINEER: {
            AssessmentDomain.TECHNICAL: 1.0,
            AssessmentDomain.COGNITIVE: 0.75,
            AssessmentDomain.ANALYTICAL: 0.65,
            AssessmentDomain.COMMUNICATION: 0.55,
            AssessmentDomain.BEHAVIORAL: 0.45,
            AssessmentDomain.LEADERSHIP: 0.35,
            AssessmentDomain.PERSONALITY: 0.30,
        },
        RoleDomain.MOBILE_DEVELOPER: {
            AssessmentDomain.TECHNICAL: 1.0,
            AssessmentDomain.COGNITIVE: 0.75,
            AssessmentDomain.COMMUNICATION: 0.50,
            AssessmentDomain.BEHAVIORAL: 0.40,
            AssessmentDomain.ANALYTICAL: 0.45,
            AssessmentDomain.PERSONALITY: 0.25,
            AssessmentDomain.LEADERSHIP: 0.20,
        },
        RoleDomain.QA_ENGINEER: {
            AssessmentDomain.TECHNICAL: 0.85,
            AssessmentDomain.ANALYTICAL: 0.90,
            AssessmentDomain.COGNITIVE: 0.75,
            AssessmentDomain.BEHAVIORAL: 0.55,
            AssessmentDomain.COMMUNICATION: 0.50,
            AssessmentDomain.PERSONALITY: 0.35,
            AssessmentDomain.LEADERSHIP: 0.25,
        },
        RoleDomain.ENGINEERING_MANAGER: {
            AssessmentDomain.LEADERSHIP: 1.0,
            AssessmentDomain.BEHAVIORAL: 0.85,
            AssessmentDomain.COMMUNICATION: 0.80,
            AssessmentDomain.TECHNICAL: 0.60,
            AssessmentDomain.COGNITIVE: 0.70,
            AssessmentDomain.PERSONALITY: 0.75,
            AssessmentDomain.ANALYTICAL: 0.50,
        },
        RoleDomain.PRODUCT_MANAGER: {
            AssessmentDomain.COMMUNICATION: 0.95,
            AssessmentDomain.ANALYTICAL: 0.85,
            AssessmentDomain.LEADERSHIP: 0.75,
            AssessmentDomain.BEHAVIORAL: 0.70,
            AssessmentDomain.COGNITIVE: 0.70,
            AssessmentDomain.TECHNICAL: 0.50,
            AssessmentDomain.PERSONALITY: 0.60,
        },
        RoleDomain.SALES_REP: {
            AssessmentDomain.SALES: 1.0,
            AssessmentDomain.COMMUNICATION: 0.95,
            AssessmentDomain.PERSONALITY: 0.80,
            AssessmentDomain.BEHAVIORAL: 0.70,
            AssessmentDomain.COGNITIVE: 0.50,
            AssessmentDomain.LEADERSHIP: 0.30,
            AssessmentDomain.TECHNICAL: 0.20,
        },
        RoleDomain.SALES_MANAGER: {
            AssessmentDomain.SALES: 0.95,
            AssessmentDomain.LEADERSHIP: 0.90,
            AssessmentDomain.COMMUNICATION: 0.90,
            AssessmentDomain.PERSONALITY: 0.75,
            AssessmentDomain.BEHAVIORAL: 0.70,
            AssessmentDomain.COGNITIVE: 0.55,
            AssessmentDomain.TECHNICAL: 0.25,
        },
        RoleDomain.EXECUTIVE: {
            AssessmentDomain.LEADERSHIP: 1.0,
            AssessmentDomain.PERSONALITY: 0.85,
            AssessmentDomain.COMMUNICATION: 0.80,
            AssessmentDomain.BEHAVIORAL: 0.70,
            AssessmentDomain.ANALYTICAL: 0.65,
            AssessmentDomain.COGNITIVE: 0.60,
            AssessmentDomain.TECHNICAL: 0.20,
        },
        RoleDomain.HR_PROFESSIONAL: {
            AssessmentDomain.PERSONALITY: 0.90,
            AssessmentDomain.COMMUNICATION: 0.85,
            AssessmentDomain.BEHAVIORAL: 0.80,
            AssessmentDomain.LEADERSHIP: 0.60,
            AssessmentDomain.ANALYTICAL: 0.50,
            AssessmentDomain.COGNITIVE: 0.50,
            AssessmentDomain.TECHNICAL: 0.25,
        },
        RoleDomain.GENERAL: {
            AssessmentDomain.TECHNICAL: 0.60,
            AssessmentDomain.COGNITIVE: 0.70,
            AssessmentDomain.PERSONALITY: 0.60,
            AssessmentDomain.LEADERSHIP: 0.50,
            AssessmentDomain.BEHAVIORAL: 0.60,
            AssessmentDomain.COMMUNICATION: 0.60,
            AssessmentDomain.ANALYTICAL: 0.60,
        },
    }
    
    # Domain keywords for classification
    DOMAIN_KEYWORDS: Dict[AssessmentDomain, List[str]] = {
        AssessmentDomain.TECHNICAL: [
            "programming", "code", "software", "development", "technical",
            "java", "python", "javascript", "react", "angular", "node",
            "backend", "frontend", "fullstack", "devops", "database",
            "api", "framework", "library", "system", "architecture",
            "engineering", "implementation", "coding", "debugging"
        ],
        AssessmentDomain.COGNITIVE: [
            "reasoning", "problem solving", "logical", "analytical thinking",
            "critical thinking", "mental ability", "intelligence", "aptitude",
            "abstract reasoning", "numerical reasoning", "verbal reasoning",
            "inductive reasoning", "deductive reasoning", "fluid intelligence",
            "general ability", "gsa", "cognitive", "mental", "thinking"
        ],
        AssessmentDomain.PERSONALITY: [
            "personality", "behavior", "trait", "style", "preference",
            "temperament", "character", "disposition", "attitude",
            "work style", "interpersonal", "social", "emotional",
            "opq", "16pf", "big five", "mbti", "workplace behavior"
        ],
        AssessmentDomain.LEADERSHIP: [
            "leadership", "management", "executive", "director",
            "strategic", "decision making", "vision", "influence",
            "team management", "people management", "organizational",
            "transformational", "situational", "authentic leadership"
        ],
        AssessmentDomain.BEHAVIORAL: [
            "behavior", "conduct", "action", "workplace behavior",
            "teamwork", "collaboration", "cooperation", "team player",
            "adaptability", "flexibility", "resilience", "stress management",
            "work ethic", "professionalism", "integrity"
        ],
        AssessmentDomain.COMMUNICATION: [
            "communication", "verbal", "written", "presentation",
            "interpersonal", "listening", "speaking", "language",
            "clarity", "articulation", "expression", "comprehension",
            "negotiation", "persuasion", "influence", "rapport"
        ],
        AssessmentDomain.ANALYTICAL: [
            "analysis", "analytical", "data", "statistics", "quantitative",
            "research", "investigation", "evaluation", "assessment",
            "diagnostic", "interpretation", "synthesis", "modeling",
            "data science", "machine learning", "algorithm", "pattern"
        ],
        AssessmentDomain.SALES: [
            "sales", "selling", "commercial", "revenue", "business development",
            "customer", "client", "account management", "relationship",
            "prospecting", "closing", "negotiation", "deal making",
            "market", "competitive", "persuasion", "influence"
        ],
    }
    
    def __init__(self, catalog_assessments: Optional[List[AssessmentWithMetadata]] = None):
        """Initialize taxonomy with optional catalog assessments."""
        self._classifications: Dict[str, AssessmentClassification] = {}
        self._assessment_domains: Dict[str, Set[AssessmentDomain]] = {}
        
        if catalog_assessments:
            self.build_taxonomy(catalog_assessments)
    
    def build_taxonomy(self, assessments: List[AssessmentWithMetadata]) -> None:
        """Build taxonomy classifications for all assessments."""
        logger.info(f"Building taxonomy for {len(assessments)} assessments")
        
        for assessment in assessments:
            classification = self._classify_assessment(assessment)
            self._classifications[assessment.id] = classification
            self._assessment_domains[assessment.id] = {
                classification.primary_domain
            } | set(classification.secondary_domains)
        
        logger.info(f"Taxonomy built: {len(self._classifications)} assessments classified")
    
    def _classify_assessment(self, assessment: AssessmentWithMetadata) -> AssessmentClassification:
        """Classify a single assessment based on its metadata."""
        
        # Analyze text fields for domain signals
        text = f"{assessment.name} {assessment.description} {' '.join(assessment.skills)}".lower()
        
        # Score each domain
        domain_scores: Dict[AssessmentDomain, float] = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = 0.0
            for keyword in keywords:
                if keyword in text:
                    # Higher weight for name matches
                    if keyword in assessment.name.lower():
                        score += 0.3
                    else:
                        score += 0.1
            domain_scores[domain] = min(score, 1.0)
        
        # Override based on test type
        test_type = assessment.test_type.value
        if test_type == "P":  # Personality
            domain_scores[AssessmentDomain.PERSONALITY] = max(
                domain_scores.get(AssessmentDomain.PERSONALITY, 0), 0.8
            )
        elif test_type == "K":  # Knowledge/Technical
            domain_scores[AssessmentDomain.TECHNICAL] = max(
                domain_scores.get(AssessmentDomain.TECHNICAL, 0), 0.7
            )
        elif test_type == "A":  # Ability/Cognitive
            domain_scores[AssessmentDomain.COGNITIVE] = max(
                domain_scores.get(AssessmentDomain.COGNITIVE, 0), 0.8
            )
        
        # Leadership focus flag override
        if hasattr(assessment, 'leadership_focus') and assessment.leadership_focus:
            domain_scores[AssessmentDomain.LEADERSHIP] = max(
                domain_scores.get(AssessmentDomain.LEADERSHIP, 0), 0.9
            )
        
        # Communication focus flag override
        if hasattr(assessment, 'communication_focus') and assessment.communication_focus:
            domain_scores[AssessmentDomain.COMMUNICATION] = max(
                domain_scores.get(AssessmentDomain.COMMUNICATION, 0), 0.9
            )
        
        # Determine primary and secondary domains
        sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
        primary_domain = sorted_domains[0][0] if sorted_domains else AssessmentDomain.GENERAL
        secondary_domains = [d for d, s in sorted_domains[1:3] if s > 0.3]
        
        # Extract technical depth
        technical_depth = self._calculate_technical_depth(assessment)
        
        # Extract behavioral relevance
        behavioral_relevance = self._calculate_behavioral_relevance(assessment)
        
        # Get seniority suitability
        seniority = set(assessment.seniority_levels) if hasattr(assessment, 'seniority_levels') else {"mid", "senior"}
        
        # Determine category
        category = self._determine_category(assessment, primary_domain)
        
        # Extract key capabilities from description
        key_capabilities = self._extract_capabilities(assessment)
        
        # Generate ideal use cases
        ideal_use_cases = self._generate_use_cases(assessment, primary_domain)
        
        return AssessmentClassification(
            assessment_id=assessment.id,
            primary_domain=primary_domain,
            secondary_domains=secondary_domains,
            domain_scores=domain_scores,
            technical_depth=technical_depth,
            behavioral_relevance=behavioral_relevance,
            seniority_suitability=seniority,
            category=category,
            key_capabilities=key_capabilities,
            ideal_use_cases=ideal_use_cases,
        )
    
    def _calculate_technical_depth(self, assessment: AssessmentWithMetadata) -> int:
        """Calculate technical depth score (0-10)."""
        depth = 0
        text = assessment.description.lower()
        
        # Check for advanced technical terms
        advanced_terms = [
            "advanced", "expert", "complex", "architecture", "design patterns",
            "optimization", "performance", "scalability", "system design"
        ]
        for term in advanced_terms:
            if term in text:
                depth += 1
        
        # Check duration (longer = more comprehensive)
        if hasattr(assessment, 'duration_minutes'):
            if assessment.duration_minutes > 45:
                depth += 2
            elif assessment.duration_minutes > 30:
                depth += 1
        
        # Technical focus flag
        if hasattr(assessment, 'technical_focus') and assessment.technical_focus:
            depth += 3
        
        return min(depth, 10)
    
    def _calculate_behavioral_relevance(self, assessment: AssessmentWithMetadata) -> int:
        """Calculate behavioral relevance score (0-10)."""
        relevance = 0
        text = assessment.description.lower()
        
        # Check for behavioral terms
        behavioral_terms = [
            "workplace", "behavior", "team", "collaboration", "communication",
            "interpersonal", "leadership", "management", "culture"
        ]
        for term in behavioral_terms:
            if term in text:
                relevance += 1
        
        # Personality test
        if assessment.test_type.value == "P":
            relevance += 4
        
        # Leadership/communication focus
        if hasattr(assessment, 'leadership_focus') and assessment.leadership_focus:
            relevance += 2
        if hasattr(assessment, 'communication_focus') and assessment.communication_focus:
            relevance += 2
        
        return min(relevance, 10)
    
    def _determine_category(self, assessment: AssessmentWithMetadata, primary_domain: AssessmentDomain) -> str:
        """Determine assessment category string."""
        domain_to_category = {
            AssessmentDomain.TECHNICAL: "Technical Knowledge",
            AssessmentDomain.COGNITIVE: "Cognitive Ability",
            AssessmentDomain.PERSONALITY: "Personality & Behavioral",
            AssessmentDomain.LEADERSHIP: "Leadership Assessment",
            AssessmentDomain.BEHAVIORAL: "Behavioral Assessment",
            AssessmentDomain.COMMUNICATION: "Communication Skills",
            AssessmentDomain.ANALYTICAL: "Analytical Assessment",
            AssessmentDomain.SALES: "Sales Aptitude",
            AssessmentDomain.GENERAL: "General Assessment",
        }
        return domain_to_category.get(primary_domain, "Assessment")
    
    def _extract_capabilities(self, assessment: AssessmentWithMetadata) -> List[str]:
        """Extract key capabilities from assessment."""
        capabilities = []
        
        # From skills
        if hasattr(assessment, 'skills'):
            capabilities.extend(assessment.skills[:5])
        
        # From description (extract key phrases)
        desc = assessment.description.lower()
        capability_patterns = [
            r"measures\s+(\w+(?:\s+\w+)?)",
            r"assesses\s+(\w+(?:\s+\w+)?)",
            r"evaluates\s+(\w+(?:\s+\w+)?)",
        ]
        import re
        for pattern in capability_patterns:
            matches = re.findall(pattern, desc)
            capabilities.extend(matches)
        
        return list(set(capabilities))[:8]  # Deduplicate and limit
    
    def _generate_use_cases(self, assessment: AssessmentWithMetadata, domain: AssessmentDomain) -> List[str]:
        """Generate ideal use cases for assessment."""
        use_cases = []
        
        domain_use_cases = {
            AssessmentDomain.TECHNICAL: [
                "Technical skill verification",
                "Programming competency screening",
                "Technology stack assessment"
            ],
            AssessmentDomain.COGNITIVE: [
                "General mental ability screening",
                "Problem-solving capability assessment",
                "Learning agility evaluation"
            ],
            AssessmentDomain.PERSONALITY: [
                "Culture fit assessment",
                "Team dynamics evaluation",
                "Work style understanding"
            ],
            AssessmentDomain.LEADERSHIP: [
                "Leadership readiness evaluation",
                "Executive potential assessment",
                "Management capability screening"
            ],
            AssessmentDomain.BEHAVIORAL: [
                "Workplace behavior prediction",
                "Team collaboration assessment",
                "Professional conduct evaluation"
            ],
            AssessmentDomain.COMMUNICATION: [
                "Communication skills verification",
                "Presentation ability assessment",
                "Interpersonal effectiveness"
            ],
            AssessmentDomain.ANALYTICAL: [
                "Data analysis capability",
                "Research skills assessment",
                "Quantitative reasoning evaluation"
            ],
            AssessmentDomain.SALES: [
                "Sales aptitude screening",
                "Customer relationship assessment",
                "Revenue generation potential"
            ],
        }
        
        return domain_use_cases.get(domain, ["General hiring assessment"])
    
    def classify_role(self, role_title: str, tech_stack: Optional[List[str]] = None) -> RoleDomain:
        """
        Classify a role title into a RoleDomain using weighted keyword matching.
        
        Implements:
        - Weighted keyword scoring (exact matches get higher scores)
        - Multi-token priority analysis
        - Backend-specific boosts for Java/Python/Go without frontend indicators
        - Role confidence scoring with debug metadata
        - Fallback hierarchy for ambiguous roles
        """
        role_lower = role_title.lower()
        tech_text = " ".join(tech_stack or []).lower()
        
        # Weighted keyword patterns with scores
        ROLE_PATTERNS = {
            RoleDomain.BACKEND_ENGINEER: {
                "exact": ["backend engineer", "backend developer", "server-side developer", "api engineer", "java developer", "python developer", "go developer", "node developer"],
                "strong": ["backend", "back-end", "server-side", "api developer", "systems engineer", "database engineer", "distributed systems"],
                "boost": ["java", "python", "go", "rust", "c++", "node.js", "database", "microservices", "sql", "nosql", "redis", "kafka"],
                "weight": 1.0
            },
            RoleDomain.FRONTEND_ENGINEER: {
                "exact": ["frontend engineer", "frontend developer", "ui engineer", "client-side developer", "react developer", "angular developer", "vue developer", "javascript developer"],
                "strong": ["frontend", "front-end", "ui developer", "web developer", "css", "html", "spa", "pwa"],
                "boost": ["react", "angular", "vue", "javascript", "typescript", "webpack", "sass", "less", "tailwind"],
                "weight": 1.0
            },
            RoleDomain.FULLSTACK_ENGINEER: {
                "exact": ["fullstack engineer", "fullstack developer", "full stack engineer", "full stack developer"],
                "strong": ["fullstack", "full-stack", "full stack"],
                "boost": [],
                "weight": 0.9  # Slightly lower - prefer specific domains
            },
            RoleDomain.DATA_SCIENTIST: {
                "exact": ["data scientist", "machine learning engineer", "ml engineer", "ai engineer"],
                "strong": ["data science", "machine learning", "deep learning", "ai specialist"],
                "boost": ["tensorflow", "pytorch", "scikit-learn", "pandas", "numpy"],
                "weight": 1.0
            },
            RoleDomain.DATA_ANALYST: {
                "exact": ["data analyst", "business analyst"],
                "strong": ["data analytics", "business intelligence", "reporting analyst"],
                "boost": ["sql", "tableau", "excel", "statistics"],
                "weight": 1.0
            },
            RoleDomain.DEVOPS_ENGINEER: {
                "exact": ["devops engineer", "sre", "site reliability engineer", "platform engineer"],
                "strong": ["devops", "infrastructure", "cloud engineer", "platform"],
                "boost": ["kubernetes", "docker", "aws", "terraform", "ci/cd"],
                "weight": 1.0
            },
            RoleDomain.MOBILE_DEVELOPER: {
                "exact": ["mobile developer", "ios developer", "android developer", "app developer"],
                "strong": ["mobile", "ios", "android", "swift", "kotlin"],
                "boost": ["react native", "flutter", "mobile app"],
                "weight": 1.0
            },
            RoleDomain.QA_ENGINEER: {
                "exact": ["qa engineer", "quality assurance engineer", "test engineer", "automation engineer"],
                "strong": ["qa", "quality assurance", "testing", "test automation"],
                "boost": ["selenium", "cypress", "junit", "automation"],
                "weight": 1.0
            },
            RoleDomain.ENGINEERING_MANAGER: {
                "exact": ["engineering manager", "development manager", "software engineering manager"],
                "strong": ["tech lead", "team lead", "engineering lead", "development lead"],
                "boost": ["management", "leadership", "team building"],
                "weight": 1.0
            },
            RoleDomain.PRODUCT_MANAGER: {
                "exact": ["product manager", "product owner"],
                "strong": ["product management", "program manager", "technical product manager"],
                "boost": ["roadmap", "agile", "scrum", "user stories"],
                "weight": 1.0
            },
            RoleDomain.SALES_REP: {
                "exact": ["sales executive", "account executive", "sales representative"],
                "strong": ["sales", "business development", "account management"],
                "boost": ["crm", "salesforce", "negotiation"],
                "weight": 1.0
            },
            RoleDomain.SALES_MANAGER: {
                "exact": ["sales manager", "sales director"],
                "strong": ["sales leadership", "sales team lead"],
                "boost": ["team management", "revenue", "quota"],
                "weight": 1.0
            },
            RoleDomain.EXECUTIVE: {
                "exact": ["chief executive officer", "chief technology officer", "chief operating officer"],
                "strong": ["ceo", "cto", "cfo", "coo", "chief", "vp", "vice president", "director"],
                "boost": ["head of", "executive", "senior director"],
                "weight": 1.0
            },
            RoleDomain.HR_PROFESSIONAL: {
                "exact": ["human resources manager", "hr manager", "talent acquisition manager"],
                "strong": ["hr", "human resources", "recruiter", "talent acquisition"],
                "boost": ["hiring", "recruiting", "people operations"],
                "weight": 1.0
            },
        }
        
        # Calculate scores for each role domain
        scores: Dict[RoleDomain, float] = {}
        debug_info: Dict[RoleDomain, Dict] = {}
        
        for domain, patterns in ROLE_PATTERNS.items():
            score = 0.0
            matched_patterns = []
            
            # Exact matches (highest score)
            for pattern in patterns["exact"]:
                if pattern in role_lower:
                    score += 3.0 * patterns["weight"]
                    matched_patterns.append(f"exact:{pattern}")
            
            # Strong matches
            for pattern in patterns["strong"]:
                if pattern in role_lower:
                    score += 2.0 * patterns["weight"]
                    matched_patterns.append(f"strong:{pattern}")
            
            # Boost from tech stack
            for tech in patterns["boost"]:
                if tech in tech_text:
                    score += 0.5 * patterns["weight"]
                    matched_patterns.append(f"boost:{tech}")
            
            scores[domain] = score
            debug_info[domain] = {
                "score": score,
                "matches": matched_patterns
            }
        
        # Special handling: Backend boost for Java/Python/Go WITHOUT frontend indicators
        backend_indicators = ["java", "python", "go", "rust", "c++", "node", "backend"]
        frontend_indicators = ["react", "angular", "vue", "frontend", "css", "html"]
        
        has_backend_tech = any(tech in role_lower or tech in tech_text for tech in backend_indicators)
        has_frontend_tech = any(tech in role_lower or tech in tech_text for tech in frontend_indicators)
        
        # If we have backend tech but no explicit frontend indicators, boost backend
        if has_backend_tech and not has_frontend_tech and "fullstack" not in role_lower:
            if scores.get(RoleDomain.BACKEND_ENGINEER, 0) > 0:
                scores[RoleDomain.BACKEND_ENGINEER] += 2.0
                debug_info[RoleDomain.BACKEND_ENGINEER]["matches"].append("backend_tech_boost")
            elif scores.get(RoleDomain.GENERAL, 0) == 0:
                # No strong match yet, check if this is an engineer/developer role
                if any(term in role_lower for term in ["engineer", "developer", "programmer"]):
                    scores[RoleDomain.BACKEND_ENGINEER] = 1.5  # Give it a base score
                    debug_info[RoleDomain.BACKEND_ENGINEER] = {
                        "score": 1.5,
                        "matches": ["inferred_from_backend_tech"]
                    }
        
        # Find highest scoring domain
        if scores:
            best_domain = max(scores.items(), key=lambda x: x[1])
            if best_domain[1] > 0:
                # Store debug info for analysis
                self._last_classification_debug = {
                    "input": role_title,
                    "tech_stack": tech_stack,
                    "scores": {k.value: v for k, v in scores.items()},
                    "winner": best_domain[0].value,
                    "confidence": best_domain[1],
                    "details": {k.value: v for k, v in debug_info.items()}
                }
                return best_domain[0]
        
        # Fallback: General developer/engineer classification
        if any(term in role_lower for term in ["developer", "engineer", "programmer", "software"]):
            # Check tech stack for domain clues
            if any(t in tech_text for t in ["react", "angular", "vue", "frontend", "css", "html", "javascript", "typescript"]):
                self._last_classification_debug = {
                    "input": role_title,
                    "fallback": "frontend_from_tech_stack"
                }
                return RoleDomain.FRONTEND_ENGINEER
            if any(t in tech_text for t in ["node", "java", "python", "go", "rust", "database", "sql", "nosql"]):
                self._last_classification_debug = {
                    "input": role_title,
                    "fallback": "backend_from_tech_stack"
                }
                return RoleDomain.BACKEND_ENGINEER
            self._last_classification_debug = {
                "input": role_title,
                "fallback": "fullstack_default"
            }
            return RoleDomain.FULLSTACK_ENGINEER
        
        self._last_classification_debug = {
            "input": role_title,
            "fallback": "general"
        }
        return RoleDomain.GENERAL
    
    def get_last_classification_debug(self) -> Dict:
        """Get debug info from last role classification."""
        return getattr(self, '_last_classification_debug', {})
    
    def get_domain_priorities(self, role_domain: RoleDomain) -> Dict[AssessmentDomain, float]:
        """Get assessment domain priorities for a role domain."""
        return self.ROLE_DOMAIN_PRIORITIES.get(role_domain, self.ROLE_DOMAIN_PRIORITIES[RoleDomain.GENERAL])
    
    def get_assessment_classification(self, assessment_id: str) -> Optional[AssessmentClassification]:
        """Get classification for an assessment by ID."""
        return self._classifications.get(assessment_id)
    
    def get_assessments_by_domain(self, domain: AssessmentDomain) -> List[str]:
        """Get all assessment IDs in a specific domain."""
        return [
            aid for aid, domains in self._assessment_domains.items()
            if domain in domains
        ]
    
    def calculate_domain_alignment(
        self, 
        assessment_id: str, 
        role_domain: RoleDomain
    ) -> Tuple[float, str]:
        """
        Calculate alignment score between assessment and role domain.
        Returns (score, reasoning).
        """
        classification = self._classifications.get(assessment_id)
        if not classification:
            return 0.5, "Unknown assessment"
        
        priorities = self.get_domain_priorities(role_domain)
        
        # Calculate weighted alignment
        alignment_score = 0.0
        max_possible = 0.0
        
        for domain, priority in priorities.items():
            domain_score = classification.domain_scores.get(domain, 0)
            alignment_score += domain_score * priority
            max_possible += priority
        
        # Normalize
        normalized_score = alignment_score / max_possible if max_possible > 0 else 0.5
        
        # Generate reasoning
        primary_priority = priorities.get(classification.primary_domain, 0)
        if primary_priority >= 0.8:
            reasoning = f"Critical {classification.primary_domain.value} assessment for {role_domain.value}"
        elif primary_priority >= 0.6:
            reasoning = f"Relevant {classification.primary_domain.value} evaluation"
        elif primary_priority >= 0.4:
            reasoning = f"Supporting {classification.primary_domain.value} insight"
        else:
            reasoning = f"Secondary {classification.primary_domain.value} measurement"
        
        return normalized_score, reasoning
    
    def get_taxonomy_stats(self) -> Dict:
        """Get statistics about the taxonomy."""
        if not self._classifications:
            return {"total_assessments": 0}
        
        domain_counts = {}
        for classification in self._classifications.values():
            domain = classification.primary_domain
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        return {
            "total_assessments": len(self._classifications),
            "domain_distribution": domain_counts,
            "avg_technical_depth": sum(
                c.technical_depth for c in self._classifications.values()
            ) / len(self._classifications),
            "avg_behavioral_relevance": sum(
                c.behavioral_relevance for c in self._classifications.values()
            ) / len(self._classifications),
        }
