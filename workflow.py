from typing import Dict, Any
from agents import *
import logging
import json

def run_workflow(txn_json: dict, feedback: dict = None) -> dict:
    if not isinstance(txn_json, dict):
        import logging
        logging.error(f"txn_json is not a dict: {txn_json}")
        txn_json = {}
    state = {"input": txn_json}
    try:
        # 1. TransactionContext Agent
        state = transaction_context_agent(state, txn_json)
        # 2. CustomerInfo Agent
        state = customer_info_agent(state)
        # 3. MerchantInfo Agent
        state = merchant_info_agent(state)
        # 4. BehavioralPattern Agent
        state = behavioral_pattern_agent(state)
        # 5. RiskSynthesizer Agent
        state = risk_synthesizer_agent(state)
        # 6. PolicyDecision Agent
        state = policy_decision_agent(state)
        # 7. Dialogue Agent (conversational loop if escalation required)
        if state["decision_context"].get("escalate", False):
            # Start conversational loop
            state = dialogue_agent(state)
            while not state.get("dialogue_context", {}).get("done", False):
                # In UI, user will provide answer interactively; here, simulate with placeholder
                user_answer = "[USER_INPUT_REQUIRED]"  # Placeholder for UI to fill
                state = dialogue_agent(state, user_answer)
            # After conversation, run RiskAssessorAgent and finalize decision
            state = risk_assessor_agent(state)
            _risk = state.get("risk_summary_context")
            risk_ctx = _risk if isinstance(_risk, dict) else {}
            state["decision_context"] = {
                "action": "block" if risk_ctx.get("risk_score", 0) > 0.7 else "clear",
                "reason": risk_ctx.get("summary", "Dialogue complete."),
                "escalate": False
            }
            save_context("DecisionContext", state["transaction_context"]["txn_id"], state["decision_context"])
        # 8. Generate final report
        state["final_report"] = generate_final_report(state)
        return state
    except Exception as e:
        state["error"] = str(e)
        return state

def generate_final_report(state):
    # Summarize the decision, conversation, and all contexts
    report = {
        "Transaction": state.get("transaction_context", {}),
        "User": state.get("user_context", {}),
        "Merchant": state.get("merchant_context", {}),
        "Anomaly": state.get("anomaly_context", {}),
        "RiskSummary": state.get("risk_summary_context", {}),
        "Decision": state.get("decision_context", {}),
        "Conversation": state.get("dialogue_context", {}).get("dialogue_turns", []),
        "AuditTrace": state.get("context_trace", [])
    }
    # Add a human-readable summary
    decision = report["Decision"].get("action", "N/A")
    reason = report["Decision"].get("reason", "")
    report["Summary"] = f"Final Decision: {decision.upper()}\nReason: {reason}"
    return report

# New: process_ftp_alert for full FTP alert flow
def process_ftp_alert(alert: dict) -> Dict[str, Any]:
    logging.info(f"[Orchestrator] Processing FTP alert: {alert}")
    # Map FTP alert to transaction context input (PRD: TransactionContext Agent expects txn_json)
    txn_json = {
        "txn_id": alert.get("alertId"),
        "amount": 15000.0,  # Example: parse from description or add real extraction
        "timestamp": f"{alert.get('alertDate', '')}T{alert.get('alertTime', '')}Z",
        "location": "Unknown",  # Could be parsed from alert or set as needed
        "merchant_id": "m123",  # Placeholder, should be mapped from alert or context
        "user_id": alert.get("customerId"),
        "device_id": None
    }
    return run_workflow(txn_json)

# Test harness for local debugging
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with open("datasets/FTP.json") as f:
        ftp_alerts = json.load(f)
    for alert in ftp_alerts:
        result = process_ftp_alert(alert)
        print(json.dumps(result, indent=2)) 