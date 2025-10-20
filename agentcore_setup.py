# # import os
# # from bedrock_agentcore.runtime import BedrockAgentCoreApp
# # from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
# # from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

# # # Initialize BedrockAgentCoreApp
# # app = BedrockAgentCoreApp()

# # # Environment variables
# # MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
# # REGION = os.getenv("AWS_REGION")
# # MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"

# # def initialize_memory_config(actor_id: str, session_id: str) -> AgentCoreMemoryConfig:
# #     """
# #     Initialize AgentCore memory configuration.
# #     """
# #     return AgentCoreMemoryConfig(
# #         memory_id=MEMORY_ID,
# #         session_id=session_id,
# #         actor_id=actor_id,
# #         retrieval_config={
# #             f"/users/{actor_id}/facts": RetrievalConfig(top_k=3, relevance_score=0.5),
# #             f"/users/{actor_id}/preferences": RetrievalConfig(top_k=3, relevance_score=0.5)
# #         }
# #     )

# # def create_agent_session_manager(actor_id: str, session_id: str) -> AgentCoreMemorySessionManager:
# #     """
# #     Create an AgentCoreMemorySessionManager for an agent.
# #     """
# #     memory_config = initialize_memory_config(actor_id, session_id)
# #     return AgentCoreMemorySessionManager(memory_config, REGION)

# # # Export the app and other necessary components
# # __all__ = ['app', 'MODEL_ID', 'create_agent_session_manager']
# import os
# from bedrock_agentcore.runtime import BedrockAgentCoreApp
# from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
# from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

# # Initialize BedrockAgentCoreApp
# app = BedrockAgentCoreApp()

# # Environment variables
# MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
# REGION = os.getenv("AWS_REGION")
# MODEL_ID = "global.anthropic.claude-sonnet-4-20250514-v1:0"


# def initialize_memory_config(actor_id: str, session_id: str) -> AgentCoreMemoryConfig:
#     """Initialize AgentCore memory configuration."""
#     return AgentCoreMemoryConfig(
#         memory_id=MEMORY_ID,
#         session_id=session_id,
#         actor_id=actor_id,
#         retrieval_config={
#             f"/users/{actor_id}/facts": RetrievalConfig(top_k=3, relevance_score=0.5),
#             f"/users/{actor_id}/preferences": RetrievalConfig(top_k=3, relevance_score=0.5),
#         },
#     )


# def create_agent_session_manager(actor_id: str, session_id: str) -> AgentCoreMemorySessionManager:
#     """Create an AgentCoreMemorySessionManager for an agent."""
#     memory_config = initialize_memory_config(actor_id, session_id)
#     return AgentCoreMemorySessionManager(memory_config, REGION)


# def test_agentcore_memory():
#     print("✅ Starting AgentCore memory test...")

#     try:
#         manager = create_agent_session_manager("test_agent", "test_session")
#         print(f"✅ AgentCore Session Manager initialized successfully for test_agent in {REGION}")
#         print(f"Type: {type(manager).__name__}")

#         # Test memory operations
#         memory_key = "/users/test_agent/facts"
#         test_fact = "This is a test fact for AgentCore memory."
        
#         # Write to memory
#         manager.write(memory_key, test_fact)
#         print("✅ Successfully wrote to AgentCore memory")

#         # Read from memory
#         retrieved_facts = manager.read(memory_key)
#         if test_fact in [fact.content for fact in retrieved_facts]:
#             print("✅ Successfully retrieved fact from AgentCore memory")
#         else:
#             print("❌ Failed to retrieve fact from AgentCore memory")

#         print("✅ All AgentCore memory tests passed!")
#     except Exception as e:
#         print(f"❌ AgentCore memory test failed: {e}")


# if __name__ == "__main__":
#     test_agentcore_memory()
"""
Strands-based Multi-Agent System with AgentCore memory
Fully integrated with AWS Bedrock AgentCore memory
Replaces mem0 for persistent state
"""

import os
import time
import concurrent.futures
from functools import wraps
from typing import Dict, Any, List

# Strands agents imports
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

# Optional XAI dialogue agent
try:
    from intelligent_dialogue import IntelligentDialogueAgent as _XaiDialogue
except Exception:
    _XaiDialogue = None

# Bedrock AgentCore
from bedrock_agentcore import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
MEMORY_NAMESPACE = "fraud_detection_pipeline"

# ----------------------------
# Utilities
# ----------------------------
def performance_monitor(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"[perf] {func.__name__} executed in {end_time - start_time:.2f}s")
        return result
    return wrapper

def save_state_to_agentcore(state: Dict[str, Any], description: str = ""):
    """
    Persist state to AgentCore memory
    """
    try:
        mem_id = f"AgentCoreMemory-{int(time.time()*1000)}"
        app.memory.create_or_get_memory(
            memory_id=mem_id,
            namespace=MEMORY_NAMESPACE,
            description=description,
            initial_content=state.copy()
        )
        print(f"✅ Saved state to AgentCore memory: {description}")
    except Exception as e:
        print(f"[ERROR] Failed to save AgentCore memory: {e}")

# ----------------------------
# Context Agents (Parallel)
# ----------------------------
@performance_monitor
def run_context_agents_parallel(state: Dict[str, Any]):
    """Run all context agents in parallel"""
    context_results = {}
    logs = []
    responses = []

    context_agents = [
        (transaction_context_agent, 'TransactionContextAgent', 'transaction_context', 'analyze_transaction'),
        (customer_info_agent, 'CustomerInfoAgent', 'customer_context', 'analyze_customer'),
        (merchant_info_agent, 'MerchantInfoAgent', 'merchant_context', 'analyze_merchant'),
        (behavioral_pattern_agent, 'BehavioralPatternAgent', 'anomaly_context', 'analyze_behavior'),
    ]

    def run_single_agent(agent_config):
        agent, name, key, method_name = agent_config
        try:
            method = getattr(agent, method_name)
            result = method(state)
            return {'name': name, 'key': key, 'result': result, 'response': result.get(key, '[No response]') if result else '[No response]'}
        except Exception as e:
            return {'name': name, 'key': key, 'result': None, 'response': f'[Error: {e}]'}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(run_single_agent, a): a[1] for a in context_agents}
        for future in concurrent.futures.as_completed(futures):
            agent_name = futures[future]
            try:
                res = future.result()
                if res['result'] and res['key'] in res['result']:
                    context_results[res['key']] = res['result'][res['key']]
                logs.append(res['name'])
                responses.append(res['response'])
            except Exception as e:
                logs.append(agent_name)
                responses.append(f'[Error: {e}]')

    state.update(context_results)
    state.setdefault('logs', []).extend(logs)
    state.setdefault('agent_responses', []).extend(responses)
    return state

# ----------------------------
# Streaming Strands Pipeline
# ----------------------------
@performance_monitor
def stream_strands_steps(alert_or_state):
    """
    Streaming Strands pipeline with AgentCore memory
    """
    # Initialize state
    if 'transaction' not in alert_or_state:
        state = {
            'transaction': alert_or_state,
            'logs': [],
            'agent_responses': [],
            'dialogue_history': [],
            'contexts_built': False,
            'risk_synth_done': False,
            'triage_done': False,
            'current_step': 0,
            'risk_cache': {}
        }
    else:
        state = alert_or_state

    save_state_to_agentcore(state, description="Initial state")
    yield state.copy()

    # Step 1: Context Agents
    if not state.get('contexts_built', False):
        state = run_context_agents_parallel(state)
        state['contexts_built'] = True
        state['current_step'] = 1
        save_state_to_agentcore(state, description="Context agents completed")
        yield state.copy()

    # Step 2: Risk Synthesizer
    if not state.get('risk_synth_done', False):
        result = risk_synthesizer_agent.synthesize_risk(state)
        if result:
            state.update(result)
        state['risk_synth_done'] = True
        state['current_step'] = 2
        save_state_to_agentcore(state, description="Risk synthesizer completed")
        yield state.copy()

    # Step 3: Triage
    if not state.get('triage_done', False):
        result = triage_agent.triage_case(state)
        if result:
            state.update(result)
        state['triage_done'] = True
        state['current_step'] = 3
        save_state_to_agentcore(state, description="Triage completed")
        yield state.copy()

    # Step 4: Dialogue + RiskAssessor Loop
    dialogue_history = state.get('dialogue_history', [])
    done = False
    turn_count = 0
    max_turns = 5

    while not done and turn_count < max_turns:
        # DialogueAgent next question
        question, agent_name, finished = dialogue_agent.get_next_question_and_agent(dialogue_history, state)
        dialogue_history.append({'agent': agent_name, 'question': question})
        state['dialogue_history'] = dialogue_history

        # Risk assessment caching
        cache_key = f"risk_turn_{turn_count}"
        if cache_key in state['risk_cache']:
            risk_result = state['risk_cache'][cache_key]
        else:
            risk_result = risk_assessor_agent.assess_risk(state)
            state['risk_cache'][cache_key] = risk_result
        if risk_result:
            state.update(risk_result)

        turn_count += 1
        state['current_step'] = 4
        save_state_to_agentcore(state, description=f"Dialogue turn {turn_count}")
        yield state.copy()

        if finished or turn_count >= max_turns:
            done = True

    # Step 5: Policy Decision
    policy_result = policy_decision_agent.make_policy_decision(state)
    if policy_result:
        state.update(policy_result)
    state['current_step'] = 5
    save_state_to_agentcore(state, description="Policy decision completed")
    yield state.copy()

    # Step 6: Feedback Collector
    feedback_result = feedback_collector_agent.collect_feedback(state)
    if feedback_result:
        state.update(feedback_result)
    state['current_step'] = 6
    save_state_to_agentcore(state, description="Feedback collected")
    yield state.copy()

    # Final: save final state
    save_state_to_agentcore(state, description="Final pipeline state")
    yield state.copy()

# ----------------------------
# Simple wrapper for running pipeline directly
# ----------------------------
def run_strands_pipeline(alert: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Run full pipeline to completion
        final_state = None
        for state in stream_strands_steps(alert):
            final_state = state
        return final_state
    except Exception as e:
        return {'error': str(e), 'transaction': alert, 'logs': ['Pipeline error'], 'agent_responses': [f'Pipeline error: {e}']}

# ----------------------------
# Exports
# ----------------------------
__all__ = [
    'stream_strands_steps',
    'run_strands_pipeline'
]
