import streamlit as st
import json
import os
from agents_multi import SupervisorAgent, DialogueAgent
from context_store import ContextStore
import copy

# Try to import vector search if available
try:
    from vector_utils import search_similar
    VECTOR_SEARCH = True
except ImportError:
    VECTOR_SEARCH = False

def load_alerts():
    with open('datasets/FTP.json', encoding='utf-8') as f:
        return json.load(f)

def load_sop():
    with open('datasets/SOP.md', encoding='utf-8') as f:
        return f.read()

def load_questions():
    with open('datasets/questions.md', encoding='utf-8') as f:
        return f.read()

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

def alerts_page():
    st.title('🔔 Alerts')
    alerts = load_alerts()
    st.dataframe(alerts)

def agentic_system_page():
    # --- Ensure session state for checkpoints and edit mode is initialized ---
    if 'checkpoints' not in st.session_state:
        st.session_state['checkpoints'] = {}
    if 'edit_mode' not in st.session_state:
        st.session_state['edit_mode'] = None
    if 'edit_value' not in st.session_state:
        st.session_state['edit_value'] = ''
    if 'chat_versions' not in st.session_state or not isinstance(st.session_state['chat_versions'], dict):
        st.session_state['chat_versions'] = {}
    if 'show_version' not in st.session_state:
        st.session_state['show_version'] = {}  # {idx: version_number}
    # --- Reconstruct missing checkpoints for all user messages ---
    if 'chat_history' in st.session_state:
        user_indices = [i for i, m in enumerate(st.session_state['chat_history']) if m['role'] == 'user']
        for user_idx in user_indices:
            if user_idx not in st.session_state['checkpoints']:
                # Save a minimal checkpoint (best effort, may not be perfect for old messages)
                st.session_state['checkpoints'][user_idx] = {
                    k: copy.deepcopy(st.session_state[k]) if k in st.session_state else None for k in [
                        'chat_history', 'agent_log', 'final_report', 'awaiting_user', 'current_question', 'context', 'user_response', 'analysis_started', 'step', 'error'
                    ]
                }
    # --- Enhanced UI: Alert selection and Start Analysis ---
    alerts = load_alerts()
    alert_options = [f"[{a['alertId']}] {a['description']}" for a in alerts]
    selected = st.selectbox('Fraud Alerts', alert_options, help='Select a fraud alert to analyze')
    alert = alerts[alert_options.index(selected)]

    # Context panel: show alert/customer/summary info
    with st.expander('ℹ️ Alert & Customer Context', expanded=True):
        st.markdown(f"""
        <b>Alert ID:</b> {alert.get('alertId','')}<br>
        <b>Description:</b> {alert.get('description','')}<br>
        <b>Priority:</b> {alert.get('priority','')}<br>
        <b>Status:</b> {alert.get('status','')}<br>
        <b>Customer ID:</b> {alert.get('customerId','')}<br>
        <b>Date:</b> {alert.get('alertDate','')}<br>
        <b>Time:</b> {alert.get('alertTime','')}<br>
        """, unsafe_allow_html=True)
        # Optionally, show more context (e.g., customer info) if available

    # Robust session state initialization
    for k, v in [
        ('chat_history', []),
        ('agent_log', []),
        ('final_report', ''),
        ('awaiting_user', False),
        ('current_question', None),
        ('context', None),
        ('user_response', None),
        ('analysis_started', False),
        ('step', 0),
        ('error', None),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    # Show Start Analysis button below alert selection/context only if not started
    if not st.session_state['analysis_started']:
        st.markdown('---')
        if st.button('🚀 Start Analysis', help='Begin multi-agent fraud analysis for the selected alert'):
            st.session_state['analysis_started'] = True
            st.rerun()
        return

    # --- Only show below after analysis started ---
    # Persistent Restart button
    if st.button('🔄 Restart', key='restart-top', help='Restart the analysis and clear all progress'):
        for k in list(st.session_state.keys()):
            if k not in ['checkpoints', 'edit_mode', 'edit_value']:
                del st.session_state[k]
        st.rerun()

    context_store = ContextStore()
    supervisor = SupervisorAgent(context_store)

    st.markdown("---")
    st.subheader("Conversation", help='Dialogue between agents and user. User responses are editable.')
    chat_placeholder = st.container()
    with chat_placeholder:
        for idx, msg in enumerate(st.session_state.chat_history):
            if msg['role'] == 'agent':
                st.markdown(f"<div style='background:#001F3F;color:#fff;padding:10px;border-radius:8px;margin-bottom:4px;'><b>{msg['agent']}:</b> {msg['content']}</div>", unsafe_allow_html=True)
            else:
                col1, col2 = st.columns([10,1])
                with col1:
                    st.markdown(f"<div style='background:#2E003E;color:#fff;padding:10px;border-radius:8px;margin-bottom:8px;text-align:right;'><b>You:</b> {msg['content']}</div>", unsafe_allow_html=True)
                    # Show version history as numbered buttons below the message
                    versions = st.session_state['chat_versions'].get(idx, [])
                    if versions:
                        st.markdown('<div style="margin-bottom:4px;">', unsafe_allow_html=True)
                        btn_cols = st.columns(len(versions))
                        for vnum, v in enumerate(versions, 1):
                            if btn_cols[vnum-1].button(str(vnum), key=f'ver_btn_{idx}_{vnum}'):
                                st.session_state['show_version'][idx] = vnum
                        st.markdown('</div>', unsafe_allow_html=True)
                        # Show selected version inline
                        if idx in st.session_state['show_version']:
                            vnum = st.session_state['show_version'][idx]
                            if 1 <= vnum <= len(versions):
                                st.markdown(f"<div style='background:#444;color:#fff;padding:6px;border-radius:6px;margin-bottom:4px;'><b>Version {vnum}:</b> {versions[vnum-1]}</div>", unsafe_allow_html=True)
                            if st.button('Hide', key=f'hide_ver_{idx}'):
                                del st.session_state['show_version'][idx]
                with col2:
                    if st.session_state['edit_mode'] is None and st.button('✏️', key=f'edit_{idx}', help='Edit this response'):
                        st.session_state['edit_mode'] = idx
                        st.session_state['edit_value'] = msg['content']
                if st.session_state['edit_mode'] == idx:
                    new_val = st.text_area('Edit your response:', st.session_state['edit_value'], key=f'edit_input_{idx}', help='Modify your previous answer')
                    st.session_state['edit_value'] = new_val
                    checkpoint = st.session_state['checkpoints'].get(idx)
                    if checkpoint is None:
                        st.warning('No checkpoint available for this response. Edit is not possible.')
                    else:
                        if st.button('Save', key=f'save_{idx}', help='Save edited response and replay from here'):
                            # Save previous version before editing
                            if idx not in st.session_state['chat_versions']:
                                st.session_state['chat_versions'][idx] = []
                            st.session_state['chat_versions'][idx].append(st.session_state['chat_history'][idx]['content'])
                            for k, v in checkpoint.items():
                                st.session_state[k] = copy.deepcopy(v)
                            st.session_state['chat_history'][idx]['content'] = new_val
                            if st.session_state['context'] and 'dialogue_history' in st.session_state['context']:
                                # Map nth user message in chat_history to nth user message in dialogue_history
                                chat_user_indices = [i for i, m in enumerate(st.session_state['chat_history']) if m['role'] == 'user']
                                dialogue_user_indices = [i for i, m in enumerate(st.session_state['context']['dialogue_history']) if 'user' in m]
                                if idx in chat_user_indices:
                                    user_order = chat_user_indices.index(idx)
                                    if user_order < len(dialogue_user_indices):
                                        st.session_state['context']['dialogue_history'][dialogue_user_indices[user_order]]['user'] = new_val
                            st.session_state['edit_mode'] = None
                            st.session_state['edit_value'] = ''
                            st.session_state['step'] = 6  # Resume from DialogueAgent
                            st.session_state['awaiting_user'] = False
                            st.rerun()
                    if st.button('Cancel', key=f'cancel_{idx}', help='Cancel editing'):
                        st.session_state['edit_mode'] = None
                        st.session_state['edit_value'] = ''

    st.markdown("---")
    st.subheader("Agent Log", help='Chronological log of agent actions and steps')
    st.write(", ".join(st.session_state.agent_log))

    if st.session_state['error']:
        st.error(st.session_state['error'])
        if st.button('Restart', key='restart-error', help='Restart after error'):
            for k in list(st.session_state.keys()):
                if k not in ['checkpoints', 'edit_mode', 'edit_value']:
                    del st.session_state[k]
            st.rerun()
        return

    # Progress bar for agent steps
    steps = [
        'TransactionContextAgent',
        'CustomerInfoAgent',
        'MerchantInfoAgent',
        'BehavioralPatternAgent',
        'RiskSynthesizerAgent',
        'TriageAgent',
        'DialogueAgent',
        'RiskAssessorAgent',
        'PolicyDecisionAgent',
        'FeedbackCollectorAgent',
        'FinalReport',
    ]
    progress_value = min(st.session_state['step'] / (len(steps)-1), 1.0)
    st.progress(progress_value)

    # Main agentic system logic, step by step, with loading spinner
    try:
        if st.session_state['step'] == 6:
            if st.session_state['awaiting_user'] and 'dialogue_history' in st.session_state['context']:
                user_msg_idx = len([m for m in st.session_state['chat_history'] if m['role'] == 'user']) - 1
                st.session_state['checkpoints'][user_msg_idx] = {
                    k: copy.deepcopy(st.session_state[k]) for k in [
                        'chat_history', 'agent_log', 'final_report', 'awaiting_user', 'current_question', 'context', 'user_response', 'analysis_started', 'step', 'error'
                    ]
                }
        with st.spinner('Running agentic step...'):
            # ... existing code for agentic steps ...
            if st.session_state['step'] == 0:
                context = {'transaction': alert}
                context = supervisor.transaction_agent.act('Build transaction context', context)
                st.session_state.context = context
                st.session_state.chat_history.append({'role': 'agent', 'agent': 'TransactionContextAgent', 'content': str(context.get('transaction_context', ''))})
                st.session_state.agent_log.append('TransactionContextAgent')
                st.session_state['step'] += 1
                st.rerun()
            elif st.session_state['step'] == 1:
                context = st.session_state.context
                context = supervisor.customer_agent.act('Build customer context', context)
                st.session_state.context = context
                st.session_state.chat_history.append({'role': 'agent', 'agent': 'CustomerInfoAgent', 'content': str(context.get('customer_context', ''))})
                st.session_state.agent_log.append('CustomerInfoAgent')
                st.session_state['step'] += 1
                st.rerun()
            elif st.session_state['step'] == 2:
                context = st.session_state.context
                context = supervisor.merchant_agent.act('Build merchant context', context)
                st.session_state.context = context
                st.session_state.chat_history.append({'role': 'agent', 'agent': 'MerchantInfoAgent', 'content': str(context.get('merchant_context', ''))})
                st.session_state.agent_log.append('MerchantInfoAgent')
                st.session_state['step'] += 1
                st.rerun()
            elif st.session_state['step'] == 3:
                context = st.session_state.context
                context = supervisor.behavior_agent.act('Build anomaly context', context)
                st.session_state.context = context
                st.session_state.chat_history.append({'role': 'agent', 'agent': 'BehavioralPatternAgent', 'content': str(context.get('anomaly_context', ''))})
                st.session_state.agent_log.append('BehavioralPatternAgent')
                st.session_state['step'] += 1
                st.rerun()
            elif st.session_state['step'] == 4:
                context = st.session_state.context
                context = supervisor.risk_synth_agent.act('Synthesize risk', context)
                st.session_state.context = context
                st.session_state.chat_history.append({'role': 'agent', 'agent': 'RiskSynthesizerAgent', 'content': str(context.get('risk_summary_context', ''))})
                st.session_state.agent_log.append('RiskSynthesizerAgent')
                st.session_state['step'] += 1
                st.rerun()
            elif st.session_state['step'] == 5:
                context = st.session_state.context
                context = supervisor.triage_agent.act('Triage', context)
                st.session_state.context = context
                st.session_state.chat_history.append({'role': 'agent', 'agent': 'TriageAgent', 'content': str(context.get('triage_decision', ''))})
                st.session_state.agent_log.append('TriageAgent')
                st.session_state['step'] += 1
                st.rerun()
            elif st.session_state['step'] == 6:
                context = st.session_state.context
                if 'dialogue_history' not in context:
                    context['dialogue_history'] = []
                dialogue_agent = supervisor.dialogue_agent
                if not context['dialogue_history'] or ('user' in context['dialogue_history'][-1]):
                    next_q, agent_name, _ = dialogue_agent.get_next_question_and_agent(context['dialogue_history'], context)
                    if next_q:
                        context['dialogue_history'].append({'agent': agent_name, 'question': next_q, 'agent_log': agent_name})
                        st.session_state.chat_history.append({'role': 'agent', 'agent': agent_name, 'content': next_q})
                        st.session_state.agent_log.append(agent_name)
                        st.session_state.current_question = next_q
                        st.session_state.awaiting_user = True
                        st.session_state.context = context
                        st.rerun()
                if st.session_state.awaiting_user:
                    user_input = st.chat_input('Your response:')
                    if user_input:
                        context['dialogue_history'][-1]['user'] = user_input
                        st.session_state.chat_history.append({'role': 'user', 'agent': 'User', 'content': user_input})
                        # Create a checkpoint for this user message
                        user_msg_idx = len([m for m in st.session_state['chat_history'] if m['role'] == 'user']) - 1
                        st.session_state['checkpoints'][user_msg_idx] = {
                            k: copy.deepcopy(st.session_state[k]) for k in [
                                'chat_history', 'agent_log', 'final_report', 'awaiting_user', 'current_question', 'context', 'user_response', 'analysis_started', 'step', 'error'
                            ]
                        }
                        st.session_state.awaiting_user = False
                        st.session_state.context = context
                        st.rerun()
                    return
                context, done = dialogue_agent.act('Continue', context, user_response=context['dialogue_history'][-1].get('user'), max_turns=12)
                st.session_state.context = context
                if done:
                    st.session_state['step'] += 1
                    st.rerun()
                else:
                    st.rerun()
            elif st.session_state['step'] == 7:
                context = st.session_state.context
                context = supervisor.risk_assessor_agent.act('Assess risk', context)
                st.session_state.context = context
                st.session_state.chat_history.append({'role': 'agent', 'agent': 'RiskAssessorAgent', 'content': str(context.get('risk_assessment', ''))})
                st.session_state.agent_log.append('RiskAssessorAgent')
                st.session_state['step'] += 1
                st.rerun()
            elif st.session_state['step'] == 8:
                context = st.session_state.context
                context = supervisor.policy_agent.act('Policy decision', context)
                st.session_state.context = context
                st.session_state.chat_history.append({'role': 'agent', 'agent': 'PolicyDecisionAgent', 'content': str(context.get('policy_decision', ''))})
                st.session_state.agent_log.append('PolicyDecisionAgent')
                st.session_state['step'] += 1
                st.rerun()
            elif st.session_state['step'] == 9:
                context = st.session_state.context
                context = supervisor.feedback_agent.act('Collect feedback', context)
                st.session_state.context = context
                st.session_state.chat_history.append({'role': 'agent', 'agent': 'FeedbackCollectorAgent', 'content': str(context.get('feedback', ''))})
                st.session_state.agent_log.append('FeedbackCollectorAgent')
                st.session_state['step'] += 1
                st.rerun()
            elif st.session_state['step'] == 10:
                # --- Finalization logic: only finalize if all required questions are answered ---
                context = st.session_state.context
                missing_questions = []
                if context and 'dialogue_history' in context:
                    for turn in context['dialogue_history']:
                        if 'question' in turn and (('user' not in turn) or (not str(turn['user']).strip())):
                            missing_questions.append(turn['question'])
                if missing_questions:
                    st.warning('Cannot finalize: Please answer all required questions before generating the final report.')
                    st.markdown('<b>Missing answers for:</b>', unsafe_allow_html=True)
                    for q in missing_questions:
                        st.markdown(f'- {q}')
                    return
                st.info('Finalizing... Generating fraud analysis report.')
                report = supervisor._finalize_report(context)
                st.session_state.final_report = report
                st.session_state.chat_history.append({'role': 'agent', 'agent': 'SupervisorAgent', 'content': report})
                st.session_state.agent_log.append('SupervisorAgent')
                st.session_state['step'] += 1
                st.rerun()
            elif st.session_state['step'] == 11:
                st.success('Dialogue complete. Final report below:')
                st.markdown(f"<div style='background:#004D40;color:#fff;padding:12px;border-radius:10px;margin-top:12px;'><b>Final Fraud Analysis Report</b><br>{st.session_state.final_report}</div>", unsafe_allow_html=True)
                if st.button('Restart', key='restart-final', help='Restart after completion'):
                    for k in list(st.session_state.keys()):
                        if k not in ['checkpoints', 'edit_mode', 'edit_value']:
                            del st.session_state[k]
                    st.rerun()
    except Exception as e:
        st.session_state['error'] = f"Error: {e}"
        st.rerun()

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
    st.markdown('---')
    st.write('**SOP.md Preview:**')
    st.code(load_sop()[:1000])

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
page = st.sidebar.radio("Go to", ["Dashboard", "Alerts", "Agentic System", "Semantic Search", "Docs"])

if page == "Dashboard":
    dashboard_page()
elif page == "Alerts":
    alerts_page()
elif page == "Agentic System":
    agentic_system_page()
elif page == "Semantic Search":
    semantic_search_page()
elif page == "Docs":
    docs_page() 