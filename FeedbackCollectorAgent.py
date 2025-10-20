from strands import Agent, tool
from typing import Dict, Any, List
import json
from datetime import datetime
from aws_bedrock import converse_with_claude_stream
from config import config
from vector_utils import search_similar
import logging

class FeedbackCollectorAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="feedback-collector-agent",
            name="FeedbackCollectorAgent",
            description="Advanced feedback collector agent with structured improvement analysis"
        )
        self.agent_config = config.get_agent_config(self.name)
        self.logger = logging.getLogger(self.name)

    @tool
    def collect_feedback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect feedback and generate improvement suggestions based on case outcomes."""
        try:
            # Get dynamic SOPs based on feedback context
            feedback_query = self._build_feedback_query(context)
            sops = self._retrieve_sop(context, query=feedback_query)
            
            # Get the final determinations
            final_risk = context.get('final_risk_determination', context.get('risk_assessment_summary', '[Not available]'))
            policy_decision = context.get('policy_decision', '[Not available]')
            
            # Build intelligent feedback prompt
            prompt = self._build_feedback_prompt(context, final_risk, policy_decision, sops)
            
            # Get expert feedback
            result = self._get_expert_feedback(prompt)
            
            # Add to context with metadata
            context['feedback'] = result
            context['feedback_timestamp'] = datetime.now().isoformat()
            context['improvement_priorities'] = self._extract_improvement_priorities(result)
            
            self.logger.info(f"Feedback collection completed for case: {context.get('transaction', {}).get('alert_id', 'Unknown')}")
            return context
        except Exception as e:
            self.logger.error(f"Error in collect_feedback: {str(e)}")
            context['feedback_error'] = str(e)
            return context

    def _build_feedback_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for feedback analysis"""
        query_parts = []
        
        # Add case outcome context
        if 'policy_decision' in context:
            query_parts.append("case outcome feedback")
        
        # Add system performance context
        if 'dialogue_history' in context:
            query_parts.append("system performance feedback")
        
        return " ".join(query_parts) if query_parts else "authorized scam feedback collection"

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

    def _build_feedback_prompt(self, context: Dict[str, Any], final_risk: str, policy_decision: str, sops: List[str]) -> str:
        """Build intelligent feedback prompt"""
        specialized_prompts = self.agent_config.specialized_prompts
        
        feedback_prompt = specialized_prompts.get('feedback_generation',
            "Generate structured feedback questions to improve detection and customer protection")
        
        improvement_prompt = specialized_prompts.get('improvement_analysis',
            "Analyze system performance and identify improvement opportunities")
        
        # Build case summary
        case_summary = self._build_case_summary(context, final_risk, policy_decision)
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:5]) if sops else "No specific SOPs found"
        
        prompt = f"""
You are an expert feedback collector for the AUTHORIZED SCAM prevention system.

{feedback_prompt}
{improvement_prompt}

CASE SUMMARY:
{case_summary}

RELEVANT SOPs:
{sop_summary}

GENERATE FEEDBACK COLLECTION FOCUSING ON:

1. DETECTION ACCURACY:
   - Was this correctly identified as an authorized scam?
   - What indicators did we miss?
   - False positive/negative assessment?

2. CUSTOMER INTERACTION QUALITY:
   - Were questions empathetic and appropriate?
   - Did we identify customer vulnerability?
   - Was the dialogue length optimal?

3. RISK INDICATORS:
   - New scam patterns observed?
   - Behavioral red flags we should add?
   - SOPs that need updating?

4. DECISION EFFECTIVENESS:
   - Was the policy action appropriate?
   - Customer outcome (if known)?
   - Regulatory compliance gaps?

5. SYSTEM IMPROVEMENTS:
   - Additional data points needed?
   - Agent performance issues?
   - Process optimization opportunities?

FORMAT: Create specific questions an analyst can answer to improve future detection. Include rating scales where appropriate (1-5) and text fields for detailed feedback.
"""
        return prompt

    def _build_case_summary(self, context: Dict[str, Any], final_risk: str, policy_decision: str) -> str:
        """Build intelligent case summary for feedback"""
        summary_parts = []
        
        # Transaction summary
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 'Unknown')
                payee = txn.get('payee', 'Unknown')
                summary_parts.append(f"Transaction: ${amount} to {payee}")
        
        # Risk assessment summary
        scam_detected = 'yes' in final_risk.lower() and 'authorized scam' in final_risk.lower()
        summary_parts.append(f"Final Risk Assessment: {'SCAM DETECTED' if scam_detected else 'CHECK ASSESSMENT'}")
        
        # Policy decision summary
        blocked = 'block' in str(policy_decision).lower()
        summary_parts.append(f"Policy Action: {'BLOCKED' if blocked else 'CHECK DECISION'}")
        
        # Dialogue summary
        dialogue_turns = len(context.get('dialogue_history', []))
        summary_parts.append(f"Dialogue Turns: {dialogue_turns}")
        
        return "\n".join(summary_parts)

    def _get_expert_feedback(self, prompt: str) -> str:
        """Get expert feedback with error handling"""
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            return result
        except Exception as e:
            self.logger.error(f"Failed to get expert feedback: {e}")
            return "Feedback collection unavailable due to technical issues"

    def _extract_improvement_priorities(self, result: str) -> List[str]:
        """Extract improvement priorities from feedback"""
        if not result:
            return []
        
        priorities = []
        result_lower = result.lower()
        
        # Identify improvement areas
        improvement_areas = {
            'detection_accuracy': ['missed indicators', 'false positive', 'false negative'],
            'customer_interaction': ['empathy', 'dialogue quality', 'question appropriateness'],
            'risk_indicators': ['new patterns', 'red flags', 'sop updates'],
            'decision_effectiveness': ['policy action', 'regulatory compliance'],
            'system_performance': ['data points', 'agent performance', 'process optimization']
        }
        
        for area, indicators in improvement_areas.items():
            if any(indicator in result_lower for indicator in indicators):
                priorities.append(area)
        
        return priorities

feedback_collector_agent = FeedbackCollectorAgent()