"""
Tools for the Intel Agent
"""

import os
import logging
import yaml
import feedparser
import requests
from datetime import datetime
from typing import Dict, List, Any


def fetch_and_update_threat_patterns() -> Dict[str, Any]:
    """
    Fetches threat intelligence from various sources and updates the fraud_patterns.yaml file.
    
    This tool:
    1. Fetches data from RSS feeds and web sources
    2. Analyzes content for authorized fraud patterns
    3. Updates the fraud_patterns.yaml file with new findings
    4. Uploads results to S3 if configured
    
    Returns:
        Dict containing execution status and summary
    """
    logging.info("Starting AUTHORIZED SCAM intelligence gathering (enhanced with 15+ sources)...")
    
    # ENHANCED: 15+ specialized sources for authorized fraud/scam intelligence
    threat_feeds = {
        # Tier 1: Premier Fraud & Banking Security (Best Coverage)
        "https://krebsonsecurity.com/feed/": "Krebs on Security",
        "https://www.bankinfosecurity.com/rss-feeds": "Bank Info Security",
        "https://www.fraud.org/feed": "National Consumers League Fraud.org",
        
        # Tier 2: Cybersecurity with Strong Fraud Coverage
        "https://www.infosecurity-magazine.com/rss/news/": "Infosecurity Magazine",
        "https://threatpost.com/feed/": "Threatpost",
        "https://www.darkreading.com/rss_simple.asp": "Dark Reading",
        "https://www.securityweek.com/feed/": "SecurityWeek",
        
        # Tier 3: Financial Crime & Compliance
        "https://www.financialfraudaction.org.uk/feed/": "Financial Fraud Action UK",
        "https://www.pymnts.com/feed/": "PYMNTS - Payment Fraud News",
        
        # Tier 4: Business Email Compromise (BEC) Specialists  
        "https://www.bleepingcomputer.com/feed/": "BleepingComputer",
        "https://feeds.feedburner.com/TheHackersNews": "The Hacker News",
        
        # Tier 5: Social Engineering & Phishing Intelligence
        "https://blog.knowbe4.com/rss.xml": "KnowBe4 Security Blog",
        "https://www.proofpoint.com/us/blog/rss.xml": "Proofpoint Threat Intelligence",
        
        # Tier 6: Banking Trojan & Financial Malware
        "https://www.welivesecurity.com/feed/": "ESET WeLiveSecurity",
        "https://blog.talosintelligence.com/rss/": "Cisco Talos Intelligence",
    }
    
    patterns = []
    error_count = 0
    fraud_specific_count = 0
    banking_related_count = 0
    
    for feed_url, source_name in threat_feeds.items():
        try:
            logging.info(f"Fetching feed: {source_name} ({feed_url})")
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                logging.warning(f"No entries found in feed: {source_name}")
                continue
            
            # Process entries from feed
            for entry in feed.entries[:10]:  # Check more entries but filter strictly
                title = entry.get('title', 'N/A')
                summary = entry.get('summary', entry.get('description', ''))
                full_text = title + ' ' + summary
                
                # Analyze the content
                fraud_category = _categorize_fraud_type(full_text)
                is_banking_related = _is_banking_related(full_text)
                
                # ⚠️ STRICT FILTER: ONLY keep authorized scam/fraud patterns
                if not _is_authorized_scam_relevant(full_text, fraud_category, is_banking_related):
                    continue  # Skip this entry
                
                risk_level = _analyze_risk_level(full_text)
                confidence_score = _calculate_confidence_score(full_text, fraud_category, is_banking_related)
                
                # Only keep patterns with decent confidence (>0.6)
                if confidence_score < 0.6:
                    continue
                
                if 'fraud' in fraud_category or 'scam' in fraud_category:
                    fraud_specific_count += 1
                if is_banking_related:
                    banking_related_count += 1
                
                # Enhanced intelligence extraction
                threat_actors = _extract_threat_actors(full_text)
                attack_vectors = _identify_attack_vectors(full_text)
                target_sectors = _identify_target_sectors(full_text)
                recommended_mitigations = _get_mitigation_recommendations(fraud_category, attack_vectors)
                
                pattern = {
                    'source': source_name,
                    'source_url': feed_url,
                    'title': title,
                    'link': entry.get('link', 'N/A'),
                    'published': entry.get('published', str(datetime.now())),
                    'summary': summary[:300],  # First 300 chars for better context
                    'risk_level': risk_level,
                    'fraud_category': fraud_category,
                    'banking_related': is_banking_related,
                    'confidence_score': confidence_score,
                    'fetched_at': datetime.now().isoformat(),
                    
                    # Enhanced intelligence fields
                    'threat_actors': threat_actors,
                    'attack_vectors': attack_vectors,
                    'target_sectors': target_sectors,
                    'mitigations': recommended_mitigations,
                    'urgency': _calculate_urgency(risk_level, confidence_score, is_banking_related)
                }
                patterns.append(pattern)
                
                logging.info(f"  ✓ Found authorized scam: {title[:60]}... (confidence: {confidence_score:.2f}, urgency: {pattern['urgency']})")
                
        except Exception as e:
            logging.warning(f"Failed to fetch feed {source_name}: {str(e)}")
            error_count += 1
    
    # Update YAML file
    try:
        yaml_path = 'fraud_patterns.yaml'
        
        # Load existing patterns if file exists
        existing_data = {'patterns': []}
        if os.path.exists(yaml_path):
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    existing_data = yaml.safe_load(f) or {'patterns': []}
            except Exception as e:
                logging.warning(f"Could not load existing YAML: {e}")
        
        # Add metadata with enhanced analytics
        result_data = {
            'last_update': datetime.now().isoformat(),
            'total_patterns': len(patterns),
            'sources_checked': len(threat_feeds),
            'fraud_specific_patterns': fraud_specific_count,
            'banking_related_patterns': banking_related_count,
            'errors': error_count,
            'source_details': [{'url': url, 'name': name} for url, name in threat_feeds.items()],
            'patterns': patterns
        }
        
        # Write updated data
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(result_data, f, default_flow_style=False, allow_unicode=True)
        
        logging.info(f"Successfully updated {yaml_path} with {len(patterns)} patterns")
        logging.info(f"  - Fraud-specific: {fraud_specific_count}")
        logging.info(f"  - Banking-related: {banking_related_count}")
        
        # Optional: Upload to S3 if configured
        s3_bucket = os.getenv('S3_BUCKET_NAME')
        if s3_bucket:
            try:
                _upload_to_s3(yaml_path, s3_bucket)
            except Exception as e:
                logging.warning(f"S3 upload failed: {e}")
        
        return {
            'status': 'success',
            'patterns_found': len(patterns),
            'fraud_specific': fraud_specific_count,
            'banking_related': banking_related_count,
            'sources_checked': len(threat_feeds),
            'errors': error_count,
            'output_file': yaml_path
        }
        
    except Exception as e:
        logging.error(f"Failed to update patterns file: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'patterns_found': len(patterns)
        }


def _is_authorized_scam_relevant(text: str, fraud_category: str, is_banking: bool) -> bool:
    """
    Strict filter: ONLY keep patterns relevant to AUTHORIZED SCAMS.
    
    Authorized scams involve victims being tricked into authorizing fraudulent transactions.
    
    Args:
        text: Full text to analyze
        fraud_category: Already categorized fraud type
        is_banking: Whether it's banking-related
        
    Returns:
        True if relevant to authorized scams, False otherwise
    """
    text_lower = text.lower()
    
    # Must have at least ONE of these core authorized scam indicators
    authorized_scam_keywords = [
        # Direct authorized fraud terms
        'authorized push payment', 'app fraud', 'authorized fraud', 
        'push payment scam', 'authorized transaction',
        
        # Social engineering (key to authorized scams)
        'social engineering', 'social engineer', 'pretexting',
        'impersonation', 'impersonate', 'imposter',
        
        # Business Email Compromise (authorized by victim)
        'business email compromise', 'bec', 'ceo fraud', 'cfo fraud',
        'invoice fraud', 'invoice scam', 'vendor fraud', 'vendor impersonation',
        'payroll diversion', 'wire fraud', 'wire transfer fraud',
        
        # Banking fraud (victim authorizes)
        'bank fraud', 'banking scam', 'banking fraud', 'financial fraud',
        'account takeover', 'credential theft', 'stolen credentials',
        
        # Phishing leading to authorized actions
        'phishing', 'spear phishing', 'whaling', 'vishing', 'voice phishing',
        'smishing', 'fake website', 'fake bank', 'fake portal',
        
        # Payment fraud (authorized by victim)
        'payment fraud', 'payment scam', 'fraudulent payment',
        'fake invoice', 'fake payment request', 
        
        # Romance/Investment scams (victim sends money)
        'romance scam', 'investment scam', 'crypto scam',
        
        # Other relevant terms
        'scam', 'fraud', 'deception', 'trick', 'manipulation',
        'convince', 'deceive', 'dupe'
    ]
    
    # Check if any authorized scam keywords are present
    has_scam_keyword = any(keyword in text_lower for keyword in authorized_scam_keywords)
    
    # Must be relevant fraud category OR banking-related with scam indicators
    is_relevant_category = fraud_category in [
        'banking_fraud',
        'business_email_compromise', 
        'phishing_social_engineering',
        'general_scam',
        'cryptocurrency_scam'
    ]
    
    # Exclude pure technical vulnerabilities or malware unless fraud-related
    exclude_keywords = [
        'dos', 'ddos', 'botnet', 'vulnerability patch', 'cve-',
        'zero-day exploit', 'buffer overflow', 'sql injection'
    ]
    
    # If it's purely technical without fraud context, exclude it
    is_purely_technical = any(keyword in text_lower for keyword in exclude_keywords) and not has_scam_keyword
    
    if is_purely_technical:
        return False
    
    # MUST have scam keywords AND (relevant category OR banking context)
    return has_scam_keyword and (is_relevant_category or is_banking)


def _analyze_risk_level(text: str) -> str:
    """
    Enhanced heuristic to assign risk levels based on keywords and context.
    
    Args:
        text: Text to analyze
        
    Returns:
        Risk level: 'critical', 'high', 'medium', or 'low'
    """
    text_lower = text.lower()
    
    # Critical: Immediate threat, widespread impact, or zero-day
    critical_keywords = [
        'ransomware', 'zero-day', 'critical vulnerability', 'data breach', 
        'compromise', 'widespread attack', 'nation-state', 'supply chain attack',
        'actively exploited', 'millions affected'
    ]
    
    # High: Serious threats including fraud and financial crimes
    high_keywords = [
        'malware', 'phishing', 'exploit', 'attack', 'fraud', 'scam',
        'authorized push payment', 'app fraud', 'banking trojan', 'credential theft',
        'social engineering', 'wire fraud', 'payment fraud', 'account takeover',
        'business email compromise', 'bec attack', 'financial theft'
    ]
    
    # Medium: Vulnerabilities and warnings that need attention
    medium_keywords = [
        'vulnerability', 'patch', 'security update', 'warning', 'advisory',
        'misconfiguration', 'exposure', 'weak password', 'outdated software'
    ]
    
    if any(keyword in text_lower for keyword in critical_keywords):
        return 'critical'
    elif any(keyword in text_lower for keyword in high_keywords):
        return 'high'
    elif any(keyword in text_lower for keyword in medium_keywords):
        return 'medium'
    else:
        return 'low'


def _categorize_fraud_type(text: str) -> str:
    """
    Categorize the type of fraud or threat based on content analysis.
    
    Args:
        text: Text to analyze
        
    Returns:
        Fraud category as a string
    """
    text_lower = text.lower()
    
    # Banking and Financial Fraud
    if any(keyword in text_lower for keyword in [
        'authorized push payment', 'app fraud', 'wire fraud', 'payment fraud',
        'banking trojan', 'bank fraud', 'financial fraud', 'account takeover',
        'authorized fraud', 'push payment scam', 'invoice fraud'
    ]):
        return 'banking_fraud'
    
    # Business Email Compromise
    if any(keyword in text_lower for keyword in [
        'business email compromise', 'bec', 'ceo fraud', 'invoice scam',
        'vendor fraud', 'payroll diversion'
    ]):
        return 'business_email_compromise'
    
    # Phishing and Social Engineering
    if any(keyword in text_lower for keyword in [
        'phishing', 'spear phishing', 'smishing', 'vishing', 'social engineering',
        'pretexting', 'impersonation', 'fake website'
    ]):
        return 'phishing_social_engineering'
    
    # Ransomware
    if any(keyword in text_lower for keyword in [
        'ransomware', 'crypto locker', 'file encryption', 'ransom demand'
    ]):
        return 'ransomware'
    
    # Malware
    if any(keyword in text_lower for keyword in [
        'malware', 'trojan', 'virus', 'worm', 'botnet', 'backdoor', 'rootkit'
    ]):
        return 'malware'
    
    # Data Breach / Theft
    if any(keyword in text_lower for keyword in [
        'data breach', 'data leak', 'credential theft', 'data exfiltration',
        'stolen credentials', 'database leak'
    ]):
        return 'data_breach'
    
    # Cryptocurrency Scams
    if any(keyword in text_lower for keyword in [
        'crypto scam', 'cryptocurrency fraud', 'bitcoin scam', 'nft scam',
        'defi hack', 'crypto theft'
    ]):
        return 'cryptocurrency_scam'
    
    # Other Scams
    if any(keyword in text_lower for keyword in ['scam', 'fraud', 'deception']):
        return 'general_scam'
    
    # Vulnerabilities
    if any(keyword in text_lower for keyword in [
        'vulnerability', 'cve', 'exploit', 'zero-day', 'security flaw'
    ]):
        return 'vulnerability'
    
    return 'other'


def _is_banking_related(text: str) -> bool:
    """
    Determine if the content is related to banking or financial services.
    
    Args:
        text: Text to analyze
        
    Returns:
        True if banking-related, False otherwise
    """
    text_lower = text.lower()
    
    banking_keywords = [
        'bank', 'banking', 'financial', 'payment', 'transaction', 'account',
        'credit card', 'debit card', 'atm', 'wire transfer', 'swift',
        'fintech', 'finance', 'monetary', 'currency', 'authorized push payment',
        'app fraud', 'payment processor', 'merchant', 'payroll', 'invoice',
        'financial institution', 'credit union', 'online banking', 'mobile banking',
        'payment gateway', 'pos system', 'point of sale', 'clearing house',
        'ach transfer', 'zelle', 'venmo', 'paypal', 'cryptocurrency exchange'
    ]
    
    return any(keyword in text_lower for keyword in banking_keywords)


def _calculate_confidence_score(text: str, fraud_category: str, is_banking: bool) -> float:
    """
    Calculate a confidence score for how relevant this threat is to authorized banking fraud.
    
    Args:
        text: Full text of the threat
        fraud_category: Categorized fraud type
        is_banking: Whether it's banking-related
        
    Returns:
        Confidence score from 0.0 to 1.0
    """
    score = 0.5  # Base score
    text_lower = text.lower()
    
    # High value categories
    if fraud_category == 'banking_fraud':
        score += 0.3
    elif fraud_category in ['business_email_compromise', 'phishing_social_engineering']:
        score += 0.2
    
    # Banking context adds value
    if is_banking:
        score += 0.15
    
    # Specific high-value keywords
    high_value_keywords = [
        'authorized push payment', 'app fraud', 'authorized fraud',
        'social engineering', 'payment fraud', 'wire fraud'
    ]
    keyword_matches = sum(1 for keyword in high_value_keywords if keyword in text_lower)
    score += min(keyword_matches * 0.05, 0.15)
    
    # Recent/current threat indicators
    if any(word in text_lower for word in ['new', 'emerging', 'recent', 'current', 'active']):
        score += 0.05
    
    # Cap at 1.0
    return min(score, 1.0)


def _extract_threat_actors(text: str) -> List[str]:
    """
    Extract known threat actor names from the text.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of identified threat actor names
    """
    text_lower = text.lower()
    actors = []
    
    # Known threat actor groups related to fraud
    known_actors = [
        'scattered spider', 'shinyhunters', 'evil corp', 'fin7', 'fin8',
        'carbanak', 'cobalt group', 'lazarus', 'apt38', 'silence',
        'wizard spider', 'trickbot', 'emotet', 'dridex', 'zloader',
        'goznym', 'dyre', 'zeus', 'carberp', 'tinba', 'qakbot',
        'octopus', '0ktapus', 'lapsus', 'lapsus$', 'conti',
        'lockbit', 'alphv', 'blackcat', 'cl0p', 'revil'
    ]
    
    for actor in known_actors:
        if actor in text_lower:
            actors.append(actor.title())
    
    return actors if actors else ['Unknown']


def _identify_attack_vectors(text: str) -> List[str]:
    """
    Identify attack vectors used in the fraud scheme.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of identified attack vectors
    """
    text_lower = text.lower()
    vectors = []
    
    vector_mapping = {
        'email': ['email', 'phishing email', 'spear phishing', 'business email compromise', 'bec'],
        'phone_call': ['phone call', 'vishing', 'voice phishing', 'telephone', 'cold call'],
        'sms': ['sms', 'text message', 'smishing', 'text'],
        'social_media': ['social media', 'facebook', 'twitter', 'linkedin', 'instagram', 'whatsapp'],
        'fake_website': ['fake website', 'spoofed site', 'phishing site', 'malicious link', 'fake portal'],
        'malware': ['malware', 'trojan', 'banking trojan', 'keylogger', 'backdoor'],
        'credential_theft': ['stolen credentials', 'credential theft', 'password theft', 'account compromise'],
        'impersonation': ['impersonation', 'impersonate', 'pretending', 'posing as', 'fake identity'],
        'invoice_manipulation': ['fake invoice', 'altered invoice', 'invoice fraud', 'payment redirect'],
        'wire_transfer': ['wire transfer', 'bank transfer', 'ach', 'swift', 'payment instruction']
    }
    
    for vector_name, keywords in vector_mapping.items():
        if any(keyword in text_lower for keyword in keywords):
            vectors.append(vector_name)
    
    return vectors if vectors else ['social_engineering']


def _identify_target_sectors(text: str) -> List[str]:
    """
    Identify target sectors/industries mentioned.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of target sectors
    """
    text_lower = text.lower()
    sectors = []
    
    sector_mapping = {
        'Banking': ['bank', 'banking', 'financial institution', 'credit union'],
        'Healthcare': ['hospital', 'healthcare', 'medical', 'patient'],
        'Retail': ['retail', 'e-commerce', 'online store', 'merchant'],
        'Government': ['government', 'municipal', 'federal', 'state agency'],
        'Education': ['university', 'school', 'education', 'college'],
        'Technology': ['tech company', 'software', 'saas', 'cloud provider'],
        'Manufacturing': ['manufacturing', 'factory', 'production', 'supply chain'],
        'Finance': ['finance', 'investment', 'trading', 'fintech', 'payment processor'],
        'Insurance': ['insurance', 'insurer', 'policy holder'],
        'Small Business': ['small business', 'smb', 'small enterprise']
    }
    
    for sector_name, keywords in sector_mapping.items():
        if any(keyword in text_lower for keyword in keywords):
            sectors.append(sector_name)
    
    return sectors if sectors else ['General']


def _get_mitigation_recommendations(fraud_category: str, attack_vectors: List[str]) -> List[str]:
    """
    Generate mitigation recommendations based on fraud category and attack vectors.
    
    Args:
        fraud_category: Type of fraud
        attack_vectors: Attack vectors identified
        
    Returns:
        List of mitigation recommendations
    """
    mitigations = []
    
    # Category-specific mitigations
    if fraud_category == 'banking_fraud':
        mitigations.extend([
            'Implement multi-factor authentication for all transactions',
            'Enable transaction monitoring and alerts',
            'Verify payment changes via secondary channel',
            'Train staff on authorized push payment fraud indicators'
        ])
    
    if fraud_category == 'business_email_compromise':
        mitigations.extend([
            'Implement email authentication (SPF, DKIM, DMARC)',
            'Establish verification procedures for wire transfers',
            'Use out-of-band verification for payment changes',
            'Train employees on CEO fraud tactics'
        ])
    
    if fraud_category == 'phishing_social_engineering':
        mitigations.extend([
            'Conduct regular phishing awareness training',
            'Implement email filtering and link scanning',
            'Enable MFA on all accounts',
            'Report suspicious emails to security team'
        ])
    
    # Vector-specific mitigations
    if 'email' in attack_vectors:
        mitigations.append('Deploy advanced email security solutions')
    
    if 'phone_call' in attack_vectors or 'sms' in attack_vectors:
        mitigations.append('Verify caller identity through official channels')
    
    if 'fake_website' in attack_vectors:
        mitigations.append('Check URL carefully and bookmark legitimate sites')
    
    if 'malware' in attack_vectors:
        mitigations.append('Keep antivirus updated and scan regularly')
    
    if 'credential_theft' in attack_vectors:
        mitigations.append('Change passwords immediately if compromise suspected')
    
    # Generic mitigations
    mitigations.extend([
        'Verify unusual requests through alternate communication channel',
        'Be suspicious of urgent payment requests',
        'Never share sensitive information via email or phone'
    ])
    
    # Remove duplicates and limit to top 5
    return list(dict.fromkeys(mitigations))[:5]


def _calculate_urgency(risk_level: str, confidence: float, is_banking: bool) -> str:
    """
    Calculate urgency level for the threat.
    
    Args:
        risk_level: Risk level (critical/high/medium/low)
        confidence: Confidence score
        is_banking: Whether banking-related
        
    Returns:
        Urgency level: 'immediate', 'high', 'medium', 'low'
    """
    score = 0
    
    # Risk level contribution
    if risk_level == 'critical':
        score += 4
    elif risk_level == 'high':
        score += 3
    elif risk_level == 'medium':
        score += 2
    else:
        score += 1
    
    # Confidence contribution
    if confidence >= 0.9:
        score += 3
    elif confidence >= 0.75:
        score += 2
    elif confidence >= 0.6:
        score += 1
    
    # Banking-related boost
    if is_banking:
        score += 1
    
    # Determine urgency
    if score >= 7:
        return 'immediate'
    elif score >= 5:
        return 'high'
    elif score >= 3:
        return 'medium'
    else:
        return 'low'


def _upload_to_s3(file_path: str, bucket_name: str) -> None:
    """
    Upload a file to S3 bucket.
    
    Args:
        file_path: Path to the file to upload
        bucket_name: Name of the S3 bucket
    """
    try:
        import boto3
        
        s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        
        # Upload file
        s3_key = f"threat-intel/{os.path.basename(file_path)}"
        s3_client.upload_file(file_path, bucket_name, s3_key)
        
        logging.info(f"Successfully uploaded {file_path} to s3://{bucket_name}/{s3_key}")
        
    except Exception as e:
        raise Exception(f"S3 upload error: {str(e)}")

