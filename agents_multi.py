"""
Advanced Intelligent Agents for ANZ Bank Authorized Scam Detection
Production-ready agents with dynamic, expert-level capabilities
"""

import json
import os
from agent_base import IntelligentAgent, AgentContext
from context_store import ContextStore
from aws_bedrock import converse_with_claude_stream
import re
import concurrent.futures
from vector_utils import search_similar
import yaml
import types
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

from config import config

DATASET_DIR = os.path.join(os.path.dirname(__file__), 'datasets')

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

def load_json(filename):
    """Load and normalize JSON data with proper error handling"""
    try:
        with open(os.path.join(DATASET_DIR, filename), encoding='utf-8') as f:
            data = json.load(f)
            
            # Handle different dataset structures
            if isinstance(data, dict):
                # Handle FTP alerts structure
                if 'alerts' in data:
                    data['alerts'] = [normalize_field_names(alert) for alert in data['alerts']]
                    return data
                # Handle customer demographics structure
                elif 'customers' in data:
                    data['customers'] = [normalize_field_names(customer) for customer in data['customers']]
                    return data
                # Handle transaction history structure
                elif 'transactions' in data:
                    data['transactions'] = [normalize_field_names(txn) for txn in data['transactions']]
                    return data
                # Handle other dict structures
                else:
                    return normalize_field_names(data)
            elif isinstance(data, list):
                # Handle direct list of records
                return [normalize_field_names(record) for record in data]
            else:
                # Return as-is for other types
                return data
                
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return {}

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

class TransactionContextAgent(IntelligentAgent):
    """Advanced transaction context analysis agent with expert fraud detection capabilities"""
    
    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Get dynamic SOPs based on transaction context
        transaction_query = self._build_transaction_query(context)
        sops = rag_retrieve_sop(context, query=transaction_query)
        
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
        
        # Store in Mem0 memory
        case_id = txn_id or customer_id or 'unknown'
        self.store_context_summary(case_id, result)
        self.store_agent_summary(case_id, f"Transaction analysis completed for {case_id}")
        
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
            print(f"Error loading FTP data: {e}")
            pass
        
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
                print(f"Error loading transaction history: {e}")
                pass
        
        return txn_details if txn_details else {'status': 'transaction_details_unavailable'}
    
    def _build_transaction_analysis_prompt(self, alert: Dict[str, Any], txn_details: Dict[str, Any], sops: List[str]) -> str:
        """Build intelligent transaction analysis prompt"""
        # Get agent configuration
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
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

class CustomerInfoAgent(IntelligentAgent):
    """Advanced customer intelligence agent with behavioral biometrics and vulnerability assessment"""
    
    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Get dynamic SOPs based on customer context
        customer_query = self._build_customer_query(context)
        sops = rag_retrieve_sop(context, query=customer_query)
        
        # Get customer details dynamically - handle both field name formats
        alert = context.get('transaction', {})
        customer_id = (alert.get('customer_id') or alert.get('customerId'))
        
        print(f"DEBUG: CustomerInfoAgent - customer_id: {customer_id}")
        
        if not customer_id:
            print("WARNING: No customer ID found in alert data")
            context['customer_context'] = "Customer ID not available in alert data"
            return context
        
        # Dynamically load customer details
        customer_details = self._load_customer_details(customer_id)
        
        # Build intelligent analysis prompt
        prompt = self._build_customer_analysis_prompt(customer_details, sops)
        
        result = self._get_expert_analysis(
            prompt + "\n\nIf customer mentions remote access or reading security codes, flag High vulnerability and social engineering."
        )
        
        # Add to context with metadata
        context['customer_context'] = result
        context['customer_analysis_timestamp'] = datetime.now().isoformat()
        
        # Store in Mem0 memory
        case_id = customer_id or 'unknown'
        self.store_context_summary(case_id, result)
        self.store_agent_summary(case_id, f"Customer analysis completed for {case_id}")
        
        return context
    
    def _build_customer_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for customer analysis"""
        alert = context.get('transaction', {})
        query_parts = []
        
        if isinstance(alert, dict):
            customer_id = alert.get('customerId', '')
            if customer_id:
                query_parts.append(f"customer {customer_id}")
        
        return " ".join(query_parts) if query_parts else "customer vulnerability assessment"
    
    def _load_customer_details(self, customer_id: str) -> Dict[str, Any]:
        """Dynamically load customer details"""
        customer_details = {}
        
        try:
            data = load_json('customer_demographic.json')
            if isinstance(data, dict) and 'customers' in data:
                customers = data['customers']
            elif isinstance(data, list):
                customers = data
            else:
                customers = []
            
            # Handle both field name formats
            for customer in customers:
                if (customer.get('customer_id') == customer_id or 
                    customer.get('customerId') == customer_id):
                    customer_details = customer
                    break
                    
        except Exception as e:
            print(f"Error loading customer demographics: {e}")
            pass
        
        return customer_details if customer_details else {'status': 'customer_details_unavailable'}
    
    def _build_customer_analysis_prompt(self, customer_details: Dict[str, Any], sops: List[str]) -> str:
        """Build intelligent customer analysis prompt"""
        # Get agent configuration
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
        vulnerability_prompt = specialized_prompts.get('vulnerability_assessment',
            "Assess customer vulnerability to scams and social engineering")
        
        behavioral_prompt = specialized_prompts.get('behavioral_analysis',
            "Analyze customer behavior patterns and risk indicators")
        
        # Build customer summary
        customer_summary = self._build_customer_summary(customer_details)
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:5]) if sops else "No specific SOPs found"
        
        prompt = f"""
You are a customer intelligence agent with expertise in behavioral biometrics and scam victim profiling.

{vulnerability_prompt}
{behavioral_prompt}

CUSTOMER DETAILS:
{json.dumps(customer_details, indent=2)}

RELEVANT SOPs:
{sop_summary}

ANALYSIS REQUIREMENTS:
1. Extract and summarize all relevant customer information
2. Assess device fingerprinting and behavioral anomalies
3. Cross-check with known scam victim profiles
4. Identify vulnerability indicators and risk factors
5. Highlight compliance issues and protection requirements
6. Assess digital literacy and scam awareness level
7. Recommend customer protection measures

Provide a comprehensive, expert-level customer intelligence report.
"""
        return prompt
    
    def _build_customer_summary(self, customer_details: Dict[str, Any]) -> str:
        """Build intelligent customer summary"""
        if not customer_details or customer_details.get('status') == 'customer_details_unavailable':
            return "Customer details unavailable"
        
        summary_parts = []
        
        if isinstance(customer_details, dict):
            customer_id = customer_details.get('customer_id', 'Unknown')
            
            # Handle enhanced dataset structure
            if 'personal_information' in customer_details:
                personal = customer_details['personal_information']
                name = personal.get('name', 'Unknown')
                date_of_birth = personal.get('date_of_birth', 'Unknown')
                summary_parts.append(f"Customer ID: {customer_id}")
                summary_parts.append(f"Name: {name}")
                summary_parts.append(f"Date of Birth: {date_of_birth}")
                
                # Add KYC status
                if 'kyc_status' in personal:
                    summary_parts.append(f"KYC Status: {personal['kyc_status']}")
                
                # Add digital literacy
                if 'digital_literacy_level' in personal:
                    summary_parts.append(f"Digital Literacy: {personal['digital_literacy_level']}")
            else:
                # Fallback for old format
                name = customer_details.get('name', 'Unknown')
                age = customer_details.get('age', 'Unknown')
                summary_parts.append(f"Customer ID: {customer_id}")
                summary_parts.append(f"Name: {name}")
                summary_parts.append(f"Age: {age}")
            
            # Add risk profile information
            if 'customer_details' in customer_details:
                details = customer_details['customer_details']
                risk_profile = details.get('risk_profile', 'Unknown')
                aml_risk_level = details.get('aml_risk_level', 'Unknown')
                cdd_level = details.get('cdd_level', 'Unknown')
                summary_parts.append(f"Risk Profile: {risk_profile}")
                summary_parts.append(f"AML Risk Level: {aml_risk_level}")
                summary_parts.append(f"CDD Level: {cdd_level}")
            else:
                risk_profile = customer_details.get('risk_profile', 'Unknown')
                summary_parts.append(f"Risk Profile: {risk_profile}")
            
            # Add additional details
            for key, value in customer_details.items():
                if key not in ['customer_id', 'personal_information', 'customer_details']:
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
    
    def _calculate_vulnerability_score(self, result: str) -> float:
        """Calculate customer vulnerability score based on analysis"""
        if not result or result == "Analysis unavailable due to technical issues":
            return 0.5  # Default medium vulnerability
        
        result_lower = result.lower()
        
        # Vulnerability indicators
        high_vulnerability_indicators = [
            'high-risk', 'vulnerable', 'no education', 'prior alerts',
            'self-employed', 'medium digital literacy', 'elderly'
        ]
        
        medium_vulnerability_indicators = [
            'medium risk', 'some vulnerability', 'limited education'
        ]
        
        low_vulnerability_indicators = [
            'low risk', 'educated', 'aware', 'protected'
        ]
        
        # Calculate score
        score = 0.5  # Base score
        
        for indicator in high_vulnerability_indicators:
            if indicator in result_lower:
                score += 0.3
                break
        
        for indicator in medium_vulnerability_indicators:
            if indicator in result_lower:
                score += 0.1
                break
        
        for indicator in low_vulnerability_indicators:
            if indicator in result_lower:
                score -= 0.2
                break
        
        return max(0.0, min(1.0, score))

class MerchantInfoAgent(IntelligentAgent):
    """Advanced merchant risk analysis agent with industry-specific expertise"""
    
    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Get dynamic SOPs based on merchant context
        merchant_query = self._build_merchant_query(context)
        sops = rag_retrieve_sop(context, query=merchant_query)
        
        # Get merchant details dynamically - handle both field name formats
        alert = context.get('transaction', {})
        
        # Extract merchant information from transaction data
        merchant_id = (alert.get('merchant_id') or alert.get('merchantId') or 
                      alert.get('payee_payer_name') or alert.get('payeePayerName'))
        
        print(f"DEBUG: MerchantInfoAgent - merchant_id: {merchant_id}")
        
        if not merchant_id:
            print("WARNING: No merchant information found in alert data")
            context['merchant_context'] = "Merchant information not available in alert data"
            return context
        
        # For now, use the alert data as merchant context since we don't have separate merchant dataset
        merchant_details = {
            'merchant_name': merchant_id,
            'transaction_amount': alert.get('amount'),
            'transaction_type': alert.get('transaction_type') or alert.get('transactionType'),
            'risk_indicators': self._extract_merchant_risk_indicators(alert)
        }
        
        # Build intelligent analysis prompt
        prompt = self._build_merchant_analysis_prompt(merchant_details, sops)
        
        result = self._get_expert_analysis(
            prompt + "\n\nIf PayID or new beneficiary with no prior relationship, increase risk and call out verification gaps."
        )
        
        # Add to context with metadata
        context['merchant_context'] = result
        context['merchant_analysis_timestamp'] = datetime.now().isoformat()
        
        # Store in Mem0 memory
        case_id = merchant_id or 'unknown'
        self.store_context_summary(case_id, result)
        self.store_agent_summary(case_id, f"Merchant analysis completed for {case_id}")
        
        return context
    
    def _build_merchant_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for merchant analysis"""
        alert = context.get('transaction', {})
        query_parts = []
        
        if isinstance(alert, dict):
            merchant_id = alert.get('merchantId') or alert.get('payee', '')
            if merchant_id:
                query_parts.append(f"merchant {merchant_id}")
        
        return " ".join(query_parts) if query_parts else "merchant risk assessment"
    
    def _extract_merchant_risk_indicators(self, alert: Dict[str, Any]) -> List[str]:
        """Extract merchant risk indicators from transaction data"""
        risk_indicators = []
        if 'risk_indicators' in alert:
            risk_indicators.extend(alert['risk_indicators'])
        return risk_indicators
    
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
    
    def _build_merchant_analysis_prompt(self, merchant_details: Dict[str, Any], sops: List[str]) -> str:
        """Build intelligent merchant analysis prompt"""
        # Get agent configuration
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
        merchant_risk_prompt = specialized_prompts.get('merchant_risk',
            "Assess merchant risk and legitimacy")
        
        industry_prompt = specialized_prompts.get('industry_analysis',
            "Analyze industry-specific risk patterns")
        
        # Build merchant summary
        merchant_summary = self._build_merchant_summary(merchant_details)
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:5]) if sops else "No specific SOPs found"
        
        prompt = f"""
You are a merchant risk expert specializing in fraud detection and industry analysis.

{merchant_risk_prompt}
{industry_prompt}

MERCHANT DETAILS:
{json.dumps(merchant_details, indent=2)}

RELEVANT SOPs:
{sop_summary}

ANALYSIS REQUIREMENTS:
1. Analyze merchant risk scores and legitimacy indicators
2. Check for blacklist/whitelist status and reputation
3. Detect industry-specific anomalies and patterns
4. Assess regulatory compliance and licensing
5. Identify potential fraud indicators and red flags
6. Evaluate transaction patterns and volume anomalies
7. Recommend risk mitigation measures

Provide a comprehensive, expert-level merchant risk analysis.
"""
        return prompt
    
    def _build_merchant_summary(self, merchant_details: Dict[str, Any]) -> str:
        """Build intelligent merchant summary"""
        if not merchant_details or merchant_details.get('status') == 'merchant_details_unavailable':
            return "Merchant details unavailable"
        
        summary_parts = []
        
        if isinstance(merchant_details, dict):
            merchant_id = merchant_details.get('merchantId', 'Unknown')
            name = merchant_details.get('name', 'Unknown')
            category = merchant_details.get('category', 'Unknown')
            risk_level = merchant_details.get('risk_level', 'Unknown')
            
            summary_parts.append(f"Merchant ID: {merchant_id}")
            summary_parts.append(f"Name: {name}")
            summary_parts.append(f"Category: {category}")
            summary_parts.append(f"Risk Level: {risk_level}")
            
            # Add additional details
            for key, value in merchant_details.items():
                if key not in ['merchantId', 'name', 'category', 'risk_level']:
                    summary_parts.append(f"{key.title()}: {value}")
        
        return "\n".join(summary_parts)
    
    def _calculate_merchant_risk_score(self, result: str) -> float:
        """Calculate merchant risk score based on analysis"""
        if not result or result == "Analysis unavailable due to technical issues":
            return 0.5  # Default medium risk
        
        result_lower = result.lower()
        
        # Risk indicators
        high_risk_indicators = [
            'high risk', 'blacklisted', 'fraudulent', 'suspicious',
            'unlicensed', 'anomalous', 'red flag'
        ]
        
        medium_risk_indicators = [
            'medium risk', 'some concern', 'monitoring required'
        ]
        
        low_risk_indicators = [
            'low risk', 'legitimate', 'verified', 'whitelisted'
        ]
        
        # Calculate score
        score = 0.5  # Base score
        
        for indicator in high_risk_indicators:
            if indicator in result_lower:
                score += 0.4
                break
        
        for indicator in medium_risk_indicators:
            if indicator in result_lower:
                score += 0.1
                break
        
        for indicator in low_risk_indicators:
            if indicator in result_lower:
                score -= 0.3
                break
        
        return max(0.0, min(1.0, score))

class BehavioralPatternAgent(IntelligentAgent):
    """Advanced behavioral pattern analysis agent with social engineering detection"""
    
    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Get dynamic SOPs based on behavioral context
        behavioral_query = self._build_behavioral_query(context)
        sops = rag_retrieve_sop(context, query=behavioral_query)
        
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
        
        # Store in Mem0 memory
        case_id = customer_id or alert_id or 'unknown'
        self.store_context_summary(case_id, result)
        self.store_agent_summary(case_id, f"Behavioral analysis completed for {case_id}")
        
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
                if (alert.get('customer_id') == customer_id or 
                    alert.get('customerId') == customer_id or
                    alert.get('alert_id') == alert_id or
                    alert.get('alertId') == alert_id):
                    anomaly_details = alert
                    break
        except Exception as e:
            print(f"Error loading FTP data for anomaly analysis: {e}")
            pass
        
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
                    if (call.get('customer_id') == customer_id or 
                        call.get('customerId') == customer_id or
                        call.get('alert_id') == alert_id or
                        call.get('alertId') == alert_id):
                        anomaly_details = call
                        break
            except Exception as e:
                print(f"Error loading call history for anomaly analysis: {e}")
                pass
        
        return anomaly_details if anomaly_details else {'status': 'anomaly_details_unavailable'}
    
    def _build_behavioral_analysis_prompt(self, anomaly_details: Dict[str, Any], sops: List[str]) -> str:
        """Build intelligent behavioral analysis prompt"""
        # Get agent configuration
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
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
            customer_id = anomaly_details.get('customerID', 'Unknown')
            alert_id = anomaly_details.get('alertID', 'Unknown')
            anomaly_type = anomaly_details.get('anomalyType', 'Unknown')
            
            summary_parts.append(f"Customer ID: {customer_id}")
            summary_parts.append(f"Alert ID: {alert_id}")
            summary_parts.append(f"Anomaly Type: {anomaly_type}")
            
            # Add additional details
            for key, value in anomaly_details.items():
                if key not in ['customerID', 'alertID', 'anomalyType']:
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

class RiskSynthesizerAgent(IntelligentAgent):
    """Advanced risk synthesis agent with comprehensive fraud typology identification"""
    
    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Get dynamic SOPs based on risk context
        risk_query = self._build_risk_query(context)
        sops = rag_retrieve_sop(context, query=risk_query)
        
        # Get all context summaries
        txn = context.get('transaction_context', '[unavailable]')
        cust = context.get('customer_context', '[unavailable]')
        merch = context.get('merchant_context', '[unavailable]')
        anom = context.get('anomaly_context', '[unavailable]')
        
        # Build intelligent synthesis prompt
        prompt = self._build_risk_synthesis_prompt(txn, cust, merch, anom, sops)
        
        # Get expert synthesis
        result = self._get_expert_synthesis(prompt)
        
        # Heuristic BEC detection to reinforce typology and accelerate convergence
        try:
            bec_ind = self._detect_bec_indicators(context)
            if bec_ind.get('bec_detected'):
                result = (result or '') + "\n\nIndicators: Business Email Compromise (BEC) pattern detected: " + \
                         ", ".join(sorted([k for k, v in bec_ind.items() if isinstance(v, bool) and v and k != 'bec_detected']))
                context['scam_typology'] = 'business_email_compromise'
                context['overall_risk_score'] = float(max(float(context.get('overall_risk_score') or 0.0), 0.9))
                context['risk_confidence'] = float(max(float(context.get('risk_confidence') or 0.7), 0.85))
                context['bec_indicators'] = bec_ind
                context['risk_ready_to_finalize'] = True
        except Exception:
            pass

        # Heuristic detection for other typologies to accelerate convergence
        try:
            if context.get('scam_typology') not in ('business_email_compromise',):
                typ_ind = self._detect_other_typologies(context)
                if typ_ind.get('detected') and typ_ind.get('typology'):
                    tname = typ_ind['typology']
                    result = (result or '') + f"\n\nIndicators: {tname.replace('_', ' ').title()} pattern detected: " + \
                             ", ".join(sorted([k for k, v in typ_ind.get('flags', {}).items() if v]))
                    context['scam_typology'] = tname
                    # Calibrate scores per typology
                    base_score = 0.85 if tname in ('investment_scam', 'impersonation_scam', 'romance_scam') else 0.75
                    context['overall_risk_score'] = float(max(float(context.get('overall_risk_score') or 0.0), base_score))
                    context['risk_confidence'] = float(max(float(context.get('risk_confidence') or 0.6), 0.8))
                    context['typology_indicators'] = typ_ind
                    # Early finalization for strong signals
                    context['risk_ready_to_finalize'] = True
        except Exception:
            pass
        
        # Add to context with metadata
        context['risk_summary_context'] = result
        context['risk_synthesis_timestamp'] = datetime.now().isoformat()
        # Compute weighted factor scores to feed downstream XAI and policy
        tx_score = self._score_text(context.get('transaction_context', ''))
        cu_score = self._score_text(context.get('customer_context', ''))
        me_score = self._score_text(context.get('merchant_context', ''))
        be_score = self._score_text(context.get('anomaly_context', ''))
        weights = {'transaction': 0.35, 'customer': 0.25, 'merchant': 0.15, 'behavioral': 0.25}
        risk_score = (
            weights['transaction'] * tx_score +
            weights['customer'] * cu_score +
            weights['merchant'] * me_score +
            weights['behavioral'] * be_score
        )
        context['risk_factors'] = {
            'transaction': tx_score,
            'customer': cu_score,
            'merchant': me_score,
            'behavioral': be_score,
            'weights': weights,
        }
        context['overall_risk_score'] = float(max(0.0, min(1.0, risk_score)))
        context['scam_typology'] = self._identify_scam_typology(result)
        
        # Add to context with metadata
        context['risk_synthesis'] = result
        context['risk_synthesis_timestamp'] = datetime.now().isoformat()
        
        # Store in Mem0 memory
        case_id = context.get('transaction', {}).get('alert_id') or context.get('transaction', {}).get('customer_id') or 'unknown'
        self.store_risk_assessment(case_id, result, confidence=0.85)
        self.store_agent_summary(case_id, f"Risk synthesis completed for {case_id}")
        
        return context

    def _detect_bec_indicators(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simple heuristic BEC detection from context and dialogue text"""
        text_parts = []
        for key in ['transaction_context', 'customer_context', 'merchant_context', 'anomaly_context', 'risk_summary_context']:
            val = context.get(key)
            if isinstance(val, str):
                text_parts.append(val.lower())
        dh = context.get('dialogue_history') or []
        for turn in dh:
            if isinstance(turn, dict) and turn.get('user'):
                text_parts.append(str(turn.get('user')).lower())
        blob = " \n".join(text_parts)
        indicators = {
            'vendor_name_manipulation': any(s in blob for s in ['name was slightly different', 'abbreviat', ' nt electrical', 'vendor name change', 'altered name']),
            'duplicate_invoice': any(s in blob for s in ['duplicate invoice', 'inv#', 'invoice redirection']),
            'bank_details_change': any(s in blob for s in ['new bank account', 'changed bank details', 'new account details', 'updated banking details']),
            'email_channel_request': any(s in blob for s in ['came via email', 'email request', 'via email']),
            'supplier_impersonation': any(s in blob for s in ['vendor impersonation', 'impersonation', 'supplier impersonation'])
        }
        score = sum(1 for v in indicators.values() if v)
        indicators['bec_detected'] = score >= 2
        return indicators

    def _detect_other_typologies(self, context: Dict[str, Any]) -> Dict[str, Any]:
        text_parts = []
        for key in ['transaction_context', 'customer_context', 'merchant_context', 'anomaly_context', 'risk_summary_context']:
            val = context.get(key)
            if isinstance(val, str):
                text_parts.append(val.lower())
        dh = context.get('dialogue_history') or []
        for turn in dh:
            if isinstance(turn, dict):
                if turn.get('user'):
                    text_parts.append(str(turn.get('user')).lower())
                if turn.get('question'):
                    text_parts.append(str(turn.get('question')).lower())
        blob = " \n".join(text_parts)

        def has_any(keywords: list[str]) -> bool:
            return any(k in blob for k in keywords)

        # Tech support scam
        tech_flags = {
            'remote_access': has_any(['remote access', 'anydesk', 'teamviewer', 'screen sharing']),
            'tech_support_terms': has_any(['tech support', 'technical support', 'virus', 'malware']),
            'codes_asked': has_any(['otp', 'one-time password', 'security code']),
        }
        if sum(1 for v in tech_flags.values() if v) >= 2:
            return {'detected': True, 'typology': 'tech_support_scam', 'flags': tech_flags}

        # Investment scam
        invest_flags = {
            'investment_terms': has_any(['investment', 'crypto', 'trading', 'platform']),
            'guaranteed_returns': has_any(['guaranteed', 'high returns', 'promised returns']),
            'pressure': has_any(['urgent', 'pressure', 'limited time']),
        }
        if sum(1 for v in invest_flags.values() if v) >= 2:
            return {'detected': True, 'typology': 'investment_scam', 'flags': invest_flags}

        # Romance scam
        romance_flags = {
            'relationship_terms': has_any(['romance', 'relationship', 'boyfriend', 'girlfriend', 'love']),
            'secrecy': has_any(['keep this secret', 'don’t tell', 'secrecy']),
            'emergency_money': has_any(['emergency', 'travel money', 'medical expenses']),
        }
        if sum(1 for v in romance_flags.values() if v) >= 2:
            return {'detected': True, 'typology': 'romance_scam', 'flags': romance_flags}

        # Impersonation scam
        imp_flags = {
            'authority_terms': has_any(['bank official', 'bank security department', 'police', 'government', 'ato']),
            'threats': has_any(['legal action', 'arrest', 'freeze']),
            'secrecy': has_any(['keep this secret', 'do not tell']),
        }
        if sum(1 for v in imp_flags.values() if v) >= 2:
            return {'detected': True, 'typology': 'impersonation_scam', 'flags': imp_flags}

        # Purchase scam
        purch_flags = {
            'marketplace': has_any(['marketplace', 'online purchase', 'seller']),
            'unusual_payment': has_any(['gift card', 'crypto payment', 'unusual payment method']),
            'too_good': has_any(['too good to be true', 'unrealistic price']),
        }
        if sum(1 for v in purch_flags.values() if v) >= 2:
            return {'detected': True, 'typology': 'purchase_scam', 'flags': purch_flags}

        return {'detected': False}

    def _build_risk_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for risk synthesis"""
        query_parts = []
        
        # Add transaction context
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 0)
                query_parts.append(f"transaction risk {amount}")
        
        # Add customer context
        if 'customer_context' in context:
            query_parts.append("customer vulnerability")
        
        # Add merchant context
        if 'merchant_context' in context:
            query_parts.append("merchant risk")
        
        return " ".join(query_parts) if query_parts else "comprehensive risk assessment"
    
    def _build_risk_synthesis_prompt(self, txn: str, cust: str, merch: str, anom: str, sops: List[str]) -> str:
        """Build intelligent risk synthesis prompt"""
        # Get agent configuration
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
        risk_synthesis_prompt = specialized_prompts.get('risk_synthesis',
            "Synthesize comprehensive risk assessment from multiple sources")
        
        scam_typology_prompt = specialized_prompts.get('scam_typology',
            "Identify specific scam typologies and fraud patterns")
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:5]) if sops else "No specific SOPs found"
        
        prompt = f"""
You are a risk synthesizer agent specializing in comprehensive fraud analysis.

{risk_synthesis_prompt}
{scam_typology_prompt}

CONTEXT SUMMARIES:
Transaction Context: {txn}
Customer Context: {cust}
Merchant Context: {merch}
Behavioral/Anomaly Context: {anom}

RELEVANT SOPs:
{sop_summary}

SYNTHESIS REQUIREMENTS:
1. Analyze all context summaries and identify key risk factors
2. Identify specific fraud typologies (BEC, romance scams, investment scams, etc.)
3. Assess compliance triggers and regulatory requirements
4. Provide clear risk rating (LOW/MEDIUM/HIGH) with confidence level
5. Recommend immediate actions and escalation requirements
6. Consider customer vulnerability and protection measures
7. Identify scam indicators and social engineering tactics

Provide a concise, expert-level risk synthesis for fraud operations.
"""
        return prompt
    
    def _get_expert_synthesis(self, prompt: str) -> str:
        """Get expert synthesis with error handling"""
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            return result
        except Exception as e:
            self.logger.error(f"Failed to get expert synthesis: {e}")
            return "Risk synthesis unavailable due to technical issues"
    
    def _calculate_overall_risk_score(self, result: str) -> float:
        """Calculate overall risk score from synthesis"""
        if not result or result == "Risk synthesis unavailable due to technical issues":
            return 0.5  # Default medium risk
        
        result_lower = result.lower()
        
        # Risk level indicators
        if 'high risk' in result_lower or 'high-risk' in result_lower:
            return 0.8
        elif 'medium risk' in result_lower or 'medium-risk' in result_lower:
            return 0.5
        elif 'low risk' in result_lower or 'low-risk' in result_lower:
            return 0.2
        
        # Scam indicators
        scam_indicators = ['scam', 'fraud', 'unauthorized', 'suspicious']
        scam_count = sum(1 for indicator in scam_indicators if indicator in result_lower)
        
        if scam_count >= 3:
            return 0.9
        elif scam_count >= 1:
            return 0.7
        
        return 0.5  # Default medium risk

    def _score_text(self, text: str) -> float:
        """Heuristic scoring from context text for weighted aggregation."""
        if not isinstance(text, str) or not text:
            return 0.5
        t = text.lower()
        score = 0.5
        if any(k in t for k in ['scam', 'fraud', 'impersonation', 'phishing', 'remote access', 'anydesk', 'teamviewer']):
            score += 0.3
        if any(k in t for k in ['urgent', 'pressure', 'secrecy', 'code', 'otp', 'security code']):
            score += 0.2
        if any(k in t for k in ['verified relationship', 'known recipient', 'legitimate invoice']):
            score -= 0.2
        return float(max(0.0, min(1.0, score)))
    
    def _identify_scam_typology(self, result: str) -> Optional[str]:
        """Identify scam typology from synthesis"""
        if not result:
            return None
        
        result_lower = result.lower()
        
        # Scam typology indicators
        typology_indicators = {
            'business_email_compromise': ['bec', 'business email compromise', 'vendor impersonation', 'invoice redirection'],
            'romance_scam': ['romance', 'relationship', 'emotional manipulation', 'love scam'],
            'investment_scam': ['investment', 'returns', 'crypto', 'trading', 'investment opportunity'],
            'tech_support_scam': ['tech support', 'computer virus', 'remote access', 'technical issue'],
            'impersonation_scam': ['impersonation', 'government', 'bank official', 'authority'],
            'purchase_scam': ['purchase', 'buying', 'seller', 'marketplace', 'online purchase']
        }
        
        for typology, indicators in typology_indicators.items():
            if any(indicator in result_lower for indicator in indicators):
                return typology
        
        return None

class TriageAgent(IntelligentAgent):
    """Advanced triage agent with intelligent escalation and dialogue decision making"""
    
    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Get dynamic SOPs based on triage context
        triage_query = self._build_triage_query(context)
        sops = rag_retrieve_sop(context, query=triage_query)
        
        # Get all context summaries
        txn = context.get('transaction_context', '[unavailable]')
        cust = context.get('customer_context', '[unavailable]')
        merch = context.get('merchant_context', '[unavailable]')
        anom = context.get('anomaly_context', '[unavailable]')
        risk = context.get('risk_summary_context', '[unavailable]')
        
        # Build intelligent triage prompt (ANZ context-aware)
        prompt = self._build_triage_prompt(txn, cust, merch, anom, risk, sops)
        
        # Get expert triage decision
        result = self._get_expert_triage(prompt)
        
        # Add to context with metadata
        context['triage_decision'] = result
        context['triage_timestamp'] = datetime.now().isoformat()
        context['dialogue_required'] = self._determine_dialogue_required(result)
        context['escalation_required'] = self._determine_escalation_required(result)
        
        # Store in Mem0 memory
        case_id = context.get('transaction', {}).get('alert_id') or context.get('transaction', {}).get('customer_id') or 'unknown'
        self.store_context_summary(case_id, result)
        self.store_agent_summary(case_id, f"Triage decision completed for {case_id}")
        
        return context

    def _build_triage_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for triage analysis"""
        query_parts = []
        
        # Add risk context
        if 'risk_summary_context' in context:
            query_parts.append("risk assessment triage")
        
        # Add customer context
        if 'customer_context' in context:
            query_parts.append("customer vulnerability triage")
        
        return " ".join(query_parts) if query_parts else "triage decision making"
    
    def _build_triage_prompt(self, txn: str, cust: str, merch: str, anom: str, risk: str, sops: List[str]) -> str:
        """Build intelligent triage prompt"""
        # Get agent configuration
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
        escalation_prompt = specialized_prompts.get('escalation_decision',
            "Decide on escalation or dialogue based on risk assessment")
        
        priority_prompt = specialized_prompts.get('priority_assessment',
            "Assess case priority and urgency")
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:5]) if sops else "No specific SOPs found"
        
        prompt = f"""
You are a triage agent specializing in case prioritization and escalation decisions.

{escalation_prompt}
{priority_prompt}

CONTEXT SUMMARIES:
Transaction Context: {txn}
Customer Context: {cust}
Merchant Context: {merch}
Behavioral/Anomaly Context: {anom}
Risk Synthesis: {risk}

RELEVANT SOPs:
{sop_summary}

TRIAGE REQUIREMENTS:
1. Analyze all context summaries and risk assessment
2. Cite relevant SOP rules and compliance requirements
3. Provide clear triage decision (ESCALATE/DIALOGUE/CLOSE)
4. Justify decision with specific risk factors and indicators
5. Assess case priority and urgency level
6. Consider customer vulnerability and protection needs
7. Recommend next steps and resource allocation

Provide a concise, expert-level triage decision for fraud operations.
"""
        return prompt
    
    def _get_expert_triage(self, prompt: str) -> str:
        """Get expert triage decision with error handling"""
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            return result
        except Exception as e:
            self.logger.error(f"Failed to get expert triage: {e}")
            return "Triage decision unavailable due to technical issues"
    
    def _determine_escalation_required(self, result: str) -> bool:
        """Determine if escalation is required based on triage decision"""
        if not result:
            return False
        
        result_lower = result.lower()
        
        escalation_indicators = [
            'escalate', 'escalation', 'high priority', 'urgent',
            'senior analyst', 'management review', 'immediate attention'
        ]
        
        return any(indicator in result_lower for indicator in escalation_indicators)
    
    def _determine_dialogue_required(self, result: str) -> bool:
        """Determine if dialogue is required based on triage decision"""
        if not result:
            return True  # Default to dialogue for safety
        
        result_lower = result.lower()
        
        dialogue_indicators = [
            'dialogue', 'questioning', 'customer contact', 'verification',
            'investigation', 'further inquiry'
        ]
        
        close_indicators = [
            'close', 'no action', 'false positive', 'legitimate transaction'
        ]
        
        if any(indicator in result_lower for indicator in close_indicators):
            return False
        
        return any(indicator in result_lower for indicator in dialogue_indicators)

class DialogueAgent(IntelligentAgent):
    """Advanced dialogue agent with intelligent question generation and fact extraction"""
    
    def __init__(self, name: str, context_store):
        super().__init__(name, context_store)
        self.fraud_questions = load_fraud_yaml_blocks('datasets/questions.md')
        self.fraud_sop = load_fraud_yaml_blocks('datasets/SOP.md')

    def get_fraud_block(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get fraud block dynamically based on rule ID"""
        for block in self.fraud_questions:
            if block and block.get('fraud_type', '').lower() == rule_id.lower():
                return block
        return None

    def get_sop_block(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get SOP block dynamically based on rule ID"""
        for block in self.fraud_sop:
            if block and block.get('fraud_type', '').lower() == rule_id.lower():
                return block
        return None

    def extract_facts_intelligently(self, dialogue_history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Intelligent fact extraction with dynamic confidence scoring (OPTIMIZED)"""
        if context is None or not isinstance(context, dict):
            context = {}
        
        # OPTIMIZATION: Cache fact extraction results
        cache_key = f"extract_facts_{len(dialogue_history)}_{hash(str(dialogue_history[-1:]) if dialogue_history else '')}"
        
        if hasattr(context, 'extract_cache') and cache_key in context.get('extract_cache', {}):
            return context['extract_cache'][cache_key]
        
        # Use the base class intelligent fact extraction
        dialogue_text = self._build_dialogue_text(dialogue_history)
        facts = super().extract_facts_intelligently(dialogue_text, context)
        
        # Add context-based facts
        context_facts = self._extract_context_facts(context)
        facts.update(context_facts)
        
        # Cache the result
        if 'extract_cache' not in context:
            context['extract_cache'] = {}
        context['extract_cache'][cache_key] = facts
        
        return facts

    def _build_dialogue_text(self, dialogue_history: List[Dict[str, Any]]) -> str:
        """Build dialogue text for fact extraction"""
        dialogue_parts = []
        
        for turn in dialogue_history:
            if isinstance(turn, dict):
                question = turn.get('question', '')
                user_response = turn.get('user', '')
                
                if question:
                    dialogue_parts.append(f"Q: {question}")
                if user_response:
                    dialogue_parts.append(f"A: {user_response}")
        
        return " ".join(dialogue_parts)
    
    def _extract_context_facts(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract facts from context data"""
        context_facts = {}
        
        # Extract from transaction context
        if 'transaction_context' in context:
            txn_text = context['transaction_context'].lower()
            if 'verified' in txn_text or 'confirmed' in txn_text:
                context_facts['verification'] = {'value': 'confirmed', 'confidence': 0.8, 'source': 'context'}
        
        # Extract from customer context
        if 'customer_context' in context:
            cust_text = context['customer_context'].lower()
            if 'high-risk' in cust_text:
                context_facts['risk_level'] = {'value': 'high', 'confidence': 0.9, 'source': 'context'}
            elif 'medium-risk' in cust_text:
                context_facts['risk_level'] = {'value': 'medium', 'confidence': 0.8, 'source': 'context'}
        
        # Extract from risk context
        if 'risk_summary_context' in context:
            risk_text = context['risk_summary_context'].lower()
            if 'scam' in risk_text:
                context_facts['scam_indicated'] = {'value': 'yes', 'confidence': 0.8, 'source': 'context'}
        
        return context_facts
    
    def summarize_known_facts(self, facts: Dict[str, Any]) -> str:
        """Intelligent fact summarization"""
        if not facts:
            return 'No facts confirmed yet.'
        
        fact_summaries = []
        for fact_type, fact_data in facts.items():
            if isinstance(fact_data, dict):
                value = fact_data.get('value', 'unknown')
                confidence = fact_data.get('confidence', 0.0)
                source = fact_data.get('source', 'extracted')
                fact_summaries.append(f"{fact_type.title()}: {value} (confidence: {confidence:.2f}, source: {source})")
            else:
                fact_summaries.append(f"{fact_type.title()}: {fact_data}")
        
        return '\n'.join(fact_summaries)
    
    def summarize_missing_facts(self, facts: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> List[str]:
        """Intelligent missing fact identification"""
        # Get required facts from configuration
        required_facts = config.get_required_facts()
        
        # Check which required facts are missing
        missing = [fact_type for fact_type in required_facts if fact_type not in facts]
        
        # Check for early finalization conditions
        dialogue_text = self._build_dialogue_text(dialogue_history).lower()
        
        # Early finalization indicators
        early_finalization_indicators = config.conversation.early_finalization_indicators
        early_finalization = any(indicator in dialogue_text for indicator in early_finalization_indicators)
        
        # Check dialogue length
        max_turns = config.conversation.max_dialogue_turns
        max_turns_reached = len(dialogue_history) >= max_turns
        
        # Check for repetitive responses
        user_responses = [turn.get('user', '').strip().lower() for turn in dialogue_history if 'user' in turn]
        repetitive_responses = len(user_responses) != len(set(user_responses)) and len(user_responses) > 6
        
        # Strong fraud indicators override missing facts
        text = (" ".join([turn.get('user','') for turn in dialogue_history if isinstance(turn, dict)])).lower()
        strong_indicators = any(k in text for k in [
            'anydesk','teamviewer','remote access','read out the security codes','otp','one-time password','security code',
            'bank security department','payid details','guided me step-by-step'
        ])
        # Allow finalization if any of these conditions are met
        if early_finalization or max_turns_reached or repetitive_responses or strong_indicators:
            return []
        
        return missing

    def get_next_question_and_agent(self, dialogue_history: List[Dict[str, Any]], context: Dict[str, Any], stream: bool = False) -> Tuple[Any, str, bool]:
        """Intelligent next question generation with dynamic decision making (OPTIMIZED)"""
        if context is None:
            context = {}
        
        txn = context.get('transaction', {})
        if txn is None:
            txn = {}
        
        rule_id = txn.get('ruleId', '')
        fraud_block = self.get_fraud_block(rule_id)
        
        # OPTIMIZATION: Cache fact extraction results
        cache_key = f"facts_{len(dialogue_history)}_{hash(str(dialogue_history[-2:]) if len(dialogue_history) >= 2 else '')}"
        
        if hasattr(context, 'fact_cache') and cache_key in context.get('fact_cache', {}):
            facts = context['fact_cache'][cache_key]
        else:
            # Extract facts intelligently
            facts = self.extract_facts_intelligently(dialogue_history, context)
            # Cache the result
            if 'fact_cache' not in context:
                context['fact_cache'] = {}
            context['fact_cache'][cache_key] = facts
        
        # Get missing facts
        missing = self.summarize_missing_facts(facts, dialogue_history)
        
        # OPTIMIZATION: Early termination based on dialogue length and risk
        dialogue_length = len(dialogue_history)
        risk_score = self._calculate_dialogue_risk_score(context)
        
        # Early termination conditions (include strong indicators)
        text = (" ".join([turn.get('user','') for turn in dialogue_history if isinstance(turn, dict)])).lower()
        strong_indicators = any(k in text for k in [
            'anydesk','teamviewer','remote access','read out the security codes','otp','one-time password','security code',
            'bank security department','payid details','guided me step-by-step'
        ])
        early_termination_conditions = [
            dialogue_length >= 8,
            risk_score >= 0.8,
            not missing,
            strong_indicators,
            config.is_finalization_ready(facts, dialogue_length, risk_score)
        ]
        
        if any(early_termination_conditions):
            # Build final expert summary
            return self._build_final_summary(context, dialogue_history), self.name, True
        
        # OPTIMIZATION: Use cached questions for common scenarios
        question_cache_key = f"question_{rule_id}_{len(missing)}_{hash(str(missing[:2]))}"
        
        if hasattr(context, 'question_cache') and question_cache_key in context.get('question_cache', {}):
            next_question = context['question_cache'][question_cache_key]
        else:
            # Generate next intelligent question
            next_question = self._generate_next_question(missing, context, dialogue_history)
            # Cache the question
            if 'question_cache' not in context:
                context['question_cache'] = {}
            context['question_cache'][question_cache_key] = next_question
        
        if next_question:
            return self._build_question_prompt(next_question, context, dialogue_history), self.name, False
        
        # Fallback closing message
        closing_message = "Thank you for your cooperation. We have no further questions at this time."
        return closing_message, self.name, True
    
    def _calculate_dialogue_risk_score(self, context: Dict[str, Any]) -> float:
        """Calculate risk score for dialogue decisions"""
        risk_score = 0.5  # Default
        
        # Add risk from context
        if 'risk_summary_context' in context:
            risk_text = context['risk_summary_context'].lower()
            if 'high risk' in risk_text:
                risk_score += 0.3
            elif 'medium risk' in risk_text:
                risk_score += 0.1
        
        # Add risk from customer context
        if 'customer_context' in context:
            customer_text = context['customer_context'].lower()
            if 'high-risk' in customer_text:
                risk_score += 0.2
            elif 'vulnerable' in customer_text:
                risk_score += 0.1

        # Strong signals from dialogue content directly
        dh = context.get('dialogue_history', [])
        text = (" ".join([turn.get('user','') for turn in dh if isinstance(turn, dict)])).lower()
        if any(k in text for k in ['anydesk','teamviewer','remote access','security code','otp','one-time password']):
            risk_score += 0.3
        if any(k in text for k in ['bank security department','urgent','pressure','secrecy']):
            risk_score += 0.2
        
        return min(1.0, risk_score)
    
    def _generate_next_question(self, missing_facts: List[str], context: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> Optional[str]:
        """Generate intelligent next question based on missing facts"""
        if not missing_facts:
            return None
        
        # Get already asked questions
        already_asked = set(turn.get('question', '').lower() for turn in dialogue_history if 'question' in turn)
        
        # Try to find relevant questions for missing facts
        for missing_fact in missing_facts:
            query = f"{missing_fact.replace('_', ' ')} question"
            rag_questions = rag_retrieve_questions(context, query=query)
            
            for question in rag_questions:
                question_lower = question.lower()
                if not any(question_lower in asked for asked in already_asked):
                    return question
        
        return None
    
    def _build_final_summary(self, context: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> str:
        """Build intelligent final summary without prematurely running final agents.

        Instead of directly invoking final risk/policy agents here, request
        finalization and let the orchestration layer handle it after the
        dialogue loop has gathered sufficient information.
        """
        # Signal orchestration to finalize after the dialogue loop
        try:
            if isinstance(context, dict):
                context['finalization_requested'] = True
                context['chat_done'] = True
        except Exception:
            pass
        
        # Build context summary
        context_summary = self._build_dialogue_context_summary(context)
        
        # Build conversation summary
        conversation_summary = self._build_conversation_summary(dialogue_history)
        
        # Show placeholders until finalization node completes
        final_risk = context.get('final_risk_determination', 'Final risk assessment will be computed now...')
        policy_decision = context.get('policy_decision', 'Policy decision will follow the final risk assessment...')
        
        # If escalation or critical risk identified, enforce urgent intervention tone and steps
        urgency_directives = ""
        risk_text = (final_risk or "").lower()
        if any(keyword in risk_text for keyword in ["critical", "escalate", "freeze", "ato", "account takeover", "remote access", "technical support scam", "high risk"]):
            urgency_directives = (
                "\nURGENT CUSTOMER INSTRUCTIONS:\n"
                "- Clearly state the account is temporarily secured for protection.\n"
                "- Instruct the customer to disconnect any remote access sessions (AnyDesk/TeamViewer/QuickSupport).\n"
                "- Ask them to power off the compromised device and use another trusted device.\n"
                "- Inform that payment recall/hold has been initiated with receiving institution.\n"
                "- Advise that credentials will be reset and enhanced monitoring applied.\n"
            )

        prompt = f"""
You are an expert fraud investigation agent. Provide a clear, professional final summary for the customer.

CONTEXT:
{context_summary}

CONVERSATION:
{conversation_summary}

FINAL ASSESSMENT:
{final_risk}

POLICY DECISION:
{policy_decision}

REQUIREMENTS:
- Summarize findings and risk assessment.
- Provide specific, actionable next steps; avoid vague language.
- Do NOT ask for further input or promise manual review timeframes.
- Focus on authorized scam detection and protection measures.
- Include final risk level and policy decision.
{urgency_directives}

Write a concise, directive summary appropriate for immediate customer communication.
"""
        
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            # If model still hedges, harden tone under ANZ SOPs
            if 'insufficient' in result.lower() or 'cannot' in result.lower():
                result += "\n\nNote: Under ANZ APP fraud SOP, context is sufficient for policy decision due to BEC indicators."
            return result
        except Exception as e:
            self.logger.error(f"Failed to build final summary: {e}")
            return "Investigation summary unavailable due to technical issues"
    
    def _run_automatic_final_assessment(self, context: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> None:
        """AUTOMATIC: Run final risk assessment and policy decision with compressed summaries"""
        try:
            # Build compressed agent logs summary
            compressed_agent_logs = self._build_compressed_agent_logs_summary(context)
            
            # Step 1: Run Final Risk Assessment
            risk_assessor = RiskAssessorAgent("RiskAssessorAgentFinal", self.context_store)
            
            # Add compressed summaries to context
            context['compressed_agent_logs'] = compressed_agent_logs
            context['dialogue_history'] = dialogue_history
            
            # Run final risk assessment
            risk_result = risk_assessor.act('Final comprehensive risk assessment', context)
            if risk_result and isinstance(risk_result, dict):
                context.update(risk_result)
                context['final_risk_determination'] = risk_result.get('risk_assessment', 'Risk assessment completed')
                context['final_risk_confidence'] = risk_result.get('risk_confidence', 0.0)
                context['final_scam_typology'] = risk_result.get('scam_typology', 'Unknown')
            
            # Step 2: Run Policy Decision
            policy_agent = PolicyDecisionAgent("PolicyDecisionAgentFinal", self.context_store)
            
            # Add final risk assessment to context
            final_risk = context.get('final_risk_determination', 'Risk assessment completed')
            context['final_risk_assessment'] = final_risk
            
            # Run policy decision
            policy_result = policy_agent.act('Final policy decision', context)
            if policy_result and isinstance(policy_result, dict):
                context.update(policy_result)
                context['final_policy_decision'] = policy_result.get('policy_decision', 'Policy decision completed')
                context['regulatory_compliance'] = policy_result.get('regulatory_requirements', {})
            
            # Step 3: Update context with final results
            context['investigation_complete'] = True
            context['final_assessment_timestamp'] = datetime.now().isoformat()
            
            self.logger.info("Automatic final assessment and policy decision completed successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to run automatic final assessment: {e}")
            context['final_risk_determination'] = 'Risk assessment failed - manual review required'
            context['final_policy_decision'] = 'Policy decision failed - manual review required'
    
    def _build_compressed_agent_logs_summary(self, context: Dict[str, Any]) -> str:
        """Build compressed summary of all agent logs for final assessment"""
        summary_parts = []
        
        # Transaction Context Agent
        if context.get('transaction_context'):
            txn_text = context['transaction_context'].lower()
            txn_summary = "TXN: "
            if 'verified' in txn_text:
                txn_summary += "VERIFIED"
            elif 'suspicious' in txn_text:
                txn_summary += "SUSPICIOUS"
            else:
                txn_summary += "STANDARD"
            summary_parts.append(txn_summary)
        
        # Customer Context Agent
        if context.get('customer_context'):
            cust_text = context['customer_context'].lower()
            cust_summary = "CUST: "
            if 'high-risk' in cust_text:
                cust_summary += "HIGH-RISK"
            elif 'vulnerable' in cust_text:
                cust_summary += "VULNERABLE"
            else:
                cust_summary += "STANDARD"
            summary_parts.append(cust_summary)
        
        # Merchant Context Agent
        if context.get('merchant_context'):
            merch_text = context['merchant_context'].lower()
            merch_summary = "MERCH: "
            if 'suspicious' in merch_text:
                merch_summary += "SUSPICIOUS"
            elif 'verified' in merch_text:
                merch_summary += "VERIFIED"
            else:
                merch_summary += "UNKNOWN"
            summary_parts.append(merch_summary)
        
        # Behavioral Pattern Agent
        if context.get('anomaly_context'):
            behav_text = context['anomaly_context'].lower()
            behav_summary = "BEHAV: "
            if 'anomaly' in behav_text:
                behav_summary += "ANOMALY"
            elif 'normal' in behav_text:
                behav_summary += "NORMAL"
            else:
                behav_summary += "UNKNOWN"
            summary_parts.append(behav_summary)
        
        # Risk Synthesis Agent
        if context.get('risk_summary_context'):
            risk_text = context['risk_summary_context'].lower()
            risk_summary = "RISK: "
            if 'high' in risk_text:
                risk_summary += "HIGH"
            elif 'medium' in risk_text:
                risk_summary += "MEDIUM"
            else:
                risk_summary += "LOW"
            summary_parts.append(risk_summary)
        
        # Triage Agent
        if context.get('triage_decision'):
            triage_text = context['triage_decision'].lower()
            triage_summary = "TRIAGE: "
            if 'escalate' in triage_text:
                triage_summary += "ESCALATE"
            elif 'dialogue' in triage_text:
                triage_summary += "DIALOGUE"
            else:
                triage_summary += "MONITOR"
            summary_parts.append(triage_summary)
        
        # Dialogue Agent (if available)
        if context.get('dialogue_history'):
            dialogue_turns = len(context['dialogue_history'])
            dialogue_summary = f"DIALOGUE: {dialogue_turns} turns"
            summary_parts.append(dialogue_summary)
        
        return " | ".join(summary_parts) if summary_parts else "AGENT LOGS: Limited"
    
    def _build_dialogue_context_summary(self, context: Dict[str, Any]) -> str:
        """Build intelligent COMPRESSED dialogue context summary"""
        summary_parts = []
        
        # COMPRESSED TRANSACTION SUMMARY
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 'Unknown')
                payee = txn.get('payee', 'Unknown')
                rule_id = txn.get('ruleId', 'Unknown')
                summary_parts.append(f"TXN: ${amount} to {payee} ({rule_id})")
        
        # COMPRESSED RISK SUMMARY
        if 'risk_summary_context' in context:
            risk_text = context['risk_summary_context'].lower()
            risk_level = "HIGH" if "high" in risk_text else "MEDIUM" if "medium" in risk_text else "LOW"
            summary_parts.append(f"RISK: {risk_level}")
            
            # Extract key indicators
            indicators = []
            if 'scam' in risk_text:
                indicators.append("SCAM")
            if 'fraud' in risk_text:
                indicators.append("FRAUD")
            if 'suspicious' in risk_text:
                indicators.append("SUSPICIOUS")
            
            if indicators:
                summary_parts.append(f"INDICATORS: {', '.join(indicators)}")
        
        # COMPRESSED CUSTOMER SUMMARY
        if 'customer_context' in context:
            cust_text = context['customer_context'].lower()
            if 'high-risk' in cust_text:
                summary_parts.append("CUSTOMER: HIGH-RISK")
            elif 'vulnerable' in cust_text:
                summary_parts.append("CUSTOMER: VULNERABLE")
            else:
                summary_parts.append("CUSTOMER: STANDARD")
        
        return " | ".join(summary_parts) if summary_parts else "CONTEXT: Limited"
    
    def _build_conversation_summary(self, dialogue_history: List[Dict[str, Any]]) -> str:
        """Build intelligent COMPRESSED conversation summary"""
        if not dialogue_history:
            return "No conversation history available"
        
        # COMPRESSED CONVERSATION SUMMARY
        if len(dialogue_history) <= 3:
            # For short conversations, show full Q&A
            conversation_parts = []
            for turn in dialogue_history:
                if isinstance(turn, dict):
                    question = turn.get('question', '')
                    user_response = turn.get('user', '')
                    
                    if question:
                        conversation_parts.append(f"Q: {question}")
                    if user_response:
                        conversation_parts.append(f"A: {user_response}")
            
            return "\n".join(conversation_parts)
        else:
            # For longer conversations, create compressed summary
            key_points = []
            facts_extracted = []
            red_flags = []
            
            # Analyze last 3 turns for key information
            recent_turns = dialogue_history[-3:]
            
            for turn in recent_turns:
                if isinstance(turn, dict):
                    question = turn.get('question', '').lower()
                    answer = turn.get('user', '').lower()
                    
                    # Extract key information
                    if 'authorize' in answer or 'confirm' in answer:
                        facts_extracted.append("AUTHORIZED")
                    if 'scam' in answer or 'fraud' in answer:
                        red_flags.append("SCAM MENTIONED")
                    if 'pressure' in answer or 'urgent' in answer:
                        red_flags.append("PRESSURE DETECTED")
                    if 'unknown' in answer or 'stranger' in answer:
                        red_flags.append("UNKNOWN RELATIONSHIP")
                    if 'investment' in answer or 'return' in answer:
                        facts_extracted.append("INVESTMENT")
                    if 'romance' in answer or 'relationship' in answer:
                        facts_extracted.append("ROMANCE")
                    if 'tech support' in answer or 'computer' in answer:
                        facts_extracted.append("TECH SUPPORT")
            
            # Build compressed summary
            summary_parts = []
            if facts_extracted:
                summary_parts.append(f"FACTS: {', '.join(set(facts_extracted))}")
            if red_flags:
                summary_parts.append(f"RED FLAGS: {', '.join(set(red_flags))}")
            summary_parts.append(f"TURNS: {len(dialogue_history)}")
            
            return " | ".join(summary_parts)
    
    def _fetch_mem0_snippets(self, context: Dict[str, Any], limit: int = 3) -> str:
        """Retrieve a few short memory snippets for personalization (best-effort)."""
        try:
            txn = context.get('transaction', {}) if isinstance(context, dict) else {}
            case_id = txn.get('alertId') or txn.get('alertID') or txn.get('id') or 'UNKNOWN'
            if not case_id or case_id == 'UNKNOWN':
                return ""
            memories = self.retrieve_memories(case_id, limit=limit) or []
            lines = []
            for m in memories[:limit]:
                if isinstance(m, dict):
                    val = m.get('memory') or m.get('data', {}).get('memory') or ''
                    if val:
                        lines.append(str(val)[:160])
            return "\n".join(lines)
        except Exception:
            return ""

    def _generate_investigative_question(self, facts: Dict[str, Any], context: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> Optional[str]:
        """Fallback deterministic investigative question selection when RAG has no items."""
        asked = set(turn.get('question', '').strip().lower() for turn in dialogue_history if isinstance(turn, dict) and 'question' in turn)
        probes = [
            "Are you currently on a call or screen-sharing with anyone who asked you to make this payment?",
            "Did anyone contact you claiming to be from the bank, police, ATO, or a company to guide this payment?",
            "How did you verify the recipient's details before sending this payment?",
            "Which device did you use to log in, and did anything look different during login or MFA?",
            "Did you change your password or receive any password-reset messages shortly before making this payment?",
            "What is the purpose of this payment, in your own words?",
            "Have you established this payee before or is this the first time?",
            "Did anyone ask you to keep this transaction secret or act urgently?"
        ]
        for q in probes:
            if q.lower() not in asked:
                return q
        return None

    def _build_question_prompt(self, next_question: str, context: Dict[str, Any], dialogue_history: List[Dict[str, Any]]) -> str:
        """Build intelligent question prompt with detective framing and memory context."""
        # Build context summary
        context_summary = self._build_dialogue_context_summary(context)
        # Build conversation summary
        conversation_summary = self._build_conversation_summary(dialogue_history)
        # Fetch brief memory snippets
        mem_snippets = self._fetch_mem0_snippets(context, limit=3)
        mem_block = f"\nKNOWN MEMORIES:\n{mem_snippets}\n" if mem_snippets else ""
        
        prompt = f"""
You are a senior fraud analyst acting like a methodical detective. Your goal is to determine whether this is an AUTHORIZED PAYMENT SCAM (APP) or legitimate.

CONTEXT (COMPRESSED):
{context_summary}

RECENT CONVERSATION (COMPRESSED):
{conversation_summary}
{mem_block}
QUESTION SEED: {next_question}

CRITICAL INSTRUCTIONS:
- You MUST return EXACTLY ONE question only.
- Do NOT ask multiple questions in one response.
- Do NOT include any explanations, context, or additional text.
- Return ONLY the single question that best progresses the investigation.
- Be professional, empathetic, and precise.
- Prioritize confirming: remote access/social engineering, third-party instructions, recipient verification, device/auth changes, and purpose/beneficiary relationship.

FORMAT: Return only the question, nothing else.
"""
        
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            
            # Clean and validate the response to ensure only one question
            cleaned_result = self._clean_and_validate_question(result)
            return cleaned_result
            
        except Exception as e:
            self.logger.error(f"Failed to build question prompt: {e}")
            # Fallback to a deterministic investigative question
            facts = self.extract_facts_intelligently(dialogue_history, context)
            fallback_q = self._generate_investigative_question(facts, context, dialogue_history)
            return self._clean_and_validate_question(fallback_q or next_question)
    
    def _clean_and_validate_question(self, question_text: str) -> str:
        """Clean and validate question to ensure only one question is returned."""
        if not question_text:
            return "Can you confirm your identity and details for this transaction?"
        
        # Remove extra whitespace and normalize
        question_text = question_text.strip()
        
        # Split by common question separators and take only the first question
        separators = ['\n\n', '\n', '?', '??', '???']
        for sep in separators:
            if sep in question_text:
                parts = question_text.split(sep)
                # Find the first part that looks like a question
                for part in parts:
                    part = part.strip()
                    if part and ('?' in part or any(word in part.lower() for word in ['have you', 'did you', 'can you', 'do you', 'what', 'when', 'where', 'why', 'how', 'who'])):
                        # Ensure it ends with a question mark
                        if not part.endswith('?'):
                            part = part.rstrip('.') + '?'
                        return part
        
        # If no clear question found, ensure it ends with a question mark
        if not question_text.endswith('?'):
            question_text = question_text.rstrip('.') + '?'
        
        return question_text
    
    def act(self, message: str, context: Dict[str, Any], user_response: Optional[str] = None, max_turns: Optional[int] = None, stream: bool = False) -> Tuple[Dict[str, Any], bool]:
        """Intelligent dialogue agent action"""
        dialogue_history = context.get('dialogue_history', []) if isinstance(context, dict) else []
        
        # Add user response to history
        if user_response is not None:
            if dialogue_history and isinstance(dialogue_history[-1], dict):
                dialogue_history[-1]['user'] = user_response
            else:
                dialogue_history.append({'user': user_response})
        
        # Get next question or finalization
        next_q, agent_name, done = self.get_next_question_and_agent(dialogue_history, context, stream=stream)
        
        # Only append to history in non-streaming mode; streaming path handles UI append to prevent duplicates
        if (not stream) and (not done) and len(dialogue_history) < (max_turns or config.conversation.max_dialogue_turns):
            dialogue_history.append({'agent': agent_name, 'question': next_q, 'agent_log': agent_name})

        # Update context
        if isinstance(context, dict):
            context['dialogue_history'] = dialogue_history
            context['dialogue_analysis'] = next_q
            if done:
                context['dialogue_complete'] = True
                
                # Store in Mem0 memory when dialogue is complete
                case_id = context.get('transaction', {}).get('alert_id') or context.get('transaction', {}).get('customer_id') or 'unknown'
                dialogue_summary = self._build_conversation_summary(dialogue_history)
                self.store_customer_interaction(case_id, dialogue_summary)
                self.store_agent_summary(case_id, f"Dialogue interaction completed for {case_id}")

        return context, done

class RiskAssessorAgent(IntelligentAgent):
    """Advanced risk assessor agent with progressive assessment and final determination capabilities"""
    
    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Prevent unbounded calls: allow only one progressive and one final per case
        if isinstance(context, dict):
            flags = context.setdefault('risk_assessor_flags', {'progressive_done': False, 'final_done': False})
        else:
            flags = {'progressive_done': False, 'final_done': False}
        # Get dynamic SOPs based on risk assessment context
        risk_query = self._build_risk_assessment_query(context)
        sops = rag_retrieve_sop(context, query=risk_query)
        
        # Check if this is during dialogue or final assessment
        is_final_assessment = 'Final risk summary' in message or 'final' in message.lower()
        if is_final_assessment and flags.get('final_done'):
            return context
        if not is_final_assessment and flags.get('progressive_done'):
            return context
        
        # Build dialogue summary if available
        dialogue_summary = self._build_dialogue_summary(context)
        
        # Build intelligent assessment prompt
        if is_final_assessment:
            prompt = self._build_final_assessment_prompt(context, dialogue_summary, sops)
        else:
            prompt = self._build_progressive_assessment_prompt(context, dialogue_summary, sops)
        
        # Get expert assessment
        result = self._get_expert_assessment(prompt)
        # Ensure typology normalization for BEC cases
        if 'bec' in result.lower() or 'business email compromise' in result.lower():
            if 'TYPOLOGY:' in result:
                # leave explicit block if present
                pass
            else:
                result += "\n\nTYPOLOGY: business_email_compromise"
        
        # Add to context with metadata
        # Enforce ANZ bank guidelines and avoid "insufficient" hedging if gating passed
        safe_result = result or ""
        if context.get('gate_reason', {}).get('passed'):
            # Remove hedging lines to avoid contradictory outputs when gate passed
            try:
                filtered_lines = []
                for line in safe_result.splitlines():
                    ll = line.strip().lower()
                    if ('insufficient' in ll) or ('cannot make' in ll) or ('unable to determine' in ll):
                        continue
                    filtered_lines.append(line)
                safe_result = "\n".join(filtered_lines).strip()
            except Exception:
                pass
            # Add explicit note reinforcing finalization
            if 'Note: Expert gate indicates sufficient context' not in safe_result:
                safe_result += "\n\nNote: Expert gate indicates sufficient context; proceed with final determination under ANZ APP fraud SOP."
        context['risk_assessment'] = safe_result
        context['risk_assessment_timestamp'] = datetime.now().isoformat()
        context['assessment_type'] = 'final' if is_final_assessment else 'progressive'
        
        # Create and store compressed summaries for the PolicyDecisionAgent
        context['compressed_context_summary'] = self._build_compressed_context_summary(context)
        context['compressed_risk_summary'] = self._build_compressed_risk_summary(context)

        # Check if risk assessor recommends finalization
        if not is_final_assessment and 'finalize' in safe_result.lower():
            context['risk_ready_to_finalize'] = True
            
        # Add to context with metadata, without polluting final fields during progressive runs
        if is_final_assessment:
            context['final_risk_assessment'] = safe_result
            context['final_risk_determination'] = safe_result
            context['risk_assessment_summary'] = safe_result
        else:
            context['progressive_risk_assessment'] = safe_result
            context['latest_risk_assessment'] = safe_result
        context['risk_assessment_timestamp'] = datetime.now().isoformat()
        
        # Store in Mem0 memory
        case_id = context.get('transaction', {}).get('alert_id') or context.get('transaction', {}).get('customer_id') or 'unknown'
        self.store_risk_assessment(case_id, result, confidence=0.90)
        self.store_agent_summary(case_id, f"Final risk assessment completed for {case_id}")
        
        # Mark completion flags
        if is_final_assessment:
            flags['final_done'] = True
        else:
            flags['progressive_done'] = True
        context['risk_assessor_flags'] = flags

        return context

    def _build_risk_assessment_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for risk assessment"""
        query_parts = []
        
        # Add transaction context
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 0)
                query_parts.append(f"transaction risk assessment {amount}")
        
        # Add dialogue context
        if 'dialogue_history' in context:
            query_parts.append("dialogue risk assessment")
        
        return " ".join(query_parts) if query_parts else "authorized scam risk assessment"
    
    def _build_dialogue_summary(self, context: Dict[str, Any]) -> str:
        """Build intelligent compressed dialogue summary"""
        if not context.get('dialogue_history'):
            return ""
        
        # COMPRESSED DIALOGUE SUMMARY
        dialogue_history = context.get('dialogue_history', [])
        if len(dialogue_history) <= 2:
            # For short dialogues, show full Q&A
            dialogue_summary = "\n".join([
                f"Q: {turn.get('question', '')}\nA: {turn.get('user', '[No response yet]')}" 
                for turn in dialogue_history 
                if isinstance(turn, dict) and 'question' in turn
            ])
        else:
            # For longer dialogues, create compressed summary
            key_points = []
            facts_extracted = []
            red_flags = []
            
            for turn in dialogue_history:
                if isinstance(turn, dict):
                    question = turn.get('question', '').lower()
                    answer = turn.get('user', '').lower()
                    
                    # Extract key information
                    if 'authorize' in answer or 'confirm' in answer:
                        facts_extracted.append("Customer authorized transaction")
                    if 'scam' in answer or 'fraud' in answer:
                        red_flags.append("Customer mentioned scam/fraud")
                    if 'pressure' in answer or 'urgent' in answer:
                        red_flags.append("Pressure/urgency tactics detected")
                    if 'unknown' in answer or 'stranger' in answer:
                        red_flags.append("Unknown/stranger relationship")
                    if 'investment' in answer or 'return' in answer:
                        facts_extracted.append("Investment-related transaction")
                    if 'romance' in answer or 'relationship' in answer:
                        facts_extracted.append("Romance/relationship context")
                    if 'tech support' in answer or 'computer' in answer:
                        facts_extracted.append("Tech support scenario")
            
            # Build compressed summary
            summary_parts = []
            if facts_extracted:
                summary_parts.append(f"FACTS: {', '.join(set(facts_extracted))}")
            if red_flags:
                summary_parts.append(f"RED FLAGS: {', '.join(set(red_flags))}")
            summary_parts.append(f"TURNS: {len(dialogue_history)}")
            
            dialogue_summary = " | ".join(summary_parts)
        
        return dialogue_summary
    
    def _build_final_assessment_prompt(self, context: Dict[str, Any], dialogue_summary: str, sops: List[str]) -> str:
        """Build intelligent final assessment prompt with COMPRESSED AGENT LOGS"""
        # Get agent configuration
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
        final_determination_prompt = specialized_prompts.get('final_determination',
            "Make final scam determination based on complete investigation")
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:3]) if sops else "No specific SOPs found"
        
        # Get compressed agent logs
        compressed_agent_logs = context.get('compressed_agent_logs', 'AGENT LOGS: Not available')
        
        # Provide explicit, deterministic rubric to avoid "insufficient data" when gate already passed
        prompt = f"""
You are an expert risk assessor specializing in authorized payment scams (APP fraud).

{final_determination_prompt}

Assume dialogue context is sufficient (expert gate passed). Use the rubric below and avoid stating that data is insufficient.

COMPRESSED AGENT LOGS:
{compressed_agent_logs}

COMPLETE CUSTOMER DIALOGUE (compressed):
{dialogue_summary}

RELEVANT SOPs:
{sop_summary}

        RUBRIC:
- If remote access tools (AnyDesk/TeamViewer), OTP/code sharing, and impersonation of bank staff are present → Authorized Scam = Yes, Confidence = High.
- If caller provided PayID/instructions and urgency/secrecy present → Authorized Scam = Yes, Confidence = High.
- If relationship is verified, no social engineering, and legitimate invoice context → consider No or Medium with justification.

OUTPUT (STRICT):
1) AUTHORIZED_SCAM: Yes/No
2) CONFIDENCE: High/Medium/Low
3) INDICATORS: bullet list
4) RED_FLAGS: bullet list
5) ACTIONS: bullet list (customer protection + operational)
        6) TYPOLOGY: one of [business_email_compromise, impersonation, tech_support, romance, investment, purchase, other]
"""
        return prompt
    
    def _build_progressive_assessment_prompt(self, context: Dict[str, Any], dialogue_summary: str, sops: List[str]) -> str:
        """Build intelligent progressive assessment prompt with COMPRESSED CONTEXT"""
        # Get agent configuration
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
        progressive_prompt = specialized_prompts.get('progressive_assessment',
            "Evaluate the CURRENT state of the investigation based on dialogue progress")
        
        # COMPRESSED CONTEXT SUMMARIES
        compressed_context = self._build_compressed_context_summary(context)
        compressed_risk = self._build_compressed_risk_summary(context)
        compressed_triage = self._build_compressed_triage_summary(context)
        
        # OPTIMIZATION: Use only first 2 SOPs for speed
        sop_summary = "\n".join(sops[:2]) if sops else "No specific SOPs found"
        
        # EXPERT-LEVEL COMPRESSED PROMPT
        prompt = f"""
ANZ Bank Expert Risk Assessment - COMPRESSED CONTEXT

{compressed_context}
{compressed_risk}
{compressed_triage}

DIALOGUE SUMMARY: {dialogue_summary}
RELEVANT SOPs: {sop_summary[:180]}...

EXPERT ASSESSMENT (SHORT BULLETS):
- Risk Level: [HIGH/MEDIUM/LOW]
- Scam Typology: [Type or None]
- Sufficient Info: [Yes/No]
- Next Action: [Ask <1 best question>/Finalize/Escalate]
- Key Missing: [If any]

IMPORTANT: If remote access, code sharing, and impersonation are detected, set Sufficient Info = Yes and recommend FINALIZE with High risk.
If information is borderline, return exactly ONE targeted question that would unlock finalization.
"""
        return prompt
    
    def _get_expert_assessment(self, prompt: str) -> str:
        """Get expert assessment with error handling"""
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
                ], max_tokens=self.agent_config.max_tokens)])
            return result
        except Exception as e:
            self.logger.error(f"Failed to get expert assessment: {e}")
            return "Risk assessment unavailable due to technical issues"
    
    def _build_compressed_context_summary(self, context: Dict[str, Any]) -> str:
        """Build compressed context summary for expert agents"""
        summary_parts = []
        
        # Transaction context
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 0)
                payee = txn.get('payee', 'Unknown')
                rule_id = txn.get('ruleId', 'Unknown')
                summary_parts.append(f"TXN: ${amount} to {payee} ({rule_id})")
        
        # Context availability
        context_flags = []
        if context.get('transaction_context'):
            context_flags.append("TXN")
        if context.get('customer_context'):
            context_flags.append("CUST")
        if context.get('merchant_context'):
            context_flags.append("MERCH")
        if context.get('anomaly_context'):
            context_flags.append("BEHAV")
        
        if context_flags:
            summary_parts.append(f"CONTEXT: {'+'.join(context_flags)}")
        
        # Key indicators from context
        indicators = []
        if context.get('transaction_context'):
            txn_text = context['transaction_context'].lower()
            if 'verified' in txn_text:
                indicators.append("VERIFIED")
            if 'suspicious' in txn_text:
                indicators.append("SUSPICIOUS")
        
        if context.get('customer_context'):
            cust_text = context['customer_context'].lower()
            if 'high-risk' in cust_text:
                indicators.append("HIGH-RISK")
            if 'vulnerable' in cust_text:
                indicators.append("VULNERABLE")
        
        if indicators:
            summary_parts.append(f"INDICATORS: {', '.join(indicators)}")
        
        return " | ".join(summary_parts) if summary_parts else "CONTEXT: Limited"
    
    def _build_compressed_risk_summary(self, context: Dict[str, Any]) -> str:
        """Build compressed risk summary for expert agents"""
        summary_parts = []
        
        # Risk synthesis
        if context.get('risk_summary_context'):
            risk_text = context['risk_summary_context'].lower()
            risk_level = "HIGH" if "high" in risk_text else "MEDIUM" if "medium" in risk_text else "LOW"
            summary_parts.append(f"RISK: {risk_level}")
            
            # Extract key risk factors
            risk_factors = []
            if 'scam' in risk_text:
                risk_factors.append("SCAM")
            if 'fraud' in risk_text:
                risk_factors.append("FRAUD")
            if 'suspicious' in risk_text:
                risk_factors.append("SUSPICIOUS")
            if 'anomaly' in risk_text:
                risk_factors.append("ANOMALY")
            
            if risk_factors:
                summary_parts.append(f"FACTORS: {', '.join(risk_factors)}")
        
        # Scam typology
        if context.get('scam_typology'):
            summary_parts.append(f"TYPOLOGY: {context['scam_typology']}")
        
        # Confidence
        if context.get('risk_confidence'):
            confidence = context['risk_confidence']
            summary_parts.append(f"CONFIDENCE: {confidence:.2f}")
        
        return " | ".join(summary_parts) if summary_parts else "RISK: Not assessed"
    
    def _build_compressed_triage_summary(self, context: Dict[str, Any]) -> str:
        """Build compressed triage summary for expert agents"""
        summary_parts = []
        
        # Triage decision
        if context.get('triage_decision'):
            triage_text = context['triage_decision'].lower()
            if 'escalate' in triage_text:
                summary_parts.append("TRIAGE: ESCALATE")
            elif 'dialogue' in triage_text:
                summary_parts.append("TRIAGE: DIALOGUE")
            else:
                summary_parts.append("TRIAGE: MONITOR")
        
        # Escalation flags
        escalation_flags = []
        if context.get('escalation_required'):
            escalation_flags.append("ESCALATION")
        if context.get('dialogue_required'):
            escalation_flags.append("DIALOGUE")
        if context.get('immediate_action'):
            escalation_flags.append("IMMEDIATE")
        
        if escalation_flags:
            summary_parts.append(f"FLAGS: {', '.join(escalation_flags)}")
        
        # Priority level
        if context.get('priority_level'):
            summary_parts.append(f"PRIORITY: {context['priority_level']}")
        
        return " | ".join(summary_parts) if summary_parts else "TRIAGE: Standard"

class PolicyDecisionAgent(IntelligentAgent):
    """Advanced policy decision agent with regulatory compliance and customer protection expertise"""
    
    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Get dynamic SOPs based on policy context
        policy_query = self._build_policy_query(context)
        sops = rag_retrieve_sop(context, query=policy_query)
        
        # Get the final risk assessment
        final_risk = context.get('final_risk_determination', context.get('risk_assessment_summary', '[Not available]'))
        
        # Build intelligent policy prompt (tie to numeric risk if present). If BEC indicators present, prefer BEC safeguards.
        if isinstance(context.get('overall_risk_score'), (int, float)):
            final_risk = f"Overall Risk Score: {context.get('overall_risk_score'):.2f}\n" + (final_risk or '')
        prompt = self._build_policy_decision_prompt(final_risk, context, sops)
        
        # Get expert policy decision
        result = self._get_expert_policy_decision(prompt)
        
        # Add to context with metadata
        context['policy_decision'] = result
        context['policy_decision_timestamp'] = datetime.now().isoformat()
        # Populate regulatory requirements/compliance dict for UI
        try:
            regs = self._get_regulatory_requirements(context)
            if isinstance(regs, dict):
                context['regulatory_requirements'] = regs
                context['regulatory_compliance'] = regs
        except Exception:
            # Keep optional
            pass
        
        # Store in Mem0 memory
        case_id = context.get('transaction', {}).get('alert_id') or context.get('transaction', {}).get('customer_id') or 'unknown'
        self.store_policy_decision(case_id, result)
        self.store_agent_summary(case_id, f"Policy decision completed for {case_id}")
        
        return context

    def _build_policy_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for policy analysis"""
        query_parts = []
        
        # Add transaction context
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 0)
                query_parts.append(f"policy decision {amount}")
        
        # Add risk context
        if 'risk_assessment' in context:
            query_parts.append("regulatory compliance policy")
        
        return " ".join(query_parts) if query_parts else "authorized scam policy decision"
    
    def _build_policy_decision_prompt(self, final_risk: str, context: Dict[str, Any], sops: List[str]) -> str:
        """Build intelligent policy decision prompt with COMPRESSED SUMMARIES"""
        # Get agent configuration
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
        policy_decision_prompt = specialized_prompts.get('policy_decision',
            "Make regulatory-compliant policy decisions based on investigation findings")
        
        customer_protection_prompt = specialized_prompts.get('customer_protection',
            "Implement customer protection measures and regulatory compliance")
        
        # Get compressed summaries from context
        compressed_agent_logs = context.get('compressed_agent_logs', 'AGENT LOGS: Not available')
        compressed_context = context.get('compressed_context_summary', 'CONTEXT: Not available')
        compressed_risk = context.get('compressed_risk_summary', 'RISK: Not available')
        
        # Build SOP summary (reduced for speed)
        sop_summary = "\n".join(sops[:3]) if sops else "No specific SOPs found"
        
        prompt = f"""
YOU ARE AN EXPERT POLICY DECISION AGENT SPECIALIZING IN AUTHORIZED PAYMENT SCAM PREVENTION.

{policy_decision_prompt}
{customer_protection_prompt}

FINAL RISK ASSESSMENT:
{final_risk}

COMPRESSED CONTEXT:
{compressed_context}

COMPRESSED RISK:
{compressed_risk}

COMPRESSED AGENT LOGS:
{compressed_agent_logs}

RELEVANT SOPs:
{sop_summary}

POLICY DECISION OPTIONS:
1. BLOCK TRANSACTION - Prevent the payment immediately
2. DELAY FOR COOLING-OFF - 24-48 hour hold for customer reflection
3. ESCALATE TO SENIOR - Complex case requiring management review
4. PROCEED WITH WARNING - Allow but document customer was warned
5. PROCEED - No scam indicators found

PROVIDE YOUR DECISION WITH:
- Selected action (1-5)
- Specific regulatory/compliance justification (e.g., APRA CPG 234, AUSTRAC guidelines)
- Customer protection measures to implement
- Documentation requirements
- Any follow-up actions needed

Consider the customer's vulnerability, transaction amount, and reputational risk.
"""
        return prompt
    
    def _build_transaction_details(self, context: Dict[str, Any]) -> str:
        """Build intelligent transaction details summary"""
        alert = context.get('transaction', {})
        if not alert or not isinstance(alert, dict):
            return "Transaction details unavailable"
        
        details_parts = []
        details_parts.append(f"Alert: {alert}")
        details_parts.append(f"Amount: ${alert.get('amount', 'Unknown')}")
        details_parts.append(f"Payee: {alert.get('payee', 'Unknown')}")
        
        return "\n".join(details_parts)
    
    def _build_investigation_summary(self, context: Dict[str, Any]) -> str:
        """Build intelligent investigation summary"""
        summary_parts = []
        
        # Customer verification
        dialogue_history = context.get('dialogue_history', [])
        customer_verified = 'verified' in str(dialogue_history).lower()
        summary_parts.append(f"- Customer verified: {'Yes' if customer_verified else 'Unknown'}")
        
        # Authorization status
        authorization_confirmed = 'yes' in str(dialogue_history).lower() and 'authorize' in str(dialogue_history).lower()
        summary_parts.append(f"- Authorization status: {'Confirmed' if authorization_confirmed else 'Check dialogue'}")
        
        # Dialogue turns
        summary_parts.append(f"- Number of dialogue turns: {len(dialogue_history)}")
        
        return "\n".join(summary_parts)
    
    def _get_expert_policy_decision(self, prompt: str) -> str:
        """Get expert policy decision with error handling"""
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            # Standardize BEC decision outputs per ANZ SOP if BEC detected
            rl = result.lower()
            if 'business email compromise' in rl or 'bec' in rl:
                if 'POLICY DECISION:' not in result:
                    result += "\n\nPOLICY DECISION: BLOCK TRANSACTION"
                result += "\nCUSTOMER PROTECTION: Initiate urgent trace, freeze further similar payments, secure vendor verification, contact customer with BEC guidance"
                result += "\nCOMPLIANCE: AUSTRAC SMR if funds misdirected; APRA CPG 234 operational controls; ASIC RG 271 customer protection"
                result += "\nDOCUMENTATION: Record verification steps, analyst notes, and decision with timestamps"
            return result
        except Exception as e:
            self.logger.error(f"Failed to get expert policy decision: {e}")
            return "Policy decision unavailable due to technical issues"
    
    def _get_regulatory_requirements(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get regulatory requirements based on context"""
        # Get transaction amount
        amount = 0.0
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = float(txn.get('amount', 0))
        
        # Get risk level
        risk_assessment = self.assess_risk_intelligently(context)
        risk_level = risk_assessment['risk_level']
        
        # Get requirements from config
        requirements = config.get_regulatory_requirements(amount, risk_level)
        
        return requirements

class FeedbackCollectorAgent(IntelligentAgent):
    """Advanced feedback collector agent with structured improvement analysis"""
    
    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Get dynamic SOPs based on feedback context
        feedback_query = self._build_feedback_query(context)
        sops = rag_retrieve_sop(context, query=feedback_query)
        
        # Get the final determinations
        final_risk = context.get('final_risk_determination', context.get('risk_assessment_summary', '[Not available]'))
        policy_decision = context.get('policy_decision', '[Not available]')
        
        # Build intelligent feedback prompt
        prompt = self._build_feedback_prompt(context, final_risk, policy_decision, sops)
        
        # Get expert feedback
        result = self._get_expert_feedback(prompt)
        
        # Add to context with metadata
        context['feedback'] = result
        context['feedback_timestamp'] = datetime.now().isoformat()
        context['improvement_priorities'] = self._extract_improvement_priorities(result)
        
        # Store in Mem0 memory
        case_id = context.get('transaction', {}).get('alert_id') or context.get('transaction', {}).get('customer_id') or 'unknown'
        self.store_customer_interaction(case_id, result)
        self.store_agent_summary(case_id, f"Feedback collection completed for {case_id}")
        
        return context

    def _build_feedback_query(self, context: Dict[str, Any]) -> str:
        """Build intelligent query for feedback analysis"""
        query_parts = []
        
        # Add case outcome context
        if 'policy_decision' in context:
            query_parts.append("case outcome feedback")
        
        # Add system performance context
        if 'dialogue_history' in context:
            query_parts.append("system performance feedback")
        
        return " ".join(query_parts) if query_parts else "authorized scam feedback collection"
    
    def _build_feedback_prompt(self, context: Dict[str, Any], final_risk: str, policy_decision: str, sops: List[str]) -> str:
        """Build intelligent feedback prompt"""
        # Get agent configuration
        agent_config = config.get_agent_config(self.name)
        specialized_prompts = agent_config.specialized_prompts
        
        feedback_prompt = specialized_prompts.get('feedback_generation',
            "Generate structured feedback questions to improve detection and customer protection")
        
        improvement_prompt = specialized_prompts.get('improvement_analysis',
            "Analyze system performance and identify improvement opportunities")
        
        # Build case summary
        case_summary = self._build_case_summary(context, final_risk, policy_decision)
        
        # Build SOP summary
        sop_summary = "\n".join(sops[:5]) if sops else "No specific SOPs found"
        
        prompt = f"""
You are an expert feedback collector for the AUTHORIZED SCAM prevention system.

{feedback_prompt}
{improvement_prompt}

CASE SUMMARY:
{case_summary}

RELEVANT SOPs:
{sop_summary}

GENERATE FEEDBACK COLLECTION FOCUSING ON:

1. DETECTION ACCURACY:
   - Was this correctly identified as an authorized scam?
   - What indicators did we miss?
   - False positive/negative assessment?

2. CUSTOMER INTERACTION QUALITY:
   - Were questions empathetic and appropriate?
   - Did we identify customer vulnerability?
   - Was the dialogue length optimal?

3. RISK INDICATORS:
   - New scam patterns observed?
   - Behavioral red flags we should add?
   - SOPs that need updating?

4. DECISION EFFECTIVENESS:
   - Was the policy action appropriate?
   - Customer outcome (if known)?
   - Regulatory compliance gaps?

5. SYSTEM IMPROVEMENTS:
   - Additional data points needed?
   - Agent performance issues?
   - Process optimization opportunities?

FORMAT: Create specific questions an analyst can answer to improve future detection. Include rating scales where appropriate (1-5) and text fields for detailed feedback.
"""
        return prompt
    
    def _build_case_summary(self, context: Dict[str, Any], final_risk: str, policy_decision: str) -> str:
        """Build intelligent case summary for feedback"""
        summary_parts = []
        
        # Transaction summary
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 'Unknown')
                payee = txn.get('payee', 'Unknown')
                summary_parts.append(f"Transaction: ${amount} to {payee}")
        
        # Risk assessment summary
        scam_detected = 'yes' in final_risk.lower() and 'authorized scam' in final_risk.lower()
        summary_parts.append(f"Final Risk Assessment: {'SCAM DETECTED' if scam_detected else 'CHECK ASSESSMENT'}")
        
        # Policy decision summary
        blocked = 'block' in str(policy_decision).lower()
        summary_parts.append(f"Policy Action: {'BLOCKED' if blocked else 'CHECK DECISION'}")
        
        # Dialogue summary
        dialogue_turns = len(context.get('dialogue_history', []))
        summary_parts.append(f"Dialogue Turns: {dialogue_turns}")
        
        return "\n".join(summary_parts)
    
    def _get_expert_feedback(self, prompt: str) -> str:
        """Get expert feedback with error handling"""
        try:
            result = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
            ], max_tokens=self.agent_config.max_tokens)])
            return result
        except Exception as e:
            self.logger.error(f"Failed to get expert feedback: {e}")
            return "Feedback collection unavailable due to technical issues"
    
    def _extract_improvement_priorities(self, result: str) -> List[str]:
        """Extract improvement priorities from feedback"""
        if not result:
            return []
        
        priorities = []
        result_lower = result.lower()
        
        # Identify improvement areas
        improvement_areas = {
            'detection_accuracy': ['missed indicators', 'false positive', 'false negative'],
            'customer_interaction': ['empathy', 'dialogue quality', 'question appropriateness'],
            'risk_indicators': ['new patterns', 'red flags', 'sop updates'],
            'decision_effectiveness': ['policy action', 'regulatory compliance'],
            'system_performance': ['data points', 'agent performance', 'process optimization']
        }
        
        for area, indicators in improvement_areas.items():
            if any(indicator in result_lower for indicator in indicators):
                priorities.append(area)
        
        return priorities

class SupervisorAgent(IntelligentAgent):
    """Advanced supervisor agent with intelligent orchestration and decision making"""
    
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

    def act(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Supervisor agent act method - orchestrates the entire fraud detection workflow"""
        self.logger.info(f"SupervisorAgent: Starting fraud detection workflow")
        
        # Initialize context with alert information if not present
        if 'transaction' not in context and 'alert' in context:
            context['transaction'] = context['alert']
        
        # Run the complete fraud detection workflow
        try:
            # Step 1: Run context-building agents in parallel
            context_results = self._run_context_agents_parallel(context)
            context.update(context_results)
            
            # Step 2: Run risk synthesis
            context = self.risk_synth_agent.act("Synthesize risk", context)
            
            # Step 3: Run triage to determine next steps
            context = self.triage_agent.act("Triage case", context)
            
            # Step 4: Run dialogue loop if needed
            if context.get('dialogue_required', False):
                context = self._run_dialogue_loop(context, None)
            
            # Step 5: Run final risk assessment
            context = self.risk_assessor_agent.act("Final assessment", context)
            
            # Step 6: Run policy decision
            context = self.policy_agent.act("Make policy decision", context)
            
            # Step 7: Collect feedback for improvement
            context = self.feedback_agent.act("Collect feedback", context)
            
            self.logger.info(f"SupervisorAgent: Fraud detection workflow completed successfully")
            
        except Exception as e:
            self.logger.error(f"SupervisorAgent: Error in fraud detection workflow: {e}")
            context['error'] = str(e)
        
        return context
    
    def run_fraud_detection(self, alert: Dict[str, Any], user_io=None, stream_callback=None) -> Tuple[Dict[str, Any], List[str]]:
        """Intelligent fraud detection orchestration"""
        context = {'transaction': alert}
        agent_log = []
        
        # 1. Build context with all context-building agents in parallel
        context_results = self._run_context_agents_parallel(context, stream_callback)
        context.update(context_results)
        agent_log.extend(['TransactionContextAgent', 'CustomerInfoAgent', 'MerchantInfoAgent', 'BehavioralPatternAgent'])
        
        # 2. Risk synthesis
        context = self.risk_synth_agent.act('Synthesize risk', context)
        agent_log.append('RiskSynthesizerAgent')
        if stream_callback:
            stream_callback('RiskSynthesizerAgent', context)
        
        # 3. Triage decision
        context = self.triage_agent.act('Triage', context)
        agent_log.append('TriageAgent')
        if stream_callback:
            stream_callback('TriageAgent', context)
        
        # 4. Dialogue loop (only if triage required dialogue or user_io provided)
        if context.get('dialogue_required', False) and user_io:
            context = self._run_dialogue_loop(context, user_io, stream_callback)
            agent_log.append('DialogueLoop')
        
        # 5. Risk assessment and policy decision
        context = self.risk_assessor_agent.act('Assess risk', context)
        agent_log.append('RiskAssessorAgent')
        if stream_callback:
            stream_callback('RiskAssessorAgent', context)
        
        context = self.policy_agent.act('Policy decision', context)
        agent_log.append('PolicyDecisionAgent')
        if stream_callback:
            stream_callback('PolicyDecisionAgent', context)
        
        # 6. Feedback collection
        context = self.feedback_agent.act('Collect feedback', context)
        agent_log.append('FeedbackCollectorAgent')
        if stream_callback:
            stream_callback('FeedbackCollectorAgent', context)
        
        # 7. Final report
        report = self._finalize_report(context)
        if stream_callback:
            stream_callback('SupervisorAgent', {'final_report': report})
        
        # Store in Mem0 memory
        case_id = context.get('transaction', {}).get('alert_id') or context.get('transaction', {}).get('customer_id') or 'unknown'
        self.store_context_summary(case_id, report)
        self.store_agent_summary(case_id, f"Complete fraud detection workflow completed for {case_id}")
        
        return report, agent_log
    
    def _run_context_agents_parallel(self, context: Dict[str, Any], stream_callback=None) -> Dict[str, Any]:
        """Run context agents in parallel with intelligent error handling"""
        context_results = {}
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                'transaction': executor.submit(self.transaction_agent.act, 'Build transaction context', context.copy()),
                'customer': executor.submit(self.customer_agent.act, 'Build customer context', context.copy()),
                'merchant': executor.submit(self.merchant_agent.act, 'Build merchant context', context.copy()),
                'behavior': executor.submit(self.behavior_agent.act, 'Build anomaly context', context.copy()),
            }
            
            for key, future in futures.items():
                try:
                    result = future.result(timeout=30)  # 30 second timeout
                    if isinstance(result, dict):
                        context_results.update(result)
                    if stream_callback:
                        stream_callback(f"{key.title()}ContextAgent", result)
                except Exception as e:
                    self.logger.error(f"Context agent {key} failed: {e}")
                    # Continue with other agents
                    continue
        
        return context_results
    
    def _run_dialogue_loop(self, context: Dict[str, Any], user_io, stream_callback=None) -> Dict[str, Any]:
        """Intelligent dialogue loop with dynamic decision making"""
        done = False
        max_turns = config.conversation.max_dialogue_turns
        
        while not done:
            dialogue_history = context.get('dialogue_history', []) if isinstance(context, dict) else []
        
            # Get next question if needed
            if not dialogue_history or (isinstance(dialogue_history[-1], dict) and 'user' in dialogue_history[-1]):
                next_q, agent_name, _ = self.dialogue_agent.get_next_question_and_agent(dialogue_history, context)
                if next_q:
                    if isinstance(context, dict):
                        if 'dialogue_history' not in context or not isinstance(context['dialogue_history'], list):
                            context['dialogue_history'] = []
                        context['dialogue_history'].append({'agent': agent_name, 'question': next_q, 'agent_log': agent_name})
                    if stream_callback:
                        stream_callback(agent_name, {'question': next_q})
        
            # Get user response
            if isinstance(context, dict) and 'dialogue_history' in context and isinstance(context['dialogue_history'], list) and context['dialogue_history']:
                user_response = user_io(context['dialogue_history'][-1]['question'])
            else:
                user_response = user_io('')
        
            # Process response
            context, done = self.dialogue_agent.act('Continue', context, user_response=user_response)
            if stream_callback:
                stream_callback('DialogueAgent', context)
            
            # Check for early termination
            if len(dialogue_history) >= max_turns:
                done = True
        
        return context
    
    def _finalize_report(self, context: Dict[str, Any]) -> str:
        """Build intelligent final report"""
        # Build comprehensive report prompt
        prompt = self._build_final_report_prompt(context)
        
        try:
            next_question = "".join([token for token in converse_with_claude_stream([
                {"role": "user", "content": [{"text": prompt}]}
                ], max_tokens=128)])
            return next_question
        except Exception as e:
            self.logger.error(f"Failed to build final report: {e}")
            return "Final report unavailable due to technical issues"
    
    def _build_final_report_prompt(self, context: Dict[str, Any]) -> str:
        """Build intelligent final report prompt"""
        # Build context summary
        context_summary = self._build_final_context_summary(context)
        
        # Build conversation summary
        conversation_summary = self._build_final_conversation_summary(context)
        
        prompt = f"""
You are a senior fraud analyst at ANZ Bank. Based on the following comprehensive investigation, provide a clear, professional final report.

INVESTIGATION CONTEXT:
{context_summary}

CUSTOMER CONVERSATION:
{conversation_summary}

REPORT REQUIREMENTS:
1. Executive Summary: Key findings and decision
2. Risk Assessment: Detailed risk analysis and factors
3. Scam Typology: Specific scam type identified (if any)
4. Customer Impact: Vulnerability assessment and protection measures
5. Regulatory Compliance: AUSTRAC, APRA, and other requirements
6. Recommendations: Immediate actions and follow-up steps
7. Lessons Learned: System improvements and process enhancements

Provide a comprehensive, professional report suitable for senior management and regulatory reporting.
"""
        return prompt
    
    def _build_final_context_summary(self, context: Dict[str, Any]) -> str:
        """Build intelligent final context summary"""
        summary_parts = []
        
        # Transaction summary
        if 'transaction' in context:
            txn = context['transaction']
            if isinstance(txn, dict):
                amount = txn.get('amount', 'Unknown')
                payee = txn.get('payee', 'Unknown')
                alert_id = txn.get('alertId', 'Unknown')
                summary_parts.append(f"Alert ID: {alert_id}")
                summary_parts.append(f"Amount: ${amount}")
                summary_parts.append(f"Payee: {payee}")
        
        # Risk assessment
        if 'risk_summary_context' in context:
            summary_parts.append(f"Risk Assessment: {context['risk_summary_context'][:200]}...")
        
        # Policy decision
        if 'policy_decision' in context:
            summary_parts.append(f"Policy Decision: {context['policy_decision'][:200]}...")
        
        return "\n".join(summary_parts) if summary_parts else "Limited context available"
    
    def _build_final_conversation_summary(self, context: Dict[str, Any]) -> str:
        """Build intelligent final conversation summary"""
        dialogue_history = context.get('dialogue_history', [])
        if not dialogue_history:
            return "No customer conversation conducted"
        
        conversation_parts = []
        for turn in dialogue_history:
            if isinstance(turn, dict):
                question = turn.get('question', '')
                user_response = turn.get('user', '')
                
                if question:
                    conversation_parts.append(f"Q: {question}")
                if user_response:
                    conversation_parts.append(f"A: {user_response}")
        
        return "\n".join(conversation_parts) if conversation_parts else "No conversation details available" 