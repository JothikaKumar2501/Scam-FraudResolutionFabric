import os
from agents_multi import (
    TransactionContextAgent, CustomerInfoAgent, MerchantInfoAgent, BehavioralPatternAgent,
    RiskSynthesizerAgent, TriageAgent, DialogueAgent, RiskAssessorAgent, PolicyDecisionAgent, FeedbackCollectorAgent
)
from context_store import ContextStore

context_store = ContextStore()

def log_step(state, message):
    if state is None:
        print(f"[ERROR] State is None when logging: {message}")
        return {'logs': [f'[ERROR] State is None: {message}']}
    print(message)
    if 'logs' not in state:
        state['logs'] = []
    state['logs'].append(message)
    return state

def run_context_agents(state):
    # Run all context agents in parallel and merge their results
    context_results = {}
    logs = []
    responses = []
    for agent_cls, name, key, prompt in [
        (TransactionContextAgent, 'TransactionContextAgent', 'transaction_context', 'Build transaction context'),
        (CustomerInfoAgent, 'CustomerInfoAgent', 'customer_context', 'Build customer context'),
        (MerchantInfoAgent, 'MerchantInfoAgent', 'merchant_context', 'Build merchant context'),
        (BehavioralPatternAgent, 'BehavioralPatternAgent', 'anomaly_context', 'Build anomaly context'),
    ]:
        agent = agent_cls(name, context_store)
        result = agent.act(prompt, state)
        if result is not None and key in result:
            context_results[key] = result[key]
        logs.append(f"{name}")
        responses.append(result.get(key, '[No response]') if result else '[No response]')
    state.update(context_results)
    if 'logs' not in state:
        state['logs'] = []
    if 'agent_responses' not in state:
        state['agent_responses'] = []
    state['logs'].extend(logs)
    state['agent_responses'].extend(responses)
    return state

def run_langgraph_multi_agent(alert, max_steps=None):
    state = {'transaction': alert, 'logs': [], 'agent_responses': []}
    total_steps = 9  # 4 context + 1 risk + 1 triage + 1 dialogue loop + 1 policy + 1 feedback
    step = 0
    # 1. Context agents (parallel)
    if max_steps is None or step < max_steps:
        state = run_context_agents(state)
        step += 4
    # 2. RiskSynthesizerAgent
    if max_steps is None or step < max_steps:
        agent = RiskSynthesizerAgent("RiskSynthesizerAgent", context_store)
        result = agent.act("Synthesize risk", state)
        state['logs'].append("RiskSynthesizerAgent")
        state['agent_responses'].append(result.get('risk_summary_context', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        step += 1
    # 3. TriageAgent
    if max_steps is None or step < max_steps:
        agent = TriageAgent("TriageAgent", context_store)
        result = agent.act("Triage", state)
        state['logs'].append("TriageAgent")
        state['agent_responses'].append(result.get('triage_decision', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        step += 1
    # 4. DialogueAgent <-> RiskAssessorAgent loop
    dialogue_history = []
    done = False
    max_turns = 8
    while not done and (max_steps is None or step < max_steps):
        agent = DialogueAgent("DialogueAgent", context_store)
        risk_agent = RiskAssessorAgent("RiskAssessorAgent", context_store)
        next_q, agent_name, finished = agent.get_next_question_and_agent(dialogue_history, state)
        if next_q:
            dialogue_history.append({'agent': agent_name, 'question': next_q, 'agent_log': agent_name})
        user_response = "[Simulated user response]"
        if dialogue_history:
            result, done = agent.act('Continue', state, user_response=user_response)
        else:
            result, done = agent.act('Continue', state, user_response=None)
        if result is None or not isinstance(result, dict):
            break
        state = result
        result_risk = risk_agent.act('Assess risk', state)
        if result_risk is None or not isinstance(result_risk, dict):
            break
        state = result_risk
        step += 1
        if done or len(dialogue_history) >= max_turns:
            break
    state['dialogue_history'] = dialogue_history
    state['logs'].append("DialogueAndRiskLoop")
    state['agent_responses'].append('[Dialogue loop completed]')
    # 5. PolicyDecisionAgent
    if max_steps is None or step < max_steps:
        agent = PolicyDecisionAgent("PolicyDecisionAgent", context_store)
        result = agent.act("Policy decision", state)
        state['logs'].append("PolicyDecisionAgent")
        state['agent_responses'].append(result.get('policy_decision', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        step += 1
    # 6. FeedbackCollectorAgent
    if max_steps is None or step < max_steps:
        agent = FeedbackCollectorAgent("FeedbackCollectorAgent", context_store)
        result = agent.act("Collect feedback", state)
        state['logs'].append("FeedbackCollectorAgent")
        state['agent_responses'].append(result.get('feedback', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        step += 1
    state['total_steps'] = total_steps
    state['current_step'] = step
    return state

def summarize_risk_report(state):
    """Generate a risk report summary from the conversation and context."""
    prompt = "You are a fraud analyst. Given the following conversation and context, summarize if the transaction is fraudulent or not, and explain why."
    history = "\n".join([f"Q: {turn['question']}\nA: {turn.get('user', '')}" for turn in state.get('dialogue_history', [])])
    txn_info = str(state.get('transaction', {}))
    full_prompt = f"{prompt}\nTransaction: {txn_info}\nConversation:\n{history}\nReport:"
    # Use the same LLM call as other agents
    from aws_bedrock import converse_with_claude_stream
    report = "".join([token for token in converse_with_claude_stream([
        {"role": "user", "content": [{"text": full_prompt}]}
    ], max_tokens=512)])
    state['risk_report_summary'] = report
    return state

def stream_langgraph_steps(state):
    # Accepts a full state dict. If context already present, skip to dialogue loop.
    # If state is just an alert dict, initialize full state.
    if 'transaction' not in state:
        state = {'transaction': state, 'logs': [], 'agent_responses': [], 'dialogue_history': []}
    context_keys = ['transaction_context', 'customer_context', 'merchant_context', 'anomaly_context', 'risk_summary_context', 'triage_decision']
    context_ready = all(k in state for k in context_keys)
    
    if not context_ready:
        # Stream individual context agents one by one
        context_agents = [
            (TransactionContextAgent, 'TransactionContextAgent', 'transaction_context', 'Build transaction context'),
            (CustomerInfoAgent, 'CustomerInfoAgent', 'customer_context', 'Build customer context'),
            (MerchantInfoAgent, 'MerchantInfoAgent', 'merchant_context', 'Build merchant context'),
            (BehavioralPatternAgent, 'BehavioralPatternAgent', 'anomaly_context', 'Build anomaly context'),
        ]
        
        for i, (agent_cls, name, key, prompt) in enumerate(context_agents):
            agent = agent_cls(name, context_store)
            result = agent.act(prompt, state)
            if result is not None and key in result:
                state[key] = result[key]
            if 'logs' not in state:
                state['logs'] = []
            if 'agent_responses' not in state:
                state['agent_responses'] = []
            state['logs'].append(name)
            state['agent_responses'].append(result.get(key, '[No response]') if result else '[No response]')
            state['current_step'] = i + 1
            state['total_steps'] = 9  # Now 9 steps, not 10
            yield state.copy()
        
        # RiskSynthesizerAgent
        agent = RiskSynthesizerAgent("RiskSynthesizerAgent", context_store)
        result = agent.act("Synthesize risk", state)
        state['logs'].append("RiskSynthesizerAgent")
        state['agent_responses'].append(result.get('risk_summary_context', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        state['current_step'] = 5
        yield state.copy()
        
        # TriageAgent
        agent = TriageAgent("TriageAgent", context_store)
        result = agent.act("Triage", state)
        state['logs'].append("TriageAgent")
        state['agent_responses'].append(result.get('triage_decision', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        state['current_step'] = 6
        yield state.copy()
    
    if 'dialogue_history' not in state or not isinstance(state['dialogue_history'], list):
        state['dialogue_history'] = []
    done = False
    finalized = False
    turn_count = 0
    
    while not done:
        dialogue_history = state['dialogue_history']
        
        # Step 1: DialogueAgent asks a question
        agent = DialogueAgent("DialogueAgent", context_store)
        user_response = None
        if dialogue_history and dialogue_history[-1].get('role') == 'user':
            user_response = dialogue_history[-1]['user']
            for i in range(len(dialogue_history) - 2, -1, -1):
                if dialogue_history[i].get('role') == 'assistant' and 'user' not in dialogue_history[i]:
                    dialogue_history[i]['user'] = user_response
                    break
        
        # Get question from DialogueAgent
        stream_gen = agent.act('Continue', state, user_response=user_response, stream=True)
        buffer = ''
        for token in stream_gen:
            if token == '__END__':
                break
            buffer += token
            state['streaming_token'] = token
            yield state.copy()
        
        if 'logs' not in state:
            state['logs'] = []
        if 'agent_responses' not in state:
            state['agent_responses'] = []
        
        # Add dialogue question to history
        state['dialogue_history'].append({'role': 'assistant', 'question': buffer})
        state['logs'].append('DialogueAgent')
        state['agent_responses'].append(buffer)
        state['current_step'] = 7
        yield state.copy()
        
        # Check if DialogueAgent itself says to finalize
        if 'finalize' in buffer.lower():
            done = True
            finalized = True
            state['chat_done'] = True
            # Store latest risk assessment for DialogueAgent
            state['latest_risk_assessment'] = state.get('risk_assessment', '')
            # Don't continue here - let it break naturally from the loop
            break
        
        # Wait for user response
        yield state.copy()
        
        # After user responds, run RiskAssessorAgent to evaluate progress
        if dialogue_history and len(dialogue_history) > 0 and dialogue_history[-1].get('role') == 'user':
            turn_count += 1
            # Only run risk assessment if the last assistant question is NOT an identity/security check
            last_assistant_q = None
            for t in reversed(dialogue_history[:-1]):
                if t.get('role') == 'assistant' and 'question' in t:
                    last_assistant_q = t['question'].lower()
                    break
            identity_keywords = ['name', 'date of birth', 'dob', 'identity', 'address', 'email', 'phone']
            is_identity_check = last_assistant_q and any(kw in last_assistant_q for kw in identity_keywords)
            if not is_identity_check:
                # Step 2: RiskAssessorAgent evaluates dialogue progress
                risk_agent = RiskAssessorAgent("RiskAssessorAgent", context_store)
                result_risk = risk_agent.act('Assess risk progress', state)
                if result_risk and isinstance(result_risk, dict):
                    state.update(result_risk)
                    risk_summary = result_risk.get('risk_assessment', str(result_risk))
                    state['logs'].append(f'RiskAssessorAgent_DialogueTurn{turn_count}')
                    state['agent_responses'].append(risk_summary)
                    # Store latest risk assessment for UI display
                    state['latest_risk_assessment'] = risk_summary
                    # Check if RiskAssessorAgent determines we have enough information
                    if result_risk.get('risk_ready_to_finalize') or 'finalize' in risk_summary.lower():
                        done = True
                        finalized = True
                        state['chat_done'] = True
                        state['finalized_by_risk'] = True
                # Yield to show risk assessment in UI
                yield state.copy()
        # Safety check: max dialogue turns
        if turn_count >= 10:
            done = True
            finalized = True
            state['chat_done'] = True
    
    # After dialogue loop, always proceed to final steps
    if finalized:
        # Final comprehensive risk assessment after dialogue completes
        risk_assessor = RiskAssessorAgent("RiskAssessorAgentFinalSummary", context_store)
        risk_summary_result = risk_assessor.act('Final risk summary based on complete dialogue', state)
        if risk_summary_result and isinstance(risk_summary_result, dict):
            state.update(risk_summary_result)
            summary = risk_summary_result.get('risk_assessment', str(risk_summary_result))
            state['logs'].append('RiskAssessorAgentFinalSummary')
            state['agent_responses'].append(summary)
            state['risk_assessment_summary'] = summary
            state['final_risk_determination'] = summary
        state['current_step'] = 8
        yield state.copy()
        
        # Policy Decision
        policy_agent = PolicyDecisionAgent("PolicyDecisionAgent", context_store)
        policy_result = policy_agent.act("Policy decision", state)
        state['logs'].append("PolicyDecisionAgent")
        state['agent_responses'].append(policy_result.get('policy_decision', '[No response]') if policy_result and isinstance(policy_result, dict) else '[No response]')
        if policy_result and isinstance(policy_result, dict):
            state.update(policy_result)
        state['current_step'] = 9
        yield state.copy()
        # Feedback agent is now skipped entirely. 