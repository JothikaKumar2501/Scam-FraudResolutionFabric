from strands import Agent, tool
from typing import Dict, Any, List
import json
from datetime import datetime
from aws_bedrock import converse_with_claude_stream
from config import config
from vector_utils import search_similar
import logging

class RiskAssessorAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="risk-assessor-agent",
            name="RiskAssessorAgent",
            description="Advanced risk assessor agent with progressive assessment and final determination capabilities"
        )
        self.agent_config = config.get_agent_config(self.name)
        self.logger = logging.getLogger(self.name)

    @tool
    def assess_risk(self, context: Dict[str, Any], is_final: bool = False) -> Dict[str, Any]:
        """Assess risk based on current context and dialogue progress."""
        try:
            # Prevent unbounded calls: allow only one progressive and one final per case
            if isinstance(context, dict):
                flags = context.setdefault('risk_assessor_flags', {'progressive_done': False, 'final_done': False})
            else:
                flags = {'progressive_done': False, 'final_done': False}
            
            # Get dynamic SOPs based on risk assessment context
            risk_query = self._build_risk_assessment_query(context)
            sops = self._retrieve_sop(context, query=risk_query)
            
            # Check if this is during dialogue or final assessment
            is_final_assessment = is_final or 'Final risk summary' in str(context) or 'final' in str(context).lower()
            if is_final_assessment and flags.get('final_done'):
                return context
            if not is_final_assessment and flags.get('progressive_done'):
                return context
            
            # Build dialogue summary if available
            dialogue_summary = self._build_dialogue_summary(context)
            
            # Build intelligent assessment prompt
            if is_final_assessment:
                prompt = self._build_final_assessment_prompt(context, dialogue_summary, sops)
            else:
                prompt = self._build_progressive_assessment_prompt(context, dialogue_summary, sops)
            
            # Get expert assessment
            result = self._get_expert_assessment(prompt)
            
            # Ensure typology normalization for BEC cases
            if 'bec' in result.lower() or 'business email compromise' in result.lower():
                if 'TYPOLOGY:' in result:
                    # leave explicit block if present
                    pass
                else:
                    result += "\n\nTYPOLOGY: business_email_compromise"
            
            # Add to context with metadata
            # Enforce ANZ bank guidelines and avoid "insufficient" hedging if gating passed
            safe_result = result or ""
            if context.get('gate_reason', {}).get('passed'):
                # Remove hedging lines to avoid contradictory outputs when gate passed
                try:
                    filtered_lines = []
                    for line in safe_result.splitlines():
                        ll = line.strip().lower()
                        if ('insufficient' in ll) or ('cannot make' in ll) or ('unable to determine' in ll):
                            continue
                        filtered_lines.append(line)
                    safe_result = "\n".join(filtered_lines).strip()
                except Exception:
                    pass
                # Add explicit note reinforcing finalization
                if 'Note: Expert gate indicates sufficient context' not in safe_result:
                    safe_result += "\n\nNote: Expert gate indicates sufficient context; proceed with final determination under ANZ APP fraud SOP."
            
            context['risk_assessment'] = safe_result
            context['risk_assessment_timestamp'] = datetime.now().isoformat()
            context['assessment_type'] = 'final' if is_final_assessment else 'progressive'
            
            # Create and store compressed summaries for the PolicyDecisionAgent
            context['compressed_context_summary'] = self._build_compressed_context_summary(context)
            context['compressed_risk_summary'] = self._build_compressed_risk_summary(context)

            # Check if risk assessor recommends finalization
            if not is_final_assessment and 'finalize' in safe_result.lower():
                context['risk_ready_to_finalize'] = True
                
            # Add to context with metadata, without polluting final fields during progressive runs
            if is_final_assessment:
                context['final_risk_assessment'] = safe_result
                context['final_risk_determination'] = safe_result
                context['risk_assessment_summary'] = safe_result
            else:
                context['progressive_risk_assessment'] = safe_result
                context['latest_risk_assessment'] = safe_result
            context['risk_assessment_timestamp'] = datetime.now().isoformat()
            
            # Mark completion flags
            if is_final_assessment:
                flags['final_done'] = True
            else:
                flags['progressive_done'] = True
            context['risk_assessor_flags'] = flags

            self.logger.info(f"Risk assessment completed for case: {context.get('transaction', {}).get('alert_id', 'Unknown')}")
            return context
        except Exception as e:
            self.logger.error(f"Error in assess_risk: {str(e)}")
            context['risk_assessment_error'] = str(e)
            return context

    def _build_risk_assessment_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for risk assessment"""
        query_parts = []
        
        # Add transaction context
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 0)
                query_parts.append(f"transaction risk assessment {amount}")
        
        # Add dialogue context
        if 'dialogue_history' in context:
            query_parts.append("dialogue risk assessment")
        
        return " ".join(query_parts) if query_parts else "authorized scam risk assessment"

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

    def _build_dialogue_summary(self, context: Dict[str, Any]) -> str:
        """Build intelligent compressed dialogue summary"""
        if not context.get('dialogue_history'):
            return ""
        
        # COMPRESSED DIALOGUE SUMMARY
        dialogue_history = context.get('dialogue_history', [])
        if len(dialogue_history) <= 2:
            # For short dialogues, show full Q&A
            dialogue_summary = "\n".join([
                f"Q: {turn.get('question', '')}\nA: {turn.get('user', '[No response yet]')}" 
                for turn in dialogue_history 
                if isinstance(turn, dict) and 'question' in turn
            ])
        else:
            # For longer dialogues, create compressed summary
            key_points = []
            facts_extracted = []
            red_flags = []
            
            for turn in dialogue_history:
                if isinstance(turn, dict):
                    question = turn.get('question', '').lower()
                    answer = turn.get('user', '').lower()
                    
                    # Extract key information
                    if 'authorize' in answer or 'confirm' in answer:
                        facts_extracted.append("Customer authorized transaction")
                    if 'scam' in answer or 'fraud' in answer:
                        red_flags.append("Customer mentioned scam/fraud")
                    if 'pressure' in answer or 'urgent' in answer:
                        red_flags.append("Pressure/urgency tactics detected")
                    if 'unknown' in answer or 'stranger' in answer:
                        red_flags.append("Unknown/stranger relationship")
                    if 'investment' in answer or 'return' in answer:
                        facts_extracted.append("Investment-related transaction")
                    if 'romance' in answer or 'relationship' in answer:
                        facts_extracted.append("Romance/relationship context")
                    if 'tech support' in answer or 'computer' in answer:
                        facts_extracted.append("Tech support scenario")
            
            # Build compressed summary
            summary_parts = []
            if facts_extracted:
                summary_parts.append(f"FACTS: {', '.join(set(facts_extracted))}")
            if red_flags:
                summary_parts.append(f"RED FLAGS: {', '.join(set(red_flags))}")
            summary_parts.append(f"TURNS: {len(dialogue_history)}")
            
            dialogue_summary = " | ".join(summary_parts)
        
        return dialogue_summary

    def _build_final_assessment_prompt(self, context: Dict[str, Any], dialogue_summary: str, sops: List[str]) -> str:
        """Build intelligent final assessment prompt with COMPRESSED AGENT LOGS"""
        specialized_prompts = self.agent_config.specialized_prompts
        
        final_determination_prompt = specialized_prompts.get('final_determination',
            "Make final scam determination based on complete investigation")
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:3]) if sops else "No specific SOPs found"
        
        # Get compressed agent logs
        compressed_agent_logs = context.get('compressed_agent_logs', 'AGENT LOGS: Not available')
        
        # Provide explicit, deterministic rubric to avoid "insufficient data" when gate already passed
        prompt = f"""
You are an expert risk assessor specializing in authorized payment scams (APP fraud).

{final_determination_prompt}

Assume dialogue context is sufficient (expert gate passed). Use the rubric below and avoid stating that data is insufficient.

COMPRESSED AGENT LOGS:
{compressed_agent_logs}

COMPLETE CUSTOMER DIALOGUE (compressed):
{dialogue_summary}

RELEVANT SOPs:
{sop_summary}

RUBRIC:
- If remote access tools (AnyDesk/TeamViewer), OTP/code sharing, and impersonation of bank staff are present → Authorized Scam = Yes, Confidence = High.
- If caller provided PayID/instructions and urgency/secrecy present → Authorized Scam = Yes, Confidence = High.
- If relationship is verified, no social engineering, and legitimate invoice context → consider No or Medium with justification.

OUTPUT (STRICT):
1) AUTHORIZED_SCAM: Yes/No
2) CONFIDENCE: High/Medium/Low
3) INDICATORS: bullet list
4) RED_FLAGS: bullet list
5) ACTIONS: bullet list (customer protection + operational)
6) TYPOLOGY: one of [business_email_compromise, impersonation, tech_support, romance, investment, purchase, other]
"""
        return prompt

    def _build_progressive_assessment_prompt(self, context: Dict[str, Any], dialogue_summary: str, sops: List[str]) -> str:
        """Build intelligent progressive assessment prompt with COMPRESSED CONTEXT"""
        specialized_prompts = self.agent_config.specialized_prompts
        
        progressive_prompt = specialized_prompts.get('progressive_assessment',
            "Evaluate the CURRENT state of the investigation based on dialogue progress")
        
        # COMPRESSED CONTEXT SUMMARIES
        compressed_context = self._build_compressed_context_summary(context)
        compressed_risk = self._build_compressed_risk_summary(context)
        compressed_triage = self._build_compressed_triage_summary(context)
        
        # OPTIMIZATION: Use only first 2 SOPs for speed
        sop_summary = "\n".join(sops[:2]) if sops else "No specific SOPs found"
        
        # EXPERT-LEVEL COMPRESSED PROMPT
        prompt = f"""
ANZ Bank Expert Risk Assessment - COMPRESSED CONTEXT

{compressed_context}
{compressed_risk}
{compressed_triage}

DIALOGUE SUMMARY: {dialogue_summary}
RELEVANT SOPs: {sop_summary[:180]}...

EXPERT ASSESSMENT (SHORT BULLETS):
- Risk Level: [HIGH/MEDIUM/LOW]
- Scam Typology: [Type or None]
- Sufficient Info: [Yes/No]
- Next Action: [Ask <1 best question>/Finalize/Escalate]
- Key Missing: [If any]

IMPORTANT: If remote access, code sharing, and impersonation are detected, set Sufficient Info = Yes and recommend FINALIZE with High risk.
If information is borderline, return exactly ONE targeted question that would unlock finalization.
"""
        return prompt

    def _get_expert_assessment(self, prompt: str) -> str:
        """Get expert assessment with error handling"""
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
                ], max_tokens=self.agent_config.max_tokens)])
            return result
        except Exception as e:
            self.logger.error(f"Failed to get expert assessment: {e}")
            return "Risk assessment unavailable due to technical issues"

    def _build_compressed_context_summary(self, context: Dict[str, Any]) -> str:
        """Build compressed context summary for expert agents"""
        summary_parts = []
        
        # Transaction context
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 0)
                payee = txn.get('payee', 'Unknown')
                rule_id = txn.get('ruleId', 'Unknown')
                summary_parts.append(f"TXN: ${amount} to {payee} ({rule_id})")
        
        # Context availability
        context_flags = []
        if context.get('transaction_context'):
            context_flags.append("TXN")
        if context.get('customer_context'):
            context_flags.append("CUST")
        if context.get('merchant_context'):
            context_flags.append("MERCH")
        if context.get('anomaly_context'):
            context_flags.append("BEHAV")
        
        if context_flags:
            summary_parts.append(f"CONTEXT: {'+'.join(context_flags)}")
        
        # Key indicators from context
        indicators = []
        if context.get('transaction_context'):
            txn_text = context['transaction_context'].lower()
            if 'verified' in txn_text:
                indicators.append("VERIFIED")
            if 'suspicious' in txn_text:
                indicators.append("SUSPICIOUS")
        
        if context.get('customer_context'):
            cust_text = context['customer_context'].lower()
            if 'high-risk' in cust_text:
                indicators.append("HIGH-RISK")
            if 'vulnerable' in cust_text:
                indicators.append("VULNERABLE")
        
        if indicators:
            summary_parts.append(f"INDICATORS: {', '.join(indicators)}")
        
        return " | ".join(summary_parts) if summary_parts else "CONTEXT: Limited"

    def _build_compressed_risk_summary(self, context: Dict[str, Any]) -> str:
        """Build compressed risk summary for expert agents"""
        summary_parts = []
        
        # Risk synthesis
        if context.get('risk_summary_context'):
            risk_text = context['risk_summary_context'].lower()
            risk_level = "HIGH" if "high" in risk_text else "MEDIUM" if "medium" in risk_text else "LOW"
            summary_parts.append(f"RISK: {risk_level}")
            
            # Extract key risk factors
            risk_factors = []
            if 'scam' in risk_text:
                risk_factors.append("SCAM")
            if 'fraud' in risk_text:
                risk_factors.append("FRAUD")
            if 'suspicious' in risk_text:
                risk_factors.append("SUSPICIOUS")
            if 'anomaly' in risk_text:
                risk_factors.append("ANOMALY")
            
            if risk_factors:
                summary_parts.append(f"FACTORS: {', '.join(risk_factors)}")
        
        # Scam typology
        if context.get('scam_typology'):
            summary_parts.append(f"TYPOLOGY: {context['scam_typology']}")
        
        # Confidence
        if context.get('risk_confidence'):
            confidence = context['risk_confidence']
            summary_parts.append(f"CONFIDENCE: {confidence:.2f}")
        
        return " | ".join(summary_parts) if summary_parts else "RISK: Not assessed"

    def _build_compressed_triage_summary(self, context: Dict[str, Any]) -> str:
        """Build compressed triage summary for expert agents"""
        summary_parts = []
        
        # Triage decision
        if context.get('triage_decision'):
            triage_text = context['triage_decision'].lower()
            if 'escalate' in triage_text:
                summary_parts.append("TRIAGE: ESCALATE")
            elif 'dialogue' in triage_text:
                summary_parts.append("TRIAGE: DIALOGUE")
            else:
                summary_parts.append("TRIAGE: MONITOR")
        
        # Escalation flags
        escalation_flags = []
        if context.get('escalation_required'):
            escalation_flags.append("ESCALATION")
        if context.get('dialogue_required'):
            escalation_flags.append("DIALOGUE")
        if context.get('immediate_action'):
            escalation_flags.append("IMMEDIATE")
        
        if escalation_flags:
            summary_parts.append(f"FLAGS: {', '.join(escalation_flags)}")
        
        # Priority level
        if context.get('priority_level'):
            summary_parts.append(f"PRIORITY: {context['priority_level']}")
        
        return " | ".join(summary_parts) if summary_parts else "TRIAGE: Standard"

risk_assessor_agent = RiskAssessorAgent()