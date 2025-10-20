"""
Fraud Detection Agent for AgentCore Runtime
Wraps the existing langgraph_multi_agent.py system for deployment to AgentCore Runtime
"""

import json
import uuid
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import AgentCore Runtime framework
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent

# Import your existing working fraud detection system
from langgraph_multi_agent import (
    run_strands_multi_agent,
    stream_strands_steps,
    get_case_history,
    search_case_patterns,
    get_case_memories
)

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Initialize Strands agent for AgentCore compatibility
strands_agent = Agent()

class FraudDetectionAgent:
    """
    AgentCore Runtime wrapper for the fraud detection pipeline
    """
    
    def __init__(self):
        self.name = "FraudDetectionAgent"
        self.version = "1.0.0"
        print(f"✅ {self.name} v{self.version} initialized for AgentCore Runtime")
    
    def process_fraud_alert(self, alert_data: Dict[str, Any], mode: str = "full") -> Dict[str, Any]:
        """
        Process a fraud alert using the existing pipeline
        
        Args:
            alert_data: The fraud alert to process
            mode: Processing mode - "full", "streaming", or "quick"
        
        Returns:
            Processing results with case analysis
        """
        try:
            if mode == "streaming":
                # Use streaming for real-time processing
                final_state = None
                for state in stream_strands_steps(alert_data):
                    final_state = state
                return final_state or {"error": "Streaming failed"}
            
            elif mode == "quick":
                # Quick analysis with limited steps
                return run_strands_multi_agent(alert_data, max_steps=3)
            
            else:
                # Full analysis (default)
                return run_strands_multi_agent(alert_data)
                
        except Exception as e:
            return {
                "error": f"Processing failed: {str(e)}",
                "alert_id": alert_data.get('alertId', 'unknown'),
                "status": "error"
            }
    
    def get_case_analysis(self, case_id: str) -> Dict[str, Any]:
        """Get historical analysis for a case"""
        try:
            history = get_case_history(case_id)
            memories = get_case_memories(case_id, limit=5)
            
            return {
                "case_id": case_id,
                "history": history,
                "memories": memories,
                "status": "success"
            }
        except Exception as e:
            return {
                "case_id": case_id,
                "error": str(e),
                "status": "error"
            }
    
    def search_fraud_patterns(self, case_id: str, query: str) -> Dict[str, Any]:
        """Search for fraud patterns in case history"""
        try:
            patterns = search_case_patterns(case_id, query)
            # Ensure patterns is a list
            if not isinstance(patterns, list):
                patterns = []
            
            return {
                "case_id": case_id,
                "query": query,
                "patterns": patterns,
                "count": len(patterns),
                "status": "success"
            }
        except Exception as e:
            return {
                "case_id": case_id,
                "query": query,
                "error": str(e),
                "patterns": [],
                "count": 0,
                "status": "error"
            }

# Initialize the fraud detection agent
fraud_agent = FraudDetectionAgent()

@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    AgentCore Runtime entrypoint for fraud detection
    
    Expected payload formats:
    1. Fraud Alert Processing:
       {
         "action": "process_alert",
         "alert": { ... alert data ... },
         "mode": "full|streaming|quick"
       }
    
    2. Case History Retrieval:
       {
         "action": "get_case_history",
         "case_id": "CASE_001"
       }
    
    3. Pattern Search:
       {
         "action": "search_patterns",
         "case_id": "CASE_001",
         "query": "fraud indicators"
       }
    
    4. Simple Chat (for testing):
       {
         "prompt": "Hello, analyze this transaction..."
       }
    """
    
    try:
        # Handle simple chat/prompt for testing
        if "prompt" in payload and "action" not in payload:
            # Use Strands agent for simple responses
            result = strands_agent(payload.get("prompt", "Hello"))
            return {
                "result": result.message,
                "agent": "FraudDetectionAgent",
                "mode": "chat",
                "status": "success"
            }
        
        # Handle structured fraud detection actions
        action = payload.get("action", "process_alert")
        
        if action == "process_alert":
            alert_data = payload.get("alert", {})
            mode = payload.get("mode", "full")
            
            if not alert_data:
                return {
                    "error": "No alert data provided",
                    "status": "error",
                    "required_format": {
                        "action": "process_alert",
                        "alert": {"alertId": "...", "amount": "...", "customerId": "..."},
                        "mode": "full|streaming|quick"
                    }
                }
            
            result = fraud_agent.process_fraud_alert(alert_data, mode)
            result["agent"] = "FraudDetectionAgent"
            result["action"] = action
            return result
        
        elif action == "get_case_history":
            case_id = payload.get("case_id")
            if not case_id:
                return {"error": "case_id required", "status": "error"}
            
            result = fraud_agent.get_case_analysis(case_id)
            result["agent"] = "FraudDetectionAgent"
            result["action"] = action
            return result
        
        elif action == "search_patterns":
            case_id = payload.get("case_id")
            query = payload.get("query")
            
            if not case_id or not query:
                return {"error": "case_id and query required", "status": "error"}
            
            result = fraud_agent.search_fraud_patterns(case_id, query)
            result["agent"] = "FraudDetectionAgent"
            result["action"] = action
            return result
        
        else:
            return {
                "error": f"Unknown action: {action}",
                "status": "error",
                "supported_actions": ["process_alert", "get_case_history", "search_patterns"],
                "agent": "FraudDetectionAgent"
            }
    
    except Exception as e:
        return {
            "error": f"Agent execution failed: {str(e)}",
            "status": "error",
            "agent": "FraudDetectionAgent",
            "payload_received": payload
        }

if __name__ == "__main__":
    print("🚀 Starting Fraud Detection Agent for AgentCore Runtime...")
    print("📋 Supported actions:")
    print("   - process_alert: Analyze fraud alerts")
    print("   - get_case_history: Retrieve case analysis")
    print("   - search_patterns: Search fraud patterns")
    print("   - prompt: Simple chat interface")
    print()
    print("🌐 Starting server on http://localhost:8080")
    app.run()