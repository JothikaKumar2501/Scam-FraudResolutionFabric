from strands import Agent, tool
from typing import Dict, Any

from SupervisorAgent import supervisor_agent
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

class StrandsMultiAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="strands-multi-agent",
            name="StrandsMultiAgent",
            description="Integrated multi-agent system for authorized scam detection"
        )

    @tool
    def process_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Process an alert through the entire fraud detection workflow."""
        context = {'transaction': alert}
        
        # Run the complete fraud detection workflow
        context = supervisor_agent.orchestrate_fraud_detection(context)
        
        # Generate final report
        final_report = supervisor_agent.generate_final_report(context)
        context['final_report'] = final_report
        
        return context

    @tool
    def analyze_transaction(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze transaction context."""
        return transaction_context_agent.analyze_transaction(context)

    @tool
    def analyze_customer(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze customer information."""
        return customer_info_agent.analyze_customer(context)

    @tool
    def analyze_merchant(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze merchant information."""
        return merchant_info_agent.analyze_merchant(context)

    @tool
    def analyze_behavior(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze behavioral patterns."""
        return behavioral_pattern_agent.analyze_behavior(context)

    @tool
    def synthesize_risk(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesize risk from multiple sources."""
        return risk_synthesizer_agent.synthesize_risk(context)

    @tool
    def triage_case(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform triage on the case."""
        return triage_agent.triage_case(context)

    @tool
    def conduct_dialogue(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Conduct dialogue with the customer."""
        return dialogue_agent.conduct_dialogue(context)[0]  # Return only the context, not the 'done' flag

    @tool
    def assess_risk(self, context: Dict[str, Any], is_final: bool = False) -> Dict[str, Any]:
        """Assess risk based on the current context."""
        return risk_assessor_agent.assess_risk(context, is_final)

    @tool
    def make_policy_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make a policy decision based on the risk assessment."""
        return policy_decision_agent.make_policy_decision(context)

    @tool
    def collect_feedback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect feedback and generate improvement suggestions."""
        return feedback_collector_agent.collect_feedback(context)

strands_multi_agent = StrandsMultiAgent()

# Example usage
if __name__ == "__main__":
    # Sample alert data
    sample_alert = {
        "alert_id": "ALT123456",
        "customer_id": "CUST789012",
        "transaction_id": "TXN345678",
        "amount": 5000.00,
        "currency": "AUD",
        "payee": "Unknown Beneficiary",
        "transaction_type": "Online Transfer",
        "transaction_date": "2025-10-19T16:30:00Z",
        "risk_score": 0.75
    }

    # Process the alert
    result = strands_multi_agent.process_alert(sample_alert)

    # Print the final report
    print(result.get('final_report', 'No final report generated.'))
