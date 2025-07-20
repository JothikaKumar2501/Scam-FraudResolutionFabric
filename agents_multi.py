import json
import os
from agent_base import Agent
from context_store import ContextStore
from aws_bedrock import converse_with_claude_stream
import re
import concurrent.futures
from vector_utils import search_similar

DATASET_DIR = os.path.join(os.path.dirname(__file__), 'datasets')

def load_json(filename):
    with open(os.path.join(DATASET_DIR, filename), encoding='utf-8') as f:
        return json.load(f)

# --- Agent Stubs ---
class TransactionContextAgent(Agent):
    def act(self, message, context):
        prompt = (
            "You are a transaction context builder. Given the following alert, extract and summarize all relevant transaction details for fraud analysis. "
            f"Alert: {context.get('transaction', {})}"
        )
        result = converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=2048)
        context['transaction_context'] = result
        return context

class CustomerInfoAgent(Agent):
    def act(self, message, context):
        prompt = (
            "You are a customer info agent. Given the following alert and any available context, extract and summarize all relevant customer information for fraud analysis. "
            f"Alert: {context.get('transaction', {})}"
        )
        result = converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=2048)
        context['customer_context'] = result
        return context

class MerchantInfoAgent(Agent):
    def act(self, message, context):
        prompt = (
            "You are a merchant info agent. Given the following alert and any available context, extract and summarize all relevant merchant information for fraud analysis. "
            f"Alert: {context.get('transaction', {})}"
        )
        result = converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=2048)
        context['merchant_context'] = result
        return context

class BehavioralPatternAgent(Agent):
    def act(self, message, context):
        prompt = (
            "You are a behavioral pattern agent. Given the following alert and any available context, extract and summarize any behavioral anomalies or patterns for fraud analysis. "
            f"Alert: {context.get('transaction', {})}"
        )
        result = converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=2048)
        context['anomaly_context'] = result
        return context

class RiskSynthesizerAgent(Agent):
    def act(self, message, context):
        prompt = (
            "You are a risk synthesizer agent. Given the following context, synthesize a risk summary for the transaction. "
            f"Transaction: {context.get('transaction_context', {})}\n"
            f"Customer: {context.get('customer_context', {})}\n"
            f"Merchant: {context.get('merchant_context', {})}\n"
            f"Anomaly: {context.get('anomaly_context', {})}"
        )
        result = converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=2048)
        context['risk_summary_context'] = result
        return context

class PolicyDecisionAgent(Agent):
    def act(self, message, context):
        prompt = (
            "You are a policy decision agent. Given the following context, make a policy decision (Approve, Decline, Escalate) and explain your reasoning. "
            f"Transaction: {context.get('transaction_context', {})}\n"
            f"Customer: {context.get('customer_context', {})}\n"
            f"Merchant: {context.get('merchant_context', {})}\n"
            f"Anomaly: {context.get('anomaly_context', {})}\n"
            f"Risk: {context.get('risk_summary_context', {})}\n"
            f"Dialogue: {context.get('dialogue_history', [])}"
        )
        result = converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=2048)
        context['policy_decision'] = result
        return context

class RiskAssessorAgent(Agent):
    def act(self, message, context):
        prompt = (
            "You are a risk assessor agent. Given the following context, assess the risk score (0-100) and explain your reasoning. "
            f"Transaction: {context.get('transaction_context', {})}\n"
            f"Customer: {context.get('customer_context', {})}\n"
            f"Merchant: {context.get('merchant_context', {})}\n"
            f"Anomaly: {context.get('anomaly_context', {})}\n"
            f"Risk: {context.get('risk_summary_context', {})}\n"
            f"Dialogue: {context.get('dialogue_history', [])}"
        )
        result = converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=2048)
        context['risk_assessment'] = result
        return context

class FeedbackCollectorAgent(Agent):
    def act(self, message, context):
        prompt = (
            "You are a feedback collector agent. Given the following context, collect feedback from the analyst or user. "
            f"Transaction: {context.get('transaction_context', {})}\n"
            f"Customer: {context.get('customer_context', {})}\n"
            f"Merchant: {context.get('merchant_context', {})}\n"
            f"Anomaly: {context.get('anomaly_context', {})}\n"
            f"Risk: {context.get('risk_summary_context', {})}\n"
            f"Dialogue: {context.get('dialogue_history', [])}"
        )
        result = converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=2048)
        context['feedback'] = result
        return context

class TriageAgent(Agent):
    def act(self, message, context):
        prompt = (
            "You are a triage agent. Given the following context, determine if this alert requires escalation to a human analyst or can be resolved automatically. "
            f"Transaction: {context.get('transaction_context', {})}\n"
            f"Customer: {context.get('customer_context', {})}\n"
            f"Merchant: {context.get('merchant_context', {})}\n"
            f"Anomaly: {context.get('anomaly_context', {})}\n"
            f"Risk: {context.get('risk_summary_context', {})}"
        )
        result = converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=2048)
        context['triage_decision'] = result
        return context

# Helper for RAG over SOP.md and questions.md
def rag_retrieve_questions(context, query=None):
    # Dynamic RAG: use vector search if query provided
    if query:
        hits = search_similar(query, top_k=3)
        return [hit['text'] if isinstance(hit, dict) and 'text' in hit else str(hit) for hit in hits]
    # Fallback: simple keyword search over questions.md
    questions = []
    try:
        with open('datasets/questions.md', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('*'):
                    questions.append(line.strip('- *"'))
    except Exception:
        pass
    return questions

def rag_retrieve_sop(context, query=None):
    # Dynamic RAG: use vector search if query provided
    if query:
        hits = search_similar(query, top_k=3)
        return [hit['text'] if isinstance(hit, dict) and 'text' in hit else str(hit) for hit in hits]
    # Fallback: simple keyword search over SOP.md
    sops = []
    try:
        with open('datasets/SOP.md', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    sops.append(line.strip())
    except Exception:
        pass
    return sops

# --- DialogueAgent ---
class DialogueAgent(Agent):
    def extract_facts(self, dialogue_history):
        # Extract facts from user answers
        facts = {}
        for turn in dialogue_history:
            if 'question' in turn and 'user' in turn:
                q = turn['question'].lower()
                a = turn['user'].lower()
                if any(x in q for x in ['name', 'date of birth', 'dob']):
                    facts['verified'] = True
                if any(x in q for x in ['recipient', 'payee', 'friend', 'entity']):
                    facts['recipient'] = a
                if any(x in q for x in ['authorize', 'authorized', 'permission']):
                    facts['authorization'] = a
                if any(x in q for x in ['device', 'login', 'biometric']):
                    facts['device'] = a
                if any(x in q for x in ['purpose', 'reason', 'investment', 'plan']):
                    facts['purpose'] = a
                if any(x in q for x in ['relationship', 'known', 'new', 'trusted']):
                    facts['relationship'] = a
                if any(x in q for x in ['amount', 'value', 'sum', 'transfer']):
                    facts['amount'] = a
                if any(x in q for x in ['pattern', 'usual', 'consistent', 'behaviour']):
                    facts['pattern'] = a
        return facts

    def summarize_known_facts(self, facts):
        if not facts:
            return 'No facts confirmed yet.'
        return '\n'.join(f"{k.capitalize()}: {v}" for k, v in facts.items())

    def summarize_missing_facts(self, facts):
        needed = ['recipient', 'authorization', 'device', 'purpose', 'relationship', 'amount', 'pattern']
        missing = [k for k in needed if k not in facts]
        if 'verified' not in facts:
            return ['verified'] + missing
        return missing

    def get_next_question_and_agent(self, dialogue_history, context):
        # Use dynamic RAG for SOPs based on current context
        facts = self.extract_facts(dialogue_history)
        missing = self.summarize_missing_facts(facts)
        # Use the last user answer or the transaction as the query for RAG
        last_user = ''
        if dialogue_history and 'user' in dialogue_history[-1]:
            last_user = dialogue_history[-1]['user']
        rag_query = last_user or str(context.get('transaction', {}))
        sops = rag_retrieve_sop(context, query=rag_query)
        prompt = (
            "You are a senior fraud analyst. Your job is to determine if a transaction is fraudulent by asking the minimum number of targeted, non-repetitive questions.\n"
            f"Verification status: {'verified' if 'verified' in facts else 'not verified'}\n"
            "Known facts:\n" + self.summarize_known_facts(facts) + "\n"
            "Missing facts:\n" + (', '.join(missing) if missing else 'None. All key facts appear to be covered.') + "\n"
            "If not verified, ask for identity verification (name and DOB) and do not ask again.\n"
            "If verified, ask only the most relevant next question to resolve the fraud risk.\n"
            "When enough is known, say FINALIZE and explain your decision (Fraud/Not Fraud/Needs Escalation).\n"
            "Relevant transaction context:\n" + str(context.get('transaction', {})) + "\n"
            "Relevant SOP guidance (dynamically retrieved):\n" + '\n'.join(sops) + "\n"
            "Conversation so far:\n" + '\n'.join([f"Q: {turn['question']}\nA: {turn.get('user', '')}" for turn in dialogue_history if 'question' in turn])
        )
        llm_output = converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=2048)
        # If LLM says FINALIZE, treat as end of dialogue
        if llm_output and 'finalize' in llm_output.lower():
            agent_name = self.name
            print(f"[Agent Log] {agent_name} involved in prompt: FINALIZE")
            return llm_output, agent_name, True
        # Otherwise, use LLM output as next question
        agent_name = self.name
        print(f"[Agent Log] {agent_name} involved in prompt: {llm_output}")
        return llm_output, agent_name, False

    def act(self, message, context, user_response=None, max_turns=12):
        dialogue_history = context.get('dialogue_history', [])
        if user_response is not None:
            dialogue_history[-1]['user'] = user_response
        # Let LLM generate next question or finalization
        next_q, agent_name, done = self.get_next_question_and_agent(dialogue_history, context)
        if not done and len(dialogue_history) < max_turns:
            dialogue_history.append({'agent': agent_name, 'question': next_q, 'agent_log': agent_name})
        context['dialogue_history'] = dialogue_history
        context['dialogue_analysis'] = next_q
        return context, done

    def extract_next_question_from_analysis(self, analysis):
        # Try to extract a question from the LLM's analysis output
        # Look for lines ending with a question mark, or after 'Next question:'
        match = re.search(r'Next question[:\-]?\s*(.*\?)', analysis, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Fallback: find the last question in the text
        questions = re.findall(r'([^\n\r]*\?)', analysis)
        if questions:
            return questions[-1].strip()
        return None

    def _build_question_prompt(self, dialogue_history, context):
        base = "You are a fraud analyst. Given the following conversation and context, ask the next best question to verify if the transaction is fraudulent."
        history = "\n".join([f"Q: {turn['question']}\nA: {turn.get('user', '')}" for turn in dialogue_history])
        txn_info = str(context.get('transaction', {}))
        sops = rag_retrieve_sop(context)
        return f"{base}\nTransaction: {txn_info}\nRelevant SOPs: {sops[:3]}\nConversation so far:\n{history}\nNext question:"

    def _build_analysis_prompt(self, dialogue_history, context):
        base = "Given the following conversation, do you have enough information to make a fraud decision? If yes, say 'Finalize'. If not, say what else to ask."
        history = "\n".join([f"Q: {turn['question']}\nA: {turn.get('user', '')}" for turn in dialogue_history])
        return f"{base}\nConversation:\n{history}"

# --- SupervisorAgent ---
class SupervisorAgent(Agent):
    def __init__(self, context_store):
        super().__init__('SupervisorAgent', context_store)
        self.transaction_agent = TransactionContextAgent('TransactionContextAgent', context_store)
        self.customer_agent = CustomerInfoAgent('CustomerInfoAgent', context_store)
        self.merchant_agent = MerchantInfoAgent('MerchantInfoAgent', context_store)
        self.behavior_agent = BehavioralPatternAgent('BehavioralPatternAgent', context_store)
        self.risk_synth_agent = RiskSynthesizerAgent('RiskSynthesizerAgent', context_store)
        self.triage_agent = TriageAgent('TriageAgent', context_store)
        self.policy_agent = PolicyDecisionAgent('PolicyDecisionAgent', context_store)
        self.dialogue_agent = DialogueAgent('DialogueAgent', context_store)
        self.risk_assessor_agent = RiskAssessorAgent('RiskAssessorAgent', context_store)
        self.feedback_agent = FeedbackCollectorAgent('FeedbackCollectorAgent', context_store)

    def run_fraud_detection(self, alert, user_io=None, stream_callback=None):
        context = {'transaction': alert}
        agent_log = []
        # 1. Build context with all context-building agents in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                'transaction': executor.submit(self.transaction_agent.act, 'Build transaction context', context.copy()),
                'customer': executor.submit(self.customer_agent.act, 'Build customer context', context.copy()),
                'merchant': executor.submit(self.merchant_agent.act, 'Build merchant context', context.copy()),
                'behavior': executor.submit(self.behavior_agent.act, 'Build anomaly context', context.copy()),
            }
            for key, future in futures.items():
                result = future.result()
                context.update(result)
                agent_log.append(key)
                if stream_callback:
                    stream_callback(f"{key.title()}ContextAgent", result)
        context = self.risk_synth_agent.act('Synthesize risk', context)
        agent_log.append('RiskSynthesizerAgent')
        if stream_callback:
            stream_callback('RiskSynthesizerAgent', context)
        # 2. Triage agent
        context = self.triage_agent.act('Triage', context)
        agent_log.append('TriageAgent')
        if stream_callback:
            stream_callback('TriageAgent', context)
        # 3. Dialogue agent (if escalation needed or always for now)
        if user_io:
            done = False
            while not done:
                if not context.get('dialogue_history') or (
                    context['dialogue_history'] and 'user' in context['dialogue_history'][-1]
                ):
                    next_q, agent_name, _ = self.dialogue_agent.get_next_question_and_agent(
                        context.get('dialogue_history', []), context)
                    if next_q:
                        context.setdefault('dialogue_history', []).append({'agent': agent_name, 'question': next_q, 'agent_log': agent_name})
                        agent_log.append(agent_name)
                        if stream_callback:
                            stream_callback(agent_name, {'question': next_q})
                user_response = user_io(context['dialogue_history'][-1]['question'])
                context, done = self.dialogue_agent.act('Continue', context, user_response=user_response)
                agent_log.append('DialogueAgent')
                if stream_callback:
                    stream_callback('DialogueAgent', context)
        # 4. Risk assessment and policy decision
        context = self.risk_assessor_agent.act('Assess risk', context)
        agent_log.append('RiskAssessorAgent')
        if stream_callback:
            stream_callback('RiskAssessorAgent', context)
        context = self.policy_agent.act('Policy decision', context)
        agent_log.append('PolicyDecisionAgent')
        if stream_callback:
            stream_callback('PolicyDecisionAgent', context)
        context = self.feedback_agent.act('Collect feedback', context)
        agent_log.append('FeedbackCollectorAgent')
        if stream_callback:
            stream_callback('FeedbackCollectorAgent', context)
        # 5. Final report
        report = self._finalize_report(context)
        if stream_callback:
            stream_callback('SupervisorAgent', {'final_report': report})
        return report, agent_log

    def _finalize_report(self, context):
        # Use Claude to synthesize a final report
        prompt = "You are a fraud analyst. Given the following conversation and context, summarize if the transaction is fraudulent or not, and explain why."
        history = "\n".join([f"Q: {turn['question']}\nA: {turn.get('user', '')}" for turn in context.get('dialogue_history', [])])
        txn_info = str(context.get('transaction', {}))
        full_prompt = f"{prompt}\nTransaction: {txn_info}\nConversation:\n{history}\nReport:"
        report = converse_with_claude_stream([
            {"role": "user", "content": [{"text": full_prompt}]}
        ], max_tokens=2048)
        return report 