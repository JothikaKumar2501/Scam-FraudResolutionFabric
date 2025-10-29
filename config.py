"""
Advanced Configuration System for XYZ Bank Authorized Scam Detection
Production-ready configuration with dynamic, intelligent settings
"""

import os
import json
import yaml
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
import logging

@dataclass
class AgentConfig:
    """Dynamic agent configuration with intelligent defaults"""
    name: str
    max_tokens: int = 512
    # max_tokens: int = 1024
    temperature: float = 0.1
    max_turns: int = 12
    confidence_threshold: float = 0.8
    enable_streaming: bool = True
    enable_caching: bool = True
    cache_ttl: int = 300
    retry_attempts: int = 3
    timeout_seconds: int = 30
    
    # Dynamic settings based on agent type
    specialized_prompts: Dict[str, str] = field(default_factory=dict)
    required_contexts: List[str] = field(default_factory=list)
    decision_thresholds: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set intelligent defaults based on agent name"""
        fast = os.getenv('FAST_MODE', '0').lower() in ('1','true','yes')
        if 'Risk' in self.name:
            self.max_tokens = 512 if not fast else 256
            # self.max_tokens = 2048
            self.confidence_threshold = 0.85
            self.required_contexts = ['transaction', 'customer', 'merchant', 'behavioral']
        elif 'Dialogue' in self.name:
            self.max_tokens = 256 if not fast else 160
            # self.max_tokens = 512
            self.temperature = 0.3
            self.max_turns = 15
        elif 'Policy' in self.name:
            self.max_tokens = 512 if not fast else 256
            # self.max_tokens = 1024
            self.confidence_threshold = 0.9
        elif 'Triage' in self.name:
            self.max_tokens = 512 if not fast else 256
            # self.max_tokens = 768
            self.confidence_threshold = 0.8

@dataclass
class FraudDetectionConfig:
    """Advanced fraud detection configuration"""
    # Risk Assessment
    risk_levels: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'LOW': {'score_range': (0.0, 0.3), 'action': 'monitor', 'escalation': False},
        'MEDIUM': {'score_range': (0.3, 0.7), 'action': 'investigate', 'escalation': True},
        'HIGH': {'score_range': (0.7, 1.0), 'action': 'block', 'escalation': True}
    })
    
    # Scam Typologies
    scam_typologies: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'business_email_compromise': {
            'indicators': ['vendor_impersonation', 'banking_detail_change', 'invoice_redirection'],
            'risk_score': 0.9,
            'required_verification': ['vendor_contact', 'banking_verification', 'invoice_verification']
        },
        'romance_scam': {
            'indicators': ['emotional_manipulation', 'urgent_requests', 'isolation_tactics'],
            'risk_score': 0.85,
            'required_verification': ['relationship_verification', 'purpose_clarification']
        },
        'investment_scam': {
            'indicators': ['promised_returns', 'pressure_tactics', 'fake_platforms'],
            'risk_score': 0.9,
            'required_verification': ['investment_verification', 'platform_verification']
        },
        'tech_support_scam': {
            'indicators': ['remote_access', 'urgent_technical_issues', 'payment_demands'],
            'risk_score': 0.8,
            'required_verification': ['technical_issue_verification', 'payment_purpose']
        }
    })
    
    # Regulatory Compliance
    regulatory_frameworks: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'AUSTRAC': {
            'reporting_threshold': 10000,
            'suspicious_matter_report': True,
            'enhanced_due_diligence': True
        },
        'APRA_CPG_234': {
            'information_security_controls': True,
            'customer_protection': True,
            'fraud_monitoring': True
        },
        'ASIC_RG_271': {
            'consumer_harm_prevention': True,
            'scam_prevention': True
        },
        'Banking_Code_of_Practice': {
            'customer_protection': True,
            'scam_prevention': True,
            'dispute_resolution': True
        }
    })

@dataclass
class ConversationConfig:
    """Intelligent conversation management"""
    max_dialogue_turns: int = 15
    context_compression_threshold: int = 10
    semantic_similarity_threshold: float = 0.75
    fact_extraction_confidence: float = 0.8
    early_finalization_indicators: List[str] = field(default_factory=lambda: [
        'unauthorized_transaction',
        'confirmed_scam',
        'customer_denial',
        'clear_fraud_indicators'
    ])
    
    # Dynamic fact extraction
    fact_categories: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'verification': {
            'keywords': ['verified', 'confirmed', 'identity', 'authentication'],
            'confidence_threshold': 0.9,
            'required': True
        },
        'authorization': {
            'keywords': ['authorized', 'permission', 'consent', 'approved'],
            'confidence_threshold': 0.85,
            'required': True
        },
        'recipient': {
            'keywords': ['payee', 'recipient', 'beneficiary', 'transfer_to'],
            'confidence_threshold': 0.8,
            'required': True
        },
        'purpose': {
            'keywords': ['purpose', 'reason', 'investment', 'purchase', 'payment'],
            'confidence_threshold': 0.8,
            'required': True
        },
        'relationship': {
            'keywords': ['relationship', 'known', 'trusted', 'family', 'friend'],
            'confidence_threshold': 0.8,
            'required': True
        },
        'amount': {
            'keywords': ['amount', 'value', 'sum', 'transfer_amount'],
            'confidence_threshold': 0.8,
            'required': True
        },
        'device': {
            'keywords': ['device', 'login', 'biometric', 'authentication'],
            'confidence_threshold': 0.8,
            'required': False
        },
        'social_engineering': {
            'keywords': ['pressure', 'urgency', 'threat', 'manipulation'],
            'confidence_threshold': 0.85,
            'required': False
        }
    })

class DynamicConfig:
    """Production-ready dynamic configuration system"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.getenv('CONFIG_PATH', 'config/')
        self.logger = logging.getLogger(__name__)
        
        # Load environment-based configuration
        self._load_environment_config()
        
        # Initialize sub-configurations
        self.agents = self._initialize_agent_configs()
        self.fraud_detection = FraudDetectionConfig()
        self.conversation = ConversationConfig()
        
        # Load external configuration files
        self._load_external_configs()
        
        # Validate configuration
        self._validate_config()
    
    def _load_environment_config(self):
        """Load configuration from environment variables"""
        self.environment = {
            'ENVIRONMENT': os.getenv('ENVIRONMENT', 'production'),
            'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
            'AWS_REGION': os.getenv('AWS_REGION', 'us-east-1'),
            'AWS_CLAUDE_MODEL_ID': os.getenv('AWS_CLAUDE_MODEL_ID', 'anthropic.claude-sonnet-4-20250514-v1:0'),
            'AWS_CLAUDE_INFERENCE_PROFILE_ARN': os.getenv('AWS_CLAUDE_INFERENCE_PROFILE_ARN', ''),
            'VECTOR_DB_ENDPOINT': os.getenv('VECTOR_DB_ENDPOINT', ''),
            'CACHE_ENABLED': os.getenv('CACHE_ENABLED', 'true').lower() == 'true',
            'ASYNC_PROCESSING': os.getenv('ASYNC_PROCESSING', 'true').lower() == 'true',
            'MAX_CONCURRENT_AGENTS': int(os.getenv('MAX_CONCURRENT_AGENTS', '4')),
            'REQUEST_TIMEOUT': int(os.getenv('REQUEST_TIMEOUT', '30')),
            'RETRY_ATTEMPTS': int(os.getenv('RETRY_ATTEMPTS', '3')),
        }
    
    def _initialize_agent_configs(self) -> Dict[str, AgentConfig]:
        """Initialize intelligent agent configurations"""
        agents = {}
        
        # Define agent types with intelligent defaults
        agent_types = {
            'TransactionContextAgent': {
                'specialized_prompts': {
                    'fraud_analysis': 'Analyze transaction patterns for fraud indicators',
                    'regulatory_compliance': 'Check for regulatory triggers and compliance requirements'
                },
                'required_contexts': ['transaction', 'historical_patterns'],
                'decision_thresholds': {'fraud_confidence': 0.8, 'compliance_risk': 0.7}
            },
            'CustomerInfoAgent': {
                'specialized_prompts': {
                    'vulnerability_assessment': 'Assess customer vulnerability to scams',
                    'behavioral_analysis': 'Analyze customer behavior patterns'
                },
                'required_contexts': ['customer_profile', 'transaction_history'],
                'decision_thresholds': {'vulnerability_score': 0.7, 'risk_level': 0.8}
            },
            'MerchantInfoAgent': {
                'specialized_prompts': {
                    'merchant_risk': 'Assess merchant risk and legitimacy',
                    'industry_analysis': 'Analyze industry-specific risk patterns'
                },
                'required_contexts': ['merchant_profile', 'industry_data'],
                'decision_thresholds': {'merchant_risk': 0.8, 'legitimacy_score': 0.7}
            },
            'BehavioralPatternAgent': {
                'specialized_prompts': {
                    'anomaly_detection': 'Detect behavioral anomalies and patterns',
                    'social_engineering': 'Identify social engineering indicators'
                },
                'required_contexts': ['behavioral_data', 'device_patterns'],
                'decision_thresholds': {'anomaly_score': 0.75, 'social_engineering_risk': 0.8}
            },
            'RiskSynthesizerAgent': {
                'specialized_prompts': {
                    'risk_synthesis': 'Synthesize comprehensive risk assessment',
                    'scam_typology': 'Identify specific scam typologies'
                },
                'required_contexts': ['transaction', 'customer', 'merchant', 'behavioral'],
                'decision_thresholds': {'overall_risk': 0.8, 'scam_confidence': 0.85}
            },
            'TriageAgent': {
                'specialized_prompts': {
                    'escalation_decision': 'Decide on escalation or dialogue',
                    'priority_assessment': 'Assess case priority and urgency'
                },
                'required_contexts': ['risk_assessment', 'customer_vulnerability'],
                'decision_thresholds': {'escalation_threshold': 0.7, 'priority_score': 0.8}
            },
            'DialogueAgent': {
                'specialized_prompts': {
                    'question_generation': 'Generate intelligent follow-up questions',
                    'fact_extraction': 'Extract key facts from customer responses'
                },
                'required_contexts': ['dialogue_history', 'missing_facts'],
                'decision_thresholds': {'fact_confidence': 0.8, 'finalization_ready': 0.9}
            },
            'RiskAssessorAgent': {
                'specialized_prompts': {
                    'progressive_assessment': 'Assess risk progressively during dialogue',
                    'final_determination': 'Make final scam determination'
                },
                'required_contexts': ['dialogue_progress', 'risk_indicators'],
                'decision_thresholds': {'finalization_threshold': 0.85, 'scam_confidence': 0.9}
            },
            'PolicyDecisionAgent': {
                'specialized_prompts': {
                    'policy_decision': 'Make regulatory-compliant policy decisions',
                    'customer_protection': 'Implement customer protection measures'
                },
                'required_contexts': ['final_risk', 'regulatory_requirements'],
                'decision_thresholds': {'policy_confidence': 0.9, 'compliance_score': 0.85}
            },
            'FeedbackCollectorAgent': {
                'specialized_prompts': {
                    'feedback_generation': 'Generate structured feedback questions',
                    'improvement_analysis': 'Analyze system performance and improvements'
                },
                'required_contexts': ['case_outcome', 'system_performance'],
                'decision_thresholds': {'feedback_quality': 0.8, 'improvement_priority': 0.7}
            }
        }
        
        for agent_name, config in agent_types.items():
            agents[agent_name] = AgentConfig(
                name=agent_name,
                **config
            )
        
        return agents
    
    def _load_external_configs(self):
        """Load configuration from external files"""
        config_dir = Path(self.config_path)
        
        # Load SOPs and questions dynamically
        self.sops = self._load_yaml_file(config_dir / 'sops.yaml', {})
        self.questions = self._load_yaml_file(config_dir / 'questions.yaml', {})
        self.fraud_patterns = self._load_yaml_file(config_dir / 'fraud_patterns.yaml', {})
        
        # Load regulatory requirements
        self.regulatory_requirements = self._load_yaml_file(config_dir / 'regulatory.yaml', {})
        
        # Load customer protection measures
        self.customer_protection = self._load_yaml_file(config_dir / 'customer_protection.yaml', {})
    
    def _load_yaml_file(self, file_path: Path, default: Any) -> Any:
        """Safely load YAML configuration file"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or default
        except Exception as e:
            self.logger.warning(f"Failed to load {file_path}: {e}")
        return default
    
    def _validate_config(self):
        """Validate configuration integrity"""
        required_agents = [
            'TransactionContextAgent', 'CustomerInfoAgent', 'MerchantInfoAgent',
            'BehavioralPatternAgent', 'RiskSynthesizerAgent', 'TriageAgent',
            'DialogueAgent', 'RiskAssessorAgent', 'PolicyDecisionAgent'
        ]
        
        for agent_name in required_agents:
            if agent_name not in self.agents:
                raise ValueError(f"Required agent {agent_name} not found in configuration")
        
        # Validate risk levels
        if not self.fraud_detection.risk_levels:
            raise ValueError("Risk levels configuration is required")
        
        # Validate scam typologies
        if not self.fraud_detection.scam_typologies:
            raise ValueError("Scam typologies configuration is required")
    
    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """Get configuration for a specific agent"""
        return self.agents.get(agent_name, AgentConfig(agent_name))
    
    def get_risk_level(self, score: float) -> str:
        """Determine risk level based on score"""
        for level, config in self.fraud_detection.risk_levels.items():
            min_score, max_score = config['score_range']
            if min_score <= score <= max_score:
                return level
        return 'HIGH'  # Default to high risk if no match
    
    def get_scam_typology(self, indicators: List[str]) -> Optional[str]:
        """Identify scam typology based on indicators"""
        best_match = None
        best_score = 0.0
        
        for typology, config in self.fraud_detection.scam_typologies.items():
            typology_indicators = config.get('indicators', [])
            matches = sum(1 for indicator in indicators if indicator in typology_indicators)
            score = matches / len(typology_indicators) if typology_indicators else 0.0
            
            if score > best_score and score >= 0.5:  # Minimum 50% match
                best_score = score
                best_match = typology
        
        return best_match
    
    def get_regulatory_requirements(self, transaction_amount: float, risk_level: str) -> Dict[str, Any]:
        """Get regulatory requirements based on transaction and risk"""
        requirements = {}
        
        # AUSTRAC requirements
        if transaction_amount >= self.fraud_detection.regulatory_frameworks['AUSTRAC']['reporting_threshold']:
            requirements['AUSTRAC'] = {
                'suspicious_matter_report': True,
                'enhanced_due_diligence': True,
                'reporting_deadline': '24_hours'
            }
        
        # APRA requirements for high-risk transactions
        if risk_level == 'HIGH':
            requirements['APRA'] = {
                'information_security_controls': True,
                'customer_protection': True,
                'fraud_monitoring': True
            }
        
        return requirements
    
    def should_escalate(self, risk_score: float, scam_confidence: float, customer_vulnerability: float) -> bool:
        """Determine if case should be escalated"""
        escalation_threshold = self.get_agent_config('TriageAgent').decision_thresholds.get('escalation_threshold', 0.7)
        
        # Escalate if any of these conditions are met
        conditions = [
            risk_score >= escalation_threshold,
            scam_confidence >= 0.8,
            customer_vulnerability >= 0.8,
            risk_score >= 0.6 and scam_confidence >= 0.6  # Combined high risk
        ]
        
        return any(conditions)
    
    def get_fact_extraction_config(self, fact_type: str) -> Dict[str, Any]:
        """Get configuration for fact extraction"""
        return self.conversation.fact_categories.get(fact_type, {
            'keywords': [],
            'confidence_threshold': 0.8,
            'required': False
        })
    
    def is_finalization_ready(self, facts: Dict[str, Any], dialogue_length: int, risk_score: float) -> bool:
        """Determine if dialogue can be finalized"""
        # Check for early finalization indicators
        dialogue_text = ' '.join(str(v) for v in facts.values()).lower()
        early_indicators = any(indicator in dialogue_text for indicator in self.conversation.early_finalization_indicators)
        
        # Check dialogue length
        max_turns_reached = dialogue_length >= self.conversation.max_dialogue_turns
        
        # Check risk score
        high_risk_finalization = risk_score >= 0.8
        
        return early_indicators or max_turns_reached or high_risk_finalization
    
    def get_required_facts(self) -> List[str]:
        """Get list of required facts from conversation configuration"""
        return [fact_type for fact_type, config in self.conversation.fact_categories.items() 
                if config.get('required', False)]

# Global configuration instance
config = DynamicConfig()

# Convenience functions for backward compatibility
def get_agent_setting(agent_name: str, setting: str, default=None):
    """Get a specific setting for an agent"""
    agent_config = config.get_agent_config(agent_name)
    return getattr(agent_config, setting, default)

def get_fact_confidence_threshold(fact_type: str) -> float:
    """Get confidence threshold for a fact type"""
    fact_config = config.get_fact_extraction_config(fact_type)
    return fact_config.get('confidence_threshold', 0.8)

def get_required_facts() -> List[str]:
    """Get list of required facts"""
    return [fact_type for fact_type, config in config.conversation.fact_categories.items() 
            if config.get('required', False)]
    
def should_finalize(text: str) -> bool:
    """Check if text indicates finalization should occur"""
    text_lower = text.lower()
    positive_indicators = ['finalize', 'complete', 'sufficient information', 'enough evidence']
    negative_indicators = ['do not finalize', 'not finalize', 'insufficient information', 'continue questioning']
    
    has_positive = any(indicator in text_lower for indicator in positive_indicators)
    has_negative = any(indicator in text_lower for indicator in negative_indicators)
    
    return has_positive and not has_negative 