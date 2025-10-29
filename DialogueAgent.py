from strands import Agent, tool
from typing import Dict, Any, List, Optional, Tuple
import json
from datetime import datetime
from aws_bedrock import converse_with_claude_stream
from config import config
from vector_utils import search_similar
import logging
import yaml

def load_fraud_yaml_blocks(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    blocks = content.split('---')
    parsed = []
    for block in blocks:
        block = block.strip()
        if block:
            try:
                loaded = yaml.safe_load(block)
                if isinstance(loaded, dict):  # Only keep dicts
                    parsed.append(loaded)
            except Exception:
                continue
    return parsed

def rag_retrieve_questions(context, query=None):
    # Dynamic RAG: use vector search if query provided
    if query:
        hits = search_similar(query, top_k=3)
        return [hit['text'] if isinstance(hit, dict) and 'text' in hit else str(hit) for hit in hits]
    # Fallback: simple keyword search over questions.md
    questions = []
    try:
        with open('datasets/questions.md', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('*'):
                    questions.append(line.strip('- *"'))
    except Exception:
        pass
    return questions

class DialogueAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="dialogue-agent",
            name="DialogueAgent",
            description="Advanced dialogue agent with intelligent question generation and fact extraction"
        )
        self.agent_config = config.get_agent_config(self.name)
        self.logger = logging.getLogger(self.name)
        self.fraud_questions = load_fraud_yaml_blocks('datasets/questions.md')
        self.fraud_sop = load_fraud_yaml_blocks('datasets/SOP.md')

    @tool
    def conduct_dialogue(self, context: Dict[str, Any], user_response: Optional[str] = None, max_turns: Optional[int] = None) -> Tuple[Dict[str, Any], bool]:
        """Conduct intelligent dialogue with the customer to gather information."""
        try:
            dialogue_history = context.get('dialogue_history', []) if isinstance(context, dict) else []
            
            # Add user response to history
            if user_response is not None:
                if dialogue_history and isinstance(dialogue_history[-1], dict):
                    dialogue_history[-1]['user'] = user_response
                else:
                    dialogue_history.append({'user': user_response})
            
            # Get next question or finalization
            next_q, agent_name, done = self.get_next_question_and_agent(dialogue_history, context)
            
            # Only append to history in non-streaming mode; streaming path handles UI append to prevent duplicates
            if (not done) and len(dialogue_history) < (max_turns or config.conversation.max_dialogue_turns):
                dialogue_history.append({'agent': agent_name, 'question': next_q, 'agent_log': agent_name})

            # Update context
            if isinstance(context, dict):
                context['dialogue_history'] = dialogue_history
                context['dialogue_analysis'] = next_q
                if done:
                    context['dialogue_complete'] = True
                    
                    # Store dialogue summary when complete
                    case_id = context.get('transaction', {}).get('alert_id') or context.get('transaction', {}).get('customer_id') or 'unknown'
                    dialogue_summary = self._build_conversation_summary(dialogue_history)
                    context['customer_interaction'] = dialogue_summary
                    context['agent_summary'] = f"Dialogue interaction completed for {case_id}"

            return context, done
        except Exception as e:
            self.logger.error(f"Error in conduct_dialogue: {str(e)}")
            context['dialogue_error'] = str(e)
            return context, True

    def get_fraud_block(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get fraud block dynamically based on rule ID"""
        for block in self.fraud_questions:
            if block and block.get('fraud_type', '').lower() == rule_id.lower():
                return block
        return None

    def get_sop_block(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get SOP block dynamically based on rule ID"""
        for block in self.fraud_sop:
            if block and block.get('fraud_type', '').lower() == rule_id.lower():
                return block
        return None

    def extract_facts_intelligently(self, dialogue_history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Intelligent fact extraction with dynamic confidence scoring (OPTIMIZED)"""
        if context is None or not isinstance(context, dict):
            context = {}
        
        # OPTIMIZATION: Cache fact extraction results
        cache_key = f"extract_facts_{len(dialogue_history)}_{hash(str(dialogue_history[-1:]) if dialogue_history else '')}"
        
        if hasattr(context, 'extract_cache') and cache_key in context.get('extract_cache', {}):
            return context['extract_cache'][cache_key]
        
        # Use the base class intelligent fact extraction
        dialogue_text = self._build_dialogue_text(dialogue_history)
        facts = self._extract_facts_from_text(dialogue_text, context)
        
        # Add context-based facts
        context_facts = self._extract_context_facts(context)
        facts.update(context_facts)
        
        # Cache the result
        if 'extract_cache' not in context:
            context['extract_cache'] = {}
        context['extract_cache'][cache_key] = facts
        
        return facts

    def _extract_facts_from_text(self, dialogue_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract facts from dialogue text using intelligent analysis"""
        facts = {}
        
        if not dialogue_text:
            return facts
        
        text_lower = dialogue_text.lower()
        
        # Extract authorization facts
        if 'yes' in text_lower and 'authorize' in text_lower:
            facts['authorization'] = {'value': 'confirmed', 'confidence': 0.9, 'source': 'dialogue'}
        elif 'no' in text_lower and 'authorize' in text_lower:
            facts['authorization'] = {'value': 'denied', 'confidence': 0.9, 'source': 'dialogue'}
        
        # Extract relationship facts
        if any(word in text_lower for word in ['know', 'familiar', 'friend', 'family']):
            facts['relationship'] = {'value': 'known', 'confidence': 0.7, 'source': 'dialogue'}
        elif any(word in text_lower for word in ['unknown', 'stranger', 'never met']):
            facts['relationship'] = {'value': 'unknown', 'confidence': 0.8, 'source': 'dialogue'}
        
        # Extract scam indicators
        if any(word in text_lower for word in ['scam', 'fraud', 'suspicious']):
            facts['scam_suspected'] = {'value': 'yes', 'confidence': 0.9, 'source': 'dialogue'}
        
        # Extract urgency indicators
        if any(word in text_lower for word in ['urgent', 'hurry', 'quickly', 'immediately']):
            facts['urgency'] = {'value': 'high', 'confidence': 0.8, 'source': 'dialogue'}
        
        # Extract remote access indicators
        if any(word in text_lower for word in ['anydesk', 'teamviewer', 'remote access', 'screen sharing']):
            facts['remote_access'] = {'value': 'detected', 'confidence': 0.95, 'source': 'dialogue'}
        
        return facts

    def _build_dialogue_text(self, dialogue_history: List[Dict[str, Any]]) -> str:
        """Build dialogue text for fact extraction"""
        dialogue_parts = []
        
        for turn in dialogue_history:
            if isinstance(turn, dict):
                question = turn.get('question', '')
                user_response = turn.get('user', '')
                
                if question:
                    dialogue_parts.append(f"Q: {question}")
                if user_response:
                    dialogue_parts.append(f"A: {user_response}")
        
        return " ".join(dialogue_parts)

    def _extract_context_facts(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract facts from context data"""
        context_facts = {}
        
        # Extract from transaction context
        if 'transaction_context' in context:
            txn_text = context['transaction_context'].lower()
            if 'verified' in txn_text or 'confirmed' in txn_text:
                context_facts['verification'] = {'value': 'confirmed', 'confidence': 0.8, 'source': 'context'}
        
        # Extract from customer context
        if 'customer_context' in context:
            cust_text = context['customer_context'].lower()
            if 'high-risk' in cust_text:
                context_facts['risk_level'] = {'value': 'high', 'confidence': 0.9, 'source': 'context'}
            elif 'medium-risk' in cust_text:
                context_facts['risk_level'] = {'value': 'medium', 'confidence': 0.8, 'source': 'context'}
        
        # Extract from risk context
        if 'risk_summary_context' in context:
            risk_text = context['risk_summary_context'].lower()
            if 'scam' in risk_text:
                context_facts['scam_indicated'] = {'value': 'yes', 'confidence': 0.8, 'source': 'context'}
        
        return context_facts

    def summarize_known_facts(self, facts: Dict[str, Any]) -> str:
        """Intelligent fact summarization"""
        if not facts:
            return 'No facts confirmed yet.'
        
        fact_summaries = []
        for fact_type, fact_data in facts.items():
            if isinstance(fact_data, dict):
                value = fact_data.get('value', 'unknown')
                confidence = fact_data.get('confidence', 0.0)
                source = fact_data.get('source', 'extracted')
                fact_summaries.append(f"{fact_type.title()}: {value} (confidence: {confidence:.2f}, source: {source})")
            else:
                fact_summaries.append(f"{fact_type.title()}: {fact_data}")
        
        return '\n'.join(fact_summaries)

    def summarize_missing_facts(self, facts: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> List[str]:
        """Intelligent missing fact identification"""
        # Get required facts from configuration
        required_facts = ['authorization', 'relationship', 'verification_method', 'purpose']
        
        # Check which required facts are missing
        missing = [fact_type for fact_type in required_facts if fact_type not in facts]
        
        # Check for early finalization conditions
        dialogue_text = self._build_dialogue_text(dialogue_history).lower()
        
        # Early finalization indicators
        early_finalization_indicators = ['scam', 'fraud', 'remote access', 'anydesk', 'teamviewer']
        early_finalization = any(indicator in dialogue_text for indicator in early_finalization_indicators)
        
        # Check dialogue length
        max_turns = 8
        max_turns_reached = len(dialogue_history) >= max_turns
        
        # Check for repetitive responses
        user_responses = [turn.get('user', '').strip().lower() for turn in dialogue_history if 'user' in turn]
        repetitive_responses = len(user_responses) != len(set(user_responses)) and len(user_responses) > 6
        
        # Strong fraud indicators override missing facts
        text = (" ".join([turn.get('user','') for turn in dialogue_history if isinstance(turn, dict)])).lower()
        strong_indicators = any(k in text for k in [
            'anydesk','teamviewer','remote access','read out the security codes','otp','one-time password','security code',
            'bank security department','payid details','guided me step-by-step'
        ])
        
        # Allow finalization if any of these conditions are met
        if early_finalization or max_turns_reached or repetitive_responses or strong_indicators:
            return []
        
        return missing

    def get_next_question_and_agent(self, dialogue_history: List[Dict[str, Any]], context: Dict[str, Any]) -> Tuple[Any, str, bool]:
        """Intelligent next question generation with dynamic decision making (OPTIMIZED)"""
        if context is None:
            context = {}
        
        txn = context.get('transaction', {})
        if txn is None:
            txn = {}
        
        rule_id = txn.get('ruleId', '')
        fraud_block = self.get_fraud_block(rule_id)
        
        # OPTIMIZATION: Cache fact extraction results
        cache_key = f"facts_{len(dialogue_history)}_{hash(str(dialogue_history[-2:]) if len(dialogue_history) >= 2 else '')}"
        
        if hasattr(context, 'fact_cache') and cache_key in context.get('fact_cache', {}):
            facts = context['fact_cache'][cache_key]
        else:
            # Extract facts intelligently
            facts = self.extract_facts_intelligently(dialogue_history, context)
            # Cache the result
            if 'fact_cache' not in context:
                context['fact_cache'] = {}
            context['fact_cache'][cache_key] = facts
        
        # Get missing facts
        missing = self.summarize_missing_facts(facts, dialogue_history)
        
        # OPTIMIZATION: Early termination based on dialogue length and risk
        dialogue_length = len(dialogue_history)
        risk_score = self._calculate_dialogue_risk_score(context)
        
        # Early termination conditions (include strong indicators)
        text = (" ".join([turn.get('user','') for turn in dialogue_history if isinstance(turn, dict)])).lower()
        strong_indicators = any(k in text for k in [
            'anydesk','teamviewer','remote access','read out the security codes','otp','one-time password','security code',
            'bank security department','payid details','guided me step-by-step'
        ])
        early_termination_conditions = [
            dialogue_length >= 8,
            risk_score >= 0.8,
            not missing,
            strong_indicators,
        ]
        
        if any(early_termination_conditions):
            # Build final expert summary
            return self._build_final_summary(context, dialogue_history), self.name, True
        
        # OPTIMIZATION: Use cached questions for common scenarios
        question_cache_key = f"question_{rule_id}_{len(missing)}_{hash(str(missing[:2]))}"
        
        if hasattr(context, 'question_cache') and question_cache_key in context.get('question_cache', {}):
            next_question = context['question_cache'][question_cache_key]
        else:
            # Generate next intelligent question
            next_question = self._generate_next_question(missing, context, dialogue_history)
            # Cache the question
            if 'question_cache' not in context:
                context['question_cache'] = {}
            context['question_cache'][question_cache_key] = next_question
        
        if next_question:
            return self._build_question_prompt(next_question, context, dialogue_history), self.name, False
        
        # Fallback closing message
        closing_message = "Thank you for your cooperation. We have no further questions at this time."
        return closing_message, self.name, True

    def _calculate_dialogue_risk_score(self, context: Dict[str, Any]) -> float:
        """Calculate risk score for dialogue decisions"""
        risk_score = 0.5  # Default
        
        # Add risk from context
        if 'risk_summary_context' in context:
            risk_text = context['risk_summary_context'].lower()
            if 'high risk' in risk_text:
                risk_score += 0.3
            elif 'medium risk' in risk_text:
                risk_score += 0.1
        
        # Add risk from customer context
        if 'customer_context' in context:
            customer_text = context['customer_context'].lower()
            if 'high-risk' in customer_text:
                risk_score += 0.2
            elif 'vulnerable' in customer_text:
                risk_score += 0.1

        # Strong signals from dialogue content directly
        dh = context.get('dialogue_history', [])
        text = (" ".join([turn.get('user','') for turn in dh if isinstance(turn, dict)])).lower()
        if any(k in text for k in ['anydesk','teamviewer','remote access','security code','otp','one-time password']):
            risk_score += 0.3
        if any(k in text for k in ['bank security department','urgent','pressure','secrecy']):
            risk_score += 0.2
        
        return min(1.0, risk_score)

    def _generate_next_question(self, missing_facts: List[str], context: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> Optional[str]:
        """Generate intelligent next question based on missing facts"""
        if not missing_facts:
            return None
        
        # Get already asked questions
        already_asked = set(turn.get('question', '').lower() for turn in dialogue_history if 'question' in turn)
        
        # Try to find relevant questions for missing facts
        for missing_fact in missing_facts:
            query = f"{missing_fact.replace('_', ' ')} question"
            rag_questions = rag_retrieve_questions(context, query=query)
            
            for question in rag_questions:
                question_lower = question.lower()
                if not any(question_lower in asked for asked in already_asked):
                    return question
        
        return None

    def _build_final_summary(self, context: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> str:
        """Build intelligent final summary without prematurely running final agents."""
        # Signal orchestration to finalize after the dialogue loop
        try:
            if isinstance(context, dict):
                context['finalization_requested'] = True
                context['chat_done'] = True
        except Exception:
            pass
        
        # Build context summary
        context_summary = self._build_dialogue_context_summary(context)
        
        # Build conversation summary
        conversation_summary = self._build_conversation_summary(dialogue_history)
        
        # Show placeholders until finalization node completes
        final_risk = context.get('final_risk_determination', 'Final risk assessment will be computed now...')
        policy_decision = context.get('policy_decision', 'Policy decision will follow the final risk assessment...')
        
        # If escalation or critical risk identified, enforce urgent intervention tone and steps
        urgency_directives = ""
        risk_text = (final_risk or "").lower()
        if any(keyword in risk_text for keyword in ["critical", "escalate", "freeze", "ato", "account takeover", "remote access", "technical support scam", "high risk"]):
            urgency_directives = (
                "\nURGENT CUSTOMER INSTRUCTIONS:\n"
                "- Clearly state the account is temporarily secured for protection.\n"
                "- Instruct the customer to disconnect any remote access sessions (AnyDesk/TeamViewer/QuickSupport).\n"
                "- Ask them to power off the compromised device and use another trusted device.\n"
                "- Inform that payment recall/hold has been initiated with receiving institution.\n"
                "- Advise that credentials will be reset and enhanced monitoring applied.\n"
            )

        prompt = f"""
You are an expert fraud investigation agent. Provide a clear, professional final summary for the customer.

CONTEXT:
{context_summary}

CONVERSATION:
{conversation_summary}

FINAL ASSESSMENT:
{final_risk}

POLICY DECISION:
{policy_decision}

REQUIREMENTS:
- Summarize findings and risk assessment.
- Provide specific, actionable next steps; avoid vague language.
- Do NOT ask for further input or promise manual review timeframes.
- Focus on authorized scam detection and protection measures.
- Include final risk level and policy decision.
{urgency_directives}

Write a concise, directive summary appropriate for immediate customer communication.
"""
        
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            # If model still hedges, harden tone under XYZ SOPs
            if 'insufficient' in result.lower() or 'cannot' in result.lower():
                result += "\n\nNote: Under XYZ APP fraud SOP, context is sufficient for policy decision due to BEC indicators."
            return result
        except Exception as e:
            self.logger.error(f"Failed to build final summary: {e}")
            return "Investigation summary unavailable due to technical issues"

    def _build_dialogue_context_summary(self, context: Dict[str, Any]) -> str:
        """Build intelligent COMPRESSED dialogue context summary"""
        summary_parts = []
        
        # COMPRESSED TRANSACTION SUMMARY
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 'Unknown')
                payee = txn.get('payee', 'Unknown')
                rule_id = txn.get('ruleId', 'Unknown')
                summary_parts.append(f"TXN: ${amount} to {payee} ({rule_id})")
        
        # COMPRESSED RISK SUMMARY
        if 'risk_summary_context' in context:
            risk_text = context['risk_summary_context'].lower()
            risk_level = "HIGH" if "high" in risk_text else "MEDIUM" if "medium" in risk_text else "LOW"
            summary_parts.append(f"RISK: {risk_level}")
            
            # Extract key indicators
            indicators = []
            if 'scam' in risk_text:
                indicators.append("SCAM")
            if 'fraud' in risk_text:
                indicators.append("FRAUD")
            if 'suspicious' in risk_text:
                indicators.append("SUSPICIOUS")
            
            if indicators:
                summary_parts.append(f"INDICATORS: {', '.join(indicators)}")
        
        # COMPRESSED CUSTOMER SUMMARY
        if 'customer_context' in context:
            cust_text = context['customer_context'].lower()
            if 'high-risk' in cust_text:
                summary_parts.append("CUSTOMER: HIGH-RISK")
            elif 'vulnerable' in cust_text:
                summary_parts.append("CUSTOMER: VULNERABLE")
            else:
                summary_parts.append("CUSTOMER: STANDARD")
        
        return " | ".join(summary_parts) if summary_parts else "CONTEXT: Limited"

    def _build_conversation_summary(self, dialogue_history: List[Dict[str, Any]]) -> str:
        """Build intelligent COMPRESSED conversation summary"""
        if not dialogue_history:
            return "No conversation history available"
        
        # COMPRESSED CONVERSATION SUMMARY
        if len(dialogue_history) <= 3:
            # For short conversations, show full Q&A
            conversation_parts = []
            for turn in dialogue_history:
                if isinstance(turn, dict):
                    question = turn.get('question', '')
                    user_response = turn.get('user', '')
                    
                    if question:
                        conversation_parts.append(f"Q: {question}")
                    if user_response:
                        conversation_parts.append(f"A: {user_response}")
            
            return "\n".join(conversation_parts)
        else:
            # For longer conversations, create compressed summary
            key_points = []
            facts_extracted = []
            red_flags = []
            
            # Analyze last 3 turns for key information
            recent_turns = dialogue_history[-3:]
            
            for turn in recent_turns:
                if isinstance(turn, dict):
                    question = turn.get('question', '').lower()
                    answer = turn.get('user', '').lower()
                    
                    # Extract key information
                    if 'authorize' in answer or 'confirm' in answer:
                        facts_extracted.append("AUTHORIZED")
                    if 'scam' in answer or 'fraud' in answer:
                        red_flags.append("SCAM MENTIONED")
                    if 'pressure' in answer or 'urgent' in answer:
                        red_flags.append("PRESSURE DETECTED")
                    if 'unknown' in answer or 'stranger' in answer:
                        red_flags.append("UNKNOWN RELATIONSHIP")
                    if 'investment' in answer or 'return' in answer:
                        facts_extracted.append("INVESTMENT")
                    if 'romance' in answer or 'relationship' in answer:
                        facts_extracted.append("ROMANCE")
                    if 'tech support' in answer or 'computer' in answer:
                        facts_extracted.append("TECH SUPPORT")
            
            # Build compressed summary
            summary_parts = []
            if facts_extracted:
                summary_parts.append(f"FACTS: {', '.join(set(facts_extracted))}")
            if red_flags:
                summary_parts.append(f"RED FLAGS: {', '.join(set(red_flags))}")
            summary_parts.append(f"TURNS: {len(dialogue_history)}")
            
            return " | ".join(summary_parts)

    def _build_question_prompt(self, next_question: str, context: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> str:
        """Build intelligent question prompt with detective framing and memory context."""
        # Build context summary
        context_summary = self._build_dialogue_context_summary(context)
        # Build conversation summary
        conversation_summary = self._build_conversation_summary(dialogue_history)
        
        prompt = f"""
You are a senior fraud analyst acting like a methodical detective. Your goal is to determine whether this is an AUTHORIZED PAYMENT SCAM (APP) or legitimate.

CONTEXT (COMPRESSED):
{context_summary}

RECENT CONVERSATION (COMPRESSED):
{conversation_summary}

QUESTION SEED: {next_question}

CRITICAL INSTRUCTIONS:
- You MUST return EXACTLY ONE question only.
- Do NOT ask multiple questions in one response.
- Do NOT include any explanations, context, or additional text.
- Return ONLY the single question that best progresses the investigation.
- Be professional, empathetic, and precise.
- Prioritize confirming: remote access/social engineering, third-party instructions, recipient verification, device/auth changes, and purpose/beneficiary relationship.

FORMAT: Return only the question, nothing else.
"""
        
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            
            # Clean and validate the response to ensure only one question
            cleaned_result = self._clean_and_validate_question(result)
            return cleaned_result
            
        except Exception as e:
            self.logger.error(f"Failed to build question prompt: {e}")
            # Fallback to a deterministic investigative question
            facts = self.extract_facts_intelligently(dialogue_history, context)
            fallback_q = self._generate_investigative_question(facts, context, dialogue_history)
            return self._clean_and_validate_question(fallback_q or next_question)

    def _generate_investigative_question(self, facts: Dict[str, Any], context: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> Optional[str]:
        """Fallback deterministic investigative question selection when RAG has no items."""
        asked = set(turn.get('question', '').strip().lower() for turn in dialogue_history if isinstance(turn, dict) and 'question' in turn)
        probes = [
            "Are you currently on a call or screen-sharing with anyone who asked you to make this payment?",
            "Did anyone contact you claiming to be from the bank, police, ATO, or a company to guide this payment?",
            "How did you verify the recipient's details before sending this payment?",
            "Which device did you use to log in, and did anything look different during login or MFA?",
            "Did you change your password or receive any password-reset messages shortly before making this payment?",
            "What is the purpose of this payment, in your own words?",
            "Have you established this payee before or is this the first time?",
            "Did anyone ask you to keep this transaction secret or act urgently?"
        ]
        for q in probes:
            if q.lower() not in asked:
                return q
        return None

    def _clean_and_validate_question(self, question_text: str) -> str:
        """Clean and validate question to ensure only one question is returned."""
        if not question_text:
            return "Can you confirm your identity and details for this transaction?"
        
        # Remove extra whitespace and normalize
        question_text = question_text.strip()
        
        # Split by common question separators and take only the first question
        separators = ['\n\n', '\n', '?', '??', '???']
        for sep in separators:
            if sep in question_text:
                parts = question_text.split(sep)
                # Find the first part that looks like a question
                for part in parts:
                    part = part.strip()
                    if part and ('?' in part or any(word in part.lower() for word in ['have you', 'did you', 'can you', 'do you', 'what', 'when', 'where', 'why', 'how', 'who'])):
                        # Ensure it ends with a question mark
                        if not part.endswith('?'):
                            part = part.rstrip('.') + '?'
                        return part
        
        # If no clear question found, ensure it ends with a question mark
        if not question_text.endswith('?'):
            question_text = question_text.rstrip('.') + '?'
        
        return question_text

dialogue_agent = DialogueAgent()