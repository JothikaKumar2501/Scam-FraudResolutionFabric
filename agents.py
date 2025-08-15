import re
import json
import logging
from schemas import *
from mcp_store import save_context
from vector_utils import search_similar
from aws_bedrock import converse_with_claude
from mem0_integration import get_mem0_manager, MemoryType

# Initialize mem0 manager for memory integration
mem0_manager = None
try:
    mem0_manager = get_mem0_manager()
    logging.info("Mem0 manager initialized successfully for agent intelligence")
except Exception as e:
    logging.warning(f"Mem0 manager not available: {e}")

# Helper to call Claude 4 Sonnet

def call_claude(messages, system=None, max_tokens=512, temperature=0.5):
    # Format messages for AWS Bedrock Claude API
    conversation = []
    
    # Include system message as part of the first user message
    if system and messages:
        first_message = messages[0]
        if first_message["role"] == "user":
            enhanced_content = f"System: {system}\n\nUser: {first_message['content']}"
            conversation.append({
                "role": "user",
                "content": [{"text": enhanced_content}]
            })
            # Add remaining messages
            for m in messages[1:]:
                if m["role"] in ("user", "assistant"):
                    conversation.append({
                        "role": m["role"],
                        "content": [{"text": m["content"]}]
                    })
        else:
            # If first message is not user, add system as separate user message
            conversation.append({
                "role": "user",
                "content": [{"text": f"System: {system}"}]
            })
            for m in messages:
                if m["role"] in ("user", "assistant"):
                    conversation.append({
                        "role": m["role"],
                        "content": [{"text": m["content"]}]
                    })
    else:
        # No system message or no messages
        for m in messages:
            if m["role"] in ("user", "assistant"):
                conversation.append({
                    "role": m["role"],
                    "content": [{"text": m["content"]}]
                })

    try:
        logging.debug(f"Claude prompt: {conversation}, system: {system}")
        response = converse_with_claude(
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

# --- Memory Integration Functions ---
def retrieve_similar_case_memories(case_context, limit=5):
    """Retrieve similar case memories from mem0 for context building"""
    if not mem0_manager:
        return []
    
    try:
        # Create search query from case context
        search_query = f"fraud case {case_context.get('rule_id', '')} {case_context.get('amount', '')} {case_context.get('merchant_name', '')}"
        
        # Search for similar cases
        similar_memories = mem0_manager.search_case_memories(
            case_id="",  # Search across all cases
            query=search_query,
            limit=limit
        )
        
        logging.info(f"Retrieved {len(similar_memories)} similar case memories")
        return similar_memories
    except Exception as e:
        logging.error(f"Error retrieving similar case memories: {e}")
        return []

def retrieve_agent_memories_for_context(agent_name, case_context, limit=3):
    """Retrieve relevant agent memories for context building"""
    if not mem0_manager:
        return []
    
    try:
        # Create search query from context
        search_query = f"{agent_name} {case_context.get('rule_id', '')} {case_context.get('amount', '')}"
        
        # Search for relevant agent memories
        agent_memories = mem0_manager.search_agent_memories(
            agent_name=agent_name,
            query=search_query,
            limit=limit
        )
        
        logging.info(f"Retrieved {len(agent_memories)} {agent_name} memories")
        return agent_memories
    except Exception as e:
        logging.error(f"Error retrieving {agent_name} memories: {e}")
        return []

def build_memory_enhanced_context(case_context, agent_name):
    """Build enhanced context using mem0 memories"""
    enhanced_context = case_context.copy()
    
    # Retrieve similar case memories
    similar_cases = retrieve_similar_case_memories(case_context)
    if similar_cases:
        enhanced_context["similar_cases"] = similar_cases
    
    # Retrieve agent-specific memories
    agent_memories = retrieve_agent_memories_for_context(agent_name, case_context)
    if agent_memories:
        enhanced_context["agent_memories"] = agent_memories
    
    # Add memory summary to context
    if similar_cases or agent_memories:
        enhanced_context["memory_summary"] = {
            "similar_cases_count": len(similar_cases),
            "agent_memories_count": len(agent_memories),
            "has_historical_context": True
        }
    
    return enhanced_context

# --- LLM-using agents: robust JSON extraction ---
def extract_json_from_llm_output(result, agent_name):
    logging.debug(f"[{agent_name}] LLM raw result: {result}")
    
    # Try to find JSON in the response
    match = re.search(r'\{.*\}', result, re.DOTALL)
    if not match:
        logging.warning(f"[{agent_name}] No JSON found in LLM output: {result}")
        # Return a default JSON structure if no JSON found
        return '{"error": "No JSON found in response", "raw_response": "' + result.replace('"', '\\"') + '"}'
    
    json_str = match.group(0)
    logging.debug(f"[{agent_name}] Extracted JSON: {json_str}")
    return json_str

# --- Utility: Retrieve relevant SOP rules from SOP.md ---
def get_relevant_sop_rules(rule_id):
    try:
        # Use enhanced RAG search for SOP rules
        from vector_utils import search_sop_rules
        sop_rules = search_sop_rules(f"rule {rule_id}", rule_id=rule_id, top_k=3)
        
        if sop_rules:
            return "\n".join(sop_rules)
        
        # Fallback to direct file reading
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
        "device_id": alert.get("device_id", None),
        "rule_id": alert.get("ruleId") or alert.get("rule_id") or "unknown"
    }
    
    # Enhance context with memory integration
    enhanced_ctx = build_memory_enhanced_context(ctx, "TransactionContextAgent")
    
    state["transaction_context"] = enhanced_ctx
    save_context("TransactionContext", enhanced_ctx["txn_id"], enhanced_ctx)
    
    # Store transaction memory in mem0
    if mem0_manager:
        try:
            mem0_manager.store_fraud_case_memory(
                case_id=enhanced_ctx["txn_id"],
                case_data=enhanced_ctx
            )
            logging.info(f"[TransactionContextAgent] Stored transaction memory in mem0")
        except Exception as e:
            logging.error(f"[TransactionContextAgent] Error storing memory: {e}")
    
    logging.info(f"[TransactionContextAgent] Output: {enhanced_ctx}")
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
        
        # Enhance user context with memory integration
        enhanced_user = build_memory_enhanced_context(user, "CustomerInfoAgent")
        
        state["user_context"] = enhanced_user
        save_context("UserContext", user_id, enhanced_user)
        
        # Store customer interaction memory in mem0
        if mem0_manager:
            try:
                mem0_manager.store_customer_interaction(
                    case_id=txn_ctx["txn_id"],
                    interaction=f"Customer {user_id} transaction analysis with enhanced context"
                )
                logging.info(f"[CustomerInfoAgent] Stored customer interaction memory in mem0")
            except Exception as e:
                logging.error(f"[CustomerInfoAgent] Error storing memory: {e}")
        
        logging.info(f"[CustomerInfoAgent] Output: {enhanced_user}")
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
        
        # Enhance merchant context with memory integration
        enhanced_ctx = build_memory_enhanced_context(ctx, "MerchantInfoAgent")
        
        state["merchant_context"] = enhanced_ctx
        save_context("MerchantContext", merchant_id, enhanced_ctx)
        
        # Store merchant analysis memory in mem0
        if mem0_manager:
            try:
                mem0_manager.store_agent_summary(
                    case_id=txn_ctx["txn_id"],
                    agent_name="MerchantInfoAgent",
                    agent_summary=f"Merchant {merchant_id} analysis with risk level {enhanced_ctx['risk_level']}"
                )
                logging.info(f"[MerchantInfoAgent] Stored merchant analysis memory in mem0")
            except Exception as e:
                logging.error(f"[MerchantInfoAgent] Error storing memory: {e}")
        
        logging.info(f"[MerchantInfoAgent] Output: {enhanced_ctx}")
        return state
    except Exception as e:
        logging.error(f"[MerchantInfoAgent] Error: {e}")
        raise

# --- BehavioralPatternAgent ---
def behavioral_pattern_agent(state):
    system_prompt = (
        "You are an anomaly detection agent. Compute anomaly metrics from the provided context. "
        "Consider historical patterns and similar cases when available. "
        "Respond ONLY with a valid JSON object for AnomalyContext, and nothing else. "
        "The schema is: {\"anomaly_score\": float, \"explanation\": str, \"historical_comparison\": str} "
        "Do not include any explanation, markdown, or text outside the JSON object."
    )
    
    # Enhance state with memory context for better anomaly detection
    enhanced_state = state.copy()
    if "transaction_context" in state and "memory_summary" in state["transaction_context"]:
        enhanced_state["memory_context"] = state["transaction_context"].get("similar_cases", [])
    
    prompt = f"Given this transaction and user/merchant context with historical patterns, compute anomaly metrics: {json.dumps(enhanced_state)}"
    try:
        result = call_claude([
            {"role": "user", "content": prompt}
        ], system=system_prompt)
        json_str = extract_json_from_llm_output(result, "BehavioralPatternAgent")
        ctx = json.loads(json_str)
        state["anomaly_context"] = ctx
        save_context("AnomalyContext", state["transaction_context"]["txn_id"], ctx)
        
        # Store behavioral analysis memory in mem0
        if mem0_manager:
            try:
                mem0_manager.store_agent_summary(
                    case_id=state["transaction_context"]["txn_id"],
                    agent_name="BehavioralPatternAgent",
                    agent_summary=f"Anomaly score: {ctx.get('anomaly_score', 0)}, Explanation: {ctx.get('explanation', '')}"
                )
                logging.info(f"[BehavioralPatternAgent] Stored behavioral analysis memory in mem0")
            except Exception as e:
                logging.error(f"[BehavioralPatternAgent] Error storing memory: {e}")
        
        logging.info(f"[BehavioralPatternAgent] Output: {ctx}")
        return state
    except Exception as e:
        logging.error(f"[BehavioralPatternAgent] Error: {e}")
        raise

# --- RiskSynthesizerAgent ---
def risk_synthesizer_agent(state):
    system_prompt = (
        "You are a risk synthesizer agent. Summarize risk for the transaction using historical patterns and similar cases. "
        "Consider the memory context and similar case outcomes when available. "
        "Respond ONLY with a valid JSON object for RiskSummaryContext. "
        "The schema is: {\"risk_score\": float, \"summary\": str, \"chain_of_thought\": str, \"historical_patterns\": str}. "
        "Do not include any explanation, markdown, or text outside the JSON object."
    )
    
    # Enhance state with memory context for better risk assessment
    enhanced_state = state.copy()
    if "transaction_context" in state and "memory_summary" in state["transaction_context"]:
        enhanced_state["memory_context"] = state["transaction_context"].get("similar_cases", [])
        enhanced_state["historical_patterns"] = state["transaction_context"].get("agent_memories", [])
    
    prompt = f"Summarize risk for this transaction using historical patterns and similar cases: {json.dumps(enhanced_state)}"
    try:
        result = call_claude([
            {"role": "user", "content": prompt}
        ], system=system_prompt)
        json_str = extract_json_from_llm_output(result, "RiskSynthesizerAgent")
        ctx = json.loads(json_str)
        state["risk_summary_context"] = ctx
        save_context("RiskSummaryContext", state["transaction_context"]["txn_id"], ctx)
        
        # Store risk assessment memory in mem0
        if mem0_manager:
            try:
                mem0_manager.store_risk_assessment(
                    case_id=state["transaction_context"]["txn_id"],
                    risk_assessment=f"Risk score: {ctx.get('risk_score', 0)}, Summary: {ctx.get('summary', '')}",
                    confidence=ctx.get('risk_score', 0)
                )
                logging.info(f"[RiskSynthesizerAgent] Stored risk assessment memory in mem0")
            except Exception as e:
                logging.error(f"[RiskSynthesizerAgent] Error storing memory: {e}")
        
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
        # Guard: run PolicyDecision once per case
        if state.get('policy_decision_done'):
            return state
        result = call_claude([
            {"role": "user", "content": prompt}
        ], system=system_prompt)
        json_str = extract_json_from_llm_output(result, "PolicyDecisionAgent")
        ctx = json.loads(json_str)
        state["decision_context"] = ctx
        save_context("DecisionContext", state["transaction_context"]["txn_id"], ctx)
        state['policy_decision_done'] = True
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
        
        # Store customer response in mem0 for learning
        if mem0_manager:
            try:
                mem0_manager.store_customer_interaction(
                    case_id=txn_context["txn_id"],
                    interaction=f"Customer response: {customer_answer}"
                )
                logging.info(f"[DialogueAgent] Stored customer response in mem0")
            except Exception as e:
                logging.error(f"[DialogueAgent] Error storing customer response: {e}")
    
    # Enhanced RAG: Retrieve relevant questions using context, RAG, and memory
    context_str = f"Rule: {rule_id}, Txn: {txn_context}"
    
    # Get questions from enhanced RAG with context awareness
    from vector_utils import search_contextual_questions, get_relevant_context
    
    # Use enhanced contextual question search
    questions = search_contextual_questions(context_str, rule_id=rule_id, context=json.dumps(txn_context), top_k=5)
    logging.info(f"[DialogueAgent] Enhanced RAG questions: {questions}")
    
    # If enhanced RAG doesn't return enough questions, fallback to questions.md
    if not questions or len(questions) < 3:
        # Enhance context with memory for better question selection
        enhanced_context = txn_context.copy()
        if "memory_summary" in txn_context:
            enhanced_context["similar_cases"] = txn_context.get("similar_cases", [])
            enhanced_context["agent_memories"] = txn_context.get("agent_memories", [])
        
        fallback_questions = select_questions_from_md("datasets/questions.md", rule_id, enhanced_context)
        questions.extend(fallback_questions)
        logging.info(f"[DialogueAgent] Memory-enhanced fallback questions: {fallback_questions}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_questions = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            unique_questions.append(q)
    questions = unique_questions
    
    # Template questions with enhanced context
    def fill(q):
        enhanced_context = txn_context.copy()
        if "memory_summary" in txn_context:
            enhanced_context.update(txn_context)
        for k, v in enhanced_context.items():
            if isinstance(v, (str, int, float)):
                q = q.replace(f"[{k}]", str(v))
        return q
    
    questions = [fill(q) for q in questions]
    
    # Intelligent question selection based on customer responses
    asked = [turn["msg"] for turn in dialogue if turn["from"] == "agent"]
    
    # If we have a customer answer, use it to select the most relevant next question
    if customer_answer:
        # Use LLM to select the best next question based on customer response
        system_prompt = (
            "You are an intelligent dialogue agent. Based on the customer's response and available questions, "
            "select the most relevant next question. Consider the context and what information is still needed. "
            "Respond with ONLY the selected question text, nothing else."
        )
        
        available_questions = [q for q in questions if q not in asked]
        if available_questions:
            prompt = f"""
            Customer Response: {customer_answer}
            Available Questions: {available_questions}
            Context: {json.dumps(txn_context)}
            
            Select the most relevant next question based on the customer's response:
            """
            
            try:
                selected_question = call_claude([
                    {"role": "user", "content": prompt}
                ], system=system_prompt, max_tokens=100, temperature=0.3)
                
                # Find the closest matching question from our list
                next_q = None
                for q in available_questions:
                    if selected_question.strip().lower() in q.lower() or q.lower() in selected_question.strip().lower():
                        next_q = q
                        break
                
                if not next_q and available_questions:
                    next_q = available_questions[0]  # Fallback to first available
                    
            except Exception as e:
                logging.error(f"[DialogueAgent] Error in intelligent question selection: {e}")
                next_q = next((q for q in available_questions), None)
        else:
            next_q = None
    else:
        # First question - select based on context
        next_q = next((q for q in questions if q not in asked), None)
    
    done = False
    if next_q and turn_count < max_turns:
        dialogue.append({"from": "agent", "msg": next_q})
        logging.info(f"[DialogueAgent] Intelligently selected question: {next_q}")
    else:
        done = True
        logging.info(f"[DialogueAgent] Dialogue complete or max turns reached.")
    
    # Update state
    state["dialogue_context"] = {"dialogue_turns": dialogue, "done": done}
    save_context("DialogueContext", state["transaction_context"]["txn_id"], state["dialogue_context"])
    
    # Add context trace for UI
    trace = state.get("context_trace", [])
    if next_q is None:
        next_q = ""
    trace.append({
        "agent": "DialogueAgent",
        "customer_answer": customer_answer,
        "rag_results": [],  # Simplified for now
        "questions": questions,
        "selected_question": next_q,
        "dialogue": list(dialogue),
        "done": done,
        "intelligent_selection": customer_answer is not None
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
    system_prompt = (
        "You are a risk assessor agent. Assess the dialogue for scam indicators using historical patterns and similar cases. "
        "Consider the memory context and similar case outcomes when available. "
        "Respond ONLY with a valid JSON object for RiskSummaryContext. "
        "The schema is: {\"risk_score\": float, \"summary\": str, \"confidence\": float, \"historical_patterns\": str, \"recommendation\": str}. "
        "Do not include any explanation, markdown, or text outside the JSON object."
    )
    
    # Enhance state with memory context for better risk assessment
    enhanced_state = state.copy()
    if "transaction_context" in state and "memory_summary" in state["transaction_context"]:
        enhanced_state["memory_context"] = state["transaction_context"].get("similar_cases", [])
        enhanced_state["historical_patterns"] = state["transaction_context"].get("agent_memories", [])
    
    prompt = f"Assess this dialogue for scam indicators using historical patterns and similar cases: {json.dumps(enhanced_state)}"
    try:
        result = call_claude([
            {"role": "user", "content": prompt}
        ], system=system_prompt)
        json_str = extract_json_from_llm_output(result, "RiskAssessorAgent")
        ctx = json.loads(json_str)
        state["risk_summary_context"] = ctx
        save_context("RiskSummaryContext", state["transaction_context"]["txn_id"], ctx)
        
        # Store risk assessment memory in mem0
        if mem0_manager:
            try:
                mem0_manager.store_risk_assessment(
                    case_id=state["transaction_context"]["txn_id"],
                    risk_assessment=f"Dialogue risk assessment: {ctx.get('summary', '')}",
                    confidence=ctx.get('confidence', ctx.get('risk_score', 0))
                )
                logging.info(f"[RiskAssessorAgent] Stored dialogue risk assessment in mem0")
            except Exception as e:
                logging.error(f"[RiskAssessorAgent] Error storing memory: {e}")
        
        logging.info(f"[RiskAssessorAgent] Output: {ctx}")
        return state
    except Exception as e:
        logging.error(f"[RiskAssessorAgent] Error: {e}")
        raise 