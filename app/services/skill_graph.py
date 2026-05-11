"""
Technical Knowledge Graph for Recruiter Intelligence.
Models relationships between languages, frameworks, tools, and domains.
"""

from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field

@dataclass
class SkillNode:
    name: str
    category: str  # language, framework, tool, domain, concept
    parents: Set[str] = field(default_factory=set)
    children: Set[str] = field(default_factory=set)
    related: Set[str] = field(default_factory=set)
    weight: float = 1.0

class SkillGraph:
    """
    Recruiter-oriented skill graph.
    Supports relationship modeling, propagation, and similarity.
    """
    
    def __init__(self):
        self.nodes: Dict[str, SkillNode] = {}
        self._initialize_graph()

    def _add_node(self, name: str, category: str, weight: float = 1.0):
        name_low = name.lower()
        if name_low not in self.nodes:
            self.nodes[name_low] = SkillNode(name=name, category=category, weight=weight)
        return self.nodes[name_low]

    def _add_relationship(self, parent: str, child: str):
        p_node = self._add_node(parent, "domain") # Default category if new
        c_node = self._add_node(child, "framework") # Default category if new
        
        p_node.children.add(child.lower())
        c_node.parents.add(parent.lower())

    def _add_related(self, skill_a: str, skill_b: str):
        node_a = self._add_node(skill_a, "concept")
        node_b = self._add_node(skill_b, "concept")
        
        node_a.related.add(skill_b.lower())
        node_b.related.add(skill_a.lower())

    def _initialize_graph(self):
        """Build the core knowledge graph."""
        
        # Python Ecosystem
        self._add_node("Python", "language", weight=1.2)
        self._add_relationship("Python", "Django")
        self._add_relationship("Python", "Flask")
        self._add_relationship("Python", "FastAPI")
        self._add_relationship("Python", "Pandas")
        self._add_relationship("Python", "NumPy")
        self._add_relationship("Python", "Pytest")
        self._add_relationship("Backend Engineering", "Python")
        
        # 2. Java Ecosystem
        self._add_node("Java", "language", weight=1.2)
        self._add_relationship("Java", "Spring")
        self._add_relationship("Java", "Hibernate")
        self._add_relationship("Java", "JUnit")
        self._add_relationship("Backend Engineering", "Java")
        
        # 3. Cloud & DevOps (Expanded)
        self._add_node("AWS", "cloud", weight=1.1)
        self._add_node("Azure", "cloud", weight=1.1)
        self._add_node("GCP", "cloud", weight=1.1)
        self._add_relationship("DevOps", "Kubernetes")
        self._add_relationship("DevOps", "Docker")
        self._add_relationship("DevOps", "Terraform")
        self._add_relationship("DevOps", "CI/CD")
        self._add_relationship("DevOps", "Monitoring")
        self._add_relationship("DevOps", "Infrastructure")
        self._add_related("Cloud Engineering", "DevOps")
        
        # 4. Frontend & Fullstack
        self._add_node("JavaScript", "language")
        self._add_node("TypeScript", "language")
        self._add_relationship("JavaScript", "React")
        self._add_relationship("JavaScript", "Angular")
        self._add_relationship("JavaScript", "Vue")
        self._add_relationship("Frontend Engineering", "React")
        self._add_relationship("Frontend Engineering", "CSS")
        self._add_relationship("Frontend Engineering", "HTML")
        self._add_related("Fullstack", "Frontend Engineering")
        self._add_related("Fullstack", "Backend Engineering")
        
        # 5. QA & SDET
        self._add_node("Selenium", "tool")
        self._add_relationship("QA Automation", "Selenium")
        self._add_relationship("QA Automation", "Cypress")
        self._add_relationship("QA Automation", "Pytest")
        self._add_related("SDET", "QA Automation")
        self._add_related("SDET", "Software Engineering")
        
        # 6. Data & ML
        self._add_node("Machine Learning", "domain")
        self._add_relationship("Machine Learning", "PyTorch")
        self._add_relationship("Machine Learning", "TensorFlow")
        self._add_relationship("Data Science", "Machine Learning")
        self._add_relationship("ML Engineering", "Machine Learning")
        self._add_relationship("ML Engineering", "DevOps")
        
        # 7. Management & Leadership (New)
        self._add_node("Leadership", "domain", weight=1.3)
        self._add_relationship("Leadership", "People Management")
        self._add_relationship("Leadership", "Strategic Thinking")
        self._add_relationship("Leadership", "Stakeholder Management")
        self._add_relationship("Leadership", "Coaching")
        self._add_relationship("Engineering Manager", "Leadership")
        self._add_relationship("Engineering Manager", "Technical Strategy")
        self._add_relationship("Product Manager", "Stakeholder Management")
        self._add_relationship("Product Manager", "Product Strategy")
        self._add_relationship("Executive", "Strategic Thinking")
        
        # 8. Business & Support
        self._add_node("Sales", "domain", weight=1.2)
        self._add_relationship("Sales", "Negotiation")
        self._add_relationship("Sales", "Lead Generation")
        self._add_relationship("Customer Support", "Communication")
        self._add_relationship("Customer Support", "Empathy")
        self._add_relationship("Customer Support", "Problem Solving")
        
        # 9. Modern Technical Adjacency (Phase 2 Expansion)
        # Python Modern
        self._add_node("FastAPI", "framework", weight=1.1)
        self._add_relationship("FastAPI", "Python")
        self._add_related("FastAPI", "APIs")
        self._add_related("FastAPI", "Microservices")
        
        self._add_node("Django", "framework")
        self._add_relationship("Django", "Python")
        self._add_related("Django", "Web Development")
        
        # Cloud Native & Infra
        self._add_node("Kubernetes", "tool", weight=1.2)
        self._add_node("Terraform", "tool", weight=1.1)
        self._add_node("Docker", "tool")
        self._add_relationship("Cloud Engineering", "Kubernetes")
        self._add_relationship("Cloud Engineering", "Terraform")
        self._add_related("Kubernetes", "Infrastructure")
        self._add_related("Terraform", "Infrastructure as Code")
        self._add_related("Platform Engineering", "Kubernetes")
        self._add_related("Platform Engineering", "Terraform")
        self._add_related("SRE", "Kubernetes")
        
        # AI & Data Modern
        self._add_node("PyTorch", "framework", weight=1.1)
        self._add_node("TensorFlow", "framework")
        self._add_node("Spark", "tool")
        self._add_relationship("ML Engineering", "PyTorch")
        self._add_relationship("ML Engineering", "TensorFlow")
        self._add_relationship("Data Engineering", "Spark")
        self._add_related("AI Research", "PyTorch")
        
        # Emerging Languages
        self._add_node("Go", "language", weight=1.1)
        self._add_node("Rust", "language", weight=1.1)
        self._add_relationship("Backend Engineering", "Go")
        self._add_relationship("Systems Engineering", "Rust")
        
        # Modern QA
        self._add_node("Playwright", "tool")
        self._add_node("Cypress", "tool")
        self._add_relationship("QA Automation", "Playwright")
        self._add_relationship("QA Automation", "Cypress")
        
        # 10. Intent Mapping (Phase 3)
        self._add_related("Backend Architect", "Distributed Systems")
        self._add_related("Backend Architect", "Scalability")
        self._add_related("Platform Engineer", "Kubernetes")
        self._add_related("Platform Engineer", "Cloud Engineering")

    def expand_skills(self, skills: Set[str], depth: int = 1) -> Set[str]:
        """Expand a set of skills using the graph."""
        expanded = set(s.lower() for s in skills)
        
        for _ in range(depth):
            current_batch = list(expanded)
            for skill in current_batch:
                node = self.nodes.get(skill)
                if node:
                    expanded.update(node.parents)
                    expanded.update(node.children)
                    expanded.update(node.related)
                    
        return expanded

    def get_related_weight(self, skill_a: str, skill_b: str) -> float:
        """Calculate weighted similarity between two skills."""
        s_a = skill_a.lower()
        s_b = skill_b.lower()
        
        if s_a == s_b: return 1.0
        
        node_a = self.nodes.get(s_a)
        if not node_a: return 0.0
        
        if s_b in node_a.children: return 0.9
        if s_b in node_a.parents: return 0.8
        if s_b in node_a.related: return 0.7
        
        return 0.0

    def infer_intent(self, query: str) -> Dict[str, float]:
        """Infer recruiter intent based on keyword presence and graph."""
        query_low = query.lower()
        intents = {}
        
        for name, node in self.nodes.items():
            if name in query_low:
                intents[name] = 1.0 * node.weight
                # Propagate to parents with decay
                for parent in node.parents:
                    intents[parent] = max(intents.get(parent, 0), 0.6 * node.weight)
                    
        return intents
