"""
Hierarchical Enterprise Competency Taxonomy V2.
Models weighted relationships and inheritance for adaptive hiring intelligence.
"""

from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field

@dataclass
class CompetencyNode:
    name: str
    description: str
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    weight: float = 1.0
    related_skills: Set[str] = field(default_factory=set)

class CompetencyTaxonomyV2:
    """
    Hierarchical taxonomy for deep competency reasoning.
    """
    
    def __init__(self):
        self.nodes: Dict[str, CompetencyNode] = {}
        self._initialize_taxonomy()

    def _initialize_taxonomy(self):
        # 1. Technical Cluster
        self._add_node("Technical", "Core engineering competencies.", None, 1.0)
        
        # Backend Sub-cluster
        self._add_node("Backend Engineering", "Server-side development and logic.", "Technical", 1.0, 
                       {"python", "java", "go", "c#", "node.js", "ruby", "php"})
        self._add_node("APIs", "Web services and integration.", "Backend Engineering", 0.8, 
                       {"rest", "graphql", "grpc", "fastapi", "django", "spring boot"})
        self._add_node("Microservices", "Service-oriented architecture.", "Backend Engineering", 0.9, 
                       {"microservices", "distributed systems", "event-driven", "kafka", "rabbitmq"})
        self._add_node("Scalability", "High-load performance and growth.", "Backend Engineering", 1.0, 
                       {"scalability", "performance tuning", "caching", "redis", "elastic"})
        self._add_node("Reliability", "SRE and uptime principles.", "Backend Engineering", 0.9, 
                       {"reliability", "monitoring", "sre", "fault tolerance"})

        # Frontend Sub-cluster
        self._add_node("Frontend Engineering", "Client-side development.", "Technical", 1.0, 
                       {"javascript", "typescript", "html", "css", "react", "angular", "vue"})

        # Infrastructure / DevOps
        self._add_node("Cloud & DevOps", "Deployment and infrastructure.", "Technical", 1.0, 
                       {"aws", "azure", "gcp", "kubernetes", "docker", "terraform", "ci/cd"})

        # 2. Behavioral Cluster
        self._add_node("Behavioral", "Soft skills and personality traits.", None, 1.0)
        self._add_node("Communication", "Effective info exchange.", "Behavioral", 0.8, 
                       {"verbal", "writing", "presentation", "influence"})
        self._add_node("Collaboration", "Working in teams.", "Behavioral", 0.9, 
                       {"teamwork", "empathy", "relationship management"})
        self._add_node("Adaptability", "Dealing with change.", "Behavioral", 0.7, 
                       {"flexibility", "resilience", "learning agility"})

        # 3. Leadership Cluster
        self._add_node("Leadership", "Directing people and strategy.", None, 1.0)
        self._add_node("People Management", "Developing individuals.", "Leadership", 1.0, 
                       {"mentoring", "coaching", "delegation", "team building"})
        self._add_node("Strategic Thinking", "Long-term planning.", "Leadership", 1.0, 
                       {"vision", "planning", "business strategy", "executive decision"})

        # 4. Cognitive Cluster
        self._add_node("Cognitive", "General mental ability.", None, 1.0)
        self._add_node("Aptitude", "Core mental speed and logic.", "Cognitive", 1.0, 
                       {"logic", "reasoning", "problem solving", "critical thinking"})

    def _add_node(self, name: str, desc: str, parent: Optional[str], weight: float, skills: Set[str] = None):
        self.nodes[name] = CompetencyNode(name=name, description=desc, parent=parent, weight=weight, related_skills=skills or set())
        if parent and parent in self.nodes:
            self.nodes[parent].children.append(name)

    def get_inheritance(self, name: str) -> List[str]:
        """Get all parent nodes up to the root."""
        path = []
        curr = self.nodes.get(name)
        while curr and curr.parent:
            path.append(curr.parent)
            curr = self.nodes.get(curr.parent)
        return path

    def get_all_skills(self, name: str) -> Set[str]:
        """Get skills including those from child nodes."""
        skills = set(self.nodes[name].related_skills)
        for child in self.nodes[name].children:
            skills.update(self.get_all_skills(child))
        return skills

    def similarity(self, comp1: str, comp2: str) -> float:
        """Calculate similarity between two competencies (0.0 - 1.0)."""
        if comp1 == comp2: return 1.0
        n1, n2 = self.nodes.get(comp1), self.nodes.get(comp2)
        if not n1 or not n2: return 0.0
        
        # Common parent check
        if n1.parent == n2.parent and n1.parent is not None:
            return 0.5
            
        # Parent-child check
        if n1.parent == comp2 or n2.parent == comp1:
            return 0.7
            
        return 0.0
