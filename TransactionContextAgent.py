from strands import Agent, tool
from typing import Dict, Any, List
import json
from datetime import datetime
from aws_bedrock import converse_with_claude_stream
from config import config
from vector_utils import search_similar
import logging

def load_json(filename):
    try:
        with open(f'datasets/{filename}', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return {}

class TransactionContextAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="transaction-context-agent",
            name="TransactionContextAgent",
            description="Advanced transaction context analysis agent with expert fraud detection capabilities"
        )
        self.agent_config = config.get_agent_config(self.name)
        self.logger = logging.getLogger(self.name)

    @tool
    def analyze_transaction(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze transaction context and detect potential fraud indicators."""
        try:
            # Get dynamic SOPs based on transaction context
            transaction_query = self._build_transaction_query(context)
            sops = self._retrieve_sop(context, query=transaction_query)
            
            # Get transaction details dynamically - handle both field name formats
            alert = context.get('transaction', {})
            
            # Extract IDs using both field name formats
            txn_id = (alert.get('alert_id') or alert.get('alertId') or 
                      alert.get('transaction_id') or alert.get('transactionId'))
            customer_id = (alert.get('customer_id') or alert.get('customerId'))
            
            print(f"DEBUG: TransactionContextAgent - txn_id: {txn_id}, customer_id: {customer_id}")
            
            # Dynamically load transaction details
            txn_details = self._load_transaction_details(txn_id, customer_id)
            
            # Build intelligent analysis prompt
            prompt = self._build_transaction_analysis_prompt(alert, txn_details, sops)
            
            # Get expert analysis (emphasize extraction of concrete fraud indicators)
            result = self._get_expert_analysis(
                prompt + "\n\nBe explicit: mention remote access tools, OTP/code sharing, caller impersonation, urgency, secrecy if detected."
            )
            
            # Add to context with metadata
            context['transaction_context'] = result
            context['transaction_analysis_timestamp'] = datetime.now().isoformat()
            
            # Store in context instead of Mem0 memory
            case_id = txn_id or customer_id or 'unknown'
            context['case_id'] = case_id
            context['context_summary'] = result
            context['agent_summary'] = f"Transaction analysis completed for {case_id}"
            
            return context
        except Exception as e:
            self.logger.error(f"Error in analyze_transaction: {str(e)}")
            context['transaction_context'] = "Error occurred during transaction analysis"
            context['transaction_analysis_error'] = str(e)
            return context

    def _build_transaction_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for transaction analysis"""
        alert = context.get('transaction', {})
        query_parts = []
        
        if isinstance(alert, dict):
            amount = alert.get('amount', 0)
            payee = alert.get('payee', '')
            transaction_type = alert.get('transactionType', '')
            
            query_parts.append(f"transaction amount {amount}")
            if payee:
                query_parts.append(f"payee {payee}")
            if transaction_type:
                query_parts.append(f"transaction type {transaction_type}")
        
        return " ".join(query_parts) if query_parts else "transaction analysis"

    def _retrieve_sop(self, context, query=None) -> List[str]:
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
        except Exception as e:
            self.logger.error(f"Error reading SOP file: {str(e)}")
        return sops

    def _load_transaction_details(self, txn_id: str, customer_id: str) -> Dict[str, Any]:
        """Dynamically load transaction details from multiple sources"""
        txn_details = {}
        
        # Try FTP data first - handle both field name formats
        try:
            ftp_data = load_json('FTP.json')
            if isinstance(ftp_data, dict) and 'alerts' in ftp_data:
                ftp_alerts = ftp_data['alerts']
            elif isinstance(ftp_data, list):
                ftp_alerts = ftp_data
            else:
                ftp_alerts = []
            
            # Handle both old and new field names
            for alert in ftp_alerts:
                if (alert.get('alert_id') == txn_id or 
                    alert.get('alertId') == txn_id or
                    alert.get('transaction_id') == txn_id or
                    alert.get('transactionId') == txn_id):
                    txn_details = alert
                    break
        except Exception as e:
            self.logger.error(f"Error loading FTP data: {e}")
        
        # Try customer transaction history if no FTP match
        if not txn_details:
            try:
                txn_history = load_json('Customer_Transaction_History.json')
                if isinstance(txn_history, dict) and 'transactions' in txn_history:
                    transactions = txn_history['transactions']
                elif isinstance(txn_history, list):
                    transactions = txn_history
                else:
                    transactions = []
                
                for txn in transactions:
                    if (txn.get('transaction_id') == txn_id or 
                        txn.get('transactionId') == txn_id or
                        txn.get('customer_id') == customer_id or
                        txn.get('customerId') == customer_id):
                        txn_details = txn
                        break
            except Exception as e:
                self.logger.error(f"Error loading transaction history: {e}")
        
        return txn_details if txn_details else {'status': 'transaction_details_unavailable'}

    def _build_transaction_analysis_prompt(self, alert: Dict[str, Any], txn_details: Dict[str, Any], sops: List[str]) -> str:
        """Build intelligent transaction analysis prompt"""
        specialized_prompts = self.agent_config.specialized_prompts
        
        fraud_analysis_prompt = specialized_prompts.get('fraud_analysis', 
            "Analyze transaction patterns for fraud indicators and regulatory compliance")
        
        regulatory_prompt = specialized_prompts.get('regulatory_compliance',
            "Check for regulatory triggers and compliance requirements")
        
        # Build context summary
        context_summary = self._build_transaction_context_summary(alert, txn_details)
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:5]) if sops else "No specific SOPs found"
        
        prompt = f"""
You are a senior ANZ transaction context expert specializing in advanced fraud typologies for ANZ Bank.

{fraud_analysis_prompt}
{regulatory_prompt}

TRANSACTION ALERT:
{json.dumps(alert, indent=2)}

TRANSACTION DETAILS:
{json.dumps(txn_details, indent=2)}

RELEVANT SOPs:
{sop_summary}

ANALYSIS REQUIREMENTS:
1. Extract and summarize all relevant transaction details for fraud analysis
2. Identify rare typologies and cross-reference with historical anomalies
3. Flag unusual transaction patterns and behavioral indicators
4. Highlight regulatory or compliance triggers
5. Assess risk level and recommend immediate actions
6. Identify potential scam typologies (BEC, romance scams, investment scams, etc.)

Provide a comprehensive, expert-level analysis suitable for fraud operations.
"""
        return prompt

    def _build_transaction_context_summary(self, alert: Dict[str, Any], txn_details: Dict[str, Any]) -> str:
        """Build intelligent transaction context summary"""
        summary_parts = []
        
        if isinstance(alert, dict):
            amount = alert.get('amount', 'Unknown')
            payee = alert.get('payee_payer_name', 'Unknown')
            alert_id = alert.get('alert_id', 'Unknown')
            customer_id = alert.get('customer_id', 'Unknown')
            
            summary_parts.append(f"Alert ID: {alert_id}")
            summary_parts.append(f"Customer ID: {customer_id}")
            summary_parts.append(f"Amount: ${amount}")
            summary_parts.append(f"Payee: {payee}")
            
            # Add additional context
            if 'transaction_date' in alert:
                summary_parts.append(f"Date: {alert['transaction_date']}")
            if 'transaction_type' in alert:
                summary_parts.append(f"Type: {alert['transaction_type']}")
            if 'risk_score' in alert:
                summary_parts.append(f"Risk Score: {alert['risk_score']}")
            if 'escalation_level' in alert:
                summary_parts.append(f"Escalation Level: {alert['escalation_level']}")
        
        if txn_details and isinstance(txn_details, dict):
            summary_parts.append(f"Details: {json.dumps(txn_details, indent=2)}")
        
        return "\n".join(summary_parts)

    def _get_expert_analysis(self, prompt: str) -> str:
        """Get expert analysis with error handling"""
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
                ], max_tokens=self.agent_config.max_tokens)])
            return result
        except Exception as e:
            self.logger.error(f"Failed to get expert analysis: {e}")
            return "Analysis unavailable due to technical issues"

    def _calculate_analysis_confidence(self, result: str) -> float:
        """Calculate confidence in analysis based on content quality"""
        if not result or result == "Analysis unavailable due to technical issues":
            return 0.0
        
        # Calculate confidence based on analysis depth
        confidence_factors = {
            'fraud_indicators': 0.2,
            'regulatory_compliance': 0.2,
            'risk_assessment': 0.2,
            'recommended_actions': 0.2,
            'scam_typology': 0.2
        }
        
        total_confidence = 0.0
        result_lower = result.lower()
        
        for factor, weight in confidence_factors.items():
            if factor.replace('_', ' ') in result_lower:
                total_confidence += weight
        
        return min(1.0, total_confidence + 0.3)  # Base confidence of 0.3

transaction_context_agent = TransactionContextAgent()
