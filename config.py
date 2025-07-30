"""
Configuration system for the fraud detection system.
Removes hardcoded values and provides environment-based settings.
"""

import os
from typing import Dict, Any, List

class Config:
    """Configuration class for the fraud detection system"""
    
    def __init__(self):
        # Load from environment variables with defaults
        self.max_dialogue_turns = int(os.getenv('MAX_DIALOGUE_TURNS', '12'))
        self.max_context_turns = int(os.getenv('MAX_CONTEXT_TURNS', '10'))
        self.semantic_similarity_threshold = float(os.getenv('SEMANTIC_SIMILARITY_THRESHOLD', '0.7'))
        self.risk_finalization_threshold = float(os.getenv('RISK_FINALIZATION_THRESHOLD', '0.7'))
        self.max_tokens_per_response = int(os.getenv('MAX_TOKENS_PER_RESPONSE', '1024'))
        self.max_tokens_per_question = int(os.getenv('MAX_TOKENS_PER_QUESTION', '256'))
        
        # Agent-specific settings
        self.agent_settings = {
            'DialogueAgent': {
                'max_turns': self.max_dialogue_turns,
                'semantic_similarity_threshold': self.semantic_similarity_threshold,
                'max_tokens': self.max_tokens_per_question
            },
            'RiskAssessorAgent': {
                'max_tokens': self.max_tokens_per_response,
                'finalization_threshold': self.risk_finalization_threshold
            },
            'PolicyDecisionAgent': {
                'max_tokens': self.max_tokens_per_response
            },
            'TriageAgent': {
                'max_tokens': self.max_tokens_per_response
            }
        }
        
        # Conversation management settings
        self.conversation_settings = {
            'context_compression_threshold': self.max_context_turns,
            'max_recent_turns': 5,
            'summary_max_tokens': 256
        }
        
        # Fact extraction settings
        self.fact_extraction_settings = {
            'confidence_thresholds': {
                'verified': 0.9,
                'password_change': 0.8,
                'recipient': 0.8,
                'authorization': 0.9,
                'device': 0.8,
                'purpose': 0.8,
                'relationship': 0.8,
                'amount': 0.8,
                'contact_method': 0.8,
                'social_engineering': 0.8,
                'pattern': 0.7,
                'promised_returns': 0.9,
                'confidentiality': 0.8,
                'urgency_tactics': 0.8
            },
            'required_facts': [
                'verified',
                'password_change',
                'recipient',
                'authorization',
                'device',
                'purpose',
                'relationship',
                'amount',
                'contact_method',
                'social_engineering',
                'pattern',
                'promised_returns',
                'confidentiality',
                'urgency_tactics'
            ]
        }
        
        # Decision flow settings
        self.decision_settings = {
            'finalization_indicators': {
                'positive': ['finalize -', 'finalize:', 'finalize.', 'finalize ', 'finalize\n'],
                'negative': ['do not finalize', 'not finalize', 'cannot finalize', 'should not finalize', 'insufficient information', 'continue questioning']
            },
            'risk_decisions': ['CONTINUE_QUESTIONING', 'DO_NOT_FINALIZE', 'FINALIZE'],
            'max_turns_before_force_finalize': 12
        }
        
        # Error handling settings
        self.error_settings = {
            'max_retries': 3,
            'retry_delay': 1.0,
            'fallback_enabled': True,
            'logging_level': os.getenv('LOGGING_LEVEL', 'INFO')
        }
        
        # Performance settings
        self.performance_settings = {
            'enable_caching': os.getenv('ENABLE_CACHING', 'true').lower() == 'true',
            'cache_ttl': int(os.getenv('CACHE_TTL', '300')),  # 5 minutes
            'async_processing': os.getenv('ASYNC_PROCESSING', 'false').lower() == 'true',
            'batch_size': int(os.getenv('BATCH_SIZE', '10'))
        }
    
    def get_agent_setting(self, agent_name: str, setting: str, default=None):
        """Get a specific setting for an agent"""
        return self.agent_settings.get(agent_name, {}).get(setting, default)
    
    def get_fact_confidence_threshold(self, fact_type: str) -> float:
        """Get confidence threshold for a fact type"""
        return self.fact_extraction_settings['confidence_thresholds'].get(fact_type, 0.8)
    
    def get_required_facts(self) -> List[str]:
        """Get list of required facts"""
        return self.fact_extraction_settings['required_facts'].copy()
    
    def is_positive_finalization(self, text: str) -> bool:
        """Check if text contains positive finalization indicators"""
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in self.decision_settings['finalization_indicators']['positive'])
    
    def is_negative_finalization(self, text: str) -> bool:
        """Check if text contains negative finalization indicators"""
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in self.decision_settings['finalization_indicators']['negative'])
    
    def should_finalize(self, text: str) -> bool:
        """Check if text indicates finalization should occur"""
        return self.is_positive_finalization(text) and not self.is_negative_finalization(text)
    
    def get_decision_threshold(self, decision_type: str) -> float:
        """Get threshold for decision types"""
        if decision_type == 'risk_finalization':
            return self.risk_finalization_threshold
        elif decision_type == 'semantic_similarity':
            return self.semantic_similarity_threshold
        else:
            return 0.7  # Default threshold

# Global configuration instance
config = Config() 