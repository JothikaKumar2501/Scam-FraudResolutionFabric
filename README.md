# ANZ Bank Authorized Scam Detection System

Run backend:
python -m uvicorn api_server:app --host 127.0.0.1 --port 8002 --reload
Run frontend:
cd frontend ; set NEXT_PUBLIC_API_BASE=http://127.0.0.1:8002 ; npm run dev

## Overview

A production-ready, intelligent multi-agent system for detecting and preventing authorized payment scams (APP fraud) at ANZ Bank. This system uses advanced AI agents with dynamic, context-aware capabilities to protect customers from sophisticated social engineering attacks.

## 🚀 Key Features

### Advanced Intelligent Agents
- **TransactionContextAgent**: Expert transaction analysis with fraud typology identification
- **CustomerInfoAgent**: Behavioral biometrics and vulnerability assessment
- **MerchantInfoAgent**: Merchant risk analysis and industry-specific expertise
- **BehavioralPatternAgent**: Social engineering detection and anomaly analysis
- **RiskSynthesizerAgent**: Comprehensive risk assessment with scam typology identification
- **TriageAgent**: Intelligent escalation and dialogue decision making
- **DialogueAgent**: Dynamic question generation and fact extraction
- **RiskAssessorAgent**: Progressive risk assessment and final determination
- **PolicyDecisionAgent**: Regulatory-compliant policy decisions
- **FeedbackCollectorAgent**: Structured improvement analysis
- **SupervisorAgent**: Intelligent orchestration and decision making

### Dynamic Configuration System
- **Environment-based configuration** with intelligent defaults
- **Agent-specific settings** with specialized capabilities
- **Regulatory compliance** with AUSTRAC, APRA, ASIC requirements
- **Customer protection measures** with vulnerability assessment
- **Fraud pattern recognition** with dynamic typology identification

### Production-Ready Features
- **Real-time processing** with concurrent agent execution
- **Error handling** with graceful degradation
- **Performance monitoring** with comprehensive metrics
- **Regulatory compliance** with full audit trail
- **Customer protection** with multi-layered security

## 🏗️ Architecture

### Intelligent Agent Framework
```
┌─────────────────────────────────────────────────────────────┐
│                    Supervisor Agent                        │
│              (Intelligent Orchestration)                   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
│ Context Agents  │  │ Analysis Agents │  │ Decision Agents │
│                 │  │                 │  │                 │
│ • Transaction   │  │ • Risk Synthesis│  │ • Triage        │
│ • Customer      │  │ • Behavioral    │  │ • Policy        │
│ • Merchant      │  │ • Anomaly       │  │ • Feedback      │
│ • Behavioral    │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Dialogue Agent   │
                    │ (Customer Contact)│
                    └───────────────────┘
```

### Configuration Structure
```
config/
├── sops.yaml              # Standard Operating Procedures
├── questions.yaml         # Dynamic Question Generation
├── fraud_patterns.yaml    # Pattern Recognition
├── regulatory.yaml        # Regulatory Requirements
└── customer_protection.yaml # Protection Measures
```

## 🛠️ Installation

### Prerequisites
- Python 3.9+
- AWS Bedrock access
- Vector database (Qdrant)
- Optional: Mem0 Graph (Neo4j AuraDB or local)

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd genai_for_payments

# Install dependencies
pip install -r requirements.txt

# Set environment variables (example)
export AWS_REGION=us-east-1
export AWS_CLAUDE_INFERENCE_PROFILE_ARN=arn:aws:bedrock:us-east-1:123456789012:inference-profile/<your-anthropic-profile>
export AWS_TITAN_MODEL_ID=amazon.titan-embed-text-v2:0
# or prefer using an inference profile
# export AWS_CLAUDE_INFERENCE_PROFILE_ARN=arn:aws:bedrock:...:inference-profile/...
export ENVIRONMENT=production
export LOG_LEVEL=INFO

# Qdrant
export QDRANT_URL=https://<your-cluster>.aws.cloud.qdrant.io:6333
export QDRANT_API_KEY=... 

# Mem0
export MEM0_API_KEY=m0-...

# Neo4j (optional Mem0 Graph)
export NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=...
export NEO4J_DATABASE=neo4j

# Initialize configuration
python -c "from config import config; print('Configuration loaded successfully')"
```

## 🚀 Usage

### Basic Usage
```python
from agents_multi import SupervisorAgent
from context_store import ContextStore

# Initialize the system
context_store = ContextStore()
supervisor = SupervisorAgent(context_store)

# Run fraud detection
alert = {
    "alertId": "ALRT-AU-CUST1053-1",
    "customerId": "AU-CUST1053",
    "amount": 13800,
    "payee": "FixPro Electrical",
    "transactionType": "Business payment/transfer"
}

# Run intelligent fraud detection
report, agent_log = supervisor.run_fraud_detection(alert)
print(f"Detection completed. Agents used: {agent_log}")
```

### Advanced Usage with User Interaction
```python
def user_input_handler(question):
    """Handle user input for dialogue"""
    return input(f"Agent: {question}\nYou: ")

# Run with user interaction
report, agent_log = supervisor.run_fraud_detection(
    alert, 
    user_io=user_input_handler
)
```

### Streaming Output
```python
def stream_callback(agent_name, result):
    """Handle streaming agent outputs"""
    print(f"{agent_name}: {result}")

# Run with streaming
report, agent_log = supervisor.run_fraud_detection(
    alert,
    stream_callback=stream_callback
)
```

## 🔧 Configuration

### Environment Variables
```bash
# Core Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
AWS_REGION=ap-southeast-2
BEDROCK_MODEL=anthropic.claude-3-sonnet-20240229-v1:0

# Performance Settings
MAX_CONCURRENT_AGENTS=4
REQUEST_TIMEOUT=30
RETRY_ATTEMPTS=3
CACHE_ENABLED=true
ASYNC_PROCESSING=true

# Agent Settings
MAX_DIALOGUE_TURNS=15
SEMANTIC_SIMILARITY_THRESHOLD=0.75
RISK_FINALIZATION_THRESHOLD=0.85
MAX_TOKENS_PER_RESPONSE=2048
```

### Agent Configuration
Each agent has intelligent, dynamic configuration:

```python
from config import config

# Get agent configuration
agent_config = config.get_agent_config('RiskAssessorAgent')
print(f"Max tokens: {agent_config.max_tokens}")
print(f"Confidence threshold: {agent_config.confidence_threshold}")
```

## 📊 Scam Typologies Supported

### Business Email Compromise (BEC)
- **Risk Score**: 0.9
- **Indicators**: Vendor impersonation, banking detail changes, invoice redirection
- **Verification**: Vendor contact, banking verification, invoice verification

### Romance Scams
- **Risk Score**: 0.85
- **Indicators**: Emotional manipulation, urgent requests, isolation tactics
- **Verification**: Relationship authenticity, identity verification, meeting confirmation

### Investment Scams
- **Risk Score**: 0.9
- **Indicators**: Promised returns, pressure tactics, fake platforms
- **Verification**: Platform legitimacy, regulatory compliance, return realism

### Tech Support Scams
- **Risk Score**: 0.8
- **Indicators**: Remote access, urgent technical issues, payment demands
- **Verification**: Technical issue authenticity, remote access legitimacy

### Impersonation Scams
- **Risk Score**: 0.85
- **Indicators**: Government impersonation, authority claims, urgent legal action
- **Verification**: Identity verification, authority confirmation, contact legitimacy

## 🛡️ Regulatory Compliance

### AUSTRAC Requirements
- **Suspicious Matter Reports** (24-hour timeframe)
- **Enhanced Due Diligence** for high-risk customers
- **Customer Identification** requirements

### APRA CPG 234
- **Information Security Controls**
- **Customer Protection Measures**
- **Fraud Monitoring Capabilities**

### ASIC RG 271
- **Consumer Harm Prevention**
- **Reasonable Steps Obligations**
- **Customer Outcome Focus**

### Banking Code of Practice
- **Scam Prevention Measures**
- **Vulnerable Customer Support**
- **Dispute Resolution Processes**

## 📈 Performance Monitoring

### Key Metrics
- **Detection Accuracy**: Scam identification rate
- **False Positive Rate**: Legitimate transaction blocking
- **Customer Protection**: Financial loss prevention
- **Regulatory Compliance**: Requirement adherence

### Continuous Improvement
- **Feedback Collection**: Customer surveys, incident reviews
- **System Enhancement**: Content updates, delivery methods
- **Performance Optimization**: Agent efficiency, response times

## 🔒 Security Features

### Customer Protection
- **Enhanced Monitoring** for vulnerable customers
- **Transaction Limits** with intelligent thresholds
- **Cooling-off Periods** for large transactions
- **Real-time Blocking** of suspicious transactions

### Data Protection
- **Multi-factor Authentication**
- **Biometric Authentication**
- **Device Verification**
- **Location Monitoring**

### Education and Support
- **Mandatory Training** for high-risk customers
- **Ongoing Education** with quarterly updates
- **Family Communication** for vulnerable customers
- **Recovery Support** for scam victims

## 🧪 Testing

### Unit Tests
```bash
python -m pytest tests/unit/
```

### Integration Tests
```bash
python -m pytest tests/integration/
```

### Performance Tests
```bash
python -m pytest tests/performance/
```

## 📝 Documentation

### Agent Documentation
- [TransactionContextAgent](docs/agents/transaction_context.md)
- [CustomerInfoAgent](docs/agents/customer_info.md)
- [MerchantInfoAgent](docs/agents/merchant_info.md)
- [BehavioralPatternAgent](docs/agents/behavioral_pattern.md)
- [RiskSynthesizerAgent](docs/agents/risk_synthesizer.md)
- [TriageAgent](docs/agents/triage.md)
- [DialogueAgent](docs/agents/dialogue.md)
- [RiskAssessorAgent](docs/agents/risk_assessor.md)
- [PolicyDecisionAgent](docs/agents/policy_decision.md)
- [FeedbackCollectorAgent](docs/agents/feedback_collector.md)
- [SupervisorAgent](docs/agents/supervisor.md)

### Configuration Documentation
- [SOPs Configuration](docs/config/sops.md)
- [Questions Configuration](docs/config/questions.md)
- [Fraud Patterns](docs/config/fraud_patterns.md)
- [Regulatory Requirements](docs/config/regulatory.md)
- [Customer Protection](docs/config/customer_protection.md)

## 🤝 Contributing

### Development Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt

# Run pre-commit hooks
pre-commit install
```

### Code Standards
- **Type Hints**: All functions must have type annotations
- **Documentation**: Comprehensive docstrings for all classes and methods
- **Testing**: Minimum 90% code coverage
- **Linting**: Black, isort, flake8 compliance

## 📄 License

This project is proprietary to ANZ Bank. All rights reserved.

## 🆘 Support

### Technical Support
- **Email**: fraud-detection-support@anz.com
- **Phone**: +61 3 9683 9999
- **Hours**: 24/7 for critical issues

### Documentation
- **User Guide**: [docs/user_guide.md](docs/user_guide.md)
- **API Reference**: [docs/api_reference.md](docs/api_reference.md)
- **Troubleshooting**: [docs/troubleshooting.md](docs/troubleshooting.md)

### Emergency Contacts
- **Security Issues**: security-incident@anz.com
- **Regulatory Issues**: regulatory-compliance@anz.com
- **Customer Issues**: customer-support@anz.com

---

**ANZ Bank Authorized Scam Detection System** - Protecting customers from sophisticated fraud with intelligent, production-ready technology.
