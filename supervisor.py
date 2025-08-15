from agent_base import Agent

class SupervisorAgent(Agent):
    def __init__(self, context_store):
        super().__init__("Supervisor", context_store, self)
        self.agents = {}
        self.message_queue = []

    def register_agent(self, agent):
        self.agents[agent.name] = agent
        agent.supervisor = self

    def send_message(self, agent_name, message, context):
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"Agent {agent_name} not registered.")
        return agent.act(message, context)

    def coordinate(self, initial_context):
        context = initial_context.copy()
        trace = []
        # 1. TransactionContextAgent
        context = self.send_message("TransactionContextAgent", None, context)
        trace.append({"agent": "TransactionContextAgent", "context": context.get("transaction_context", {})})
        # 2. CustomerInfoAgent
        context = self.send_message("CustomerInfoAgent", None, context)
        trace.append({"agent": "CustomerInfoAgent", "context": context.get("user_context", {})})
        # 3. MerchantInfoAgent
        context = self.send_message("MerchantInfoAgent", None, context)
        trace.append({"agent": "MerchantInfoAgent", "context": context.get("merchant_context", {})})
        # 4. BehavioralPatternAgent
        context = self.send_message("BehavioralPatternAgent", None, context)
        trace.append({"agent": "BehavioralPatternAgent", "context": context.get("anomaly_context", {})})
        # 5. RiskSynthesizerAgent
        context = self.send_message("RiskSynthesizerAgent", None, context)
        trace.append({"agent": "RiskSynthesizerAgent", "context": context.get("risk_summary_context", {})})
        # 6. PolicyDecisionAgent
        context = self.send_message("PolicyDecisionAgent", None, context)
        trace.append({"agent": "PolicyDecisionAgent", "context": context.get("decision_context", {})})
        # 7. Dialogue loop if escalation required
        if context.get("decision_context", {}).get("escalate", False):
            dialogue_done = False
            while not dialogue_done:
                context = self.send_message("DialogueAgent", None, context)
                trace.append({"agent": "DialogueAgent", "context": context.get("dialogue_context", {})})
                # Simulate user input for now (UI should handle this interactively)
                dialogue_ctx = context.get("dialogue_context", {})
                if dialogue_ctx.get("done", False):
                    dialogue_done = True
                else:
                    # In real UI, user would answer here
                    # For now, just mark as done after one loop
                    dialogue_ctx["done"] = True
                    context["dialogue_context"] = dialogue_ctx
                # After each dialogue turn, re-assess risk
                context = self.send_message("RiskAssessorAgent", None, context)
                trace.append({"agent": "RiskAssessorAgent", "context": context.get("risk_summary_context", {})})
                # If risk is low or dialogue is done, break
                if context.get("risk_summary_context", {}).get("risk_score", 0) < 0.5 or dialogue_done:
                    break
            # Final policy decision after dialogue
            context = self.send_message("PolicyDecisionAgent", None, context)
            trace.append({"agent": "PolicyDecisionAgent", "context": context.get("decision_context", {})})
        # 8. FeedbackCollectorAgent
        context = self.send_message("FeedbackCollectorAgent", None, context)
        trace.append({"agent": "FeedbackCollectorAgent", "context": context.get("feedback_context", {})})
        context["context_trace"] = trace
        # 9. Final report
        context["final_report"] = {
            "Summary": context.get("risk_summary_context", {}).get("summary", "No summary."),
            "Decision": context.get("decision_context", {}),
            "Trace": trace
        }
        return context 