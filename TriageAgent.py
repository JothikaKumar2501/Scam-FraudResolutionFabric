from strands import Agent, tool
from typing import Dict, Any, List
import json
from datetime import datetime
from aws_bedrock import converse_with_claude_stream
from config import config
from vector_utils import search_similar
import logging

class TriageAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="triage-agent",
            name="TriageAgent",
            description="Advanced triage agent with intelligent escalation and dialogue decision making"
        )
        self.agent_config = config.get_agent_config(self.name)
        self.logger = logging.getLogger(self.name)

    @tool
    def triage_case(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform triage on the case and make escalation/dialogue decisions."""
        try:
            # Get dynamic SOPs based on triage context
            triage_query = self._build_triage_query(context)
            sops = self._retrieve_sop(context, query=triage_query)
            
            # Get all context summaries
            txn = context.get('transaction_context', '[unavailable]')
            cust = context.get('customer_context', '[unavailable]')
            merch = context.get('merchant_context', '[unavailable]')
            anom = context.get('anomaly_context', '[unavailable]')
            risk = context.get('risk_summary_context', '[unavailable]')
            
            # Build intelligent triage prompt (ANZ context-aware)
            prompt = self._build_triage_prompt(txn, cust, merch, anom, risk, sops)
            
            # Get expert triage decision
            result = self._get_expert_triage(prompt)
            
            # Add to context with metadata
            context['triage_decision'] = result
            context['triage_timestamp'] = datetime.now().isoformat()
            context['dialogue_required'] = self._determine_dialogue_required(result)
            context['escalation_required'] = self._determine_escalation_required(result)
            
            self.logger.info(f"Triage completed for case: {context.get('transaction', {}).get('alert_id', 'Unknown')}")
            return context
        except Exception as e:
            self.logger.error(f"Error in triage_case: {str(e)}")
            context['triage_error'] = str(e)
            return context

    def _build_triage_query(self, context: Dict[str, Any]) -> str:
        query_parts = []
        
        # Add risk context
        if 'risk_summary_context' in context:
            query_parts.append("risk assessment triage")
        
        # Add customer context
        if 'customer_context' in context:
            query_parts.append("customer vulnerability triage")
        
        return " ".join(query_parts) if query_parts else "triage decision making"

    def _retrieve_sop(self, context, query=None):
        # Dynamic RAG: use vector search if query provided
        if query:
            hits = search_similar(query, top_k=3)
            return [hit['text'] if isinstance(hit, dict) and 'text' in hit else str(hit) for hit in hits]
        # Fallback: simple keyword search over SOP.md
        sops = []
        try:
            with open('datasets/SOP.md', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        sops.append(line.strip())
        except Exception as e:
            self.logger.error(f"Error reading SOP file: {str(e)}")
        return sops

    def _build_triage_prompt(self, txn: str, cust: str, merch: str, anom: str, risk: str, sops: List[str]) -> str:
        specialized_prompts = self.agent_config.specialized_prompts
        
        escalation_prompt = specialized_prompts.get('escalation_decision',
            "Decide on escalation or dialogue based on risk assessment")
        
        priority_prompt = specialized_prompts.get('priority_assessment',
            "Assess case priority and urgency")
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:5]) if sops else "No specific SOPs found"
        
        prompt = f"""
You are a triage agent specializing in case prioritization and escalation decisions.

{escalation_prompt}
{priority_prompt}

CONTEXT SUMMARIES:
Transaction Context: {txn}
Customer Context: {cust}
Merchant Context: {merch}
Behavioral/Anomaly Context: {anom}
Risk Synthesis: {risk}

RELEVANT SOPs:
{sop_summary}

TRIAGE REQUIREMENTS:
1. Analyze all context summaries and risk assessment
2. Cite relevant SOP rules and compliance requirements
3. Provide clear triage decision (ESCALATE/DIALOGUE/CLOSE)
4. Justify decision with specific risk factors and indicators
5. Assess case priority and urgency level
6. Consider customer vulnerability and protection needs
7. Recommend next steps and resource allocation

Provide a concise, expert-level triage decision for fraud operations.
"""
        return prompt

    def _get_expert_triage(self, prompt: str) -> str:
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            return result
        except Exception as e:
            self.logger.error(f"Failed to get expert triage: {e}")
            return "Triage decision unavailable due to technical issues"

    def _determine_escalation_required(self, result: str) -> bool:
        if not result:
            return False
        
        result_lower = result.lower()
        
        escalation_indicators = [
            'escalate', 'escalation', 'high priority', 'urgent',
            'senior analyst', 'management review', 'immediate attention'
        ]
        
        return any(indicator in result_lower for indicator in escalation_indicators)

    def _determine_dialogue_required(self, result: str) -> bool:
        if not result:
            return True  # Default to dialogue for safety
        
        result_lower = result.lower()
        
        dialogue_indicators = [
            'dialogue', 'questioning', 'customer contact', 'verification',
            'investigation', 'further inquiry'
        ]
        
        close_indicators = [
            'close', 'no action', 'false positive', 'legitimate transaction'
        ]
        
        if any(indicator in result_lower for indicator in close_indicators):
            return False
        
        return any(indicator in result_lower for indicator in dialogue_indicators)

triage_agent = TriageAgent()
