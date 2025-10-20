"""
Hybrid Deployment Option
Use your existing API server with optional AgentCore Runtime integration
"""

import os
from typing import Dict, Any, Optional
import boto3
import json
import uuid

# Your existing working imports
from langgraph_multi_agent import (
    run_strands_multi_agent,
    stream_strands_steps,
    get_case_history,
    search_case_patterns
)

class HybridFraudDetectionService:
    """
    Hybrid service that can use either local processing or AgentCore Runtime
    Falls back gracefully if AgentCore Runtime is not available
    """
    
    def __init__(self, agentcore_arn: Optional[str] = None):
        self.agentcore_arn = agentcore_arn
        self.agentcore_client = None
        
        if agentcore_arn:
            try:
                self.agentcore_client = boto3.client('bedrock-agentcore')
                print(f"✅ AgentCore Runtime available: {agentcore_arn}")
            except Exception as e:
                print(f"⚠️ AgentCore Runtime not available: {e}")
                self.agentcore_client = None
        else:
            print("🏠 Using local processing only")
    
    def process_fraud_alert(self, alert_data: Dict[str, Any], prefer_cloud: bool = False) -> Dict[str, Any]:
        """
        Process fraud alert with hybrid approach
        
        Args:
            alert_data: Fraud alert to process
            prefer_cloud: Try AgentCore Runtime first if available
        
        Returns:
            Processing results
        """
        
        # Try AgentCore Runtime if available and preferred
        if prefer_cloud and self.agentcore_client and self.agentcore_arn:
            try:
                return self._process_via_agentcore(alert_data)
            except Exception as e:
                print(f"⚠️ AgentCore Runtime failed, falling back to local: {e}")
        
        # Use local processing (your existing working system)
        return self._process_locally(alert_data)
    
    def _process_via_agentcore(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process via AgentCore Runtime"""
        payload = {
            "action": "process_alert",
            "mode": "full",
            "alert": alert_data
        }
        
        response = self.agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=self.agentcore_arn,
            runtimeSessionId=str(uuid.uuid4()),
            payload=json.dumps(payload).encode(),
            qualifier="DEFAULT"
        )
        
        content = []
        for chunk in response.get("response", []):
            content.append(chunk.decode('utf-8'))
        
        result = json.loads(''.join(content))
        result['processing_mode'] = 'agentcore_runtime'
        return result
    
    def _process_locally(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process using your existing local system"""
        result = run_strands_multi_agent(alert_data)
        result['processing_mode'] = 'local'
        return result
    
    def get_case_analysis(self, case_id: str) -> Dict[str, Any]:
        """Get case analysis (always uses local memory integration)"""
        try:
            history = get_case_history(case_id)
            return {
                "case_id": case_id,
                "history": history,
                "status": "success",
                "source": "agentcore_memory"
            }
        except Exception as e:
            return {
                "case_id": case_id,
                "error": str(e),
                "status": "error"
            }

# Example usage in your API server
def create_hybrid_service():
    """Create hybrid service - works with or without AgentCore Runtime"""
    
    # Try to get AgentCore Runtime ARN from environment
    agentcore_arn = os.getenv("AGENTCORE_RUNTIME_ARN")
    
    return HybridFraudDetectionService(agentcore_arn)

# Integration example for your FastAPI server
"""
# Add to your api_server.py:

hybrid_service = create_hybrid_service()

@app.post("/api/fraud/analyze")
async def analyze_fraud_hybrid(alert: dict, prefer_cloud: bool = False):
    '''
    Analyze fraud with hybrid approach
    prefer_cloud=True: Try AgentCore Runtime first
    prefer_cloud=False: Use local processing
    '''
    result = hybrid_service.process_fraud_alert(alert, prefer_cloud)
    return result

@app.get("/api/fraud/case/{case_id}")
async def get_case_analysis(case_id: str):
    '''Get case analysis from AgentCore Memory'''
    return hybrid_service.get_case_analysis(case_id)
"""

if __name__ == "__main__":
    # Test the hybrid service
    service = create_hybrid_service()
    
    test_alert = {
        "alertId": "HYBRID_TEST_001",
        "customerId": "AU-CUST7712",
        "amount": 5000,
        "priority": "HIGH"
    }
    
    print("🧪 Testing Hybrid Service")
    print("=" * 40)
    
    # Test local processing
    print("🏠 Testing local processing...")
    result_local = service.process_fraud_alert(test_alert, prefer_cloud=False)
    print(f"✅ Local result: {result_local.get('processing_mode', 'unknown')}")
    
    # Test cloud processing (will fall back to local if not available)
    print("☁️ Testing cloud processing...")
    result_cloud = service.process_fraud_alert(test_alert, prefer_cloud=True)
    print(f"✅ Cloud result: {result_cloud.get('processing_mode', 'unknown')}")