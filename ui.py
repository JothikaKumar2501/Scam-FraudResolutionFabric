import streamlit as st
import json
import os
from agents_multi import SupervisorAgent, DialogueAgent
from context_store import ContextStore
import copy
from langgraph_multi_agent import run_langgraph_multi_agent, stream_langgraph_steps
import time
import re
import types

# Try to import vector search if available
try:
    from vector_utils import search_similar
    VECTOR_SEARCH = True
except ImportError:
    VECTOR_SEARCH = False

# Helper to parse markdown into sections (simple splitter)
def parse_markdown_sections(md):
    # Split on headings (## or #)
    sections = re.split(r'(^# .*$|^## .*$)', md, flags=re.MULTILINE)
    parsed = []
    current = ''
    for part in sections:
        if part.startswith('#'):
            if current:
                parsed.append(current.strip())
            current = part
        else:
            current += '\n' + part
    if current:
        parsed.append(current.strip())
    return [s for s in parsed if s.strip()]

def load_alerts():
    with open('datasets/FTP.json', encoding='utf-8') as f:
        return json.load(f)

def load_sop():
    with open('datasets/SOP.md', encoding='utf-8') as f:
        return f.read()

def load_questions():
    with open('datasets/questions.md', encoding='utf-8') as f:
        return f.read()

# --- Dynamic Question Selection ---
def get_dynamic_question(alert, dialogue_history, questions_md, sop_md):
    # Try to select a question based on ruleId, context, and previous questions
    rule_id = alert.get('ruleId', '')
    # Parse questions.md into a dict by fraud type/rule
    question_blocks = re.split(r'^### ', questions_md, flags=re.MULTILINE)
    question_map = {}
    for block in question_blocks:
        if not block.strip():
            continue
        lines = block.split('\n')
        header = lines[0].strip()
        questions = [l.strip('* ').strip() for l in lines[1:] if l.strip().startswith('*')]
        question_map[header] = questions
    # Try to match ruleId to a block
    for header, qs in question_map.items():
        if rule_id in header or rule_id.replace('-', '') in header.replace('-', ''):
            # Avoid repeating questions
            asked = set(turn.get('question') for turn in dialogue_history if 'question' in turn)
            for q in qs:
                if q not in asked:
                    return q
    # Fallback: General Questions
    general_qs = question_map.get('General Questions (Applicable to most alerts)', [])
    asked = set(turn.get('question') for turn in dialogue_history if 'question' in turn)
    for q in general_qs:
        if q not in asked:
            return q
    # Fallback: SOP identity verification
    if 'Identity Verification' in sop_md:
        match = re.search(r'Identity Verification:(.*?)\n\n', sop_md, re.DOTALL)
        if match:
            lines = [l.strip('- ').strip() for l in match.group(1).split('\n') if l.strip()]
            for q in lines:
                if q not in asked:
                    return q
    return "Can you confirm your identity and details for this transaction?"

def dashboard_page():
    st.title('📊 Dashboard')
    alerts = load_alerts()
    # Risk score trend (dummy: count of alerts per day)
    import pandas as pd
    df = pd.DataFrame(alerts)
    if 'alertDate' in df:
        trend = df.groupby('alertDate').size().reset_index()
        trend.columns = ['alertDate', 'alerts']
        st.line_chart(trend.rename(columns={'alertDate': 'Date', 'alerts': 'Alerts'}).set_index('Date'))
    st.subheader('Recent Alerts')
    cols = ['alertId', 'customerId', 'priority', 'status', 'description', 'alertDate', 'alertTime']
    if not df.empty and all(col in df.columns for col in cols):
        st.dataframe(df[cols])
    else:
        st.dataframe(df)

    # --- Flowchart Panel ---
    st.markdown("---")
    st.subheader("System Flowchart", help="Overview of the multi-agent fraud analysis system.")
    st.image("flowchart.png", caption="System Flowchart Image")
    st.image("payments_pic.png", caption="System Architecture Image")

def alerts_page():
    st.title('🔔 Alerts')
    alerts = load_alerts()
    st.dataframe(alerts)

def agentic_system_page():
    # --- Robust session state initialization ---
    session_defaults = dict(
        analysis_running=False,
        analysis_complete=False,
        agent_logs=[],
        agent_responses=[],
        progress=0,
        dialogue_history=[],
        chat_turn=0,
        chat_done=False,
        asked_questions=set(),
        backend_state=None,
        selected_alert=None,
        # Track which agents have been displayed
        displayed_agents=set(),
        # Track streaming content
        streaming_content={},
        # Track streaming generator and current state
        streaming_generator=None,
        current_state=None
    )
    for k, v in session_defaults.items():
        if k not in st.session_state:
            st.session_state[k] = copy.deepcopy(v)
    alerts = load_alerts()
    questions_md = load_questions()
    sop_md = load_sop()
    alert_options = [f"{a['alertId']}: {a.get('description','')}" for a in alerts]
    selected_idx = st.selectbox('Select an alert to analyze:', list(range(len(alert_options))), format_func=lambda i: alert_options[i] if alert_options else '', key='alert_select')
    selected_alert = alerts[selected_idx] if alerts else None
    if not st.session_state.analysis_running and not st.session_state.analysis_complete:
        if st.button('Start Analysis', key='start_analysis_btn', disabled=selected_alert is None):
            st.session_state.analysis_running = True
            st.session_state.analysis_complete = False
            st.session_state.agent_logs = []
            st.session_state.agent_responses = []
            st.session_state.progress = 0
            st.session_state.selected_alert = selected_alert
            st.session_state.dialogue_history = []
            st.session_state.chat_turn = 0
            st.session_state.chat_done = False
            st.session_state.asked_questions = set()
            st.session_state.displayed_agents = set()
            st.session_state.streaming_content = {}
            st.session_state.streaming_generator = None
            st.session_state.current_state = None
            # Initialize state for backend
            st.session_state.backend_state = {'transaction': selected_alert, 'logs': [], 'agent_responses': [], 'dialogue_history': []}
            st.rerun()
        return
    
    if st.session_state.analysis_running:
        # Use backend_state for all backend calls
        if st.session_state.backend_state is None:
            st.session_state.backend_state = {'transaction': selected_alert, 'logs': [], 'agent_responses': [], 'dialogue_history': []}
        backend_state = st.session_state.backend_state
        
        # Create containers for real-time updates
        progress_bar = st.progress(0)
        status_placeholder = st.empty()
        
        # Create containers for each section that will update in real-time
        context_container = st.container()
        risk_container = st.container()
        triage_container = st.container()
        chat_container = st.container()
        final_risk_container = st.container()
        policy_container = st.container()
        feedback_container = st.container()
        
        # --- Process streaming updates step by step ---
        # Always re-initialize the generator if it's None (e.g., after a reload)
        if st.session_state.streaming_generator is None:
            st.session_state.streaming_generator = stream_langgraph_steps(backend_state)
            st.session_state.current_state = None
        
        # Get next state from generator
        try:
            if st.session_state.current_state is None:
                st.session_state.current_state = next(st.session_state.streaming_generator)
            
            state = st.session_state.current_state
            st.session_state.backend_state = state.copy()
            logs = state.get('logs', [])
            responses = state.get('agent_responses', [])
            
            # Update progress
            current_step = state.get('current_step', 0)
            total_steps = state.get('total_steps', 10)
            progress = current_step / total_steps if total_steps > 0 else 0
            progress_bar.progress(progress)
            status_placeholder.info(f"Analysis Progress: Step {current_step} / {total_steps}")
            # Show the latest agent response right below progress
            if responses:
                latest_response = responses[-1]
                if not isinstance(latest_response, str):
                    if hasattr(latest_response, '__iter__') and not isinstance(latest_response, str):
                        latest_response = ''.join(list(latest_response))
                    else:
                        latest_response = str(latest_response)
                status_placeholder.markdown(f"**Latest Agent Response:**\n\n{latest_response}")
            
            # Handle streaming token if present
            if 'streaming_token' in state:
                token = state['streaming_token']
                if 'DialogueAgent' in logs and len(logs) > 0:
                    agent_key = 'DialogueAgent'
                    if agent_key not in st.session_state.streaming_content:
                        st.session_state.streaming_content[agent_key] = ''
                    st.session_state.streaming_content[agent_key] += token
            
            # Update agent logs and responses
            if len(logs) > len(st.session_state.agent_logs):
                new_logs = logs[len(st.session_state.agent_logs):]
                st.session_state.agent_logs.extend(new_logs)
            
            if len(responses) > len(st.session_state.agent_responses):
                new_responses = responses[len(st.session_state.agent_responses):]
                st.session_state.agent_responses.extend(new_responses)
            
            # Check if waiting for user input
            dialogue_history = state.get('dialogue_history', [])
            if dialogue_history and dialogue_history[-1].get('role') == 'assistant' and not state.get('chat_done', False):
                # Wait for user input, don't advance generator
                pass
            elif current_step >= 10:
                # Analysis complete
                st.session_state.analysis_running = False
                st.session_state.analysis_complete = True
            else:
                # Advance to next state
                if st.session_state.streaming_generator is None:
                    st.session_state.streaming_generator = stream_langgraph_steps(st.session_state.backend_state)
                st.session_state.current_state = next(st.session_state.streaming_generator)
                st.rerun()
                
        except StopIteration:
            # Generator exhausted
            st.session_state.analysis_running = False
            st.session_state.analysis_complete = True
        
        # --- Render UI sections in real-time ---

        # Show all agent responses in order, always, including final summary and policy
        with st.container():
            st.markdown('---')
            st.subheader('📊 All Agent Responses (Complete Analysis)')
            
            # Group responses by type for better organization
            context_agents = ['TransactionContextAgent', 'CustomerInfoAgent', 'MerchantInfoAgent', 'BehavioralPatternAgent']
            risk_agents = ['RiskSynthesizerAgent', 'TriageAgent']
            dialogue_agents = ['DialogueAgent']
            final_agents = ['RiskAssessorAgentFinalSummary', 'PolicyDecisionAgent']
            
            for i, (log, resp) in enumerate(zip(st.session_state.agent_logs, st.session_state.agent_responses)):
                # Determine agent type for styling
                agent_type = "Context"
                if log in context_agents:
                    agent_type = "Context Building"
                elif log in risk_agents:
                    agent_type = "Risk Analysis"
                elif log in dialogue_agents:
                    agent_type = "Dialogue"
                elif log in final_agents:
                    agent_type = "Final Decision"
                elif 'RiskAssessorAgent_DialogueTurn' in log:
                    agent_type = "Risk Assessment"
                else:
                    agent_type = "Analysis"
                
                # Color coding based on agent type
                color_map = {
                    "Context Building": "🔍",
                    "Risk Analysis": "⚠️",
                    "Dialogue": "💬",
                    "Risk Assessment": "🔍",
                    "Final Decision": "🎯",
                    "Analysis": "📋"
                }
                
                icon = color_map.get(agent_type, "📋")
                expanded = (i == len(st.session_state.agent_logs) - 1) or agent_type in ["Final Decision", "Risk Analysis"]
                
                with st.expander(f"{icon} {log} ({agent_type})", expanded=expanded):
                    if not isinstance(resp, str):
                        if hasattr(resp, '__iter__') and not isinstance(resp, str):
                            resp = ''.join(list(resp))
                            st.session_state.agent_responses[i] = resp
                        else:
                            resp = str(resp)
                    
                    # Format the response nicely
                    if agent_type == "Context Building":
                        st.info("🔍 **Context Analysis**")
                    elif agent_type == "Risk Analysis":
                        st.warning("⚠️ **Risk Assessment**")
                    elif agent_type == "Final Decision":
                        st.success("🎯 **Final Decision**")
                    elif agent_type == "Risk Assessment":
                        st.info("🔍 **Risk Evaluation**")
                    
                    for section in parse_markdown_sections(resp):
                        st.markdown(section)

        # --- Conversational Chat Loop (show in real-time, persistent chat bubbles) ---
        if len(st.session_state.agent_logs) >= 7:
            with chat_container:
                st.markdown('---')
                st.subheader('💬 Dialogue & Risk Chat')
                
                # Only show true chat turns from dialogue_history, ensuring no duplicates
                dialogue_history = state.get('dialogue_history', [])
                seen_questions = set()
                seen_answers = set()
                
                # Helper to deduplicate and clean repeated lines in chat bubbles
                def clean_chat_text(text):
                    # Remove repeated lines and excessive duplication
                    lines = text.split('\n')
                    seen = set()
                    cleaned = []
                    for line in lines:
                        l = line.strip()
                        if l and l not in seen:
                            cleaned.append(l)
                            seen.add(l)
                    return '\n'.join(cleaned)
                
                for turn in dialogue_history:
                    if isinstance(turn, dict):
                        if turn.get('role') == 'assistant' and 'question' in turn:
                            question_text = clean_chat_text(turn['question'])
                            # Only show if not already seen
                            if question_text not in seen_questions:
                                with st.chat_message("assistant"):
                                    st.markdown(question_text)
                                seen_questions.add(question_text)
                        if turn.get('role') == 'user' and 'user' in turn:
                            answer_text = clean_chat_text(turn['user'])
                            # Only show if not already seen
                            if answer_text not in seen_answers:
                                with st.chat_message("user"):
                                    st.markdown(answer_text)
                                seen_answers.add(answer_text)
                
                # Only allow user input if last message is from agent and chat not done
                if (not st.session_state.get('chat_done', False) and dialogue_history and dialogue_history[-1].get('role') == 'assistant'):
                    user_input = st.chat_input('Your response:')
                    if user_input:
                        st.session_state.backend_state['dialogue_history'].append({'role': 'user', 'user': user_input})
                        if st.session_state.streaming_generator is None:
                            st.session_state.streaming_generator = stream_langgraph_steps(st.session_state.backend_state)
                        st.session_state.current_state = next(st.session_state.streaming_generator)
                        st.rerun()
                elif st.session_state.get('chat_done', False):
                    st.success('Dialogue complete. Proceeding to Policy Decision...')

        # --- Show post-dialogue steps in real-time ---
        if st.session_state.get('chat_done', False):
            # Final Risk Assessment Summary
            if len(st.session_state.agent_logs) >= 8 and 'RiskAssessorAgentFinalSummary' not in st.session_state.displayed_agents:
                with final_risk_container:
                    st.markdown('---')
                    st.subheader('🎯 Final Risk Assessment Summary')
                    st.info("Comprehensive analysis based on complete dialogue and all context")
                    for i, log in enumerate(st.session_state.agent_logs):
                        if 'RiskAssessorAgentFinalSummary' in log and i < len(st.session_state.agent_responses):
                            with st.expander("Final Risk Determination", expanded=True):
                                resp = st.session_state.agent_responses[i]
                                if not isinstance(resp, str):
                                    resp = str(resp)
                                st.markdown(resp)
                            st.session_state.displayed_agents.add('RiskAssessorAgentFinalSummary')
                            break
            # Policy Decision
            if len(st.session_state.agent_logs) >= 9 and 'PolicyDecisionAgent' not in st.session_state.displayed_agents:
                with policy_container:
                    st.markdown('---')
                    st.subheader('📋 Policy Decision')
                    for i, log in enumerate(st.session_state.agent_logs):
                        if 'PolicyDecisionAgent' in log and i < len(st.session_state.agent_responses):
                            with st.expander("Policy Action & Compliance", expanded=True):
                                resp = st.session_state.agent_responses[i]
                                if not isinstance(resp, str):
                                    if hasattr(resp, '__iter__'):
                                        resp = ''.join(list(resp))
                                st.markdown(resp)
                            st.session_state.displayed_agents.add('PolicyDecisionAgent')
                            break
        # Feedback Collection section is now removed.
    
    if st.session_state.analysis_complete:
        st.success('Analysis complete!')
        st.button('Restart', on_click=lambda: st.session_state.clear(), key='restart_btn_final')

def semantic_search_page():
    st.title('🔎 Semantic Search')
    st.write('Search across SOPs, questions, and alerts.')
    query = st.text_input('Enter your search query:')
    results = []
    if query:
        # Search SOP.md
        sop = load_sop()
        sop_hits = []
        if VECTOR_SEARCH:
            sop_hits = search_similar(query, top_k=5)
        else:
            for line in sop.splitlines():
                if query.lower() in line.lower():
                    sop_hits.append(line.strip())
        # Search questions.md
        questions = load_questions()
        q_hits = []
        if VECTOR_SEARCH:
            q_hits = search_similar(query, top_k=5)
        else:
            for line in questions.splitlines():
                if query.lower() in line.lower():
                    q_hits.append(line.strip())
        # Search alerts
        alerts = load_alerts()
        alert_hits = [a for a in alerts if query.lower() in json.dumps(a).lower()]
        st.subheader('SOP Results')
        for hit in sop_hits:
            st.markdown(f"- {hit}")
        st.subheader('Questions Results')
        for hit in q_hits:
            st.markdown(f"- {hit}")
        st.subheader('Alert Results')
        for a in alert_hits:
            st.json(a)

def docs_page():
    st.title('📄 Documentation & Schemas')
    st.write('Context schemas and documentation.')
    # Show schemas if available
    try:
        from schemas import TransactionContext, UserContext, MerchantContext, AnomalyContext, RiskSummaryContext, DecisionContext, DialogueContext, FeedbackContext
        for schema in [TransactionContext, UserContext, MerchantContext, AnomalyContext, RiskSummaryContext, DecisionContext, DialogueContext, FeedbackContext]:
            st.subheader(schema.__name__)
            st.json(schema.__annotations__)
    except Exception:
        st.info('Schemas not available.')
    # --- Domain Data Panel ---
    st.markdown("---")
    st.subheader("Domain Data", help="Previews of SOPs and questions, and RAG results for each agent step.")
    st.markdown("**SOP.md Preview:**")
    st.code(load_sop()[:1000])
    st.markdown("**Questions.md Preview:**")
    st.code(load_questions()[:1000])

# --- Helper to deduplicate identical turns (not just consecutive) ---
def deduplicate_dialogue_history(dialogue_history):
    seen = set()
    deduped = []
    for turn in dialogue_history:
        if isinstance(turn, dict):
            if turn.get('role') == 'assistant' and 'question' in turn:
                key = ('assistant', str(turn['question']))
            elif turn.get('role') == 'user' and 'user' in turn:
                key = ('user', str(turn['user']))
            else:
                key = None
            if key and key not in seen:
                deduped.append(turn)
                seen.add(key)
        else:
            deduped.append(turn)
    return deduped

# --- Main App ---
st.set_page_config(page_title="GenAI FraudOps Suite for Authorized Scams", layout="wide")

# Modern product heading at the top of every page
st.markdown("""
<div style='background:linear-gradient(90deg,#001F3F,#0074D9);color:#fff;padding:18px 24px;border-radius:12px;margin-bottom:18px;'>
    <h1 style='margin-bottom:0;'>GenAI FraudOps Suite for Authorized Scams</h1>
    <span style='font-size:1.1em;'>🧠 Multi Agentic System for Fraud Detection, Analysis & Triage Platform, with editable user responses and context replay.</span>
</div>
""", unsafe_allow_html=True)

st.sidebar.title("Navigation")
# page = st.sidebar.radio("Go to", ["Dashboard", "Alerts", "Agentic System", "Semantic Search", "Docs"])
page = st.sidebar.radio("Go to", ["Dashboard", "Agentic System", "Semantic Search", "Docs"])

if page == "Dashboard":
    dashboard_page()
# elif page == "Alerts":
#     alerts_page()
elif page == "Agentic System":
    agentic_system_page()
elif page == "Semantic Search":
    semantic_search_page()
elif page == "Docs":
    docs_page() 