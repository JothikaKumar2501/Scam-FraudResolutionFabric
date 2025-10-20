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

class CustomerInfoAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="customer-info-agent",
            name="CustomerInfoAgent",
            description="Advanced customer intelligence agent with behavioral biometrics and vulnerability assessment"
        )
        self.agent_config = config.get_agent_config(self.name)
        self.logger = logging.getLogger(self.name)

    @tool
    def analyze_customer(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze customer information and assess vulnerability to scams."""
        try:
            # Get dynamic SOPs based on customer context
            customer_query = self._build_customer_query(context)
            sops = self._retrieve_sop(context, query=customer_query)
            
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
            
            # Store in context instead of Mem0 memory
            case_id = customer_id or 'unknown'
            context['case_id'] = case_id
            context['context_summary'] = result
            context['agent_summary'] = f"Customer analysis completed for {case_id}"
            
            self.logger.info(f"Customer analysis completed for case: {context.get('transaction', {}).get('alert_id', 'Unknown')}")
            return context
        except Exception as e:
            self.logger.error(f"Error in analyze_customer: {str(e)}")
            context['customer_context'] = "Error occurred during customer analysis"
            context['customer_analysis_error'] = str(e)
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
                    customer_details = normalize_field_names(customer)
                    break
                    
        except Exception as e:
            self.logger.error(f"Error loading customer demographics: {e}")
        
        return customer_details if customer_details else {'status': 'customer_details_unavailable'}

    def _build_customer_analysis_prompt(self, customer_details: Dict[str, Any], sops: List[str]) -> str:
        """Build intelligent customer analysis prompt"""
        specialized_prompts = self.agent_config.specialized_prompts
        
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

customer_info_agent = CustomerInfoAgent()