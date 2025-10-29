"""
Advanced Intelligent Agent Base Class for XYZ Bank Authorized Scam Detection
Production-ready agent framework with dynamic capabilities and expert-level intelligence
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import re
from abc import ABC, abstractmethod

from vector_utils import search_similar
from aws_bedrock import converse_with_claude_stream
from config import config

# Import Mem0 integration
try:
    from mem0_integration import get_mem0_manager, store_memory, retrieve_memories, MemoryType
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    print("Warning: Mem0 integration not available")

@dataclass
class AgentMemory:
    """Intelligent agent memory with context awareness"""
    context_id: str
    timestamp: datetime
    context_data: Dict[str, Any] = field(default_factory=dict)
    decisions_made: List[Dict[str, Any]] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    risk_indicators: List[str] = field(default_factory=list)
    regulatory_flags: List[str] = field(default_factory=list)
    
    def add_decision(self, decision_type: str, decision: Any, confidence: float, reasoning: str):
        """Add a decision to memory with metadata"""
        self.decisions_made.append({
            'type': decision_type,
            'decision': decision,
            'confidence': confidence,
            'reasoning': reasoning,
            'timestamp': datetime.now().isoformat()
        })
    
    def add_risk_indicator(self, indicator: str, confidence: float):
        """Add risk indicator with confidence"""
        self.risk_indicators.append(indicator)
        self.confidence_scores[f'risk_{indicator}'] = confidence
    
    def get_recent_decisions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent decisions for context"""
        return self.decisions_made[-limit:] if self.decisions_made else []
    
    def get_confidence_trend(self) -> float:
        """Calculate confidence trend over recent decisions"""
        if len(self.confidence_scores) < 2:
            return 0.0
        scores = list(self.confidence_scores.values())
        return sum(scores) / len(scores)

@dataclass
class AgentContext:
    """Advanced agent context with intelligent data structures"""
    transaction_data: Dict[str, Any] = field(default_factory=dict)
    customer_profile: Dict[str, Any] = field(default_factory=dict)
    merchant_data: Dict[str, Any] = field(default_factory=dict)
    behavioral_patterns: Dict[str, Any] = field(default_factory=dict)
    dialogue_history: List[Dict[str, Any]] = field(default_factory=list)
    risk_assessments: List[Dict[str, Any]] = field(default_factory=list)
    regulatory_requirements: Dict[str, Any] = field(default_factory=dict)
    scam_indicators: List[str] = field(default_factory=list)
    
    def get_risk_score(self) -> float:
        """Calculate overall risk score from context"""
        if not self.risk_assessments:
            return 0.0
        
        # Weight recent assessments more heavily
        weights = [0.4, 0.3, 0.2, 0.1]  # Most recent first
        total_score = 0.0
        total_weight = 0.0
        
        for i, assessment in enumerate(self.risk_assessments[-4:]):
            weight = weights[i] if i < len(weights) else 0.1
            score = assessment.get('risk_score', 0.0)
            total_score += score * weight
            total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def get_scam_typology(self) -> Optional[str]:
        """Identify scam typology from indicators"""
        if not self.scam_indicators:
            return None
        
        return config.get_scam_typology(self.scam_indicators)
    
    def get_regulatory_flags(self) -> List[str]:
        """Get regulatory flags based on context"""
        flags = []
        
        # Check transaction amount for AUSTRAC reporting
        amount = self.transaction_data.get('amount', 0)
        if amount >= config.fraud_detection.regulatory_frameworks['AUSTRAC']['reporting_threshold']:
            flags.append('AUSTRAC_REPORTING_REQUIRED')
        
        # Check risk level for APRA requirements
        risk_score = self.get_risk_score()
        risk_level = config.get_risk_level(risk_score)
        if risk_level == 'HIGH':
            flags.append('APRA_ENHANCED_DUE_DILIGENCE')
        
        return flags

class IntelligentAgent(ABC):
    """Advanced intelligent agent base class with expert-level capabilities"""
    
    def __init__(self, name: str, context_store):
        self.name = name
        self.context_store = context_store
        self.logger = logging.getLogger(f"Agent.{name}")
        self.agent_config = config.get_agent_config(name)
        self.memory = AgentMemory(
            context_id=f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now()
        )
        
        # Initialize specialized capabilities
        self._initialize_capabilities()
    
    def _initialize_capabilities(self):
        """Initialize agent-specific capabilities"""
        self.capabilities = {
            'risk_assessment': 'Risk' in self.name,
            'dialogue_management': 'Dialogue' in self.name,
            'policy_decision': 'Policy' in self.name,
            'context_analysis': 'Context' in self.name,
            'behavioral_analysis': 'Behavioral' in self.name,
            'regulatory_compliance': 'Policy' in self.name or 'Risk' in self.name
        }
    
    @abstractmethod
    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform intelligent agent action"""
        pass
    
    def retrieve_knowledge(self, query: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Intelligent knowledge retrieval with context awareness"""
        try:
            # Use vector search for semantic similarity
            results = search_similar(query, top_k=5)
            
            # Filter and enhance results based on context
            enhanced_results = []
            for result in results:
                if isinstance(result, dict):
                    text = result.get('text', str(result))
                else:
                    text = str(result)
                
                # Enhance with context-specific information
                if context:
                    text = self._enhance_with_context(text, context)
                
                enhanced_results.append(text)
            
            return enhanced_results
        except Exception as e:
            self.logger.warning(f"Knowledge retrieval failed: {e}")
            return []
    
    def _enhance_with_context(self, text: str, context: Dict[str, Any]) -> str:
        """Enhance text with relevant context information"""
        enhancements = []
        
        # Add transaction context
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 'Unknown')
                payee = txn.get('payee', 'Unknown')
                enhancements.append(f"Transaction: ${amount} to {payee}")
        
        # Add customer context
        if 'customer_context' in context:
            enhancements.append(f"Customer: {context['customer_context'][:100]}...")
        
        # Add risk context
        if 'risk_summary_context' in context:
            enhancements.append(f"Risk: {context['risk_summary_context'][:100]}...")
        
        if enhancements:
            text += f"\n\nContext: {' | '.join(enhancements)}"
        
        return text
    
    def extract_facts_intelligently(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligent fact extraction with confidence scoring"""
        facts = {}
        
        # Get fact extraction configuration
        fact_categories = config.conversation.fact_categories
        
        for fact_type, fact_config in fact_categories.items():
            keywords = fact_config.get('keywords', [])
            confidence_threshold = fact_config.get('confidence_threshold', 0.8)
            
            # Search for keywords in text
            matches = []
            text_lower = text.lower()
            
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    # Calculate confidence based on keyword strength and context
                    confidence = self._calculate_fact_confidence(keyword, text, context)
                    if confidence >= confidence_threshold:
                        matches.append((keyword, confidence))
            
            if matches:
                # Use highest confidence match
                best_match, confidence = max(matches, key=lambda x: x[1])
                facts[fact_type] = {
                    'value': best_match,
                    'confidence': confidence,
                    'source': 'extracted'
                }
        
        return facts
    
    def _calculate_fact_confidence(self, keyword: str, text: str, context: Dict[str, Any]) -> float:
        """Calculate confidence score for fact extraction"""
        base_confidence = 0.5
        
        # Keyword strength
        keyword_strength = {
            'verified': 0.9,
            'authorized': 0.85,
            'confirmed': 0.9,
            'unauthorized': 0.9,
            'denied': 0.9,
            'scam': 0.95,
            'fraud': 0.95,
            'pressure': 0.8,
            'urgency': 0.8,
            'threat': 0.9
        }
        
        base_confidence = keyword_strength.get(keyword.lower(), 0.7)
        
        # Context enhancement
        if 'transaction' in context:
            base_confidence += 0.1
        
        if 'customer_context' in context:
            base_confidence += 0.1
        
        # Text quality enhancement
        if keyword.lower() in text.lower():
            base_confidence += 0.2
        
        return min(base_confidence, 1.0)
    
    def make_intelligent_decision(self, decision_type: str, context: Dict[str, Any], 
                                options: List[str], reasoning_required: bool = True) -> Dict[str, Any]:
        """Make intelligent decision with confidence scoring"""
        # Build decision prompt
        prompt = self._build_decision_prompt(decision_type, context, options)
        
        # Get agent response
        response = self._get_agent_response(prompt)
        
        # Parse decision and confidence
        decision_result = self._parse_decision_response(response, options)
        
        # Add to memory
        self.memory.add_decision(
            decision_type=decision_type,
            decision=decision_result['decision'],
            confidence=decision_result['confidence'],
            reasoning=decision_result['reasoning']
        )
        
        return decision_result
    
    def _build_decision_prompt(self, decision_type: str, context: Dict[str, Any], 
                              options: List[str]) -> str:
        """Build intelligent decision prompt"""
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
        # Get specialized prompt for decision type
        prompt_template = specialized_prompts.get(decision_type, 
                                                f"Make a {decision_type} decision based on the context.")
        
        # Build context summary
        context_summary = self._build_context_summary(context)
        
        # Build options summary
        options_text = "\n".join([f"{i+1}. {option}" for i, option in enumerate(options)])
        
        prompt = f"""
{prompt_template}

Context:
{context_summary}

Available Options:
{options_text}

Requirements:
- Provide your decision (number or option name)
- Provide confidence level (0.0-1.0)
- Provide reasoning for your decision
- Consider regulatory compliance and customer protection

Decision:
"""
        return prompt
    
    def _build_context_summary(self, context: Dict[str, Any]) -> str:
        """Build intelligent context summary"""
        summary_parts = []
        
        # Transaction summary
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 'Unknown')
                payee = txn.get('payee', 'Unknown')
                alert_id = txn.get('alertId', 'Unknown')
                summary_parts.append(f"Transaction: ${amount} to {payee} (Alert: {alert_id})")
        
        # Risk summary
        if 'risk_summary_context' in context:
            risk_summary = context['risk_summary_context'][:200] + "..." if len(context['risk_summary_context']) > 200 else context['risk_summary_context']
            summary_parts.append(f"Risk Assessment: {risk_summary}")
        
        # Customer summary
        if 'customer_context' in context:
            customer_summary = context['customer_context'][:150] + "..." if len(context['customer_context']) > 150 else context['customer_context']
            summary_parts.append(f"Customer: {customer_summary}")
        
        # Dialogue summary
        if 'dialogue_history' in context and context['dialogue_history']:
            recent_turns = context['dialogue_history'][-3:]  # Last 3 turns
            dialogue_summary = []
            for turn in recent_turns:
                if 'question' in turn and 'user' in turn:
                    dialogue_summary.append(f"Q: {turn['question'][:50]}... A: {turn['user'][:50]}...")
            if dialogue_summary:
                summary_parts.append(f"Recent Dialogue: {' | '.join(dialogue_summary)}")
        
        return "\n".join(summary_parts) if summary_parts else "Limited context available"
    
    def _get_agent_response(self, prompt: str) -> str:
        """Get agent response with error handling"""
        try:
            response = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            return response
        except Exception as e:
            self.logger.error(f"Failed to get agent response: {e}")
            return "Unable to process request"
    
    def _parse_decision_response(self, response: str, options: List[str]) -> Dict[str, Any]:
        """Parse decision response with confidence and reasoning"""
        # Extract decision
        decision = None
        confidence = 0.5  # Default confidence
        reasoning = response
        
        # Try to extract decision number
        decision_match = re.search(r'decision[:\s]*(\d+)', response.lower())
        if decision_match:
            try:
                decision_index = int(decision_match.group(1)) - 1
                if 0 <= decision_index < len(options):
                    decision = options[decision_index]
            except ValueError:
                pass
        
        # Try to extract decision from text
        if not decision:
            for option in options:
                if option.lower() in response.lower():
                    decision = option
                    break
        
        # Extract confidence
        confidence_match = re.search(r'confidence[:\s]*(\d*\.?\d+)', response.lower())
        if confidence_match:
            try:
                confidence = float(confidence_match.group(1))
            except ValueError:
                pass
        
        # Extract reasoning
        reasoning_match = re.search(r'reasoning[:\s]*(.+)', response, re.IGNORECASE | re.DOTALL)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
        
        return {
            'decision': decision or options[0] if options else 'Unknown',
            'confidence': max(0.0, min(1.0, confidence)),
            'reasoning': reasoning,
            'raw_response': response
        }
    
    def assess_risk_intelligently(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligent risk assessment with multiple factors"""
        risk_factors = []
        risk_score = 0.0
        
        # Transaction risk
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = float(txn.get('amount', 0))
                if amount > 10000:
                    risk_factors.append(('high_amount', 0.3))
                if amount > 50000:
                    risk_factors.append(('very_high_amount', 0.5))
        
        # Customer risk
        if 'customer_context' in context:
            customer_text = context['customer_context'].lower()
            if 'high-risk' in customer_text:
                risk_factors.append(('high_risk_customer', 0.4))
            if 'prior alerts' in customer_text:
                risk_factors.append(('prior_alerts', 0.3))
            if 'no scam education' in customer_text:
                risk_factors.append(('no_education', 0.2))
        
        # Behavioral risk
        if 'anomaly_context' in context:
            anomaly_text = context['anomaly_context'].lower()
            if 'anomaly' in anomaly_text:
                risk_factors.append(('behavioral_anomaly', 0.4))
            if 'device' in anomaly_text and 'unfamiliar' in anomaly_text:
                risk_factors.append(('unfamiliar_device', 0.3))
        
        # Calculate composite risk score
        if risk_factors:
            total_weight = sum(weight for _, weight in risk_factors)
            risk_score = sum(weight for _, weight in risk_factors) / total_weight
        else:
            risk_score = 0.2  # Base risk for any transaction
        
        # Determine risk level
        risk_level = config.get_risk_level(risk_score)
        
        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'risk_factors': [factor for factor, _ in risk_factors],
            'confidence': min(0.9, 0.5 + risk_score * 0.4),  # Higher risk = higher confidence
            'assessment_timestamp': datetime.now().isoformat()
        }
    
    def get_regulatory_requirements(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get regulatory requirements based on context"""
        requirements = {}
        
        # Get transaction amount
        amount = 0.0
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = float(txn.get('amount', 0))
        
        # Get risk level
        risk_assessment = self.assess_risk_intelligently(context)
        risk_level = risk_assessment['risk_level']
        
        # Get requirements from config
        requirements = config.get_regulatory_requirements(amount, risk_level)
        
        return requirements
    
    def should_escalate_case(self, context: Dict[str, Any]) -> bool:
        """Determine if case should be escalated"""
        risk_assessment = self.assess_risk_intelligently(context)
        risk_score = risk_assessment['risk_score']
        
        # Get customer vulnerability
        customer_vulnerability = 0.5  # Default
        if 'customer_context' in context:
            customer_text = context['customer_context'].lower()
            if 'high-risk' in customer_text:
                customer_vulnerability = 0.8
            elif 'medium' in customer_text and 'digital literacy' in customer_text:
                customer_vulnerability = 0.6
        
        # Get scam confidence
        scam_confidence = 0.5  # Default
        if 'risk_summary_context' in context:
            risk_text = context['risk_summary_context'].lower()
            if 'scam' in risk_text and 'confirmed' in risk_text:
                scam_confidence = 0.9
            elif 'scam' in risk_text:
                scam_confidence = 0.7
        
        return config.should_escalate(risk_score, scam_confidence, customer_vulnerability)
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get intelligent memory summary"""
        return {
            'context_id': self.memory.context_id,
            'timestamp': self.memory.timestamp.isoformat(),
            'total_decisions': len(self.memory.decisions_made),
            'recent_decisions': self.memory.get_recent_decisions(),
            'confidence_trend': self.memory.get_confidence_trend(),
            'risk_indicators': self.memory.risk_indicators,
            'regulatory_flags': self.memory.regulatory_flags
        }
    
    def store_memory(self, memory_type: str, case_id: str, content: str, **kwargs) -> bool:
        """Store memory using Mem0 if available"""
        if not MEM0_AVAILABLE:
            return False
        
        try:
            # Map memory type to Mem0 MemoryType
            memory_type_map = {
                'fraud_case': MemoryType.FRAUD_CASE,
                'context_summary': MemoryType.CONTEXT_SUMMARY,
                'agent_summary': MemoryType.AGENT_SUMMARY,
                'risk_assessment': MemoryType.RISK_ASSESSMENT,
                'policy_decision': MemoryType.POLICY_DECISION,
                'customer_interaction': MemoryType.CUSTOMER_INTERACTION,
                'compressed_summary': MemoryType.COMPRESSED_SUMMARY
            }
            
            mem0_type = memory_type_map.get(memory_type, MemoryType.AGENT_LOG)
            
            # Add agent name to kwargs
            kwargs['agent_name'] = self.name
            
            return store_memory(mem0_type, case_id, content, **kwargs)
        except Exception as e:
            self.logger.error(f"Failed to store memory: {e}")
            return False
    
    def retrieve_memories(self, case_id: str, query: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve memories using Mem0 if available with enhanced error handling"""
        if not MEM0_AVAILABLE:
            self.logger.debug("Mem0 not available, returning empty list")
            return []
        
        try:
            self.logger.debug(f"Retrieving memories for case {case_id}, query: {query}, limit: {limit}")
            result = retrieve_memories(case_id, query, limit)
            self.logger.debug(f"Successfully retrieved {len(result)} memories for case {case_id}")
            return result
        except Exception as e:
            self.logger.error(f"Failed to retrieve memories for case {case_id}: {e}")
            # Return empty list instead of None to prevent downstream errors
            return [] 
    
    def store_context_summary(self, case_id: str, context_summary: str) -> bool:
        """Store context summary in Mem0"""
        return self.store_memory('context_summary', case_id, context_summary)
    
    def store_agent_summary(self, case_id: str, agent_summary: str) -> bool:
        """Store agent summary in Mem0"""
        return self.store_memory('agent_summary', case_id, agent_summary)
    
    def store_risk_assessment(self, case_id: str, risk_assessment: str, confidence: float) -> bool:
        """Store risk assessment in Mem0"""
        return self.store_memory('risk_assessment', case_id, risk_assessment, confidence=confidence)
    
    def store_policy_decision(self, case_id: str, policy_decision: str) -> bool:
        """Store policy decision in Mem0"""
        return self.store_memory('policy_decision', case_id, policy_decision)
    
    def store_customer_interaction(self, case_id: str, interaction: str) -> bool:
        """Store customer interaction in Mem0"""
        return self.store_memory('customer_interaction', case_id, interaction)
    
    def store_compressed_summary(self, case_id: str, summary_type: str, compressed_summary: str) -> bool:
        """Store compressed summary in Mem0"""
        return self.store_memory('compressed_summary', case_id, compressed_summary, summary_type=summary_type)

# Backward compatibility
class Agent(IntelligentAgent):
    """Legacy agent class for backward compatibility"""
    pass 