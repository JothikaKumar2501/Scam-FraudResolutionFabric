"""
Enhanced Strands Multi-Agent System with AgentCore Memory Integration
Extends your existing streaming implementation with memory capabilities
"""

import os
from typing import Dict, Any, Generator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import your existing streaming implementation
from strands_langgraph_agent import (
    stream_strands_steps as original_stream_strands_steps,
    run_strands_multi_agent as original_run_strands_multi_agent,
    run_strands_pipeline as original_run_strands_pipeline
)

# Import AgentCore memory integration
from agent_core_memory_integration import AgentCoreMemoryIntegration

class EnhancedStrandsWithMemory:
    """
    Enhanced version of your Strands pipeline with AgentCore memory integration
    Maintains all existing functionality while adding memory capabilities
    """
    
    def __init__(self):
        self.memory_integration = AgentCoreMemoryIntegration()
        print("🧠 Enhanced Strands pipeline initialized with AgentCore memory")
    
    def stream_strands_steps_with_memory(self, alert_or_state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """
        Enhanced streaming that adds memory storage without affecting existing functionality
        """
        # Get case ID for memory operations
        if 'transaction' in alert_or_state:
            case_id = (
                alert_or_state.get('transaction', {}).get('alertId') or 
                alert_or_state.get('transaction', {}).get('alert_id') or 
                f"case_{int(time.time())}"
            )
        else:
            case_id = (
                alert_or_state.get('alertId') or 
                alert_or_state.get('alert_id') or 
                f"case_{int(time.time())}"
            )
        
        print(f"🔍 Processing case with memory: {case_id}")
        
        # Store initial transaction data
        if self.memory_integration:
            transaction_data = str(alert_or_state.get('transaction', alert_or_state))
            self.memory_integration.store_context_summary(
                case_id=case_id,
                context_data=f"Initial transaction alert: {transaction_data}",
                agent_name="InitialAlert"
            )
        
        # Use the original streaming function
        for state in original_stream_strands_steps(alert_or_state):
            # Add memory storage at key points without disrupting the stream
            try:
                self._store_state_to_memory(state, case_id)
            except Exception as e:
                print(f"⚠️ Memory storage error (non-blocking): {e}")
            
            # Always yield the state unchanged
            yield state
    
    def _store_state_to_memory(self, state: Dict[str, Any], case_id: str):
        """Store relevant state information to memory"""
        if not self.memory_integration:
            return
        
        # Store context summaries when they're available
        context_fields = [
            ('transaction_context', 'TransactionContextAgent'),
            ('customer_context', 'CustomerInfoAgent'),
            ('merchant_context', 'MerchantInfoAgent'),
            ('anomaly_context', 'BehavioralPatternAgent'),
            ('threat_intelligence', 'IntelAgent')
        ]
        
        for field, agent_name in context_fields:
            if field in state and not hasattr(state, f'_stored_{field}'):
                context_data = str(state[field])
                self.memory_integration.store_context_summary(
                    case_id=case_id,
                    context_data=context_data,
                    agent_name=agent_name
                )
                # Mark as stored to avoid duplicates
                setattr(state, f'_stored_{field}', True)
        
        # Store risk assessments
        risk_fields = ['risk_assessment', 'risk_summary_context', 'final_risk_determination']
        for field in risk_fields:
            if field in state and not hasattr(state, f'_stored_{field}'):
                risk_data = str(state[field])
                self.memory_integration.store_risk_assessment(
                    case_id=case_id,
                    assessment=risk_data,
                    agent_name="RiskAssessorAgent"
                )
                setattr(state, f'_stored_{field}', True)
        
        # Store dialogue interactions
        if 'dialogue_history' in state and not hasattr(state, '_stored_dialogue'):
            dialogue_data = str(state['dialogue_history'])
            self.memory_integration.store_customer_interaction(
                case_id=case_id,
                interaction=dialogue_data,
                agent_name="DialogueAgent"
            )
            setattr(state, '_stored_dialogue', True)
        
        # Store policy decisions
        if 'policy_decision' in state and not hasattr(state, '_stored_policy'):
            policy_data = str(state['policy_decision'])
            self.memory_integration.store_policy_decision(
                case_id=case_id,
                decision=policy_data,
                agent_name="PolicyDecisionAgent"
            )
            setattr(state, '_stored_policy', True)
    
    def run_strands_pipeline_with_memory(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced pipeline that adds memory capabilities to the original implementation
        """
        # Run the original pipeline
        result = original_run_strands_pipeline(alert)
        
        # Store final result to memory
        if self.memory_integration:
            case_id = (
                alert.get('alertId') or 
                alert.get('alert_id') or 
                f"case_{int(time.time())}"
            )
            
            # Store final pipeline result
            final_summary = f"Pipeline completed. Final state: {str(result)[:500]}..."
            self.memory_integration.store_agent_summary(
                case_id=case_id,
                summary=final_summary,
                agent_name="PipelineCompletion"
            )
        
        return result
    
    def get_case_history(self, case_id: str) -> str:
        """Get the complete memory history for a case"""
        if not self.memory_integration:
            return "Memory integration not available"
        
        return self.memory_integration.get_case_summary(case_id)
    
    def search_case_patterns(self, case_id: str, query: str) -> list:
        """Search for specific patterns in case memory"""
        if not self.memory_integration:
            return []
        
        return self.memory_integration.search_memories(case_id, query)

# Create global instance for easy import
enhanced_strands = EnhancedStrandsWithMemory()

# Convenience functions that maintain compatibility with existing code
def stream_strands_steps_with_memory(alert_or_state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
    """Enhanced streaming with memory - drop-in replacement for existing function"""
    return enhanced_strands.stream_strands_steps_with_memory(alert_or_state)

def run_strands_pipeline_with_memory(alert: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced pipeline with memory - drop-in replacement for existing function"""
    return enhanced_strands.run_strands_pipeline_with_memory(alert)

def get_case_history(case_id: str) -> str:
    """Get case history from memory"""
    return enhanced_strands.get_case_history(case_id)

def search_case_patterns(case_id: str, query: str) -> list:
    """Search case patterns in memory"""
    return enhanced_strands.search_case_patterns(case_id, query)

# For backward compatibility - these functions work exactly like the originals
def stream_strands_steps(alert_or_state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
    """Original streaming function - unchanged"""
    return original_stream_strands_steps(alert_or_state)

def run_strands_pipeline(alert: Dict[str, Any]) -> Dict[str, Any]:
    """Original pipeline function - unchanged"""
    return original_run_strands_pipeline(alert)

if __name__ == "__main__":
    # Test the enhanced pipeline
    import time
    
    test_alert = {
        'alertId': 'TEST_ENHANCED_001',
        'amount': 5000,
        'recipient': 'unknown_account',
        'priority': 'HIGH',
        'ruleId': 'FRAUD_RULE_001'
    }
    
    print("🧪 Testing Enhanced Strands Pipeline with Memory")
    print("=" * 60)
    
    # Test streaming with memory
    print("🔄 Testing streaming with memory...")
    final_state = None
    for state in stream_strands_steps_with_memory(test_alert):
        final_state = state
        print(f"   Step {state.get('current_step', '?')}: {state.get('streaming_agent', 'Processing')}...")
    
    print(f"✅ Streaming completed. Final step: {final_state.get('current_step', 'Unknown')}")
    
    # Test case history retrieval
    print("\n📖 Testing case history retrieval...")
    case_history = get_case_history('TEST_ENHANCED_001')
    print(f"   History length: {len(case_history)} characters")
    print(f"   History preview: {case_history[:200]}...")
    
    print("\n🎉 Enhanced pipeline test completed!")