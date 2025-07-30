import re
import json
import logging
from schemas import *
from mcp_store import save_context
from vector_utils import search_similar
from aws_bedrock import converse_with_claude_stream

# Helper to call Claude 3.7 Sonnet

def call_claude(messages, system=None, max_tokens=512, temperature=0.5):
    # conversation = [
    #     {
    #         "role": m["role"],
    #         "content": [{"type": "text", "text": m["content"]}]
    #     } for m in messages if m["role"] in ("user", "assistant")
    # ]

    conversation = [
        {
            "role": "system",
            "content": [{"type": "text", "text": system}]
        }
    ] + [
        {
            "role": m["role"],
            "content": [{"type": "text", "text": m["content"]}]
        }
        for m in messages if m["role"] in ("user", "assistant")
    ]

    try:
        logging.debug(f"Claude prompt: {conversation}, system: {system}")
        response = converse_with_claude_stream(
            messages=conversation,
            max_tokens=max_tokens,
            temperature=temperature
        )
        logging.debug(f"Claude raw response: {response}")
        if response is None:
            raise RuntimeError("Claude LLM error: Empty response")
        return response  # Always return string
    except Exception as e:
        logging.error(f"Claude LLM error: {e}")
        raise RuntimeError(f"Claude LLM error: {e}")

# --- LLM-using agents: robust JSON extraction ---
def extract_json_from_llm_output(result, agent_name):
    logging.debug(f"[{agent_name}] LLM raw result: {result}")
    match = re.search(r'\{.*\}', result, re.DOTALL)
    if not match:
        logging.warning(f"[{agent_name}] No JSON found in LLM output: {result}")
        raise ValueError(f"No JSON object found in LLM output for {agent_name}")
    json_str = match.group(0)
    logging.debug(f"[{agent_name}] Extracted JSON: {json_str}")
    return json_str

# --- Utility: Retrieve relevant SOP rules from SOP.md ---
def get_relevant_sop_rules(rule_id):
    try:
        with open("datasets/SOP.md", encoding="utf-8") as f:
            sop_md = f.read()
        # Find the table row for the rule_id
        pattern = rf"\|[^\n]*\b{re.escape(rule_id)}\b[^\n]*\|"
        matches = re.findall(pattern, sop_md)
        return "\n".join(matches) if matches else ""
    except Exception as e:
        logging.error(f"[PolicyDecisionAgent] Error reading SOP.md: {e}")
        return ""

# --- Utility: Select and template questions from questions.md ---
def select_questions_from_md(questions_md_path, rule_id, context):
    try:
        with open(questions_md_path, encoding="utf-8") as f:
            md = f.read()
        # Find section for the rule_id
        section = ""
        if rule_id:
            # Look for section header matching the rule_id
            pattern = rf"\*\*A\. Fraud Type: [^\n]*\({re.escape(rule_id)}\)\*\*([\s\S]*?)(\n\*\*|$)"
            m = re.search(pattern, md)
            if m:
                section = m.group(1)
        if not section:
            # Fallback: use General Questions
            m = re.search(r"### General Questions \(Applicable to most alerts\)([\s\S]*?)(\n###|$)", md)
            section = m.group(1) if m else ""
        # Extract questions (lines starting with * and quoted)
        questions = re.findall(r'^\*\s+"([^"]+)"', section, re.MULTILINE)
        # Template with context
        def fill(q):
            for k, v in context.items():
                q = q.replace(f"[{k}]", str(v))
            return q
        return [fill(q) for q in questions]
    except Exception as e:
        logging.error(f"[DialogueAgent] Error reading questions.md: {e}")
        return []

# --- TransactionContextAgent ---
def transaction_context_agent(state, txn_json):
    # Always extract required fields directly from input JSON
    alert = txn_json if isinstance(txn_json, dict) else json.loads(txn_json)
    if not isinstance(alert, dict):
        alert = {}
    ctx = {
        "txn_id": alert.get("alertId") or alert.get("txn_id") or "unknown",
        "user_id": alert.get("customerId") or alert.get("user_id") or "unknown",
        "customer_id": alert.get("customerId") or alert.get("user_id") or "unknown",
        "amount": alert.get("amount") or 0.0,
        "timestamp": f"{alert.get('alertDate', '')}T{alert.get('alertTime', '')}Z" if alert.get('alertDate') and alert.get('alertTime') else alert.get("timestamp", "unknown"),
        "location": alert.get("location", "Unknown"),
        "merchant_id": alert.get("merchant_id", "m123"),
        "device_id": alert.get("device_id", None)
    }
    state["transaction_context"] = ctx
    save_context("TransactionContext", ctx["txn_id"], ctx)
    logging.info(f"[TransactionContextAgent] Output: {ctx}")
    return state

# --- CustomerInfoAgent ---
def customer_info_agent(state):
    txn_ctx = state["transaction_context"]
    if not isinstance(txn_ctx, dict):
        logging.error("[CustomerInfoAgent] transaction_context is not a dict: %s", txn_ctx)
        raise ValueError("transaction_context is not a dict")
    user_id = txn_ctx["user_id"]
    logging.info(f"[CustomerInfoAgent] Input user_id: {user_id}")
    try:
        with open("datasets/customer_demographic.json") as f:
            data = json.load(f)
        customers = data["customers"]
        user = next((u for u in customers if u["customer_id"] == user_id), None)
        if not user:
            raise ValueError("User not found")
        state["user_context"] = user
        save_context("UserContext", user_id, user)
        logging.info(f"[CustomerInfoAgent] Output: {user}")
        return state
    except Exception as e:
        logging.error(f"[CustomerInfoAgent] Error: {e}")
        raise

# --- MerchantInfoAgent ---
def merchant_info_agent(state):
    txn_ctx = state["transaction_context"]
    if not isinstance(txn_ctx, dict):
        logging.error("[MerchantInfoAgent] transaction_context is not a dict: %s", txn_ctx)
        raise ValueError("transaction_context is not a dict")
    merchant_id = txn_ctx.get("merchant_id")
    if not merchant_id:
        merchant_id = "m123"  # Default or placeholder merchant_id
    logging.info(f"[MerchantInfoAgent] Input merchant_id: {merchant_id}")
    try:
        ctx = {
            "merchant_id": merchant_id,
            "name": "Acme Corp",
            "category": "Retail",
            "risk_level": "medium",
            "profile": {}
        }
        state["merchant_context"] = ctx
        save_context("MerchantContext", merchant_id, ctx)
        logging.info(f"[MerchantInfoAgent] Output: {ctx}")
        return state
    except Exception as e:
        logging.error(f"[MerchantInfoAgent] Error: {e}")
        raise

# --- BehavioralPatternAgent ---
def behavioral_pattern_agent(state):
    system_prompt = (
        "You are an anomaly detection agent. Compute anomaly metrics from the provided context. "
        "Respond ONLY with a valid JSON object for AnomalyContext, and nothing else. "
        "The schema is: {\"anomaly_score\": float, \"explanation\": str} "
        "Do not include any explanation, markdown, or text outside the JSON object."
    )
    prompt = f"Given this transaction and user/merchant context, compute anomaly metrics: {json.dumps(state)}"
    try:
        result = call_claude([
            {"role": "user", "content": prompt}
        ], system=system_prompt)
        json_str = extract_json_from_llm_output(result, "BehavioralPatternAgent")
        ctx = json.loads(json_str)
        state["anomaly_context"] = ctx
        save_context("AnomalyContext", state["transaction_context"]["txn_id"], ctx)
        logging.info(f"[BehavioralPatternAgent] Output: {ctx}")
        return state
    except Exception as e:
        logging.error(f"[BehavioralPatternAgent] Error: {e}")
        raise

# --- RiskSynthesizerAgent ---
def risk_synthesizer_agent(state):
    system_prompt = "You are a risk synthesizer agent. Summarize risk for the transaction. Respond ONLY with a valid JSON object for RiskSummaryContext. The schema is: {\"risk_score\": float, \"summary\": str, \"chain_of_thought\": str}. Do not include any explanation, markdown, or text outside the JSON object."
    prompt = f"Summarize risk for this transaction: {json.dumps(state)}"
    try:
        result = call_claude([
            {"role": "user", "content": prompt}
        ], system=system_prompt)
        json_str = extract_json_from_llm_output(result, "RiskSynthesizerAgent")
        ctx = json.loads(json_str)
        state["risk_summary_context"] = ctx
        save_context("RiskSummaryContext", state["transaction_context"]["txn_id"], ctx)
        logging.info(f"[RiskSynthesizerAgent] Output: {ctx}")
        return state
    except Exception as e:
        logging.error(f"[RiskSynthesizerAgent] Error: {e}")
        raise

# --- PolicyDecisionAgent ---
def policy_decision_agent(state):
    rule_id = state["transaction_context"].get("rule_id", "")
    sop_rules = get_relevant_sop_rules(rule_id)
    system_prompt = (
        "You are a policy decision agent. Decide action based on risk summary and SOPs. "
        "Respond ONLY with a valid JSON object for DecisionContext. "
        "The schema is: {\"action\": str, \"reason\": str, \"escalate\": bool}. "
        "Do not include any explanation, markdown, or text outside the JSON object. "
        f"Relevant SOP rules: {sop_rules}"
    )
    prompt = f"Given this risk summary and SOPs: {json.dumps(state)}. Decide action."
    try:
        result = call_claude([
            {"role": "user", "content": prompt}
        ], system=system_prompt)
        json_str = extract_json_from_llm_output(result, "PolicyDecisionAgent")
        ctx = json.loads(json_str)
        state["decision_context"] = ctx
        save_context("DecisionContext", state["transaction_context"]["txn_id"], ctx)
        logging.info(f"[PolicyDecisionAgent] Output: {ctx}")
        return state
    except Exception as e:
        logging.error(f"[PolicyDecisionAgent] Error: {e}")
        raise

# --- DialogueAgent ---
def dialogue_agent(state, customer_answer=None, max_turns=12):
    import logging
    from vector_utils import search_similar
    rule_id = state["transaction_context"].get("rule_id", "")
    txn_context = state["transaction_context"]
    # Get current dialogue context (list of turns)
    dialogue_ctx = state.get("dialogue_context", {})
    dialogue = dialogue_ctx.get("dialogue_turns", [])
    turn_count = len([t for t in dialogue if t["from"] == "agent"])
    # If customer_answer is provided, add it to the dialogue
    if customer_answer:
        dialogue.append({"from": "user", "msg": customer_answer})
    # RAG: Retrieve relevant questions using context and RAG
    context_str = f"Rule: {rule_id}, Txn: {txn_context}"
    rag_results = search_similar(context_str, top_k=5)
    logging.info(f"[DialogueAgent] RAG results: {rag_results}")
    # Fallback to select_questions_from_md if RAG returns nothing
    questions = [q.get("text") for q in rag_results if q and q.get("text")] if rag_results else []
    if not questions:
        questions = select_questions_from_md("datasets/questions.md", rule_id, txn_context)
        logging.info(f"[DialogueAgent] Fallback to rule-based questions: {questions}")
    # Template questions with context
    def fill(q):
        for k, v in txn_context.items():
            q = q.replace(f"[{k}]", str(v))
        return q
    questions = [fill(q) for q in questions]
    # Find the next unanswered question
    asked = [turn["msg"] for turn in dialogue if turn["from"] == "agent"]
    next_q = next((q for q in questions if q not in asked), None)
    done = False
    if next_q and turn_count < max_turns:
        dialogue.append({"from": "agent", "msg": next_q})
        logging.info(f"[DialogueAgent] Selected question: {next_q}")
    else:
        done = True
        logging.info(f"[DialogueAgent] Dialogue complete or max turns reached.")
    # Update state
    state["dialogue_context"] = {"dialogue_turns": dialogue, "done": done}
    save_context("DialogueContext", state["transaction_context"]["txn_id"], state["dialogue_context"])
    # Add context trace for UI
    trace = state.get("context_trace", [])
    rag_results = rag_results if rag_results is not None else []
    questions = questions if questions is not None else []
    if next_q is None:
        next_q = ""
    trace.append({
        "agent": "DialogueAgent",
        "customer_answer": customer_answer,
        "rag_results": rag_results,
        "questions": questions,
        "selected_question": next_q,
        "dialogue": list(dialogue),
        "done": done
    })
    state["context_trace"] = trace
    logging.info(f"[DialogueAgent] Output: {state['dialogue_context']}")
    # After each user response, call RiskAssessorAgent to check if more info is needed
    if customer_answer or done:
        state = risk_assessor_agent(state)
        _risk = state.get("risk_summary_context")
        if not isinstance(_risk, dict):
            risk_ctx = {}
        else:
            risk_ctx = _risk
        if risk_ctx.get("risk_score", 0) > 0.7 or done:
            state["decision_context"] = {
                "action": "block" if risk_ctx.get("risk_score", 0) > 0.7 else "clear",
                "reason": risk_ctx.get("summary", "Dialogue complete."),
                "escalate": False
            }
            save_context("DecisionContext", state["transaction_context"]["txn_id"], state["decision_context"])
            logging.info(f"[DialogueAgent] Final Decision: {state['decision_context']}")
    return state

# --- RiskAssessorAgent ---
def risk_assessor_agent(state):
    system_prompt = "You are a risk assessor agent. Assess the dialogue for scam indicators. Respond ONLY with a valid JSON object for RiskSummaryContext."
    prompt = f"Assess this dialogue for scam indicators: {json.dumps(state)}"
    try:
        result = call_claude([
            {"role": "user", "content": prompt}
        ], system=system_prompt)
        json_str = extract_json_from_llm_output(result, "RiskAssessorAgent")
        ctx = json.loads(json_str)
        state["risk_summary_context"] = ctx
        save_context("RiskSummaryContext", state["transaction_context"]["txn_id"], ctx)
        logging.info(f"[RiskAssessorAgent] Output: {ctx}")
        return state
    except Exception as e:
        logging.error(f"[RiskAssessorAgent] Error: {e}")
        raise 