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

class MerchantInfoAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="merchant-info-agent",
            name="MerchantInfoAgent",
            description="Advanced merchant risk analysis agent with industry-specific expertise"
        )
        self.agent_config = config.get_agent_config(self.name)
        self.logger = logging.getLogger(self.name)

    @tool
    def analyze_merchant(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze merchant information and assess risk indicators."""
        try:
            # Get dynamic SOPs based on merchant context
            merchant_query = self._build_merchant_query(context)
            sops = self._retrieve_sop(context, query=merchant_query)
            
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
            
            # Store in context instead of Mem0 memory
            case_id = merchant_id or 'unknown'
            context['case_id'] = case_id
            context['context_summary'] = result
            context['agent_summary'] = f"Merchant analysis completed for {case_id}"
            
            self.logger.info(f"Merchant analysis completed for case: {context.get('transaction', {}).get('alert_id', 'Unknown')}")
            return context
        except Exception as e:
            self.logger.error(f"Error in analyze_merchant: {str(e)}")
            context['merchant_context'] = "Error occurred during merchant analysis"
            context['merchant_analysis_error'] = str(e)
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
        specialized_prompts = self.agent_config.specialized_prompts
        
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

merchant_info_agent = MerchantInfoAgent()