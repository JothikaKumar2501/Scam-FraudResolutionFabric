from strands import Agent, tool
from typing import Dict, Any, List, Tuple
import concurrent.futures
from datetime import datetime
from aws_bedrock import converse_with_claude_stream
from config import config
from vector_utils import search_similar
import logging

from TransactionContextAgent import transaction_context_agent
from CustomerInfoAgent import customer_info_agent
from MerchantInfoAgent import merchant_info_agent
from BehavioralPatternAgent import behavioral_pattern_agent
from RiskSynthesizerAgent import risk_synthesizer_agent
from TriageAgent import triage_agent
from DialogueAgent import dialogue_agent
from RiskAssessorAgent import risk_assessor_agent
from PolicyDecisionAgent import policy_decision_agent
from FeedbackCollectorAgent import feedback_collector_agent

from bedrock_agentcore import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

class SupervisorAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="supervisor-agent",
            name="SupervisorAgent",
            description="Advanced supervisor agent with intelligent orchestration and decision making"
        )
        self.logger = logging.getLogger(self.name)
        self.agent_config = config.get_agent_config(self.name)

    @tool
    def orchestrate_fraud_detection(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrate the entire fraud detection workflow."""
        self.logger.info("SupervisorAgent: Starting fraud detection workflow")
        
        try:
            # Step 1: Run context-building agents in parallel
            context_results = self._run_context_agents_parallel(context)
            context.update(context_results)
            
            # Step 2: Run risk synthesis
            context = risk_synthesizer_agent.synthesize_risk(context)
            
            # Step 3: Run triage to determine next steps
            context = triage_agent.triage_case(context)
            
            # Step 4: Run dialogue loop if needed
            if context.get('dialogue_required', False):
                context = self._run_dialogue_loop(context)
            
            # Step 5: Run final risk assessment
            context = risk_assessor_agent.assess_risk(context, is_final=True)
            
            # Step 6: Run policy decision
            context = policy_decision_agent.make_policy_decision(context)
            
            # Step 7: Collect feedback for improvement
            context = feedback_collector_agent.collect_feedback(context)
            
            self.logger.info("SupervisorAgent: Fraud detection workflow completed successfully")
            
        except Exception as e:
            self.logger.error(f"SupervisorAgent: Error in fraud detection workflow: {e}")
            context['error'] = str(e)
        
        return context

    def _run_context_agents_parallel(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run context agents in parallel with intelligent error handling."""
        context_results = {}
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                'transaction': executor.submit(transaction_context_agent.analyze_transaction, context.copy()),
                'customer': executor.submit(customer_info_agent.analyze_customer, context.copy()),
                'merchant': executor.submit(merchant_info_agent.analyze_merchant, context.copy()),
                'behavior': executor.submit(behavioral_pattern_agent.analyze_behavior, context.copy()),
            }
            
            for key, future in futures.items():
                try:
                    result = future.result(timeout=30)  # 30 second timeout
                    if isinstance(result, dict):
                        context_results.update(result)
                except Exception as e:
                    self.logger.error(f"Context agent {key} failed: {e}")
                    # Continue with other agents
                    continue
        
        return context_results

    def _run_dialogue_loop(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run the dialogue loop until completion."""
        done = False
        max_turns = config.conversation.max_dialogue_turns
        
        while not done and len(context.get('dialogue_history', [])) < max_turns:
            context, done = dialogue_agent.conduct_dialogue(context)
        
        return context

    @tool
    def generate_final_report(self, context: Dict[str, Any]) -> str:
        """Generate a comprehensive final report of the fraud detection process."""
        prompt = self._build_final_report_prompt(context)
        
        try:
            report = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            return report
        except Exception as e:
            self.logger.error(f"Failed to generate final report: {e}")
            return "Final report unavailable due to technical issues"

    def _build_final_report_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for generating the final report."""
        # Build context summary
        context_summary = self._build_final_context_summary(context)
        
        # Build conversation summary
        conversation_summary = self._build_final_conversation_summary(context)
        
        prompt = f"""
You are a senior fraud analyst at XYZ Bank. Based on the following comprehensive investigation, provide a clear, professional final report.

INVESTIGATION CONTEXT:
{context_summary}

CUSTOMER CONVERSATION:
{conversation_summary}

REPORT REQUIREMENTS:
1. Executive Summary: Key findings and decision
2. Risk Assessment: Detailed risk analysis and factors
3. Scam Typology: Specific scam type identified (if any)
4. Customer Impact: Vulnerability assessment and protection measures
5. Regulatory Compliance: AUSTRAC, APRA, and other requirements
6. Recommendations: Immediate actions and follow-up steps
7. Lessons Learned: System improvements and process enhancements

Provide a comprehensive, professional report suitable for senior management and regulatory reporting.
"""
        return prompt

    def _build_final_context_summary(self, context: Dict[str, Any]) -> str:
        """Build a summary of the final context for the report."""
        summary_parts = []
        
        # Transaction summary
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 'Unknown')
                payee = txn.get('payee', 'Unknown')
                alert_id = txn.get('alertId', 'Unknown')
                summary_parts.append(f"Alert ID: {alert_id}")
                summary_parts.append(f"Amount: ${amount}")
                summary_parts.append(f"Payee: {payee}")
        
        # Risk assessment
        if 'risk_summary_context' in context:
            summary_parts.append(f"Risk Assessment: {context['risk_summary_context'][:200]}...")
        
        # Policy decision
        if 'policy_decision' in context:
            summary_parts.append(f"Policy Decision: {context['policy_decision'][:200]}...")
        
        return "\n".join(summary_parts) if summary_parts else "Limited context available"

    def _build_final_conversation_summary(self, context: Dict[str, Any]) -> str:
        """Build a summary of the final conversation for the report."""
        dialogue_history = context.get('dialogue_history', [])
        if not dialogue_history:
            return "No customer conversation conducted"
        
        conversation_parts = []
        for turn in dialogue_history:
            if isinstance(turn, dict):
                question = turn.get('question', '')
                user_response = turn.get('user', '')
                
                if question:
                    conversation_parts.append(f"Q: {question}")
                if user_response:
                    conversation_parts.append(f"A: {user_response}")
        
        return "\n".join(conversation_parts) if conversation_parts else "No conversation details available"

supervisor_agent = SupervisorAgent()
