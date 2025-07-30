import json
import os
from agent_base import Agent
from context_store import ContextStore
from aws_bedrock import converse_with_claude_stream
import re
import concurrent.futures
from vector_utils import search_similar
import yaml
import types

DATASET_DIR = os.path.join(os.path.dirname(__file__), 'datasets')

def load_json(filename):
    with open(os.path.join(DATASET_DIR, filename), encoding='utf-8') as f:
        return json.load(f)

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

def load_fraud_yaml_blocks(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    blocks = content.split('---')
    parsed = []
    for block in blocks:
        block = block.strip()
        if block:
            try:
                loaded = yaml.safe_load(block)
                if isinstance(loaded, dict):  # Only keep dicts
                    parsed.append(loaded)
            except Exception:
                continue
    return parsed

# --- Advanced, expert, and domain-specific agent prompts below ---

class TransactionContextAgent(Agent):
    def __init__(self, name, context_store):
        super().__init__(name, context_store)

    def act(self, message, context):
        sops = rag_retrieve_sop(context, query=str(context.get('transaction', {})))
        alert = context.get('transaction', {})
        txn_id = alert.get('alertId') or alert.get('transactionId')
        customer_id = alert.get('customerId')
        txn_details = None
        try:
            ftp = load_json('FTP.json')
            txn_details = next((t for t in ftp if t.get('alertId') == txn_id), None)
        except Exception:
            pass
        if not txn_details:
            try:
                txns = load_json('Customer_Transaction_History.json')
                txn_details = next((t for t in txns if t.get('alertId') == txn_id or t.get('customerId') == customer_id), None)
            except Exception:
                pass
        txn_details = txn_details or '[unavailable]'
        prompt = (
            "You are a senior ANZ transaction context expert specializing in advanced fraud typologies for ANZ Bank. "
            "Given the alert below, extract and summarize all relevant transaction details for fraud analysis, "
            "including rare typologies, cross-referencing with historical anomalies, and flagging unusual transaction patterns.\n"
            f"Alert: {alert}\n"
            f"Transaction Details: {txn_details}\n"
            f"Relevant SOPs: {sops}\n"
            "Highlight any regulatory or compliance triggers."
        )
        result = "".join([token for token in converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ])])
        context['transaction_context'] = result
        return context

class CustomerInfoAgent(Agent):
    def __init__(self, name, context_store):
        super().__init__(name, context_store)

    def act(self, message, context):
        sops = rag_retrieve_sop(context, query=str(context.get('transaction', {})))
        alert = context.get('transaction', {})
        customer_id = alert.get('customerId')
        customer_details = None
        try:
            data = load_json('customer_demographic.json')
            customers = data['customers'] if isinstance(data, dict) and 'customers' in data else data
            customer_details = next((c for c in customers if c.get('customer_id') == customer_id), None)
        except Exception:
            pass
        customer_details = customer_details or '[unavailable]'
        prompt = (
            "You are a customer intelligence agent with expertise in behavioral biometrics and scam victim profiling. "
            "Extract and summarize all relevant customer information, including device fingerprinting, behavioral anomalies, and cross-checks with known scam victim profiles.\n"
            f"Customer Details: {customer_details}\n"
            f"Relevant SOPs: {sops}\n"
            "Highlight any risk factors or compliance issues."
        )
        result = "".join([token for token in converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ])])
        context['customer_context'] = result
        return context

class MerchantInfoAgent(Agent):
    def __init__(self, name, context_store):
        super().__init__(name, context_store)

    def act(self, message, context):
        sops = rag_retrieve_sop(context, query=str(context.get('transaction', {})))
        alert = context.get('transaction', {})
        merchant_id = alert.get('merchantId') or alert.get('payee')
        merchant_details = None
        try:
            ftp = load_json('FTP.json')
            merchant_details = next((m for m in ftp if m.get('merchantId') == merchant_id or m.get('payee') == merchant_id), None)
        except Exception:
            pass
        merchant_details = merchant_details or '[unavailable]'
        prompt = (
            "You are a merchant risk expert. Analyze the alert and context to extract merchant risk scores, check for blacklist/whitelist status, "
            "and detect industry-specific anomalies.\n"
            f"Merchant Details: {merchant_details}\n"
            f"Relevant SOPs: {sops}\n"
            "Highlight any compliance or regulatory red flags."
        )
        result = "".join([token for token in converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ])])
        context['merchant_context'] = result
        return context

class BehavioralPatternAgent(Agent):
    def __init__(self, name, context_store):
        super().__init__(name, context_store)

    def act(self, message, context):
        sops = rag_retrieve_sop(context, query=str(context.get('transaction', {})))
        alert = context.get('transaction', {})
        customer_id = alert.get('customerId')
        alert_id = alert.get('alertId')
        anomaly_details = None
        try:
            calls = load_json('Enhanced_Customer_Call_History.json')
            anomaly_details = next((a for a in calls if a.get('customerID') == customer_id and a.get('alertID') == alert_id), None)
            if not anomaly_details:
                anomaly_details = next((a for a in calls if a.get('customerID') == customer_id), None)
        except Exception:
            pass
        anomaly_details = anomaly_details or '[unavailable]'
        prompt = (
            "You are a behavioral pattern analyst specializing in time-series analysis and social engineering detection. "
            "Extract and summarize behavioral anomalies, device/IP switching, and social engineering patterns.\n"
            f"Anomaly Details: {anomaly_details}\n"
            f"Relevant SOPs: {sops}\n"
            "Highlight any escalation triggers or compliance issues."
        )
        result = "".join([token for token in converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ])])
        context['anomaly_context'] = result
        return context

class RiskSynthesizerAgent(Agent):
    def __init__(self, name, context_store):
        super().__init__(name, context_store)

    def act(self, message, context):
        # Use the context as memory, but synthesize a new risk assessment
        sops = rag_retrieve_sop(context, query=str(context.get('transaction', {})))
        txn = context.get('transaction_context', '[unavailable]')
        cust = context.get('customer_context', '[unavailable]')
        merch = context.get('merchant_context', '[unavailable]')
        anom = context.get('anomaly_context', '[unavailable]')
        # Synthesize risk assessment prompt
        prompt = (
            "You are a risk synthesizer agent. Given the following context summaries from specialized agents, synthesize a comprehensive risk assessment. "
            "Do NOT repeat the summaries verbatim. Instead, analyze the context, identify key risk factors, typologies, compliance triggers, and provide a clear risk rating and recommended actions.\n"
            f"Transaction Context: {txn}\n"
            f"Customer Context: {cust}\n"
            f"Merchant Context: {merch}\n"
            f"Behavioral/Anomaly Context: {anom}\n"
            f"Relevant SOPs: {sops}\n"
            "Output a concise, expert risk synthesis for fraud operations and compliance."
        )
        result = "".join([token for token in converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ])])
        context['risk_summary_context'] = result
        return context

class TriageAgent(Agent):
    def __init__(self, name, context_store):
        super().__init__(name, context_store)

    def act(self, message, context):
        # Use the context as memory, but decide escalation/dialogue need
        sops = rag_retrieve_sop(context, query=str(context.get('transaction', {})))
        txn = context.get('transaction_context', '[unavailable]')
        cust = context.get('customer_context', '[unavailable]')
        merch = context.get('merchant_context', '[unavailable]')
        anom = context.get('anomaly_context', '[unavailable]')
        risk = context.get('risk_summary_context', '[unavailable]')
        prompt = (
            "You are a triage agent. Given the following context summaries and risk synthesis, decide if escalation or dialogue is needed. "
            "Do NOT repeat the summaries verbatim. Instead, analyze the context, cite relevant SOP rules, and provide a clear triage decision (escalate, dialogue, or close) with justification.\n"
            f"Transaction Context: {txn}\n"
            f"Customer Context: {cust}\n"
            f"Merchant Context: {merch}\n"
            f"Behavioral/Anomaly Context: {anom}\n"
            f"Risk Synthesis: {risk}\n"
            f"Relevant SOPs: {sops}\n"
            "Output a concise, expert triage decision for fraud operations."
        )
        result = "".join([token for token in converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ])])
        context['triage_decision'] = result
        return context

class DialogueAgent(Agent):
    def __init__(self, name, context_store):
        super().__init__(name, context_store)
        self.fraud_questions = load_fraud_yaml_blocks('datasets/questions.md')
        self.fraud_sop = load_fraud_yaml_blocks('datasets/SOP.md')

    def get_fraud_block(self, rule_id):
        for block in self.fraud_questions:
            if block and block.get('fraud_type', '').lower() == rule_id.lower():
                return block
        return None

    def get_sop_block(self, rule_id):
        for block in self.fraud_sop:
            if block and block.get('fraud_type', '').lower() == rule_id.lower():
                return block
        return None

    def extract_facts(self, dialogue_history, context=None):
        if context is None or not isinstance(context, dict):
            context = {}
        # Extract facts from user answers and context
        facts = {}
        # 1. From dialogue
        for turn in dialogue_history:
            if 'question' in turn and 'user' in turn:
                q = turn['question'].lower()
                a = turn['user'].lower()
                if any(x in q for x in ['name', 'date of birth', 'dob']) or any(x in a for x in ['name', 'date of birth', 'dob']):
                    facts['verified'] = True
                if any(x in q for x in ['recipient', 'payee', 'friend', 'entity']) or any(x in a for x in ['recipient', 'payee', 'friend', 'entity']):
                    facts['recipient'] = a
                if any(x in q for x in ['authorize', 'authorized', 'permission']) or any(x in a for x in ['authorize', 'authorized', 'permission', 'otp', 'code']):
                    facts['authorization'] = a
                if any(x in q for x in ['device', 'login', 'biometric']) or any(x in a for x in ['device', 'login', 'biometric']):
                    facts['device'] = a
                if any(x in q for x in ['purpose', 'reason', 'investment', 'plan']) or any(x in a for x in ['purpose', 'reason', 'investment', 'plan']):
                    facts['purpose'] = a
                if any(x in q for x in ['relationship', 'known', 'new', 'trusted']) or any(x in a for x in ['relationship', 'known', 'new', 'trusted']):
                    facts['relationship'] = a
                if any(x in q for x in ['amount', 'value', 'sum', 'transfer']) or any(x in a for x in ['amount', 'value', 'sum', 'transfer']):
                    facts['amount'] = a
                if any(x in q for x in ['pattern', 'usual', 'consistent', 'behaviour']) or any(x in a for x in ['pattern', 'usual', 'consistent', 'behaviour']):
                    facts['pattern'] = a
        # 2. From context (other agent outputs)
        for k in ['transaction_context', 'customer_context', 'merchant_context', 'anomaly_context', 'risk_summary_context']:
            v = context.get(k, '')
            vlow = str(v).lower()
            if 'name' in vlow or 'date of birth' in vlow or 'dob' in vlow:
                facts['verified'] = True
            if 'recipient' in vlow or 'payee' in vlow or 'entity' in vlow:
                facts['recipient'] = vlow
            if 'authorize' in vlow or 'authorized' in vlow or 'otp' in vlow or 'code' in vlow:
                facts['authorization'] = vlow
            if 'device' in vlow or 'login' in vlow or 'biometric' in vlow:
                facts['device'] = vlow
            if 'purpose' in vlow or 'reason' in vlow or 'investment' in vlow or 'plan' in vlow:
                facts['purpose'] = vlow
            if 'relationship' in vlow or 'known' in vlow or 'trusted' in vlow:
                facts['relationship'] = vlow
            if 'amount' in vlow or 'value' in vlow or 'sum' in vlow or 'transfer' in vlow:
                facts['amount'] = vlow
            if 'pattern' in vlow or 'usual' in vlow or 'consistent' in vlow or 'behaviour' in vlow:
                facts['pattern'] = vlow
        return facts

    def summarize_known_facts(self, facts):
        if not facts:
            return 'No facts confirmed yet.'
        return '\n'.join(f"{k.capitalize()}: {v}" for k, v in facts.items())

    def summarize_missing_facts(self, facts, dialogue_history):
        needed = ['verified', 'recipient', 'authorization', 'device', 'purpose', 'relationship', 'amount', 'pattern']
        missing = [k for k in needed if k not in facts]
        # Early finalization: if user denied authorization, confirmed identity, and described scam, allow finalize
        user_text = ' '.join([turn.get('user', '') for turn in dialogue_history if 'user' in turn]).lower()
        if (
            ('no' in user_text and 'authorize' in user_text) or ('unauthorized' in user_text)
        ) and ('verified' in facts or 'identity' in user_text):
            return []  # allow finalize
        # If conversation is long or user repeats themselves, allow finalize
        if len(dialogue_history) > 12:
            return []
        user_responses = [turn.get('user', '').strip().lower() for turn in dialogue_history if 'user' in turn]
        if len(user_responses) != len(set(user_responses)) and len(user_responses) > 6:
            return []
        return missing

    def get_next_question_and_agent(self, dialogue_history, context, stream=False):
        if context is None:
            context = {}
        txn = context.get('transaction', {})
        if txn is None:
            txn = {}
        rule_id = txn.get('ruleId', '')
        fraud_block = self.get_fraud_block(rule_id)
        if fraud_block is None or not isinstance(fraud_block, dict):
            fraud_block = {}
        core_facts = fraud_block.get('core_facts', [])
        finalize_if = fraud_block.get('finalize_if', [])
        facts = self.extract_facts([turn for turn in dialogue_history if isinstance(turn, dict)], context)
        missing = [k for k in core_facts if k not in facts]
        user_text = ' '.join([turn.get('user', '') for turn in dialogue_history if 'user' in turn]).lower()
        can_finalize = False
        for cond in finalize_if:
            if 'user_denies_authorization' in cond and ('no' in user_text and 'authorize' in user_text or 'unauthorized' in user_text):
                if 'identity_verified' in cond and ('verified' in facts or 'identity' in user_text):
                    can_finalize = True
            if 'user_confirms_biometrics' in cond and ('biometric' in user_text or 'face id' in user_text or 'fingerprint' in user_text):
                can_finalize = True
        if len(dialogue_history) > 12 or (len(set([turn.get('user', '').strip().lower() for turn in dialogue_history if 'user' in turn])) < len([turn for turn in dialogue_history if 'user' in turn]) and len(dialogue_history) > 6):
            can_finalize = True
        already_asked = set(turn.get('question', '').lower() for turn in dialogue_history if 'question' in turn)
        next_question = None
        if missing and not can_finalize:
            for m in missing:
                query = f"{m.replace('_', ' ')} question for rule {rule_id}"
                rag_questions = rag_retrieve_questions(context, query=query)
                for q in rag_questions:
                    qlow = q.lower()
                    if not any(qlow in asked for asked in already_asked):
                        next_question = q
                        break
                if next_question:
                    break
        if not missing or can_finalize:
            # Build a final expert summary/report using all context
            txn_info = str(context.get('transaction', {}))
            transaction_context = context.get('transaction_context', '[Not available]')
            customer_context = context.get('customer_context', '[Not available]')
            merchant_context = context.get('merchant_context', '[Not available]')
            anomaly_context = context.get('anomaly_context', '[Not available]')
            risk_summary_context = context.get('risk_summary_context', '[Not available]')
            triage_decision = context.get('triage_decision', '[Not available]')
            short_history = [turn for turn in dialogue_history if isinstance(turn, dict)][-5:] if len([turn for turn in dialogue_history if isinstance(turn, dict)]) > 5 else [turn for turn in dialogue_history if isinstance(turn, dict)]
            conversation = '\n'.join([f"Q: {turn.get('question', '')}\nA: {turn.get('user', '')}" for turn in short_history if 'question' in turn or 'user' in turn])
            final_report_prompt = (
                "You are an expert fraud investigation agent. Based on the following context and conversation, provide a clear, professional summary of the fraud investigation outcome for the customer. Do NOT ask for further input.\n"
                f"Transaction Alert: {txn_info}\n"
                f"Transaction Context: {transaction_context}\n"
                f"Customer Context: {customer_context}\n"
                f"Merchant Context: {merchant_context}\n"
                f"Behavioral/Anomaly Context: {anomaly_context}\n"
                f"Risk Synthesis: {risk_summary_context}\n"
                f"Triage Decision: {triage_decision}\n"
                f"Recent Conversation:\n{conversation}\n"
                "Summarize the findings, risk, and next steps (if any) in a concise, customer-friendly manner."
            )
            if stream:
                stream_gen = converse_with_claude_stream([
                    {"role": "user", "content": [{"text": final_report_prompt}]}
                ], max_tokens=512)
                return stream_gen, self.name, True
            else:
                llm_output = "".join([token for token in converse_with_claude_stream([
                    {"role": "user", "content": [{"text": final_report_prompt}]}
                ], max_tokens=512)])
                return llm_output, self.name, True
        if next_question:
            txn_info = str(context.get('transaction', {}))
            transaction_context = context.get('transaction_context', '[Not available]')
            customer_context = context.get('customer_context', '[Not available]')
            merchant_context = context.get('merchant_context', '[Not available]')
            anomaly_context = context.get('anomaly_context', '[Not available]')
            risk_summary_context = context.get('risk_summary_context', '[Not available]')
            triage_decision = context.get('triage_decision', '[Not available]')
            short_history = [turn for turn in dialogue_history if isinstance(turn, dict)][-5:] if len([turn for turn in dialogue_history if isinstance(turn, dict)]) > 5 else [turn for turn in dialogue_history if isinstance(turn, dict)]
            conversation = '\n'.join([f"Q: {turn.get('question', '')}\nA: {turn.get('user', '')}" for turn in short_history if 'question' in turn or 'user' in turn])
            expert_prompt = (
                "You are an expert fraud dialogue agent. Continue the conversation with the customer to determine if the transaction is an authorized scam.\n"
                f"Transaction Alert: {txn_info}\n"
                f"Transaction Context: {transaction_context}\n"
                f"Customer Context: {customer_context}\n"
                f"Merchant Context: {merchant_context}\n"
                f"Behavioral/Anomaly Context: {anomaly_context}\n"
                f"Risk Synthesis: {risk_summary_context}\n"
                f"Triage Decision: {triage_decision}\n"
                f"Recent Conversation:\n{conversation}\n"
                f"Ask the next best question to the customer, based on the context and the following suggested question: '{next_question}'.\n"
                "Phrase your question naturally and empathetically, and adapt it if needed to fit the context."
            )
            if stream:
                stream_gen = converse_with_claude_stream([
                    {"role": "user", "content": [{"text": expert_prompt}]}
                ], max_tokens=256)
                return stream_gen, self.name, False
            else:
                llm_output = "".join([token for token in converse_with_claude_stream([
                    {"role": "user", "content": [{"text": expert_prompt}]}
                ], max_tokens=256)])
                return llm_output, self.name, False
        closing_message = (
            "Thank you for your cooperation. We have no further questions at this time. If we need more information, we will contact you."
        )
        if stream:
            def gen():
                for c in closing_message:
                    yield c
            return gen(), self.name, True
        else:
            return closing_message, self.name, True

    def act(self, message, context, user_response=None, max_turns=12, stream=False):
        dialogue_history = context.get('dialogue_history', []) if isinstance(context, dict) else []
        if user_response is not None:
            if dialogue_history and isinstance(dialogue_history[-1], dict):
                dialogue_history[-1]['user'] = user_response
            else:
                dialogue_history.append({'user': user_response})
        if stream:
            stream_gen, agent_name, done = self.get_next_question_and_agent(dialogue_history, context, stream=True)
            buffer = ''
            for token in stream_gen:
                buffer += token
                yield token
            # Check if buffer contains FINALIZE
            if 'finalize' in buffer.lower():
                done = True
            # After streaming, append the full agent response to dialogue history
            if not done and len(dialogue_history) < max_turns:
                dialogue_history.append({'agent': agent_name, 'question': buffer, 'agent_log': agent_name, 'role': 'assistant'})
            if isinstance(context, dict):
                context['dialogue_history'] = dialogue_history
                context['dialogue_analysis'] = buffer
                if done:
                    context['dialogue_complete'] = True
            yield '__END__'
        else:
            next_q, agent_name, done = self.get_next_question_and_agent(dialogue_history, context)
            if not done and len(dialogue_history) < max_turns:
                dialogue_history.append({'agent': agent_name, 'question': next_q, 'agent_log': agent_name})
            if isinstance(context, dict):
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
        base = "Given the following conversation, do you have enough information to make a fraud decision? If yes, say 'Finalize - [reason]' NOTE: REASON IS NECESSARY WITH FULL AND FINAL REPORT ABOUT THE AUTHORIZED SCAM BASED ON THE CONVERSATION AND THE SOPs & TRANSACTION, CONTEXTS. If not, say what else to ask."
        history = "\n".join([f"Q: {turn['question']}\nA: {turn.get('user', '')}" for turn in dialogue_history])
        return f"{base}\nConversation:\n{history}"

# --- RiskAssessorAgent ---
class RiskAssessorAgent(Agent):
    def __init__(self, name, context_store):
        super().__init__(name, context_store)

    def act(self, message, context):
        sops = rag_retrieve_sop(context, query=str(context.get('transaction', {})))
        
        # Check if this is during dialogue or final assessment
        is_final_assessment = 'Final risk summary' in message or 'final' in message.lower()
        
        # Build dialogue summary if available
        dialogue_summary = ""
        if context.get('dialogue_history'):
            dialogue_summary = "\n".join([
                f"Q: {turn.get('question', '')}\nA: {turn.get('user', '[No response yet]')}" 
                for turn in context.get('dialogue_history', []) 
                if isinstance(turn, dict) and 'question' in turn
            ])
        
        if is_final_assessment:
            # Final comprehensive risk assessment after dialogue completes
            prompt = (
                "You are an expert risk assessor specializing in authorized payment scams (APP fraud). "
                "The dialogue with the customer is now COMPLETE. Provide a FINAL comprehensive risk assessment.\n\n"
                "ANALYZE ALL EVIDENCE:\n"
                f"Transaction Alert: {context.get('transaction', {})}\n"
                f"Transaction Context: {context.get('transaction_context', '[Not available]')}\n"
                f"Customer Context: {context.get('customer_context', '[Not available]')}\n"
                f"Merchant/Payee Context: {context.get('merchant_context', '[Not available]')}\n"
                f"Behavioral Anomalies: {context.get('anomaly_context', '[Not available]')}\n"
                f"Initial Risk Assessment: {context.get('risk_summary_context', '[Not available]')}\n"
                f"Triage Decision: {context.get('triage_decision', '[Not available]')}\n\n"
                f"COMPLETE CUSTOMER DIALOGUE:\n{dialogue_summary}\n\n"
                f"Relevant SOPs: {sops[:5]}\n\n"
                "PROVIDE FINAL DETERMINATION:\n"
                "1. Is this an AUTHORIZED SCAM? (Yes/No/Unclear)\n"
                "2. Confidence level (High/Medium/Low)\n"
                "3. Key indicators supporting your decision\n"
                "4. Red flags or concerning patterns identified\n"
                "5. Recommended immediate actions\n\n"
                "Focus on authorized scam typologies: romance scams, investment scams, purchase scams, "
                "impersonation scams, tech support scams, and other social engineering attacks."
            )
        else:
            # Progressive risk assessment during dialogue
            prompt = (
                "You are an expert risk assessor specializing in authorized payment scams. "
                "Evaluate the CURRENT state of the investigation based on dialogue progress.\n\n"
                f"Transaction Alert: {context.get('transaction', {})}\n"
                f"Initial Risk Assessment: {context.get('risk_summary_context', '[Not available]')}\n\n"
                f"DIALOGUE PROGRESS SO FAR:\n{dialogue_summary if dialogue_summary else '[No dialogue yet]'}\n\n"
                f"Context Available:\n"
                f"- Transaction patterns: {bool(context.get('transaction_context'))}\n"
                f"- Customer profile: {bool(context.get('customer_context'))}\n" 
                f"- Payee/Merchant info: {bool(context.get('merchant_context'))}\n"
                f"- Behavioral analysis: {bool(context.get('anomaly_context'))}\n\n"
                "CRITICAL ASSESSMENT:\n"
                "1. Do we have ENOUGH information to determine if this is an authorized scam? "
                "Consider: customer's awareness, transaction purpose, relationship with payee, "
                "authorization method, behavioral indicators.\n"
                "2. What specific scam typology does this most resemble (if any)?\n"
                "3. Current risk level: HIGH/MEDIUM/LOW\n"
                "4. Missing critical information (if any)\n\n"
                "If you have sufficient information to make a determination with reasonable confidence, "
                "say 'FINALIZE - [reason]' NOTE: REASON IS NECESSARY WITH FULL AND FINAL REPORT ABOUT THE AUTHORIZED SCAM BASED ON THE CONVERSATION AND THE SOPs & TRANSACTION, CONTEXTS. Otherwise, specify what key information is still needed."
            )
        
        result = "".join([token for token in converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=512)])
        
        context['risk_assessment'] = result
        
        # Check if risk assessor recommends finalization
        if not is_final_assessment and 'finalize' in result.lower():
            context['risk_ready_to_finalize'] = True
            
        return context

# --- PolicyDecisionAgent ---
class PolicyDecisionAgent(Agent):
    def __init__(self, name, context_store):
        super().__init__(name, context_store)

    def act(self, message, context):
        sops = rag_retrieve_sop(context, query=str(context.get('transaction', {})))
        
        # Get the final risk assessment
        final_risk = context.get('final_risk_determination', context.get('risk_assessment_summary', '[Not available]'))
        
        prompt = (
            "You are an expert policy decision agent specializing in AUTHORIZED PAYMENT SCAM prevention. "
            "Based on the investigation findings, make a policy decision that balances customer protection "
            "with regulatory compliance.\n\n"
            "FINAL RISK ASSESSMENT:\n"
            f"{final_risk}\n\n"
            "TRANSACTION DETAILS:\n"
            f"Alert: {context.get('transaction', {})}\n"
            f"Amount: ${context.get('transaction', {}).get('amount', 'Unknown')}\n"
            f"Payee: {context.get('transaction', {}).get('payee', 'Unknown')}\n\n"
            "INVESTIGATION SUMMARY:\n"
            f"- Customer verified: {'Yes' if 'verified' in str(context.get('dialogue_history', [])).lower() else 'Unknown'}\n"
            f"- Authorization status: {'Confirmed' if 'yes' in str(context.get('dialogue_history', [])).lower() and 'authorize' in str(context.get('dialogue_history', [])).lower() else 'Check dialogue'}\n"
            f"- Number of dialogue turns: {len(context.get('dialogue_history', []))}\n\n"
            "RELEVANT SOPs:\n" + '\n'.join(sops[:5]) + "\n\n"
            "POLICY DECISION OPTIONS:\n"
            "1. BLOCK TRANSACTION - Prevent the payment immediately\n"
            "2. DELAY FOR COOLING-OFF - 24-48 hour hold for customer reflection\n"
            "3. ESCALATE TO SENIOR - Complex case requiring management review\n"
            "4. PROCEED WITH WARNING - Allow but document customer was warned\n"
            "5. PROCEED - No scam indicators found\n\n"
            "PROVIDE YOUR DECISION WITH:\n"
            "- Selected action (1-5)\n"
            "- Specific regulatory/compliance justification (e.g., APRA CPG 234, AUSTRAC guidelines)\n"
            "- Customer protection measures to implement\n"
            "- Documentation requirements\n"
            "- Any follow-up actions needed\n\n"
            "Consider the customer's vulnerability, transaction amount, and reputational risk."
        )
        
        result = "".join([token for token in converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=512)])
        
        context['policy_decision'] = result
        return context

# --- FeedbackCollectorAgent ---
class FeedbackCollectorAgent(Agent):
    def __init__(self, name, context_store):
        super().__init__(name, context_store)

    def act(self, message, context):
        sops = rag_retrieve_sop(context, query=str(context.get('transaction', {})))
        
        # Get the final determinations
        final_risk = context.get('final_risk_determination', context.get('risk_assessment_summary', '[Not available]'))
        policy_decision = context.get('policy_decision', '[Not available]')
        
        prompt = (
            "You are an expert feedback collector for the AUTHORIZED SCAM prevention system. "
            "Generate structured feedback questions to improve our detection and customer protection.\n\n"
            "CASE SUMMARY:\n"
            f"Transaction: {context.get('transaction', {})}\n"
            f"Final Risk Assessment: {'SCAM DETECTED' if 'yes' in final_risk.lower() and 'authorized scam' in final_risk.lower() else 'CHECK ASSESSMENT'}\n"
            f"Policy Action: {'BLOCKED' if 'block' in str(policy_decision).lower() else 'CHECK DECISION'}\n"
            f"Dialogue Turns: {len(context.get('dialogue_history', []))}\n\n"
            "GENERATE FEEDBACK COLLECTION FOCUSING ON:\n\n"
            "1. DETECTION ACCURACY:\n"
            "   - Was this correctly identified as an authorized scam?\n"
            "   - What indicators did we miss?\n"
            "   - False positive/negative assessment?\n\n"
            "2. CUSTOMER INTERACTION QUALITY:\n"
            "   - Were questions empathetic and appropriate?\n" 
            "   - Did we identify customer vulnerability?\n"
            "   - Was the dialogue length optimal?\n\n"
            "3. RISK INDICATORS:\n"
            "   - New scam patterns observed?\n"
            "   - Behavioral red flags we should add?\n"
            "   - SOPs that need updating?\n\n"
            "4. DECISION EFFECTIVENESS:\n"
            "   - Was the policy action appropriate?\n"
            "   - Customer outcome (if known)?\n"
            "   - Regulatory compliance gaps?\n\n"
            "5. SYSTEM IMPROVEMENTS:\n"
            "   - Additional data points needed?\n"
            "   - Agent performance issues?\n"
            "   - Process optimization opportunities?\n\n"
            "FORMAT: Create specific questions an analyst can answer to improve future detection. "
            "Include rating scales where appropriate (1-5) and text fields for detailed feedback."
        )
        
        result = "".join([token for token in converse_with_claude_stream([
            {"role": "user", "content": [{"text": prompt}]}
        ], max_tokens=512)])
        
        context['feedback'] = result
        return context

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
                if isinstance(result, dict):
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
                dialogue_history = context.get('dialogue_history', []) if isinstance(context, dict) else []
                if not dialogue_history or (isinstance(dialogue_history[-1], dict) and 'user' in dialogue_history[-1]):
                    next_q, agent_name, _ = self.dialogue_agent.get_next_question_and_agent(dialogue_history, context)
                    if next_q:
                        if isinstance(context, dict):
                            if 'dialogue_history' not in context or not isinstance(context['dialogue_history'], list):
                                context['dialogue_history'] = []
                            context['dialogue_history'].append({'agent': agent_name, 'question': next_q, 'agent_log': agent_name})
                        agent_log.append(agent_name)
                        if stream_callback:
                            stream_callback(agent_name, {'question': next_q})
                if isinstance(context, dict) and 'dialogue_history' in context and isinstance(context['dialogue_history'], list) and context['dialogue_history']:
                    user_response = user_io(context['dialogue_history'][-1]['question'])
                else:
                    user_response = user_io('')
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
        ], max_tokens=512)
        return report 