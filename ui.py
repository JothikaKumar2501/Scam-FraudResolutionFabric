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
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

# Try to import vector search if available
try:
    from vector_utils import search_similar
    VECTOR_SEARCH = True
except ImportError:
    VECTOR_SEARCH = False

# Performance monitoring
import time
from functools import wraps

def performance_monitor(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"⏱️ UI {func.__name__} executed in {execution_time:.2f} seconds")
        return result
    return wrapper

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

@performance_monitor
def load_alerts():
    with open('datasets/FTP.json', encoding='utf-8') as f:
        return json.load(f)

@performance_monitor
def load_sop():
    with open('datasets/SOP.md', encoding='utf-8') as f:
        return f.read()

@performance_monitor
def load_questions():
    with open('datasets/questions.md', encoding='utf-8') as f:
        return f.read()

# --- Dynamic Question Selection ---
def get_dynamic_question(alert, dialogue_history, questions_md, sop_md):
    # Try to select a question based on ruleId, context, and previous questions
    # Handle both old and new field names
    rule_id = alert.get('rule_id') or alert.get('ruleId', '')
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
    alerts_data = load_alerts()
    
    # Handle new dataset structure with metadata
    if isinstance(alerts_data, dict) and 'alerts' in alerts_data:
        alerts = alerts_data['alerts']
        metadata = alerts_data.get('metadata', {})
    else:
        alerts = alerts_data
        metadata = {}
    
    # Risk score trend (dummy: count of alerts per day)
    import pandas as pd
    if alerts:
        df = pd.DataFrame(alerts)
        if 'alert_date' in df.columns:
            trend = df.groupby('alert_date').size().reset_index()
            trend.columns = ['alert_date', 'alerts']
            st.line_chart(trend.rename(columns={'alert_date': 'Date', 'alerts': 'Alerts'}).set_index('Date'))
        elif 'alertDate' in df.columns:
            trend = df.groupby('alertDate').size().reset_index()
            trend.columns = ['alertDate', 'alerts']
            st.line_chart(trend.rename(columns={'alertDate': 'Date', 'alerts': 'Alerts'}).set_index('Date'))
        
        st.subheader('Recent Alerts')
        # Handle both old and new column names
        cols = ['alert_id', 'customer_id', 'priority', 'status', 'description', 'alert_date', 'alert_time']
        if not all(col in df.columns for col in cols):
            # Try old column names
            cols = ['alertId', 'customerId', 'priority', 'status', 'description', 'alertDate', 'alertTime']
        
        if not df.empty and all(col in df.columns for col in cols):
            st.dataframe(df[cols])
        else:
            st.dataframe(df)
    else:
        st.warning("No alerts data available")
    
    # Show metadata if available
    if metadata:
        st.subheader('Dataset Information')
        st.json(metadata)

    # --- Flowchart Panel ---
    st.markdown("---")
    st.subheader("System Flowchart", help="Overview of the multi-agent fraud analysis system.")
    st.image("flowchart.png", caption="System Flowchart Image")
    st.image("payments_pic.png", caption="System Architecture Image")

def alerts_page():
    st.title('🔔 Alerts')
    alerts_data = load_alerts()
    
    # Handle new dataset structure with metadata
    if isinstance(alerts_data, dict) and 'alerts' in alerts_data:
        alerts = alerts_data['alerts']
        metadata = alerts_data.get('metadata', {})
    else:
        alerts = alerts_data
        metadata = {}
    
    if alerts:
        st.dataframe(alerts)
    else:
        st.warning("No alerts data available")
    
    # Show metadata if available
    if metadata:
        st.subheader('Dataset Information')
        st.json(metadata)

def create_skeleton_loading():
    """Create skeleton loading animation for better UX"""
    st.markdown("""
    <style>
    .skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: loading 1.5s infinite;
        border-radius: 4px;
        height: 20px;
        margin: 8px 0;
    }
    @keyframes loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create skeleton placeholders
    for i in range(5):
        st.markdown('<div class="skeleton"></div>', unsafe_allow_html=True)

def create_loading_animation():
    """Create a modern loading animation"""
    with st.spinner(""):
        cols = st.columns(4)
        for i, col in enumerate(cols):
            with col:
                st.markdown(f"<div style='text-align: center; padding: 10px; background: linear-gradient(45deg, #f0f2f6, #e0e6ed); border-radius: 8px;'>⏳</div>", unsafe_allow_html=True)
        time.sleep(0.1)

def show_agent_status(agent_name, status="running"):
    """Show real-time agent status with modern styling"""
    status_icons = {
        "running": "🔄",
        "completed": "✅",
        "error": "❌",
        "waiting": "⏳"
    }
    
    status_colors = {
        "running": "#0074D9",
        "completed": "#2ECC40",
        "error": "#FF4136",
        "waiting": "#FF851B"
    }
    
    icon = status_icons.get(status, "❓")
    color = status_colors.get(status, "#AAAAAA")
    
    st.markdown(f"""
    <div style='display: flex; align-items: center; padding: 8px 12px; background: {color}15; border-left: 4px solid {color}; border-radius: 4px; margin: 4px 0;'>
        <span style='font-size: 16px; margin-right: 8px;'>{icon}</span>
        <span style='font-weight: 500;'>{agent_name}</span>
        <span style='margin-left: auto; font-size: 12px; color: {color};'>{status.upper()}</span>
    </div>
    """, unsafe_allow_html=True)

def show_performance_metrics():
    """Show real-time performance metrics"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Performance Metrics")
    
    # Cache stats
    try:
        from context_store import context_store
        cache_stats = context_store.get_cache_stats()
        st.sidebar.metric("Cache Hit Rate", cache_stats['hit_rate'])
        st.sidebar.metric("Cache Size", f"{cache_stats['memory_cache_size']}/{cache_stats['max_cache_size']}")
    except:
        pass
    
    # Memory usage (if available)
    try:
        import psutil
        memory = psutil.virtual_memory()
        st.sidebar.metric("Memory Usage", f"{memory.percent}%")
    except:
        pass

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
        # Track generator and current state
        streaming_generator=None,
        current_state=None,
        # Performance tracking
        start_time=None,
        agent_timings={},
        # Real-time updates
        last_update_time=0,
        update_interval=0.5,  # Update every 500ms
        # UI state
        show_skeleton=False,
        ui_optimized=True
    )
    for k, v in session_defaults.items():
        if k not in st.session_state:
            st.session_state[k] = copy.deepcopy(v)
    
    alerts_data = load_alerts()
    questions_md = load_questions()
    sop_md = load_sop()
    
    # Handle new dataset structure with metadata
    if isinstance(alerts_data, dict) and 'alerts' in alerts_data:
        alerts = alerts_data['alerts']
    else:
        alerts = alerts_data
    
    # Handle both old and new field names
    alert_options = []
    for a in alerts:
        alert_id = a.get('alert_id') or a.get('alertId', 'Unknown')
        description = a.get('description', 'No description')
        alert_options.append(f"{alert_id}: {description}")
    
    selected_idx = st.selectbox('Select an alert to analyze:', list(range(len(alert_options))), format_func=lambda i: alert_options[i] if alert_options else '', key='alert_select')
    selected_alert = alerts[selected_idx] if alerts else None
    
    if not st.session_state.analysis_running and not st.session_state.analysis_complete:
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button('🚀 Start Analysis', key='start_analysis_btn', disabled=selected_alert is None, use_container_width=True):
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
                st.session_state.streaming_generator = None
                st.session_state.current_state = None
                st.session_state.start_time = time.time()
                st.session_state.agent_timings = {}
                st.session_state.show_skeleton = True
                # Initialize state for backend
                st.session_state.backend_state = {'transaction': selected_alert, 'logs': [], 'agent_responses': [], 'dialogue_history': []}
                st.rerun()
        
        with col2:
            if st.button('⚙️ Performance Settings', key='settings_btn'):
                st.session_state.ui_optimized = not st.session_state.ui_optimized
                st.rerun()
        
        # Show performance settings
        if st.session_state.ui_optimized:
            st.info("🚀 **Performance Mode**: Optimized for speed with parallel processing and caching enabled.")
        else:
            st.warning("🐌 **Standard Mode**: Sequential processing for debugging.")
        
        return
    
    if st.session_state.analysis_running:
        # Use backend_state for all backend calls
        if st.session_state.backend_state is None:
            st.session_state.backend_state = {'transaction': selected_alert, 'logs': [], 'agent_responses': [], 'dialogue_history': []}
        backend_state = st.session_state.backend_state
        
        # Performance monitoring
        current_time = time.time()
        if st.session_state.start_time:
            elapsed_time = current_time - st.session_state.start_time
            st.sidebar.metric("⏱️ Total Time", f"{elapsed_time:.1f}s")
        
        # Show performance metrics
        show_performance_metrics()
        
        # Create containers for real-time updates
        progress_container = st.container()
        status_container = st.container()
        
        with progress_container:
            # Enhanced progress bar with real-time updates
            progress_bar = st.progress(0)
            progress_text = st.empty()
            
            # Real-time status display
            with status_container:
                status_placeholder = st.empty()
                agent_status_container = st.container()
        
        # Create containers for each section that will update in real-time
        context_container = st.container()
        risk_container = st.container()
        triage_container = st.container()
        chat_container = st.container()
        final_risk_container = st.container()
        policy_container = st.container()
        
        # Show skeleton loading initially
        if st.session_state.show_skeleton and not st.session_state.agent_logs:
            with st.container():
                st.subheader("🔄 Initializing Analysis...")
                create_skeleton_loading()
        
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
            
            # Hide skeleton once we have data
            if logs:
                st.session_state.show_skeleton = False
            
            # Update progress with real-time feedback
            current_step = state.get('current_step', 0)
            total_steps = state.get('total_steps', 9)
            progress = current_step / total_steps if total_steps > 0 else 0
            progress_bar.progress(progress)
            progress_text.text(f"🚀 Analysis Progress: Step {current_step} / {total_steps} ({progress*100:.1f}%)")
            
            # Show real-time agent status
            with agent_status_container:
                st.subheader("🤖 Agent Status")
                for i, log in enumerate(logs):
                    if i < len(st.session_state.agent_logs):
                        # Already displayed agent
                        show_agent_status(log, "completed")
                    else:
                        # New agent just completed
                        show_agent_status(log, "completed")
                        st.session_state.agent_timings[log] = time.time() - st.session_state.start_time
                
                # Show currently running agent
                if current_step < total_steps and logs:
                    current_agent = logs[-1] if logs else "Initializing..."
                    show_agent_status(current_agent, "running")
            
            # Show the latest agent response right below progress (non-streaming)
            if responses:
                latest_response = responses[-1]
                if not isinstance(latest_response, str):
                    if hasattr(latest_response, '__iter__') and not isinstance(latest_response, str):
                        latest_response = ''.join(list(latest_response))
                    else:
                        latest_response = str(latest_response)
                
                with status_placeholder:
                    st.markdown("### 📝 Latest Agent Response")
                    st.info(latest_response)
            
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
            elif current_step >= 9:
                # Analysis complete
                st.session_state.analysis_running = False
                st.session_state.analysis_complete = True
                st.session_state.agent_timings['Total'] = time.time() - st.session_state.start_time
            else:
                # Advance to next state - only if generator is not already executing
                if not hasattr(st.session_state, 'generator_executing') or not st.session_state.generator_executing:
                    st.session_state.generator_executing = True
                    try:
                        st.session_state.current_state = next(st.session_state.streaming_generator)
                    except StopIteration:
                        st.session_state.analysis_running = False
                        st.session_state.analysis_complete = True
                    except Exception as e:
                        st.error(f"Generator error: {e}")
                        st.session_state.analysis_running = False
                    finally:
                        st.session_state.generator_executing = False
                    st.rerun()

        except StopIteration:
            # Generator exhausted
            st.session_state.analysis_running = False
            st.session_state.analysis_complete = True
        except Exception as e:
            # Handle any other generator errors
            st.error(f"Analysis error: {e}")
            st.session_state.analysis_running = False
        
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
                    if not text:
                        return ""
                    
                    # Clean multiple question marks
                    text = text.replace('??', '?').replace('???', '?')
                    
                    # Split by lines and clean
                    lines = text.split('\n')
                    seen = set()
                    cleaned = []
                    for line in lines:
                        l = line.strip()
                        if l and l not in seen:
                            cleaned.append(l)
                            seen.add(l)
                    
                    result = '\n'.join(cleaned)
                    
                    # Ensure only one question per response
                    if result.count('?') > 1:
                        # Take only the first complete question
                        parts = result.split('?')
                        if len(parts) > 1:
                            result = parts[0] + '?'
                    
                    return result
                
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
    
    if st.session_state.analysis_complete:
        st.success('✅ Analysis complete!')
        
        # Show performance summary
        if st.session_state.agent_timings:
            st.subheader("📊 Performance Summary")
            timing_df = pd.DataFrame([
                {"Agent": agent, "Time (s)": timing} 
                for agent, timing in st.session_state.agent_timings.items()
            ])
            st.dataframe(timing_df, use_container_width=True)
        
        st.button('🔄 Restart', on_click=lambda: st.session_state.clear(), key='restart_btn_final')

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
        alerts_data = load_alerts()
        # Handle new dataset structure with metadata
        if isinstance(alerts_data, dict) and 'alerts' in alerts_data:
            alerts = alerts_data['alerts']
        else:
            alerts = alerts_data
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