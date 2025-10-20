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

def normalize_field_names(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize field names to handle both old and new formats"""
    normalized = {}
    
    # Field name mappings
    field_mappings = {
        'alert_id': ['alertId', 'alert_id'],
        'customer_id': ['customerId', 'customer_id'],
        'transaction_id': ['transactionId', 'transaction_id'],
        'rule_id': ['ruleId', 'rule_id'],
        'payee_payer_name': ['payeePayerName', 'payee_payer_name', 'payee'],
        'transaction_type': ['transactionType', 'transaction_type'],
        'transaction_date': ['transactionDate', 'transaction_date'],
        'amount': ['amount'],
        'currency': ['currency'],
        'risk_score': ['riskScore', 'risk_score'],
        'escalation_level': ['escalationLevel', 'escalation_level']
    }
    
    for normalized_name, possible_names in field_mappings.items():
        for old_name in possible_names:
            if old_name in data:
                normalized[normalized_name] = data[old_name]
                break
    
    # Copy any other fields that don't have mappings
    for key, value in data.items():
        if key not in [name for names in field_mappings.values() for name in names]:
            normalized[key] = value
    
    return normalized

class BehavioralPatternAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="behavioral-pattern-agent",
            name="BehavioralPatternAgent",
            description="Advanced behavioral pattern analysis agent with social engineering detection"
        )
        self.agent_config = config.get_agent_config(self.name)
        self.logger = logging.getLogger(self.name)

    @tool
    def analyze_behavior(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze behavioral patterns and detect anomalies and social engineering indicators."""
        try:
            # Get dynamic SOPs based on behavioral context
            behavioral_query = self._build_behavioral_query(context)
            sops = self._retrieve_sop(context, query=behavioral_query)
            
            # Get anomaly details dynamically - handle both field name formats
            alert = context.get('transaction', {})
            customer_id = (alert.get('customer_id') or alert.get('customerId'))
            alert_id = (alert.get('alert_id') or alert.get('alertId'))
            
            print(f"DEBUG: BehavioralPatternAgent - customer_id: {customer_id}, alert_id: {alert_id}")
            
            if not customer_id:
                print("WARNING: No customer ID found in alert data")
                context['anomaly_context'] = "Customer ID not available in alert data"
                return context
            
            # Dynamically load anomaly details
            anomaly_details = self._load_anomaly_details(customer_id, alert_id)
            
            # Build intelligent analysis prompt
            prompt = self._build_behavioral_analysis_prompt(anomaly_details, sops)
            
            result = self._get_expert_analysis(
                prompt + "\n\nPrioritize signals: remote access, OTP disclosure, urgency, secrecy, impersonation scripts."
            )
            
            # Add to context with metadata
            context['anomaly_context'] = result
            context['anomaly_analysis_timestamp'] = datetime.now().isoformat()
            
            # Store in context instead of Mem0 memory
            case_id = customer_id or alert_id or 'unknown'
            context['case_id'] = case_id
            context['context_summary'] = result
            context['agent_summary'] = f"Behavioral analysis completed for {case_id}"
            
            self.logger.info(f"Behavioral analysis completed for case: {context.get('transaction', {}).get('alert_id', 'Unknown')}")
            return context
        except Exception as e:
            self.logger.error(f"Error in analyze_behavior: {str(e)}")
            context['anomaly_context'] = "Error occurred during behavioral analysis"
            context['behavioral_analysis_error'] = str(e)
            return context

    def _build_behavioral_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for behavioral analysis"""
        alert = context.get('transaction', {})
        query_parts = []
        
        if isinstance(alert, dict):
            customer_id = alert.get('customerId', '')
            if customer_id:
                query_parts.append(f"customer behavior {customer_id}")
        
        return " ".join(query_parts) if query_parts else "behavioral anomaly detection"

    def _retrieve_sop(self, context, query=None):
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

    def _load_anomaly_details(self, customer_id: str, alert_id: str) -> Dict[str, Any]:
        """Dynamically load anomaly details from multiple sources"""
        anomaly_details = {}
        
        # Try FTP data first
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
                normalized_alert = normalize_field_names(alert)
                if (normalized_alert.get('customer_id') == customer_id or 
                    normalized_alert.get('alert_id') == alert_id):
                    anomaly_details = normalized_alert
                    break
        except Exception as e:
            self.logger.error(f"Error loading FTP data for anomaly analysis: {e}")
        
        # Try call history if no FTP match
        if not anomaly_details:
            try:
                call_data = load_json('Enhanced_Customer_Call_History.json')
                if isinstance(call_data, dict) and 'calls' in call_data:
                    calls = call_data['calls']
                elif isinstance(call_data, list):
                    calls = call_data
                else:
                    calls = []
                
                # Handle both old and new field names
                for call in calls:
                    normalized_call = normalize_field_names(call)
                    if (normalized_call.get('customer_id') == customer_id or 
                        normalized_call.get('alert_id') == alert_id):
                        anomaly_details = normalized_call
                        break
            except Exception as e:
                self.logger.error(f"Error loading call history for anomaly analysis: {e}")
        
        return anomaly_details if anomaly_details else {'status': 'anomaly_details_unavailable'}

    def _build_behavioral_analysis_prompt(self, anomaly_details: Dict[str, Any], sops: List[str]) -> str:
        """Build intelligent behavioral analysis prompt"""
        specialized_prompts = self.agent_config.specialized_prompts
        
        anomaly_prompt = specialized_prompts.get('anomaly_detection',
            "Detect behavioral anomalies and patterns")
        
        social_engineering_prompt = specialized_prompts.get('social_engineering',
            "Identify social engineering indicators")
        
        # Build anomaly summary
        anomaly_summary = self._build_anomaly_summary(anomaly_details)
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:5]) if sops else "No specific SOPs found"
        
        prompt = f"""
You are a behavioral pattern analyst specializing in time-series analysis and social engineering detection.

{anomaly_prompt}
{social_engineering_prompt}

ANOMALY DETAILS:
{json.dumps(anomaly_details, indent=2)}

RELEVANT SOPs:
{sop_summary}

ANALYSIS REQUIREMENTS:
1. Extract and summarize behavioral anomalies and patterns
2. Detect device/IP switching and unusual access patterns
3. Identify social engineering indicators and manipulation tactics
4. Analyze temporal patterns and timing anomalies
5. Assess behavioral biometrics and device familiarity
6. Highlight escalation triggers and compliance issues
7. Recommend behavioral monitoring measures

Provide a comprehensive, expert-level behavioral analysis.
"""
        return prompt

    def _build_anomaly_summary(self, anomaly_details: Dict[str, Any]) -> str:
        """Build intelligent anomaly summary"""
        if not anomaly_details or anomaly_details.get('status') == 'anomaly_details_unavailable':
            return "Anomaly details unavailable"
        
        summary_parts = []
        
        if isinstance(anomaly_details, dict):
            customer_id = anomaly_details.get('customer_id', 'Unknown')
            alert_id = anomaly_details.get('alert_id', 'Unknown')
            anomaly_type = anomaly_details.get('anomaly_type', 'Unknown')
            
            summary_parts.append(f"Customer ID: {customer_id}")
            summary_parts.append(f"Alert ID: {alert_id}")
            summary_parts.append(f"Anomaly Type: {anomaly_type}")
            
            # Add additional details
            for key, value in anomaly_details.items():
                if key not in ['customer_id', 'alert_id', 'anomaly_type']:
                    summary_parts.append(f"{key.title()}: {value}")
        
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

    def _calculate_anomaly_score(self, result: str) -> float:
        """Calculate anomaly score based on analysis"""
        if not result or result == "Analysis unavailable due to technical issues":
            return 0.5  # Default medium anomaly
        
        result_lower = result.lower()
        
        # Anomaly indicators
        high_anomaly_indicators = [
            'high anomaly', 'significant deviation', 'unusual pattern',
            'suspicious behavior', 'anomalous activity', 'red flag'
        ]
        
        medium_anomaly_indicators = [
            'medium anomaly', 'some concern', 'monitoring required'
        ]
        
        low_anomaly_indicators = [
            'low anomaly', 'normal behavior', 'expected pattern'
        ]
        
        # Calculate score
        score = 0.5  # Base score
        
        for indicator in high_anomaly_indicators:
            if indicator in result_lower:
                score += 0.4
                break
        
        for indicator in medium_anomaly_indicators:
            if indicator in result_lower:
                score += 0.1
                break
        
        for indicator in low_anomaly_indicators:
            if indicator in result_lower:
                score -= 0.3
                break
        
        return max(0.0, min(1.0, score))

behavioral_pattern_agent = BehavioralPatternAgent()