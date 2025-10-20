from strands import Agent, tool
from typing import Dict, Any, List
import json
from datetime import datetime
from aws_bedrock import converse_with_claude_stream
from config import config
from vector_utils import search_similar
import logging

class PolicyDecisionAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="policy-decision-agent",
            name="PolicyDecisionAgent",
            description="Advanced policy decision agent with regulatory compliance and customer protection expertise"
        )
        self.agent_config = config.get_agent_config(self.name)
        self.logger = logging.getLogger(self.name)

    @tool
    def make_policy_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make policy decisions based on risk assessment and regulatory requirements."""
        try:
            # Get dynamic SOPs based on policy context
            policy_query = self._build_policy_query(context)
            sops = self._retrieve_sop(context, query=policy_query)
            
            # Get the final risk assessment
            final_risk = context.get('final_risk_determination', context.get('risk_assessment_summary', '[Not available]'))
            
            # Build intelligent policy prompt (tie to numeric risk if present). If BEC indicators present, prefer BEC safeguards.
            if isinstance(context.get('overall_risk_score'), (int, float)):
                final_risk = f"Overall Risk Score: {context.get('overall_risk_score'):.2f}\n" + (final_risk or '')
            prompt = self._build_policy_decision_prompt(final_risk, context, sops)
            
            # Get expert policy decision
            result = self._get_expert_policy_decision(prompt)
            
            # Add to context with metadata
            context['policy_decision'] = result
            context['policy_decision_timestamp'] = datetime.now().isoformat()
            
            # Populate regulatory requirements/compliance dict for UI
            try:
                regs = self._get_regulatory_requirements(context)
                if isinstance(regs, dict):
                    context['regulatory_requirements'] = regs
                    context['regulatory_compliance'] = regs
            except Exception:
                # Keep optional
                pass
            
            self.logger.info(f"Policy decision completed for case: {context.get('transaction', {}).get('alert_id', 'Unknown')}")
            return context
        except Exception as e:
            self.logger.error(f"Error in make_policy_decision: {str(e)}")
            context['policy_decision_error'] = str(e)
            return context

    def _build_policy_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for policy analysis"""
        query_parts = []
        
        # Add transaction context
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 0)
                query_parts.append(f"policy decision {amount}")
        
        # Add risk context
        if 'risk_assessment' in context:
            query_parts.append("regulatory compliance policy")
        
        return " ".join(query_parts) if query_parts else "authorized scam policy decision"

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

    def _build_policy_decision_prompt(self, final_risk: str, context: Dict[str, Any], sops: List[str]) -> str:
        """Build intelligent policy decision prompt with COMPRESSED SUMMARIES"""
        specialized_prompts = self.agent_config.specialized_prompts
        
        policy_decision_prompt = specialized_prompts.get('policy_decision',
            "Make regulatory-compliant policy decisions based on investigation findings")
        
        customer_protection_prompt = specialized_prompts.get('customer_protection',
            "Implement customer protection measures and regulatory compliance")
        
        # Get compressed summaries from context
        compressed_agent_logs = context.get('compressed_agent_logs', 'AGENT LOGS: Not available')
        compressed_context = context.get('compressed_context_summary', 'CONTEXT: Not available')
        compressed_risk = context.get('compressed_risk_summary', 'RISK: Not available')
        
        # Build SOP summary (reduced for speed)
        sop_summary = "\n".join(sops[:3]) if sops else "No specific SOPs found"
        
        prompt = f"""
YOU ARE AN EXPERT POLICY DECISION AGENT SPECIALIZING IN AUTHORIZED PAYMENT SCAM PREVENTION.

{policy_decision_prompt}
{customer_protection_prompt}

FINAL RISK ASSESSMENT:
{final_risk}

COMPRESSED CONTEXT:
{compressed_context}

COMPRESSED RISK:
{compressed_risk}

COMPRESSED AGENT LOGS:
{compressed_agent_logs}

RELEVANT SOPs:
{sop_summary}

POLICY DECISION OPTIONS:
1. BLOCK TRANSACTION - Prevent the payment immediately
2. ESCALATE TO SENIOR - Complex case requiring management review
3. PROCEED WITH WARNING - Allow but document customer was warned
4. PROCEED - No scam indicators found

PROVIDE YOUR DECISION WITH:
- Selected action (1-4)
- Specific regulatory/compliance justification (e.g., APRA CPG 234, AUSTRAC guidelines)
- Customer protection measures to implement
- Documentation requirements
- Any follow-up actions needed

Consider the customer's vulnerability, transaction amount, and reputational risk.
"""
        return prompt

    def _build_transaction_details(self, context: Dict[str, Any]) -> str:
        """Build intelligent transaction details summary"""
        alert = context.get('transaction', {})
        if not alert or not isinstance(alert, dict):
            return "Transaction details unavailable"
        
        details_parts = []
        details_parts.append(f"Alert: {alert}")
        details_parts.append(f"Amount: ${alert.get('amount', 'Unknown')}")
        details_parts.append(f"Payee: {alert.get('payee', 'Unknown')}")
        
        return "\n".join(details_parts)

    def _build_investigation_summary(self, context: Dict[str, Any]) -> str:
        """Build intelligent investigation summary"""
        summary_parts = []
        
        # Customer verification
        dialogue_history = context.get('dialogue_history', [])
        customer_verified = 'verified' in str(dialogue_history).lower()
        summary_parts.append(f"- Customer verified: {'Yes' if customer_verified else 'Unknown'}")
        
        # Authorization status
        authorization_confirmed = 'yes' in str(dialogue_history).lower() and 'authorize' in str(dialogue_history).lower()
        summary_parts.append(f"- Authorization status: {'Confirmed' if authorization_confirmed else 'Check dialogue'}")
        
        # Dialogue turns
        summary_parts.append(f"- Number of dialogue turns: {len(dialogue_history)}")
        
        return "\n".join(summary_parts)

    def _get_expert_policy_decision(self, prompt: str) -> str:
        """Get expert policy decision with error handling"""
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            # Standardize BEC decision outputs per ANZ SOP if BEC detected
            rl = result.lower()
            if 'business email compromise' in rl or 'bec' in rl:
                if 'POLICY DECISION:' not in result:
                    result += "\n\nPOLICY DECISION: BLOCK TRANSACTION"
                result += "\nCUSTOMER PROTECTION: Initiate urgent trace, freeze further similar payments, secure vendor verification, contact customer with BEC guidance"
                result += "\nCOMPLIANCE: AUSTRAC SMR if funds misdirected; APRA CPG 234 operational controls; ASIC RG 271 customer protection"
                result += "\nDOCUMENTATION: Record verification steps, analyst notes, and decision with timestamps"
            return result
        except Exception as e:
            self.logger.error(f"Failed to get expert policy decision: {e}")
            return "Policy decision unavailable due to technical issues"

    def _get_regulatory_requirements(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get regulatory requirements based on context"""
        # Get transaction amount
        amount = 0.0
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = float(txn.get('amount', 0))
        
        # Get risk level
        risk_level = 'medium'  # default
        if 'risk_assessment' in context:
            risk_text = context['risk_assessment'].lower()
            if 'high risk' in risk_text:
                risk_level = 'high'
            elif 'low risk' in risk_text:
                risk_level = 'low'
        
        # Get requirements from config
        try:
            requirements = config.get_regulatory_requirements(amount, risk_level)
            return requirements
        except Exception:
            # Fallback requirements
            return {
                'austrac_reporting': amount >= 10000,
                'apra_compliance': risk_level == 'high',
                'asic_protection': True,
                'documentation_required': True
            }

policy_decision_agent = PolicyDecisionAgent()