"""
Intelligent Dialogue System for ANZ Bank Fraud Detection
=======================================================

This module implements enhanced dialogue intelligence with XAI capabilities
to address issues identified in conversation_2.txt:
- Repetitive questions
- Poor context management  
- Missing fact extraction
- No intelligent question selection
- Broken decision flow
"""

import logging
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from agent_base import IntelligentAgent, AgentConfig
from mem0_integration import get_mem0_manager, MemoryType
from vector_utils import embed_text, search_similar

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntelligentDialogueAgent(IntelligentAgent):
    """
    Enhanced Intelligent Dialogue Agent with XAI capabilities
    Addresses issues from conversation_2.txt: repetitive questions, poor context management, missing fact extraction
    """
    
    def __init__(self, name: str = "IntelligentDialogueAgent", config: AgentConfig = None):
        super().__init__(name, config or AgentConfig())
        self.conversation_state = {}
        self.fact_extraction_engine = FactExtractionEngine()
        self.question_selection_engine = QuestionSelectionEngine()
        self.context_manager = IntelligentContextManager()
        self.xai_framework = XAIFramework()
        
    def extract_facts_from_response(self, customer_response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract facts from customer response using NLP and context awareness
        """
        try:
            # Use enhanced fact extraction with confidence scoring
            facts = self.fact_extraction_engine.extract_facts(
                text=customer_response,
                context=context,
                conversation_history=self.conversation_state.get('dialogue_history', [])
            )
            
            # Store facts in conversation state
            if 'extracted_facts' not in self.conversation_state:
                self.conversation_state['extracted_facts'] = {}
            
            self.conversation_state['extracted_facts'].update(facts)
            
            # Store in Mem0 for learning
            self.store_memory('customer_response_facts', context.get('case_id', 'unknown'), 
                            f"Extracted facts: {json.dumps(facts, indent=2)}")
            
            return facts
            
        except Exception as e:
            self.logger.error(f"Error extracting facts: {e}")
            return {}
    
    def select_next_best_question(self, available_questions: List[str], context: Dict[str, Any]) -> Tuple[str, float, str]:
        """
        Intelligently select the next best question based on context, facts, and conversation state
        Returns: (selected_question, confidence_score, reasoning)
        """
        try:
            # Get conversation history
            dialogue_history = self.conversation_state.get('dialogue_history', [])
            extracted_facts = self.conversation_state.get('extracted_facts', {})
            
            # Get relevant memories for context
            relevant_memories = self.retrieve_memories(
                context.get('case_id', 'unknown'),
                query="similar fraud cases dialogue questions",
                limit=3
            )
            
            # Use question selection engine
            selected_question, confidence, reasoning = self.question_selection_engine.select_question(
                available_questions=available_questions,
                dialogue_history=dialogue_history,
                extracted_facts=extracted_facts,
                context=context,
                relevant_memories=relevant_memories
            )
            
            # Check for semantic similarity with previously asked questions
            if self.detect_semantic_similarity(selected_question, dialogue_history):
                # If similar question was asked, try to find a different one
                alternative_questions = [q for q in available_questions if q != selected_question]
                if alternative_questions:
                    selected_question, confidence, reasoning = self.question_selection_engine.select_question(
                        available_questions=alternative_questions,
                        dialogue_history=dialogue_history,
                        extracted_facts=extracted_facts,
                        context=context,
                        relevant_memories=relevant_memories
                    )
            
            return selected_question, confidence, reasoning
            
        except Exception as e:
            self.logger.error(f"Error selecting next question: {e}")
            return available_questions[0] if available_questions else "", 0.5, "Fallback selection"
    
    def maintain_conversation_state(self, context: Dict[str, Any], user_response: str = None) -> Dict[str, Any]:
        """
        Maintain rich conversation state across turns with context persistence
        """
        try:
            # Initialize conversation state if not exists
            if 'dialogue_history' not in self.conversation_state:
                self.conversation_state['dialogue_history'] = []
            
            # Add user response to history
            if user_response:
                self.conversation_state['dialogue_history'].append({
                    'role': 'user',
                    'content': user_response,
                    'timestamp': datetime.now().isoformat(),
                    'turn_number': len(self.conversation_state['dialogue_history']) + 1
                })
                
                # Extract facts from response
                facts = self.extract_facts_from_response(user_response, context)
                
                # Update conversation state with facts
                self.conversation_state['last_user_response'] = user_response
                self.conversation_state['last_extracted_facts'] = facts
                self.conversation_state['conversation_quality_score'] = self._calculate_conversation_quality()
            
            # Compress conversation if too long
            if len(self.conversation_state['dialogue_history']) > 10:
                self.conversation_state = self.context_manager.compress_conversation_context(
                    self.conversation_state
                )
            
            # Update context with conversation state
            context['conversation_state'] = self.conversation_state.copy()
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error maintaining conversation state: {e}")
            return context
    
    def detect_semantic_similarity(self, question: str, dialogue_history: List[Dict[str, Any]], threshold: float = 0.8) -> bool:
        """
        Detect if a question is semantically similar to previously asked questions
        """
        try:
            # Get previously asked questions
            asked_questions = []
            for turn in dialogue_history:
                if turn.get('role') == 'agent' and 'question' in turn:
                    asked_questions.append(turn['question'])
            
            if not asked_questions:
                return False
            
            # Use vector similarity to check for semantic similarity
            question_embedding = embed_text(question)
            
            for asked_q in asked_questions:
                asked_embedding = embed_text(asked_q)
                similarity = self._cosine_similarity(question_embedding, asked_embedding)
                
                if similarity > threshold:
                    self.logger.info(f"Semantic similarity detected: {similarity:.3f} between '{question}' and '{asked_q}'")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error detecting semantic similarity: {e}")
            return False
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            import numpy as np
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)
            return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        except Exception:
            return 0.0
    
    def generate_contextual_questions(self, context: Dict[str, Any], missing_facts: List[str]) -> List[str]:
        """
        Generate contextual questions based on missing facts and conversation context
        """
        try:
            # Get relevant SOPs and questions
            sop_rules = self._get_relevant_sop_rules(context)
            base_questions = self._get_base_questions(context)
            
            # Generate contextual questions
            contextual_questions = []
            
            for missing_fact in missing_facts:
                # Generate question based on missing fact
                generated_question = self._generate_question_for_fact(missing_fact, context, sop_rules)
                if generated_question:
                    contextual_questions.append(generated_question)
            
            # Combine with base questions and rank by relevance
            all_questions = base_questions + contextual_questions
            ranked_questions = self._rank_questions_by_relevance(all_questions, context)
            
            return ranked_questions[:5]  # Return top 5 questions
            
        except Exception as e:
            self.logger.error(f"Error generating contextual questions: {e}")
            return []
    
    def act(self, message: str, context: Dict[str, Any], user_response: Optional[str] = None, max_turns: Optional[int] = None, stream: bool = False) -> Tuple[Dict[str, Any], bool]:
        """
        Enhanced intelligent dialogue agent action with XAI capabilities
        """
        try:
            # Maintain conversation state
            context = self.maintain_conversation_state(context, user_response)
            
            # Get dialogue history
            dialogue_history = self.conversation_state.get('dialogue_history', [])
            
            # Check if conversation should continue
            if self._should_terminate_conversation(context, dialogue_history, max_turns):
                # Finalize conversation with XAI reasoning
                final_decision = self._finalize_conversation(context)
                context['dialogue_complete'] = True
                context['final_decision'] = final_decision
                return context, True
            
            # Get available questions
            available_questions = self.generate_contextual_questions(context, self._get_missing_facts(context))
            
            if not available_questions:
                # No more relevant questions, finalize
                final_decision = self._finalize_conversation(context)
                context['dialogue_complete'] = True
                context['final_decision'] = final_decision
                return context, True
            
            # Select next best question with XAI reasoning
            selected_question, confidence, reasoning = self.select_next_best_question(available_questions, context)
            
            # Add question to dialogue history with XAI metadata
            self.conversation_state['dialogue_history'].append({
                'role': 'agent',
                'question': selected_question,
                'timestamp': datetime.now().isoformat(),
                'turn_number': len(self.conversation_state['dialogue_history']) + 1,
                'xai_metadata': {
                    'confidence_score': confidence,
                    'reasoning': reasoning,
                    'question_source': 'intelligent_selection',
                    'context_used': list(context.keys())
                }
            })
            
            # Update context
            context['conversation_state'] = self.conversation_state.copy()
            context['current_question'] = selected_question
            context['question_confidence'] = confidence
            context['question_reasoning'] = reasoning
            
            return context, False
            
        except Exception as e:
            self.logger.error(f"Error in intelligent dialogue agent: {e}")
            return context, True
    
    def _should_terminate_conversation(self, context: Dict[str, Any], dialogue_history: List[Dict[str, Any]], max_turns: Optional[int]) -> bool:
        """
        Determine if conversation should terminate based on multiple factors
        """
        # Check max turns
        if max_turns and len(dialogue_history) >= max_turns:
            return True
        
        # Check if we have sufficient information
        extracted_facts = self.conversation_state.get('extracted_facts', {})
        if len(extracted_facts) >= 5:  # Arbitrary threshold
            return True
        
        # Check conversation quality
        quality_score = self.conversation_state.get('conversation_quality_score', 0.0)
        if quality_score > 0.8:  # High quality conversation
            return True
        
        # Check for repetitive responses
        if self._detect_repetitive_responses(dialogue_history):
            return True
        
        return False
    
    def _finalize_conversation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalize conversation with comprehensive XAI reasoning
        """
        try:
            # Get conversation summary
            conversation_summary = self.context_manager.create_context_summaries(
                self.conversation_state
            )
            
            # Analyze extracted facts
            extracted_facts = self.conversation_state.get('extracted_facts', {})
            fact_analysis = self._analyze_extracted_facts(extracted_facts)
            
            # Generate final decision with XAI reasoning
            final_decision = self.xai_framework.explain_decision_reasoning(
                decision_type="dialogue_completion",
                context=context,
                conversation_summary=conversation_summary,
                fact_analysis=fact_analysis
            )
            
            # Store final decision in memory
            self.store_memory('dialogue_completion', context.get('case_id', 'unknown'), 
                            f"Final decision: {json.dumps(final_decision, indent=2)}")
            
            return final_decision
            
        except Exception as e:
            self.logger.error(f"Error finalizing conversation: {e}")
            return {"decision": "escalate", "reasoning": "Error in finalization", "confidence": 0.5}
    
    def _calculate_conversation_quality(self) -> float:
        """
        Calculate conversation quality score based on multiple factors
        """
        try:
            dialogue_history = self.conversation_state.get('dialogue_history', [])
            extracted_facts = self.conversation_state.get('extracted_facts', {})
            
            # Base score
            quality_score = 0.5
            
            # Factor 1: Number of facts extracted
            fact_count = len(extracted_facts)
            quality_score += min(fact_count * 0.1, 0.3)
            
            # Factor 2: Conversation length (optimal range)
            conv_length = len(dialogue_history)
            if 3 <= conv_length <= 8:
                quality_score += 0.2
            elif conv_length > 8:
                quality_score += 0.1
            
            # Factor 3: Response quality (if we have user responses)
            user_responses = [turn for turn in dialogue_history if turn.get('role') == 'user']
            if user_responses:
                avg_response_length = sum(len(resp.get('content', '')) for resp in user_responses) / len(user_responses)
                if avg_response_length > 20:  # Substantial responses
                    quality_score += 0.2
            
            return min(quality_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error calculating conversation quality: {e}")
            return 0.5
    
    def _detect_repetitive_responses(self, dialogue_history: List[Dict[str, Any]]) -> bool:
        """
        Detect if user is giving repetitive responses
        """
        try:
            user_responses = [turn.get('content', '') for turn in dialogue_history if turn.get('role') == 'user']
            
            if len(user_responses) < 3:
                return False
            
            # Check for exact duplicates
            unique_responses = set(user_responses)
            if len(unique_responses) < len(user_responses) * 0.7:  # More than 30% duplicates
                return True
            
            # Check for semantic similarity in recent responses
            recent_responses = user_responses[-3:]
            for i in range(len(recent_responses)):
                for j in range(i + 1, len(recent_responses)):
                    if self.detect_semantic_similarity(recent_responses[i], [{'content': recent_responses[j]}], threshold=0.9):
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error detecting repetitive responses: {e}")
            return False
    
    def _get_missing_facts(self, context: Dict[str, Any]) -> List[str]:
        """
        Determine what facts are still missing based on context and conversation
        """
        try:
            # Define required facts for fraud detection
            required_facts = [
                'customer_authorization',
                'recipient_knowledge',
                'transaction_purpose',
                'remote_access',
                'social_engineering_indicators',
                'device_information',
                'communication_channel',
                'urgency_pressure'
            ]
            
            # Get already extracted facts
            extracted_facts = self.conversation_state.get('extracted_facts', {})
            
            # Find missing facts
            missing_facts = []
            for fact in required_facts:
                if fact not in extracted_facts or not extracted_facts[fact]:
                    missing_facts.append(fact)
            
            return missing_facts
            
        except Exception as e:
            self.logger.error(f"Error getting missing facts: {e}")
            return []
    
    def _analyze_extracted_facts(self, extracted_facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze extracted facts for fraud indicators
        """
        try:
            analysis = {
                'fraud_indicators': [],
                'risk_score': 0.0,
                'confidence': 0.0,
                'missing_critical_info': []
            }
            
            # Analyze each fact for fraud indicators
            fraud_keywords = ['unauthorized', 'unknown', 'pressure', 'urgency', 'remote', 'suspicious']
            
            for fact_key, fact_value in extracted_facts.items():
                if isinstance(fact_value, str):
                    fact_lower = fact_value.lower()
                    
                    # Check for fraud indicators
                    for keyword in fraud_keywords:
                        if keyword in fact_lower:
                            analysis['fraud_indicators'].append({
                                'fact': fact_key,
                                'indicator': keyword,
                                'value': fact_value
                            })
                            analysis['risk_score'] += 0.1
            
            # Normalize risk score
            analysis['risk_score'] = min(analysis['risk_score'], 1.0)
            
            # Calculate confidence based on fact completeness
            total_facts = len(extracted_facts)
            if total_facts > 0:
                analysis['confidence'] = min(total_facts / 8.0, 1.0)  # 8 required facts
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing extracted facts: {e}")
            return {'fraud_indicators': [], 'risk_score': 0.0, 'confidence': 0.0, 'missing_critical_info': []}
    
    def _get_relevant_sop_rules(self, context: Dict[str, Any]) -> List[str]:
        """Get relevant SOP rules for the context"""
        try:
            # This would integrate with the existing SOP retrieval system
            return []
        except Exception as e:
            self.logger.error(f"Error getting SOP rules: {e}")
            return []
    
    def _get_base_questions(self, context: Dict[str, Any]) -> List[str]:
        """Get base questions from questions.md"""
        try:
            # This would integrate with the existing questions.md system
            return []
        except Exception as e:
            self.logger.error(f"Error getting base questions: {e}")
            return []
    
    def _generate_question_for_fact(self, missing_fact: str, context: Dict[str, Any], sop_rules: List[str]) -> Optional[str]:
        """Generate a question for a specific missing fact"""
        try:
            # Simple question generation based on fact type
            question_templates = {
                'customer_authorization': "Did you personally authorize this transaction?",
                'recipient_knowledge': "Do you know the recipient of this payment?",
                'remote_access': "Has anyone asked you to install remote access software?",
                'social_engineering': "Did anyone pressure you to make this payment quickly?",
                'device_information': "What device are you using for banking?",
                'communication_channel': "How did you receive the payment request?",
                'urgency_pressure': "Was there any urgency or pressure to complete this payment?"
            }
            
            return question_templates.get(missing_fact, None)
            
        except Exception as e:
            self.logger.error(f"Error generating question for fact: {e}")
            return None
    
    def _rank_questions_by_relevance(self, questions: List[str], context: Dict[str, Any]) -> List[str]:
        """Rank questions by relevance to current context"""
        try:
            # Simple ranking - in a real implementation, this would use more sophisticated ranking
            return questions
        except Exception as e:
            self.logger.error(f"Error ranking questions: {e}")
            return questions


class FactExtractionEngine:
    """
    Advanced fact extraction engine using NLP and context awareness
    """
    
    def __init__(self):
        self.nlp_patterns = {
            'customer_authorization': [
                r'(?i)(authorized|authorized|approved|confirmed|wanted|intended)',
                r'(?i)(did you|did the customer|was this)',
                r'(?i)(personally|themselves|own)'
            ],
            'recipient_knowledge': [
                r'(?i)(know|familiar|recognize|heard of|met)',
                r'(?i)(recipient|person|company|business)',
                r'(?i)(unknown|stranger|unfamiliar|never heard)'
            ],
            'remote_access': [
                r'(?i)(remote|anydesk|teamviewer|quicksupport)',
                r'(?i)(screen share|remote access|control)',
                r'(?i)(download|install|software)'
            ],
            'social_engineering': [
                r'(?i)(pressure|urgent|emergency|threat)',
                r'(?i)(email|message|call|contact)',
                r'(?i)(suspicious|strange|unusual)'
            ]
        }
    
    def extract_facts(self, text: str, context: Dict[str, Any], conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract facts from text using NLP patterns and context
        """
        facts = {}
        
        try:
            text_lower = text.lower()
            
            # Extract facts using patterns
            for fact_type, patterns in self.nlp_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, text_lower)
                    if matches:
                        facts[fact_type] = {
                            'value': text,
                            'confidence': self._calculate_fact_confidence(text, pattern, context),
                            'extraction_method': 'nlp_pattern',
                            'timestamp': datetime.now().isoformat()
                        }
                        break
            
            # Add context-based facts
            context_facts = self._extract_context_facts(context, conversation_history)
            facts.update(context_facts)
            
            return facts
            
        except Exception as e:
            logging.error(f"Error extracting facts: {e}")
            return facts
    
    def _calculate_fact_confidence(self, text: str, pattern: str, context: Dict[str, Any]) -> float:
        """
        Calculate confidence score for extracted fact
        """
        base_confidence = 0.7
        
        # Pattern strength
        if 'authorized' in pattern or 'unauthorized' in pattern:
            base_confidence += 0.2
        elif 'remote' in pattern or 'anydesk' in pattern:
            base_confidence += 0.2
        elif 'pressure' in pattern or 'urgent' in pattern:
            base_confidence += 0.15
        
        # Text quality
        if len(text) > 20:  # Substantial response
            base_confidence += 0.1
        
        # Context relevance
        if 'transaction' in context:
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def _extract_context_facts(self, context: Dict[str, Any], conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract facts from context and conversation history
        """
        context_facts = {}
        
        try:
            # Extract facts from transaction context
            if 'transaction' in context:
                txn = context['transaction']
                if isinstance(txn, dict):
                    if 'amount' in txn:
                        context_facts['transaction_amount'] = {
                            'value': txn['amount'],
                            'confidence': 0.9,
                            'extraction_method': 'context',
                            'timestamp': datetime.now().isoformat()
                        }
            
            # Extract facts from conversation history
            for turn in conversation_history:
                if turn.get('role') == 'user':
                    content = turn.get('content', '')
                    if 'yes' in content.lower():
                        context_facts['positive_response'] = {
                            'value': content,
                            'confidence': 0.8,
                            'extraction_method': 'conversation_history',
                            'timestamp': turn.get('timestamp', datetime.now().isoformat())
                        }
            
            return context_facts
            
        except Exception as e:
            logging.error(f"Error extracting context facts: {e}")
            return context_facts


class QuestionSelectionEngine:
    """
    Intelligent question selection engine with context awareness
    """
    
    def __init__(self):
        self.question_weights = {
            'authorization': 0.9,
            'recipient': 0.8,
            'remote_access': 0.85,
            'social_engineering': 0.8,
            'device': 0.7,
            'communication': 0.6
        }
    
    def select_question(self, available_questions: List[str], dialogue_history: List[Dict[str, Any]], 
                       extracted_facts: Dict[str, Any], context: Dict[str, Any], 
                       relevant_memories: List[Dict[str, Any]]) -> Tuple[str, float, str]:
        """
        Select the best question based on multiple factors
        """
        try:
            if not available_questions:
                return "", 0.0, "No questions available"
            
            # Score each question
            question_scores = []
            for question in available_questions:
                score, reasoning = self._score_question(
                    question, dialogue_history, extracted_facts, context, relevant_memories
                )
                question_scores.append((question, score, reasoning))
            
            # Sort by score and select best
            question_scores.sort(key=lambda x: x[1], reverse=True)
            
            best_question, best_score, best_reasoning = question_scores[0]
            
            return best_question, best_score, best_reasoning
            
        except Exception as e:
            logging.error(f"Error selecting question: {e}")
            return available_questions[0] if available_questions else "", 0.5, "Fallback selection"
    
    def _score_question(self, question: str, dialogue_history: List[Dict[str, Any]], 
                       extracted_facts: Dict[str, Any], context: Dict[str, Any], 
                       relevant_memories: List[Dict[str, Any]]) -> Tuple[float, str]:
        """
        Score a question based on multiple factors
        """
        score = 0.0
        reasoning_parts = []
        
        try:
            # Factor 1: Question relevance to missing facts
            missing_facts = self._get_missing_facts(extracted_facts)
            relevance_score = self._calculate_relevance_score(question, missing_facts)
            score += relevance_score * 0.4
            reasoning_parts.append(f"relevance_score={relevance_score:.2f}")
            
            # Factor 2: Question priority based on fraud detection
            priority_score = self._calculate_priority_score(question)
            score += priority_score * 0.3
            reasoning_parts.append(f"priority_score={priority_score:.2f}")
            
            # Factor 3: Question novelty (not asked before)
            novelty_score = self._calculate_novelty_score(question, dialogue_history)
            score += novelty_score * 0.2
            reasoning_parts.append(f"novelty_score={novelty_score:.2f}")
            
            # Factor 4: Memory-based relevance
            memory_score = self._calculate_memory_score(question, relevant_memories)
            score += memory_score * 0.1
            reasoning_parts.append(f"memory_score={memory_score:.2f}")
            
            reasoning = f"Score breakdown: {', '.join(reasoning_parts)}"
            
            return score, reasoning
            
        except Exception as e:
            logging.error(f"Error scoring question: {e}")
            return 0.5, f"Error in scoring: {e}"
    
    def _get_missing_facts(self, extracted_facts: Dict[str, Any]) -> List[str]:
        """
        Determine what facts are missing
        """
        required_facts = ['customer_authorization', 'recipient_knowledge', 'remote_access', 'social_engineering']
        missing = []
        
        for fact in required_facts:
            if fact not in extracted_facts or not extracted_facts[fact]:
                missing.append(fact)
        
        return missing
    
    def _calculate_relevance_score(self, question: str, missing_facts: List[str]) -> float:
        """
        Calculate how relevant a question is to missing facts
        """
        if not missing_facts:
            return 0.5
        
        question_lower = question.lower()
        relevance_score = 0.0
        
        for fact in missing_facts:
            if fact == 'customer_authorization' and any(word in question_lower for word in ['authorize', 'approve', 'confirm']):
                relevance_score += 0.25
            elif fact == 'recipient_knowledge' and any(word in question_lower for word in ['know', 'recipient', 'person']):
                relevance_score += 0.25
            elif fact == 'remote_access' and any(word in question_lower for word in ['remote', 'access', 'device']):
                relevance_score += 0.25
            elif fact == 'social_engineering' and any(word in question_lower for word in ['pressure', 'urgent', 'email']):
                relevance_score += 0.25
        
        return min(relevance_score, 1.0)
    
    def _calculate_priority_score(self, question: str) -> float:
        """
        Calculate priority score based on fraud detection importance
        """
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['authorize', 'approve', 'confirm']):
            return 0.9
        elif any(word in question_lower for word in ['remote', 'anydesk', 'teamviewer']):
            return 0.85
        elif any(word in question_lower for word in ['know', 'recipient', 'person']):
            return 0.8
        elif any(word in question_lower for word in ['pressure', 'urgent', 'emergency']):
            return 0.8
        else:
            return 0.6
    
    def _calculate_novelty_score(self, question: str, dialogue_history: List[Dict[str, Any]]) -> float:
        """
        Calculate how novel a question is (not asked before)
        """
        asked_questions = []
        for turn in dialogue_history:
            if turn.get('role') == 'agent' and 'question' in turn:
                asked_questions.append(turn['question'].lower())
        
        question_lower = question.lower()
        
        # Check for exact duplicates
        if question_lower in asked_questions:
            return 0.0
        
        # Check for semantic similarity
        for asked_q in asked_questions:
            if self._semantic_similarity(question_lower, asked_q) > 0.8:
                return 0.2
        
        return 1.0
    
    def _calculate_memory_score(self, question: str, relevant_memories: List[Dict[str, Any]]) -> float:
        """
        Calculate score based on relevant memories
        """
        if not relevant_memories:
            return 0.5
        
        # Simple scoring based on memory relevance
        question_lower = question.lower()
        memory_score = 0.0
        
        for memory in relevant_memories:
            memory_content = str(memory.get('content', '')).lower()
            if any(word in memory_content for word in question_lower.split()):
                memory_score += 0.2
        
        return min(memory_score, 1.0)
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts
        """
        try:
            # Simple word overlap similarity
            words1 = set(text1.split())
            words2 = set(text2.split())
            
            if not words1 or not words2:
                return 0.0
            
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            return len(intersection) / len(union)
            
        except Exception as e:
            logging.error(f"Error calculating semantic similarity: {e}")
            return 0.0


class IntelligentContextManager:
    """
    Intelligent context management with compression and enrichment
    """
    
    def __init__(self):
        self.compression_threshold = 10  # Compress after 10 turns
        self.max_context_size = 5000  # Max context size in characters
    
    def compress_conversation_context(self, conversation_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress conversation context while preserving key information
        """
        try:
            dialogue_history = conversation_state.get('dialogue_history', [])
            
            if len(dialogue_history) <= self.compression_threshold:
                return conversation_state
            
            # Create summary of early conversation
            early_turns = dialogue_history[:len(dialogue_history)//2]
            late_turns = dialogue_history[len(dialogue_history)//2:]
            
            # Summarize early turns
            early_summary = self._summarize_turns(early_turns)
            
            # Create compressed state
            compressed_state = conversation_state.copy()
            compressed_state['dialogue_history'] = [
                {
                    'role': 'system',
                    'content': f"Early conversation summary: {early_summary}",
                    'timestamp': early_turns[0].get('timestamp', datetime.now().isoformat()),
                    'turn_number': 1,
                    'compressed': True
                }
            ] + late_turns
            
            return compressed_state
            
        except Exception as e:
            logging.error(f"Error compressing conversation context: {e}")
            return conversation_state
    
    def create_context_summaries(self, conversation_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create intelligent summaries of conversation context
        """
        try:
            dialogue_history = conversation_state.get('dialogue_history', [])
            extracted_facts = conversation_state.get('extracted_facts', {})
            
            summary = {
                'conversation_length': len(dialogue_history),
                'extracted_facts_count': len(extracted_facts),
                'key_facts': list(extracted_facts.keys()),
                'conversation_quality': conversation_state.get('conversation_quality_score', 0.0),
                'last_user_response': conversation_state.get('last_user_response', ''),
                'compression_applied': any(turn.get('compressed') for turn in dialogue_history)
            }
            
            return summary
            
        except Exception as e:
            logging.error(f"Error creating context summaries: {e}")
            return {}
    
    def _summarize_turns(self, turns: List[Dict[str, Any]]) -> str:
        """
        Summarize a list of conversation turns
        """
        try:
            if not turns:
                return "No conversation history"
            
            summaries = []
            for turn in turns:
                if turn.get('role') == 'user':
                    content = turn.get('content', '')
                    if len(content) > 50:
                        content = content[:50] + "..."
                    summaries.append(f"User: {content}")
                elif turn.get('role') == 'agent':
                    question = turn.get('question', '')
                    if len(question) > 50:
                        question = question[:50] + "..."
                    summaries.append(f"Agent: {question}")
            
            return "; ".join(summaries)
            
        except Exception as e:
            logging.error(f"Error summarizing turns: {e}")
            return "Error in summarization"


class XAIFramework:
    """
    Explainable AI framework for transparent decision making
    """
    
    def __init__(self):
        self.reasoning_templates = {
            'dialogue_completion': {
                'high_confidence': "Based on comprehensive analysis of {fact_count} extracted facts and {conv_length} conversation turns, the system has sufficient information to make a confident decision. Key indicators: {key_indicators}.",
                'medium_confidence': "Analysis of {fact_count} facts and {conv_length} turns provides moderate confidence. Additional information could improve accuracy. Current indicators: {key_indicators}.",
                'low_confidence': "Limited information available ({fact_count} facts, {conv_length} turns). Decision based on available data with low confidence. Missing: {missing_info}."
            }
        }
    
    def explain_decision_reasoning(self, decision_type: str, context: Dict[str, Any], 
                                 conversation_summary: Dict[str, Any], fact_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive decision reasoning with XAI
        """
        try:
            # Calculate confidence
            confidence = self._calculate_decision_confidence(conversation_summary, fact_analysis)
            
            # Generate reasoning
            reasoning = self._generate_reasoning(decision_type, conversation_summary, fact_analysis, confidence)
            
            # Create audit trail
            audit_trail = self._create_audit_trail(decision_type, context, conversation_summary, fact_analysis)
            
            # Determine action
            action = self._determine_action(confidence, fact_analysis)
            
            return {
                'decision': action,
                'confidence': confidence,
                'reasoning': reasoning,
                'audit_trail': audit_trail,
                'fact_analysis': fact_analysis,
                'conversation_summary': conversation_summary,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error explaining decision reasoning: {e}")
            return {
                'decision': 'escalate',
                'confidence': 0.5,
                'reasoning': f"Error in decision reasoning: {e}",
                'audit_trail': {},
                'fact_analysis': {},
                'conversation_summary': {},
                'timestamp': datetime.now().isoformat()
            }
    
    def _calculate_decision_confidence(self, conversation_summary: Dict[str, Any], fact_analysis: Dict[str, Any]) -> float:
        """
        Calculate confidence score for decision
        """
        confidence = 0.5  # Base confidence
        
        # Factor 1: Conversation quality
        conv_quality = conversation_summary.get('conversation_quality', 0.0)
        confidence += conv_quality * 0.2
        
        # Factor 2: Number of facts
        fact_count = conversation_summary.get('extracted_facts_count', 0)
        confidence += min(fact_count * 0.1, 0.3)
        
        # Factor 3: Fact analysis confidence
        fact_confidence = fact_analysis.get('confidence', 0.0)
        confidence += fact_confidence * 0.2
        
        # Factor 4: Conversation length (optimal range)
        conv_length = conversation_summary.get('conversation_length', 0)
        if 3 <= conv_length <= 8:
            confidence += 0.1
        elif conv_length > 8:
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _generate_reasoning(self, decision_type: str, conversation_summary: Dict[str, Any], 
                          fact_analysis: Dict[str, Any], confidence: float) -> str:
        """
        Generate human-readable reasoning for decision
        """
        try:
            template = self.reasoning_templates.get(decision_type, {}).get('high_confidence', 
                       "Decision made with {confidence:.1%} confidence based on {fact_count} facts and {conv_length} conversation turns.")
            
            # Prepare variables
            fact_count = conversation_summary.get('extracted_facts_count', 0)
            conv_length = conversation_summary.get('conversation_length', 0)
            key_indicators = self._extract_key_indicators(fact_analysis)
            missing_info = self._identify_missing_info(conversation_summary, fact_analysis)
            
            # Select template based on confidence
            if confidence >= 0.8:
                template_key = 'high_confidence'
            elif confidence >= 0.6:
                template_key = 'medium_confidence'
            else:
                template_key = 'low_confidence'
            
            template = self.reasoning_templates.get(decision_type, {}).get(template_key, template)
            
            # Format reasoning
            reasoning = template.format(
                confidence=confidence,
                fact_count=fact_count,
                conv_length=conv_length,
                key_indicators=key_indicators,
                missing_info=missing_info
            )
            
            return reasoning
            
        except Exception as e:
            logging.error(f"Error generating reasoning: {e}")
            return f"Decision made with {confidence:.1%} confidence. Error in reasoning generation: {e}"
    
    def _create_audit_trail(self, decision_type: str, context: Dict[str, Any], 
                           conversation_summary: Dict[str, Any], fact_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create comprehensive audit trail for decision
        """
        try:
            audit_trail = {
                'decision_type': decision_type,
                'timestamp': datetime.now().isoformat(),
                'context_keys': list(context.keys()),
                'conversation_summary': conversation_summary,
                'fact_analysis': fact_analysis,
                'system_version': 'IntelligentDialogueAgent_v2.0',
                'xai_framework_version': 'XAIFramework_v1.0'
            }
            
            return audit_trail
            
        except Exception as e:
            logging.error(f"Error creating audit trail: {e}")
            return {'error': str(e)}
    
    def _determine_action(self, confidence: float, fact_analysis: Dict[str, Any]) -> str:
        """
        Determine action based on confidence and fact analysis
        """
        try:
            risk_score = fact_analysis.get('risk_score', 0.0)
            fraud_indicators = fact_analysis.get('fraud_indicators', [])
            
            # High confidence with high risk
            if confidence >= 0.8 and risk_score >= 0.7:
                return 'block'
            
            # High confidence with low risk
            if confidence >= 0.8 and risk_score < 0.3:
                return 'clear'
            
            # Medium confidence or unclear risk
            if confidence >= 0.6:
                if risk_score >= 0.5 or len(fraud_indicators) > 0:
                    return 'escalate'
                else:
                    return 'clear'
            
            # Low confidence
            return 'escalate'
            
        except Exception as e:
            logging.error(f"Error determining action: {e}")
            return 'escalate'
    
    def _extract_key_indicators(self, fact_analysis: Dict[str, Any]) -> str:
        """
        Extract key indicators from fact analysis
        """
        try:
            indicators = []
            
            fraud_indicators = fact_analysis.get('fraud_indicators', [])
            for indicator in fraud_indicators[:3]:  # Top 3 indicators
                indicators.append(f"{indicator['indicator']} in {indicator['fact']}")
            
            if indicators:
                return "; ".join(indicators)
            else:
                return "no significant fraud indicators detected"
                
        except Exception as e:
            logging.error(f"Error extracting key indicators: {e}")
            return "error in indicator extraction"
    
    def _identify_missing_info(self, conversation_summary: Dict[str, Any], fact_analysis: Dict[str, Any]) -> str:
        """
        Identify missing critical information
        """
        try:
            missing = []
            
            key_facts = conversation_summary.get('key_facts', [])
            required_facts = ['customer_authorization', 'recipient_knowledge', 'remote_access']
            
            for fact in required_facts:
                if fact not in key_facts:
                    missing.append(fact.replace('_', ' '))
            
            if missing:
                return ", ".join(missing)
            else:
                return "sufficient information available"
                
        except Exception as e:
            logging.error(f"Error identifying missing info: {e}")
            return "error in missing info analysis"





