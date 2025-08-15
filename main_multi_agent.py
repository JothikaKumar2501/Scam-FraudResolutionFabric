from supervisor import SupervisorAgent
from agents_multi import (
    TransactionContextAgent, CustomerInfoAgent, MerchantInfoAgent, BehavioralPatternAgent,
    RiskSynthesizerAgent, PolicyDecisionAgent, DialogueAgent, RiskAssessorAgent, FeedbackCollectorAgent
)
from mcp_store import ContextStore  # Assume this provides a dict-like interface

# Sample context store (replace with real MCP/local file logic)
context_store = ContextStore()

# Initialize supervisor
supervisor = SupervisorAgent(context_store)

# Register agents
supervisor.register_agent(TransactionContextAgent("TransactionContextAgent", context_store))
supervisor.register_agent(CustomerInfoAgent("CustomerInfoAgent", context_store))
supervisor.register_agent(MerchantInfoAgent("MerchantInfoAgent", context_store))
supervisor.register_agent(BehavioralPatternAgent("BehavioralPatternAgent", context_store))
supervisor.register_agent(RiskSynthesizerAgent("RiskSynthesizerAgent", context_store))
supervisor.register_agent(PolicyDecisionAgent("PolicyDecisionAgent", context_store))
supervisor.register_agent(DialogueAgent("DialogueAgent", context_store))
supervisor.register_agent(RiskAssessorAgent("RiskAssessorAgent", context_store))
supervisor.register_agent(FeedbackCollectorAgent("FeedbackCollectorAgent", context_store))

# Main coordination loop (simplified)
final_context = supervisor.coordinate("")

# Print final report (to be replaced with UI integration)
print("Final Context:")
print(final_context) 