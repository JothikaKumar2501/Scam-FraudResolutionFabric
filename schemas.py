from typing import TypedDict, List, Optional

class TransactionContext(TypedDict):
    txn_id: str
    amount: float
    timestamp: str
    location: str
    merchant_id: str
    user_id: str
    device_id: Optional[str]

class UserContext(TypedDict):
    user_id: str
    name: str
    age: int
    email: str
    phone: str
    demographics: dict
    call_history: List[dict]

class MerchantContext(TypedDict):
    merchant_id: str
    name: str
    category: str
    risk_level: str
    profile: dict

class AnomalyContext(TypedDict):
    anomaly_score: float
    anomaly_features: dict
    notes: Optional[str]

class RiskSummaryContext(TypedDict):
    risk_score: float
    explanation: str
    supporting_contexts: List[str]

class DecisionContext(TypedDict):
    action: str  # e.g., 'auto_block', 'escalate', 'allow'
    reason: str
    escalate: bool
    policy_rule: Optional[str]

class DialogueContext(TypedDict):
    dialogue_turns: List[dict]
    outcome: Optional[str]

class FeedbackContext(TypedDict):
    txn_id: str
    final_decision: str
    feedback_notes: Optional[str]
    timestamp: str 