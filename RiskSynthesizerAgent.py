from strands import Agent, tool
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from aws_bedrock import converse_with_claude_stream
from config import config
from vector_utils import search_similar
import logging
import yaml

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

class RiskSynthesizerAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="risk-synthesizer-agent",
            name="RiskSynthesizerAgent",
            description="Advanced risk synthesis agent with comprehensive fraud typology identification"
        )
        self.agent_config = config.get_agent_config(self.name)
        self.logger = logging.getLogger(self.name)

    @tool
    def synthesize_risk(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesize risk assessment from multiple agent contexts and identify fraud typologies."""
        try:
            # Get dynamic SOPs based on risk context
            risk_query = self._build_risk_query(context)
            sops = self._retrieve_sop(context, query=risk_query)
            
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
            
            self.logger.info(f"Risk synthesis completed for case: {context.get('transaction', {}).get('alert_id', 'Unknown')}")
            return context
        except Exception as e:
            self.logger.error(f"Error in synthesize_risk: {str(e)}")
            context['risk_synthesis_error'] = str(e)
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

        def has_any(keywords: List[str]) -> bool:
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
            'secrecy': has_any(['keep this secret', 'dont tell', 'secrecy']),
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

    def _build_risk_synthesis_prompt(self, txn: str, cust: str, merch: str, anom: str, sops: List[str]) -> str:
        """Build intelligent risk synthesis prompt"""
        specialized_prompts = self.agent_config.specialized_prompts
        
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

risk_synthesizer_agent = RiskSynthesizerAgent()