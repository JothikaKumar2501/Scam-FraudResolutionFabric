import os
import asyncio
import concurrent.futures
from typing import Dict, Any, List, Optional
from agents_multi import (
    TransactionContextAgent, CustomerInfoAgent, MerchantInfoAgent, BehavioralPatternAgent,
    RiskSynthesizerAgent, TriageAgent, DialogueAgent, RiskAssessorAgent, PolicyDecisionAgent, FeedbackCollectorAgent
)
try:
    # Optional enhanced dialogue agent with XAI
    from intelligent_dialogue import IntelligentDialogueAgent as _XaiDialogue
except Exception:
    _XaiDialogue = None
from context_store import ContextStore

context_store = ContextStore()

# Performance monitoring
import time
from functools import wraps
from typing import Dict, Any

# LangGraph imports for true MAS orchestration
try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False

def performance_monitor(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        try:
            print(f"[perf] {func.__name__} executed in {execution_time:.2f}s")
        except Exception:
            # Fallback for consoles without UTF-8
            pass
        return result
    return wrapper

def log_step(state, message):
    if state is None:
        print(f"[ERROR] State is None when logging: {message}")
        return {'logs': [f'[ERROR] State is None: {message}']}
    print(message)
    if 'logs' not in state:
        state['logs'] = []
    state['logs'].append(message)
    return state

@performance_monitor
def run_context_agents_parallel(state):
    """Run all context agents in parallel for better performance"""
    context_results = {}
    logs = []
    responses = []
    
    # Define context agents with their configurations
    context_agents = [
        (TransactionContextAgent, 'TransactionContextAgent', 'transaction_context', 'Build transaction context'),
        (CustomerInfoAgent, 'CustomerInfoAgent', 'customer_context', 'Build customer context'),
        (MerchantInfoAgent, 'MerchantInfoAgent', 'merchant_context', 'Build merchant context'),
        (BehavioralPatternAgent, 'BehavioralPatternAgent', 'anomaly_context', 'Build anomaly context'),
    ]
    
    def run_single_agent(agent_config):
        """Run a single agent and return results"""
        agent_cls, name, key, prompt = agent_config
        try:
            agent = agent_cls(name, context_store)
            result = agent.act(prompt, state)
            return {
                'name': name,
                'key': key,
                'result': result,
                'response': result.get(key, '[No response]') if result else '[No response]'
            }
        except Exception as e:
            print(f"Error running {name}: {e}")
            return {
                'name': name,
                'key': key,
                'result': None,
                'response': f'[Error: {e}]'
            }
    
    # Run all context agents in parallel using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all agent tasks
        future_to_agent = {
            executor.submit(run_single_agent, agent_config): agent_config[1] 
            for agent_config in context_agents
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_agent):
            agent_name = future_to_agent[future]
            try:
                agent_result = future.result()
                if agent_result['result'] is not None and agent_result['key'] in agent_result['result']:
                    context_results[agent_result['key']] = agent_result['result'][agent_result['key']]
                logs.append(agent_result['name'])
                responses.append(agent_result['response'])
            except Exception as e:
                print(f"Error collecting result from {agent_name}: {e}")
                logs.append(agent_name)
                responses.append(f'[Error: {e}]')
    
    # Update state with results
    state.update(context_results)
    if 'logs' not in state:
        state['logs'] = []
    if 'agent_responses' not in state:
        state['agent_responses'] = []
    state['logs'].extend(logs)
    state['agent_responses'].extend(responses)
    
    return state

# Keep the original sequential version as fallback
def run_context_agents(state):
    """Original sequential implementation as fallback"""
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

@performance_monitor
def run_langgraph_multi_agent(alert, max_steps=None):
    state = {'transaction': alert, 'logs': [], 'agent_responses': [], 'contexts_built': False, 'risk_synth_done': False, 'triage_done': False}
    total_steps = 9  # 4 context + 1 risk + 1 triage + 1 dialogue loop + 1 policy + 1 feedback
    step = 0
    
    # 1. Context agents (parallel) - OPTIMIZED
    if (max_steps is None or step < max_steps) and not state.get('contexts_built'):
        state = run_context_agents_parallel(state)
        state['contexts_built'] = True
        step += 4
    
    # 2. RiskSynthesizerAgent
    if (max_steps is None or step < max_steps) and not state.get('risk_synth_done'):
        agent = RiskSynthesizerAgent("RiskSynthesizerAgent", context_store)
        result = agent.act("Synthesize risk", state)
        state['logs'].append("RiskSynthesizerAgent")
        state['agent_responses'].append(result.get('risk_summary_context', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        state['risk_synth_done'] = True
        step += 1
    
    # 3. TriageAgent
    if (max_steps is None or step < max_steps) and not state.get('triage_done'):
        agent = TriageAgent("TriageAgent", context_store)
        result = agent.act("Triage", state)
        state['logs'].append("TriageAgent")
        state['agent_responses'].append(result.get('triage_decision', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        state['triage_done'] = True
        step += 1
    
    # 4. DialogueAgent <-> RiskAssessorAgent loop (non-streaming fallback)
    dialogue_history = state.get('dialogue_history', [])
    done = False
    max_turns = 8
    turn_count = 0
    while not done and turn_count < max_turns and (max_steps is None or step < max_steps):
        agent = DialogueAgent("DialogueAgent", context_store)
        risk_agent = RiskAssessorAgent("RiskAssessorAgent", context_store)
        next_q, agent_name, finished = agent.get_next_question_and_agent(dialogue_history, state)
        if next_q:
            dialogue_history.append({'agent': agent_name, 'question': next_q, 'agent_log': agent_name})
        # In non-streaming path do NOT simulate user; break until UI supplies input
        # Mark waiting state and exit loop gracefully
        done = finished or (turn_count + 1) >= max_turns
        turn_count += 1
        step += 1
        break
    state['dialogue_history'] = dialogue_history
    state['logs'].append("DialogueAgent")
    state['agent_responses'].append(next_q if isinstance(next_q, str) else '[Dialogue update]')
    
    # 5. PolicyDecisionAgent (only if finalization occurred and not already run)
    if (max_steps is None or step < max_steps) and (state.get('chat_done') or state.get('risk_ready_to_finalize') or state.get('finalized_by_risk')) and not state.get('policy_decision_done'):
        agent = PolicyDecisionAgent("PolicyDecisionAgent", context_store)
        result = agent.act("Policy decision", state)
        state['logs'].append("PolicyDecisionAgent")
        state['agent_responses'].append(result.get('policy_decision', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        state['policy_decision_done'] = True
        # Attach XAI decision for non-streaming fallback path as well
        try:
            state['xai_decision'] = _build_xai_decision(state)
            state.setdefault('audit_log', []).append({'type': 'xai_decision', 'payload': state['xai_decision']})
        except Exception:
            pass
        step += 1
    
    # 6. FeedbackCollectorAgent (optional)
    if max_steps is None or step < max_steps:
        agent = FeedbackCollectorAgent("FeedbackCollectorAgent", context_store)
        result = agent.act("Collect feedback", state)
        state['logs'].append("FeedbackCollectorAgent")
        state['agent_responses'].append(result.get('feedback_summary', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        step += 1
    
    return state

def summarize_risk_report(state):
    """Summarize the risk assessment report"""
    if 'risk_assessment_summary' in state:
        return state['risk_assessment_summary']
    elif 'risk_summary_context' in state:
        return state['risk_summary_context']
    else:
        return "No risk assessment available"

# ------------------
# XAI Builder (World-class structured explainability)
# ------------------
def _normalize_score(state: Dict[str, Any]) -> float:
    """Derive a normalized 0..1 risk score from available sources."""
    try:
        # Prefer structured risk_summary_context
        rsc = state.get('risk_summary_context')
        if isinstance(rsc, dict):
            v = rsc.get('risk_score')
            if isinstance(v, (int, float)):
                v = float(v)
                if v > 1.0:
                    return max(0.0, min(1.0, v / 1000.0))
                return max(0.0, min(1.0, v))
        # Fallback: overall_risk_score already 0..1
        v = state.get('overall_risk_score')
        if isinstance(v, (int, float)):
            return max(0.0, min(1.0, float(v)))
        # Fallback: alert risk_score 0..1000
        alert = state.get('transaction') or {}
        v = alert.get('risk_score') or alert.get('riskScore')
        if isinstance(v, (int, float)):
            return max(0.0, min(1.0, float(v) / 1000.0))
    except Exception:
        pass
    return 0.0

def _gather_top_evidence(state: Dict[str, Any]) -> list:
    """Collect top evidence snippets with light weighting and tags."""
    items = []
    try:
        # Dialogue evidence
        dh = state.get('dialogue_history') or []
        indicators = []
        text = (" ".join([t.get('user','') for t in dh if isinstance(t, dict)])).lower()
        for k in ['anydesk','teamviewer','remote access','security code','otp','bank security department','payid','guided']:
            if k in text:
                indicators.append(k)
        if dh:
            q = next((t for t in reversed(dh) if t.get('role')=='assistant' and t.get('question')), None)
            a = next((t for t in reversed(dh) if t.get('user')), None)
            snippet = (q.get('question','') if q else '')
            if a and a.get('user'):
                if snippet:
                    snippet += "\n\nUser: " + a.get('user')[:240]
                else:
                    snippet = a.get('user')[:240]
            if snippet:
                items.append({
                    'title': 'Dialogue Red Flags',
                    'snippet': snippet[:480],
                    'weight': 0.40,
                    'source': 'dialogue_history',
                    'tags': indicators[:6]
                })
        # Anomaly evidence
        anom = state.get('anomaly_context')
        if isinstance(anom, dict):
            snippet = f"Anomaly score: {anom.get('anomaly_score')} - {anom.get('explanation','')[:220]}"
        else:
            snippet = str(anom)[:280] if anom else ''
        if snippet:
            items.append({
                'title': 'Behavioral Pattern Analysis',
                'snippet': snippet,
                'weight': 0.20,
                'source': 'anomaly_context',
                'tags': ['behavior', 'anomaly']
            })
        # Transaction evidence
        tx = state.get('transaction') or {}
        if tx:
            snippet = f"Alert {tx.get('alertId') or tx.get('alert_id')}: ${tx.get('amount','?')} to new/unknown recipient. Priority: {tx.get('priority') or tx.get('escalation_level')}."
            items.append({
                'title': 'Transaction Context',
                'snippet': snippet[:280],
                'weight': 0.15,
                'source': 'transaction',
                'tags': [str(tx.get('ruleId') or tx.get('rule_id') or 'rule')]
            })
        # Risk synthesis evidence
        rs = state.get('risk_summary_context')
        if rs:
            snippet = str(rs)[:320]
            items.append({
                'title': 'Risk Synthesis',
                'snippet': snippet,
                'weight': 0.15,
                'source': 'risk_summary_context',
                'tags': ['risk']
            })
        # Triage evidence
        tri = state.get('triage_decision')
        if tri:
            items.append({
                'title': 'Triage Outcome',
                'snippet': str(tri)[:240],
                'weight': 0.10,
                'source': 'triage_decision',
                'tags': ['triage']
            })
    except Exception:
        pass
    return items[:6]

def _build_xai_decision(state: Dict[str, Any]) -> Dict[str, Any]:
    """World-class XAI payload with provenance, thresholds, and structured evidence."""
    # Decision text from policy or fallback
    decision_text = state.get('policy_decision') or state.get('final_policy_decision') or ''
    decision_cls = 'investigate'
    dl = decision_text.lower()
    if 'block' in dl:
        decision_cls = 'block'
    elif 'clear' in dl or 'proceed' in dl:
        decision_cls = 'clear'
    elif 'escalate' in dl:
        decision_cls = 'escalate'
    elif 'delay' in dl or 'hold' in dl:
        decision_cls = 'delay'

    score = _normalize_score(state)
    thresholds = {
        'block': 0.75,
        'investigate': 0.50,
        'warn': 0.35,
        'clear': 0.25
    }
    evidence = _gather_top_evidence(state)
    gate = state.get('gate_reason', {})
    logs_tail = state.get('logs', [])[-10:]

    # Feature weights summary
    feature_weights = {
        'dialogue_indicators': next((e['weight'] for e in evidence if e.get('source')=='dialogue_history'), 0.0),
        'behavioral_anomaly': next((e['weight'] for e in evidence if e.get('source')=='anomaly_context'), 0.0),
        'transaction_context': next((e['weight'] for e in evidence if e.get('source')=='transaction'), 0.0),
        'risk_synthesis': next((e['weight'] for e in evidence if e.get('source')=='risk_summary_context'), 0.0),
        'triage': next((e['weight'] for e in evidence if e.get('source')=='triage_decision'), 0.0),
    }

    # Provenance
    alert = state.get('transaction') or {}
    provenance = {
        'dataset': 'datasets/FTP.json',
        'alert_id': alert.get('alertId') or alert.get('alert_id'),
        'customer_id': alert.get('customerId') or alert.get('customer_id'),
        'rule_id': alert.get('ruleId') or alert.get('rule_id'),
        'mem0_used': bool(state.get('audit_log')),
    }

    # Policy basis
    policy_basis = {
        'primary': 'APRA CPG 234 (Operational Risk)',
        'aml_ctf': 'AUSTRAC AML/CTF Act 2006 (suspicious matter reporting)',
        'customer_protection': 'ASIC RG 271 (prevent foreseeable harm, fair treatment)',
        'banking_code': 'Australian Banking Code of Practice (scam protection)'
    }

    xai = {
        'decision': decision_cls,
        'score': score,
        'thresholds': thresholds,
        'top_evidence': evidence,
        'reasoned_steps': [
            'Context agents built transaction, customer, merchant, and anomaly contexts',
            'Risk synthesized and assessed across dialogue turns',
            'Expert gate evaluated context sufficiency',
            'Final risk assessed with compressed logs and SOP alignment',
            'Policy decision selected with regulatory justification'
        ],
        'model_calls': logs_tail,
        'gate_reason': gate,
        'feature_weights': feature_weights,
        'provenance': provenance,
        'policy_basis': policy_basis,
        'schema_version': 'xai.v2',
    }
    return xai
# ------------------
# LangGraph MAS (Production Path)
# ------------------

_APP_CACHE = None

def _node_build_contexts(state: Dict[str, Any]) -> Dict[str, Any]:
    state.setdefault('logs', [])
    state.setdefault('agent_responses', [])
    return run_context_agents_parallel(state)

def _node_risk_synth(state: Dict[str, Any]) -> Dict[str, Any]:
    agent = RiskSynthesizerAgent("RiskSynthesizerAgent", context_store)
    result = agent.act("Synthesize risk", state)
    state['logs'].append("RiskSynthesizerAgent")
    state['agent_responses'].append(result.get('risk_summary_context', '[No response]') if result and isinstance(result, dict) else '[No response]')
    if result and isinstance(result, dict):
        state.update(result)
    return state

def _node_triage(state: Dict[str, Any]) -> Dict[str, Any]:
    agent = TriageAgent("TriageAgent", context_store)
    result = agent.act("Triage", state)
    state['logs'].append("TriageAgent")
    state['agent_responses'].append(result.get('triage_decision', '[No response]') if result and isinstance(result, dict) else '[No response]')
    if result and isinstance(result, dict):
        state.update(result)
    return state

def _node_dialogue_risk_loop(state: Dict[str, Any]) -> Dict[str, Any]:
    # Single-step question emission; do not auto-advance without user input
    state.setdefault('dialogue_history', [])
    dialogue_history = state['dialogue_history']
    use_xai = os.getenv("USE_INTELLIGENT_DIALOGUE", "0").lower() in ("1", "true", "yes") and _XaiDialogue is not None
    agent = (_XaiDialogue if use_xai else DialogueAgent)("DialogueAgent", context_store)
    next_q, agent_name, finished = agent.get_next_question_and_agent(dialogue_history, state)
    if next_q:
        # Defer appending to dialogue history until buffered question text is finalized downstream
        state.setdefault('logs', []).append('DialogueAgent')
        state.setdefault('agent_responses', []).append(next_q)
    # Mark awaiting user and do not perform risk or policy here
    state['awaiting_user'] = True
    state['dialogue_history'] = dialogue_history
    return state

def _node_finalize_policy(state: Dict[str, Any]) -> Dict[str, Any]:
    # Only run once and only when dialogue is finalized or explicitly ready
    if state.get('policy_decision_done'):
        return state
    ready_to_finalize = bool(
        state.get('chat_done') or state.get('risk_ready_to_finalize') or state.get('finalized_by_risk') or state.get('finalization_requested')
    )
    if not ready_to_finalize:
        state.setdefault('logs', []).append('PolicyDecisionAgent[skipped]')
        return state
    # Final comprehensive risk then policy decision (once)
    if not state.get('risk_final_done'):
        risk_assessor = RiskAssessorAgent("RiskAssessorAgentFinalSummary", context_store)
        risk_summary_result = risk_assessor.act('Final risk summary based on complete dialogue', state)
        if risk_summary_result and isinstance(risk_summary_result, dict):
            state.update(risk_summary_result)
            summary = risk_summary_result.get('risk_assessment', str(risk_summary_result))
            state.setdefault('logs', []).append('RiskAssessorAgentFinalSummary')
            state.setdefault('agent_responses', []).append(summary)
            state['risk_assessment_summary'] = summary
            state['final_risk_determination'] = summary
        state['risk_final_done'] = True
    policy_agent = PolicyDecisionAgent("PolicyDecisionAgent", context_store)
    policy_result = policy_agent.act("Policy decision", state)
    state.setdefault('logs', []).append("PolicyDecisionAgent")
    state.setdefault('agent_responses', []).append(policy_result.get('policy_decision', '[No response]') if policy_result and isinstance(policy_result, dict) else '[No response]')
    if policy_result and isinstance(policy_result, dict):
        state.update(policy_result)
    state['policy_decision_done'] = True
    # XAI decision JSON (world-class)
    try:
        xai = _build_xai_decision(state)
        state['xai_decision'] = xai
        state.setdefault('audit_log', []).append({'type': 'xai_decision', 'payload': xai})
    except Exception:
        pass
    return state

def build_langgraph_app():
    global _APP_CACHE
    if _APP_CACHE is not None:
        return _APP_CACHE
    if not LANGGRAPH_AVAILABLE:
        return None
    graph = StateGraph(dict)
    # Nodes
    graph.add_node("build_contexts", _node_build_contexts)
    graph.add_node("risk_synth", _node_risk_synth)
    graph.add_node("triage", _node_triage)
    graph.add_node("dialogue_risk_loop", _node_dialogue_risk_loop)
    graph.add_node("finalize_policy", _node_finalize_policy)
    # Edges
    graph.add_edge(START, "build_contexts")
    graph.add_edge("build_contexts", "risk_synth")
    graph.add_edge("risk_synth", "triage")
    graph.add_edge("triage", "dialogue_risk_loop")
    graph.add_edge("dialogue_risk_loop", "finalize_policy")
    graph.add_edge("finalize_policy", END)
    checkpointer = MemorySaver()
    app = graph.compile(checkpointer=checkpointer)
    _APP_CACHE = app
    return app

def run_langgraph_pipeline(alert: Dict[str, Any]) -> Dict[str, Any]:
    """Production entrypoint: run the compiled LangGraph pipeline or fall back."""
    try:
        app = build_langgraph_app()
        if app is None:
            # Fallback to existing sequential driver
            return run_langgraph_multi_agent(alert)
        init_state = {'transaction': alert, 'logs': [], 'agent_responses': []}
        return app.invoke(init_state)
    except Exception:
        # Fallback on any runtime error to ensure system availability
        return run_langgraph_multi_agent(alert)

@performance_monitor
def stream_langgraph_steps(state):
    """Optimized streaming implementation with parallel execution and better performance"""
    # Accepts a full state dict. If context already present, skip to dialogue loop.
    # If state is just an alert dict, initialize full state.
    if 'transaction' not in state:
        state = {'transaction': state, 'logs': [], 'agent_responses': [], 'dialogue_history': []}
    
    # Idempotent gating to avoid duplicate runs
    state.setdefault('contexts_built', False)
    state.setdefault('risk_synth_done', False)
    state.setdefault('triage_done', False)
    state.setdefault('total_steps', 9)

    # Immediate placeholder to reduce perceived latency in UI
    try:
        state.setdefault('current_step', 1)
        state.setdefault('total_steps', 9)
        state.setdefault('streaming_agent', 'Initializing')
        yield state.copy()
    except Exception:
        pass

    if not state.get('contexts_built'):
        print("🚀 Running context agents in parallel...")
        state = run_context_agents_parallel(state)
        state['contexts_built'] = True
        state['current_step'] = 4
        yield state.copy()

    if not state.get('risk_synth_done'):
        print("🔍 Running RiskSynthesizerAgent...")
        agent = RiskSynthesizerAgent("RiskSynthesizerAgent", context_store)
        result = agent.act("Synthesize risk", state)
        state['logs'].append("RiskSynthesizerAgent")
        state['agent_responses'].append(result.get('risk_summary_context', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        state['risk_synth_done'] = True
        state['current_step'] = 5
        yield state.copy()

    if not state.get('triage_done'):
        print("⚡ Running TriageAgent...")
        agent = TriageAgent("TriageAgent", context_store)
        result = agent.act("Triage", state)
        state['logs'].append("TriageAgent")
        state['agent_responses'].append(result.get('triage_decision', '[No response]') if result and isinstance(result, dict) else '[No response]')
        if result and isinstance(result, dict):
            state.update(result)
        state['triage_done'] = True
        state['current_step'] = 6
        yield state.copy()
    
    if 'dialogue_history' not in state or not isinstance(state['dialogue_history'], list):
        state['dialogue_history'] = []
    done = False
    finalized = False
    turn_count = 0
    
    def _expert_gate_has_context(s: Dict[str, Any]) -> bool:
        """Expert gating: ensure required contexts exist before final risk/policy.
        Also annotate gate reasons for XAI/UX.
        """
        try:
            tx_ok = bool(s.get('transaction_context'))
            cust_ok = bool(s.get('customer_context'))
            merch_ok = bool(s.get('merchant_context'))
            beh_ok = bool(s.get('anomaly_context'))
            dh = s.get('dialogue_history') or []
            # Count user turns whether attached to assistant QA pairs or as standalone 'user' role turns
            user_turns = 0
            for t in dh:
                if not isinstance(t, dict):
                    continue
                if t.get('role') == 'user' and t.get('user'):
                    user_turns += 1
                elif t.get('role') == 'assistant' and t.get('user'):
                    user_turns += 1
            turns_ok = user_turns >= 2
            # Strong indicators can relax turn requirement
            text = (" ".join([t.get('user','') for t in dh if isinstance(t, dict)])).lower()
            strong = any(k in text for k in ['anydesk','teamviewer','remote access','security code','otp','bank security department'])
            ok = tx_ok and cust_ok and merch_ok and beh_ok and (turns_ok or strong)
            s['gate_reason'] = {
                'tx_ok': tx_ok,
                'cust_ok': cust_ok,
                'merch_ok': merch_ok,
                'beh_ok': beh_ok,
                'user_turns': user_turns,
                'strong_indicators': strong,
                'passed': ok,
            }
            return ok
        except Exception:
            s['gate_reason'] = {'passed': False, 'error': True}
            return False

    while not done:
        dialogue_history = state['dialogue_history']
        # If we are waiting for user input (last turn is assistant without an appended 'user' answer), pause
        try:
            if (
                isinstance(dialogue_history, list)
                and len(dialogue_history) > 0
                and dialogue_history[-1].get('role') == 'assistant'
                and 'user' not in dialogue_history[-1]
                and not state.get('chat_done', False)
            ):
                state['current_step'] = 7
                state['streaming_agent'] = 'DialogueAgent'
                yield state.copy()
                # Do not generate a new question until the UI posts a user turn via /api/user_reply
                continue
        except Exception:
            pass
        
        # Step 1: DialogueAgent asks a question
        use_xai = os.getenv("USE_INTELLIGENT_DIALOGUE", "0").lower() in ("1", "true", "yes") and _XaiDialogue is not None
        agent = (_XaiDialogue if use_xai else DialogueAgent)("DialogueAgent", context_store)
        user_response = None
        if dialogue_history and dialogue_history[-1].get('role') == 'user':
            user_response = dialogue_history[-1]['user']
            for i in range(len(dialogue_history) - 2, -1, -1):
                if dialogue_history[i].get('role') == 'assistant' and 'user' not in dialogue_history[i]:
                    dialogue_history[i]['user'] = user_response
                    break
        
        # Prepare UI state for streaming before tokens arrive
        if 'logs' not in state:
            state['logs'] = []
        if 'agent_responses' not in state:
            state['agent_responses'] = []
        state['logs'].append('DialogueAgent')
        state['agent_responses'].append('')  # placeholder to be filled during streaming
        state['current_step'] = 7
        state['streaming_agent'] = 'DialogueAgent'
        # Yield once so UI immediately shows a placeholder under Latest Agent Response
        yield state.copy()
        
        # Get question from DialogueAgent (non-streaming), but do not auto-progress if no user input
        result, done_flag = agent.act('Continue', state, user_response=user_response, stream=False)
        # Enrich with mem0 graph snippets to reduce repetition
        try:
            from mem0_integration import search_graph as _graph_search
            cid = state.get('case_id') or (state.get('transaction', {}) or {}).get('alertId')
            graph_hits = _graph_search(cid, "authorized payment scam fraud remote urgent device", 3)
            graph_snips = []
            for g in graph_hits:
                if isinstance(g, dict):
                    v = g.get('memory') or g.get('data', {}).get('memory') or ''
                    if v:
                        graph_snips.append(str(v)[:120])
            if graph_snips:
                result['dialogue_analysis'] = (result.get('dialogue_analysis') or '') + "\n\nKnown context from graph: " + " | ".join(graph_snips)
        except Exception:
            pass
        # Prefer explicit dialogue_analysis; fall back to XAI agent current_question
        buffer = result.get('dialogue_analysis') or result.get('current_question') or ''
        
        # Update response immediately
        if state['agent_responses']:
            state['agent_responses'][-1] = buffer
        yield state.copy()
        
        # Add dialogue question to history if non-empty; avoid duplicating identical question
        if buffer.strip():
            should_append = True
            if state['dialogue_history'] and state['dialogue_history'][-1].get('role') == 'assistant':
                if state['dialogue_history'][-1].get('question') == buffer:
                    should_append = False
            if should_append:
                state['dialogue_history'].append({'role': 'assistant', 'question': buffer})
        yield state.copy()

        # Respect DialogueAgent completion and requested finalization flags
        try:
            if (
                done_flag
                or bool(result.get('dialogue_complete'))
                or bool(state.get('finalization_requested'))
            ):
                done = True
                finalized = True
                state['chat_done'] = True
                # Store latest risk assessment snapshot for UI if present
                state['latest_risk_assessment'] = state.get('risk_assessment', state.get('risk_assessment_summary', ''))
                break
        except Exception:
            pass
        
        # Check if DialogueAgent itself says to finalize
        if 'finalize' in buffer.lower():
            done = True
            finalized = True
            state['chat_done'] = True
            # Store latest risk assessment for DialogueAgent
            state['latest_risk_assessment'] = state.get('risk_assessment', '')
            # Don't continue here - let it break naturally from the loop
            break
        
        # Wait for user response. If no response yet, yield once and pause.
        if not state.get('chat_done', False) and (not state['dialogue_history'] or state['dialogue_history'][-1].get('role') == 'assistant'):
            state['current_step'] = 7
            yield state.copy()
            # Pause loop; control resumes when UI posts /api/user_reply
            continue
        
        # After user responds, run RiskAssessorAgent to evaluate progress (OPTIMIZED)
        if dialogue_history and len(dialogue_history) > 0 and dialogue_history[-1].get('role') == 'user':
            turn_count += 1
            
            # OPTIMIZATION: Only run risk assessment every 2 turns or on critical turns
            should_assess_risk = (
                turn_count % 2 == 0 or  # Every 2nd turn
                turn_count >= 5 or      # After 5 turns
                any(keyword in dialogue_history[-1].get('user', '').lower() 
                    for keyword in ['scam', 'fraud', 'unauthorized', 'suspicious', 'fake'])
            )
            
            if should_assess_risk:
                # Only run risk assessment if the last assistant question is NOT an identity/security check
                last_assistant_q = None
                for t in reversed(dialogue_history[:-1]):
                    if t.get('role') == 'assistant' and 'question' in t:
                        last_assistant_q = t['question'].lower()
                        break
                
                identity_keywords = ['name', 'date of birth', 'dob', 'identity', 'address', 'email', 'phone']
                is_identity_check = last_assistant_q and any(kw in last_assistant_q for kw in identity_keywords)
                
                if not is_identity_check:
                    # Step 2: RiskAssessorAgent evaluates dialogue progress (CACHED)
                    risk_agent = RiskAssessorAgent("RiskAssessorAgent", context_store)
                    
                    # Create a cache key for this assessment
                    cache_key = f"risk_assessment_{turn_count}_{hash(str(dialogue_history[-3:]))}"
                    
                    # Check if we have a cached result
                    if 'risk_cache' in state and cache_key in state.get('risk_cache', {}):
                        result_risk = state['risk_cache'][cache_key]
                    else:
                        result_risk = risk_agent.act('Assess risk progress', state)
                        # Cache the result
                        if 'risk_cache' not in state:
                            state['risk_cache'] = {}
                        state['risk_cache'][cache_key] = result_risk
                    
                    if result_risk and isinstance(result_risk, dict):
                        state.update(result_risk)
                        risk_summary = result_risk.get('risk_assessment', str(result_risk))
                        state['logs'].append(f'RiskAssessorAgent_DialogueTurn{turn_count}')
                        state['agent_responses'].append(risk_summary)
                        # Store latest risk assessment for UI display
                        state['latest_risk_assessment'] = risk_summary
                        
                        # Early termination if we have enough information AND expert gate passes
                        gate_ok = _expert_gate_has_context(state)
                        if (
                            (result_risk.get('risk_ready_to_finalize') or 'finalize' in risk_summary.lower())
                            and gate_ok
                        ) or turn_count >= 10:  # strict cap
                            done = True
                            finalized = True
                            state['chat_done'] = True
                            state['finalized_by_risk'] = True
                            # break out to finalize
                            pass
                    
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
        print("🎯 Running final risk assessment...")
        # Expert gating: if context insufficient, do one more dialogue prompt instead of final risk
        if not _expert_gate_has_context(state):
            # Trigger a clarifying question via DialogueAgent and do not finalize yet
            try:
                agent = (_XaiDialogue if (os.getenv("USE_INTELLIGENT_DIALOGUE", "0").lower() in ("1","true","yes") and _XaiDialogue is not None) else DialogueAgent)("DialogueAgent", context_store)
                state['finalization_requested'] = False
                state['chat_done'] = False
                result, _ = agent.act('Ask one clarifying question to complete missing context', state, user_response=None, stream=False)
                buffer = result.get('dialogue_analysis') or result.get('current_question') or 'Can you clarify the exact instructions you received and confirm any urgency or secrecy requests?'
                state.setdefault('logs', []).append('DialogueAgent')
                state.setdefault('agent_responses', []).append(buffer)
                state.setdefault('dialogue_history', []).append({'role': 'assistant', 'question': buffer})
                state['current_step'] = 7
                yield state.copy()
                # Exit without final risk; UI will wait for user input
                return
            except Exception:
                pass
        risk_assessor = RiskAssessorAgent("RiskAssessorAgentFinalSummary", context_store)
        # Ensure dialogue_history is included for final assessment
        state.setdefault('dialogue_history', state.get('dialogue_history', []))
        risk_summary_result = risk_assessor.act('Final risk summary based on complete dialogue', state)
        if risk_summary_result and isinstance(risk_summary_result, dict):
            state.update(risk_summary_result)
            summary = risk_summary_result.get('final_risk_assessment') or risk_summary_result.get('risk_assessment') or str(risk_summary_result)
            state['logs'].append('RiskAssessorAgentFinalSummary')
            state['agent_responses'].append(summary)
            state['risk_assessment_summary'] = summary
            state['final_risk_determination'] = summary
        state['current_step'] = 8
        yield state.copy()
        
        # Policy Decision (always run after finalization, once)
        print("📋 Running policy decision...")
        if not state.get('policy_decision_done'):
            policy_agent = PolicyDecisionAgent("PolicyDecisionAgent", context_store)
            policy_result = policy_agent.act("Policy decision", state)
            state['logs'].append("PolicyDecisionAgent")
            state['agent_responses'].append(policy_result.get('policy_decision', '[No response]') if policy_result and isinstance(policy_result, dict) else '[No response]')
            if policy_result and isinstance(policy_result, dict):
                state.update(policy_result)
            state['policy_decision_done'] = True
        state['current_step'] = 9
        # XAI decision JSON for streaming path
        try:
            xai = _build_xai_decision(state)
            state['xai_decision'] = xai
            state.setdefault('audit_log', []).append({'type': 'xai_decision', 'payload': xai})
        except Exception:
            pass
        yield state.copy()
        # Feedback agent is now skipped entirely for performance. 