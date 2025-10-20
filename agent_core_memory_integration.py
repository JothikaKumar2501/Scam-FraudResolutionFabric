"""
AgentCore Memory Integration for Fraud Detection Pipeline
Provides memory storage and retrieval without affecting existing streaming
"""

import os
import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# AgentCore Memory imports
try:
    from bedrock_agentcore_starter_toolkit.operations.memory.manager import MemoryManager
    from bedrock_agentcore.memory.session import MemorySessionManager
    from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole
    from bedrock_agentcore_starter_toolkit.operations.memory.models.strategies import SemanticStrategy
    AGENTCORE_AVAILABLE = True
except ImportError:
    AGENTCORE_AVAILABLE = False

class AgentCoreMemoryIntegration:
    """
    AgentCore Memory integration for fraud detection agents
    Stores and retrieves conversation context, risk assessments, and decisions
    """
    
    def __init__(self, region_name=None, memory_id=None, memory_name="FraudDetectionMemory"):
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self.memory_name = memory_name
        self.memory_manager = None
        self.memory_id = memory_id or os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
        self.sessions = {}  # Cache session managers by case_id
        
        if AGENTCORE_AVAILABLE:
            self._initialize_memory()
        else:
            print("⚠️ AgentCore Memory not available - memory operations will be skipped")
    
    def _initialize_memory(self):
        """Initialize AgentCore memory resource"""
        try:
            self.memory_manager = MemoryManager(region_name=self.region_name)
            
            if self.memory_id:
                # Use existing memory resource
                print(f"✅ AgentCore Memory initialized with existing ID: {self.memory_id}")
            else:
                # Create new memory resource with semantic strategy
                memory = self.memory_manager.get_or_create_memory(
                    name=self.memory_name,
                    description="Fraud detection pipeline memory store",
                    strategies=[
                        SemanticStrategy(
                            name="fraudDetectionSemanticMemory",
                            namespaces=['/strategies/{memoryStrategyId}/actors/{actorId}'],
                        )
                    ]
                )
                
                self.memory_id = memory.get('id')
                print(f"✅ AgentCore Memory created: {self.memory_id}")
            
        except Exception as e:
            print(f"❌ Failed to initialize AgentCore Memory: {e}")
            self.memory_manager = None
    
    def _get_session_manager(self, case_id: str) -> Optional[MemorySessionManager]:
        """Get or create session manager for a case"""
        if not AGENTCORE_AVAILABLE or not self.memory_id:
            return None
        
        if case_id not in self.sessions:
            try:
                session_manager = MemorySessionManager(
                    memory_id=self.memory_id,
                    region_name=self.region_name
                )
                self.sessions[case_id] = session_manager
            except Exception as e:
                print(f"❌ Failed to create session manager for {case_id}: {e}")
                return None
        
        return self.sessions[case_id]
    
    def store_context_summary(self, case_id: str, context_data: str, agent_name: str) -> bool:
        """Store context analysis from agents like TransactionContextAgent"""
        session_manager = self._get_session_manager(case_id)
        if not session_manager:
            return False
        
        try:
            session = session_manager.create_memory_session(
                actor_id=f"agent_{agent_name.lower()}",
                session_id=f"{case_id}_context"
            )
            
            message = f"Context Analysis by {agent_name}: {context_data}"
            session.add_turns(
                messages=[
                    ConversationalMessage(message, MessageRole.ASSISTANT)
                ]
            )
            
            print(f"✅ Stored context from {agent_name} for case {case_id}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to store context for {case_id}: {e}")
            return False
    
    def store_risk_assessment(self, case_id: str, assessment: str, confidence: float = 1.0, agent_name: str = "RiskAssessor") -> bool:
        """Store risk assessment results"""
        session_manager = self._get_session_manager(case_id)
        if not session_manager:
            return False
        
        try:
            session = session_manager.create_memory_session(
                actor_id=f"risk_assessor",
                session_id=f"{case_id}_risk"
            )
            
            timestamp = datetime.now().isoformat()
            message = f"Risk Assessment [{timestamp}] by {agent_name} (confidence: {confidence}): {assessment}"
            
            session.add_turns(
                messages=[
                    ConversationalMessage(message, MessageRole.ASSISTANT)
                ]
            )
            
            print(f"✅ Stored risk assessment for case {case_id}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to store risk assessment for {case_id}: {e}")
            return False
    
    def store_customer_interaction(self, case_id: str, interaction: str, agent_name: str = "DialogueAgent") -> bool:
        """Store customer dialogue interactions"""
        session_manager = self._get_session_manager(case_id)
        if not session_manager:
            return False
        
        try:
            session = session_manager.create_memory_session(
                actor_id=f"customer_interaction",
                session_id=f"{case_id}_dialogue"
            )
            
            message = f"Customer Interaction by {agent_name}: {interaction}"
            session.add_turns(
                messages=[
                    ConversationalMessage(message, MessageRole.USER)
                ]
            )
            
            print(f"✅ Stored customer interaction for case {case_id}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to store customer interaction for {case_id}: {e}")
            return False
    
    def store_policy_decision(self, case_id: str, decision: str, agent_name: str = "PolicyDecisionAgent") -> bool:
        """Store final policy decisions"""
        session_manager = self._get_session_manager(case_id)
        if not session_manager:
            return False
        
        try:
            session = session_manager.create_memory_session(
                actor_id=f"policy_decision",
                session_id=f"{case_id}_policy"
            )
            
            timestamp = datetime.now().isoformat()
            message = f"Policy Decision [{timestamp}] by {agent_name}: {decision}"
            
            session.add_turns(
                messages=[
                    ConversationalMessage(message, MessageRole.ASSISTANT)
                ]
            )
            
            print(f"✅ Stored policy decision for case {case_id}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to store policy decision for {case_id}: {e}")
            return False
    
    def store_agent_summary(self, case_id: str, summary: str, agent_name: str) -> bool:
        """Store general agent summaries (triage, feedback, etc.)"""
        session_manager = self._get_session_manager(case_id)
        if not session_manager:
            return False
        
        try:
            session = session_manager.create_memory_session(
                actor_id=f"agent_{agent_name.lower()}",
                session_id=f"{case_id}_summary"
            )
            
            message = f"Agent Summary by {agent_name}: {summary}"
            session.add_turns(
                messages=[
                    ConversationalMessage(message, MessageRole.ASSISTANT)
                ]
            )
            
            print(f"✅ Stored summary from {agent_name} for case {case_id}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to store agent summary for {case_id}: {e}")
            return False
    
    def retrieve_memories(self, case_id: str, limit: int = 10) -> List[Dict]:
        """Retrieve all memories for a case"""
        session_manager = self._get_session_manager(case_id)
        if not session_manager:
            return []
        
        try:
            # Try different session types
            session_types = ["context", "risk", "dialogue", "policy", "summary"]
            all_memories = []
            
            for session_type in session_types:
                try:
                    session = session_manager.create_memory_session(
                        actor_id=f"retrieval_{session_type}",
                        session_id=f"{case_id}_{session_type}"
                    )
                    
                    # Get conversation turns
                    turns = session.get_last_k_turns(k=limit)
                    for turn in turns:
                        all_memories.append({
                            'type': session_type,
                            'content': turn,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                except Exception:
                    continue
            
            return all_memories[:limit]
            
        except Exception as e:
            print(f"❌ Failed to retrieve memories for {case_id}: {e}")
            return []
    
    def search_memories(self, case_id: str, query: str, limit: int = 5) -> List[Dict]:
        """Search memories using semantic search"""
        session_manager = self._get_session_manager(case_id)
        if not session_manager:
            return []
        
        try:
            session = session_manager.create_memory_session(
                actor_id=f"search_agent",
                session_id=f"{case_id}_search"
            )
            
            # Perform semantic search
            search_results = session.search_long_term_memories(
                query=query,
                namespace_prefix="/",
                top_k=limit
            )
            
            formatted_results = []
            for result in search_results:
                formatted_results.append({
                    'query': query,
                    'content': result,
                    'timestamp': datetime.now().isoformat()
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"❌ Failed to search memories for {case_id}: {e}")
            return []
    
    def get_case_summary(self, case_id: str) -> str:
        """Get a comprehensive summary of all memories for a case"""
        memories = self.retrieve_memories(case_id, limit=20)
        
        if not memories:
            return f"No memories found for case {case_id}"
        
        summary_parts = [f"Case {case_id} Memory Summary:"]
        
        # Group by type
        by_type = {}
        for memory in memories:
            mem_type = memory.get('type', 'unknown')
            if mem_type not in by_type:
                by_type[mem_type] = []
            by_type[mem_type].append(memory)
        
        for mem_type, mems in by_type.items():
            summary_parts.append(f"\n{mem_type.upper()}:")
            for mem in mems[:3]:  # Limit to 3 per type
                content = str(mem.get('content', ''))[:100]
                summary_parts.append(f"  - {content}...")
        
        return "\n".join(summary_parts)
    
    def cleanup_case_memories(self, case_id: str) -> bool:
        """Clean up memories for a specific case (optional)"""
        # Note: AgentCore doesn't have direct delete operations for individual sessions
        # This would typically be handled by memory retention policies
        print(f"ℹ️ Memory cleanup for {case_id} handled by AgentCore retention policies")
        return True

# Global instance for easy import
agent_core_memory = AgentCoreMemoryIntegration() if AGENTCORE_AVAILABLE else None

# Convenience functions
def store_context(case_id: str, context: str, agent: str) -> bool:
    """Convenience function to store context"""
    if agent_core_memory:
        return agent_core_memory.store_context_summary(case_id, context, agent)
    return False

def store_risk(case_id: str, assessment: str, confidence: float = 1.0) -> bool:
    """Convenience function to store risk assessment"""
    if agent_core_memory:
        return agent_core_memory.store_risk_assessment(case_id, assessment, confidence)
    return False

def search_case_history(case_id: str, query: str) -> List[Dict]:
    """Convenience function to search case history"""
    if agent_core_memory:
        return agent_core_memory.search_memories(case_id, query)
    return []

def get_case_memories(case_id: str) -> List[Dict]:
    """Convenience function to get all case memories"""
    if agent_core_memory:
        return agent_core_memory.retrieve_memories(case_id)
    return []