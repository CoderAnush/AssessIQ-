"""
Conversational Memory System for AssessIQ AI.

Maintains persistent recruiter context across conversation turns.

Supports:
- Remember previous recommendations
- Remember role context
- Support follow-up refinements:
  * "more leadership focused"
  * "less technical"
  * "now compare first two"
  * "what about junior candidates"
  * etc.

Maintains session-level recruiter context.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from app.models.assessment import AssessmentWithMetadata
from app.services.conversation_analyzer import HiringContext
from app.logging.logger import get_logger

logger = get_logger("conversation_memory")


@dataclass
class RecommendationMemory:
    """Stored recommendation with metadata."""
    assessment_id: str
    name: str
    score: float
    rank: int
    category: str
    domain: str
    explanation: str
    timestamp: datetime


@dataclass
class ConversationSession:
    """Complete conversation session state."""
    session_id: str
    created_at: datetime
    last_activity: datetime
    
    # Context
    role: Optional[str] = None
    seniority: Optional[str] = None
    tech_stack: List[str] = field(default_factory=list)
    soft_skills: List[str] = field(default_factory=list)
    leadership_needed: bool = False
    communication_needed: bool = False
    
    # Recommendations history
    recommendations_history: List[List[RecommendationMemory]] = field(default_factory=list)
    current_recommendations: List[RecommendationMemory] = field(default_factory=list)
    
    # Refinement history
    refinements: List[Dict[str, Any]] = field(default_factory=list)
    
    # Comparison history
    comparisons_made: List[Dict[str, Any]] = field(default_factory=list)
    
    # Context evolution
    context_evolution: List[Dict[str, Any]] = field(default_factory=list)


class ConversationMemoryStore:
    """
    Persistent conversational memory for recruiter sessions.
    
    Maintains context across multiple turns and supports:
    - Recommendation recall
    - Refinement tracking
    - Context evolution
    """
    
    def __init__(self, ttl_minutes: int = 60):
        """
        Initialize memory store.
        
        Args:
            ttl_minutes: Time-to-live for sessions in minutes
        """
        self._sessions: Dict[str, ConversationSession] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
    
    def get_or_create_session(self, session_id: str) -> ConversationSession:
        """Get existing session or create new one."""
        self._cleanup_expired()
        
        if session_id not in self._sessions:
            now = datetime.now()
            self._sessions[session_id] = ConversationSession(
                session_id=session_id,
                created_at=now,
                last_activity=now
            )
            logger.info(f"Created new conversation session: {session_id}")
        else:
            self._sessions[session_id].last_activity = datetime.now()
        
        return self._sessions[session_id]
    
    def store_recommendations(
        self,
        session_id: str,
        recommendations: List[Dict],
        context: HiringContext
    ) -> None:
        """Store recommendations in session memory."""
        session = self.get_or_create_session(session_id)
        
        # Update context
        session.role = context.role
        session.seniority = context.seniority
        session.tech_stack = list(context.tech_stack)
        session.soft_skills = list(context.soft_skills)
        session.leadership_needed = context.leadership_needs
        session.communication_needed = "communication" in [s.lower() for s in context.soft_skills]
        
        # Convert to memory format
        mem_recs = []
        for i, rec in enumerate(recommendations, 1):
            mem_rec = RecommendationMemory(
                assessment_id=rec.get("id", ""),
                name=rec.get("name", ""),
                score=rec.get("score", 0.0),
                rank=i,
                category=rec.get("category", ""),
                domain=rec.get("domain", ""),
                explanation=rec.get("explanation", ""),
                timestamp=datetime.now()
            )
            mem_recs.append(mem_rec)
        
        # Store in history
        if session.current_recommendations:
            session.recommendations_history.append(session.current_recommendations)
        
        session.current_recommendations = mem_recs
        session.last_activity = datetime.now()
        
        logger.info(f"Stored {len(mem_recs)} recommendations in session {session_id}")
    
    def get_current_recommendations(self, session_id: str) -> List[RecommendationMemory]:
        """Get current recommendations from session."""
        session = self._sessions.get(session_id)
        if session:
            session.last_activity = datetime.now()
            return session.current_recommendations
        return []
    
    def get_recommendation_by_rank(
        self, 
        session_id: str, 
        rank: int
    ) -> Optional[RecommendationMemory]:
        """Get recommendation by rank position (1-indexed)."""
        recs = self.get_current_recommendations(session_id)
        for rec in recs:
            if rec.rank == rank:
                return rec
        return None
    
    def get_top_n_recommendations(
        self, 
        session_id: str, 
        n: int = 2
    ) -> List[RecommendationMemory]:
        """Get top N recommendations."""
        recs = self.get_current_recommendations(session_id)
        return sorted(recs, key=lambda r: r.rank)[:n]
    
    def record_refinement(
        self,
        session_id: str,
        refinement_type: str,
        changes: Dict[str, Any]
    ) -> None:
        """Record a refinement made by the user."""
        session = self.get_or_create_session(session_id)
        
        refinement = {
            "type": refinement_type,
            "changes": changes,
            "timestamp": datetime.now(),
            "previous_recommendations": [
                {"id": r.assessment_id, "name": r.name, "rank": r.rank}
                for r in session.current_recommendations
            ]
        }
        
        session.refinements.append(refinement)
        session.last_activity = datetime.now()
        
        logger.info(f"Recorded refinement in session {session_id}: {refinement_type}")
    
    def record_comparison(
        self,
        session_id: str,
        assessment_1_id: str,
        assessment_2_id: str,
        result: Dict[str, Any]
    ) -> None:
        """Record a comparison made by the user."""
        session = self.get_or_create_session(session_id)
        
        comparison = {
            "assessment_1_id": assessment_1_id,
            "assessment_2_id": assessment_2_id,
            "result": result,
            "timestamp": datetime.now()
        }
        
        session.comparisons_made.append(comparison)
        session.last_activity = datetime.now()
        
        logger.info(f"Recorded comparison in session {session_id}")
    
    def get_context_for_followup(self, session_id: str) -> Optional[HiringContext]:
        """Reconstruct hiring context from session for follow-up queries."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        context = HiringContext()
        context.role = session.role
        context.seniority = session.seniority
        context.tech_stack = set(session.tech_stack)
        context.soft_skills = set(session.soft_skills)
        context.leadership_needs = session.leadership_needed
        
        return context
    
    def detect_refinement_intent(
        self,
        session_id: str,
        message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if message is a refinement request.
        
        Returns refinement parameters if detected, None otherwise.
        """
        message_lower = message.lower()
        
        # Refinement patterns
        refinement_patterns = {
            "more_leadership": [
                "more leadership", "add leadership", "leadership focus",
                "include leadership", "leadership assessment"
            ],
            "less_technical": [
                "less technical", "fewer technical", "reduce technical",
                "remove technical", "not technical"
            ],
            "more_technical": [
                "more technical", "add technical", "technical focus",
                "include technical", "technical assessment"
            ],
            "junior_focus": [
                "junior", "entry level", "graduate", "less experienced",
                "early career"
            ],
            "senior_focus": [
                "senior", "more experienced", "expert level", "staff level"
            ],
            "compare_request": [
                "compare", "vs", "versus", "difference between",
                "which is better", "which one"
            ],
            "communication_focus": [
                "communication", "soft skills", "interpersonal"
            ],
        }
        
        for refinement_type, patterns in refinement_patterns.items():
            if any(pattern in message_lower for pattern in patterns):
                return {
                    "type": refinement_type,
                    "original_message": message
                }
        
        return None
    
    def resolve_relative_reference(
        self,
        session_id: str,
        reference: str
    ) -> Optional[List[RecommendationMemory]]:
        """
        Resolve relative references like 'top 2', 'first two', 'them'.
        
        Returns list of referenced recommendations.
        """
        reference_lower = reference.lower()
        
        # Top 2 / First two patterns
        if any(term in reference_lower for term in ["top 2", "top two", "first 2", "first two"]):
            return self.get_top_n_recommendations(session_id, 2)
        
        # Top 3
        if any(term in reference_lower for term in ["top 3", "top three", "first 3", "first three"]):
            return self.get_top_n_recommendations(session_id, 3)
        
        # "Them" / "These" / "Those" - refers to all current recommendations
        if any(term in reference_lower for term in ["them", "these", "those", "all"]):
            return self.get_current_recommendations(session_id)
        
        # Default to top 2 for comparison queries
        if any(term in reference_lower for term in ["compare", "vs", "which is better"]):
            return self.get_top_n_recommendations(session_id, 2)
        
        return None
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of conversation session."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        return {
            "session_id": session_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "role": session.role,
            "seniority": session.seniority,
            "tech_stack": session.tech_stack,
            "soft_skills": session.soft_skills,
            "current_recommendations_count": len(session.current_recommendations),
            "recommendation_history_count": len(session.recommendations_history),
            "refinements_count": len(session.refinements),
            "comparisons_count": len(session.comparisons_made),
        }
    
    def clear_session(self, session_id: str) -> bool:
        """Clear a conversation session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Cleared session {session_id}")
            return True
        return False
    
    def _cleanup_expired(self) -> None:
        """Remove expired sessions."""
        now = datetime.now()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session.last_activity > self._ttl
        ]
        
        for sid in expired:
            del self._sessions[sid]
            logger.info(f"Cleaned up expired session: {sid}")
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        self._cleanup_expired()
        return len(self._sessions)


# Global memory store instance
_global_memory_store: Optional[ConversationMemoryStore] = None


def get_memory_store() -> ConversationMemoryStore:
    """Get global memory store instance."""
    global _global_memory_store
    if _global_memory_store is None:
        _global_memory_store = ConversationMemoryStore()
    return _global_memory_store


def generate_session_id(user_identifier: str) -> str:
    """Generate unique session ID from user identifier."""
    import hashlib
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hash_input = f"{user_identifier}_{timestamp}"
    hash_digest = hashlib.md5(hash_input.encode()).hexdigest()[:12]
    return f"session_{hash_digest}"


# Convenience functions
def store_recommendations(
    session_id: str,
    recommendations: List[Dict],
    context: HiringContext
) -> None:
    """Store recommendations in global memory store."""
    store = get_memory_store()
    store.store_recommendations(session_id, recommendations, context)


def get_current_recommendations(session_id: str) -> List[RecommendationMemory]:
    """Get current recommendations from global memory store."""
    store = get_memory_store()
    return store.get_current_recommendations(session_id)


def resolve_comparison_references(
    session_id: str,
    message: str
) -> Optional[List[RecommendationMemory]]:
    """Resolve comparison references using global memory store."""
    store = get_memory_store()
    return store.resolve_relative_reference(session_id, message)
