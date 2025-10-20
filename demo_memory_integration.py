"""
Demo: AgentCore Memory Integration with Fraud Detection Pipeline
Shows how to use the enhanced pipeline with memory capabilities
"""

from dotenv import load_dotenv
load_dotenv()

# You can choose between:
# 1. Original implementation (no memory) - your existing working code
from langgraph_multi_agent import stream_strands_steps, run_strands_pipeline, run_strands_multi_agent

# 2. Enhanced implementation (with memory) - new memory-enabled version
from enhanced_langgraph_with_memory import (
    stream_strands_steps_with_memory, 
    run_strands_pipeline_with_memory,
    run_strands_multi_agent_with_memory,
    get_case_history,
    search_case_patterns
)

def demo_original_vs_enhanced():
    """Demo showing original vs enhanced pipeline"""
    
    # Sample fraud alert
    fraud_alert = {
        'alertId': 'DEMO_CASE_001',
        'customerId': 'CUST_12345',
        'amount': 5000,
        'recipient': 'unknown_account_xyz',
        'priority': 'HIGH',
        'ruleId': 'AUTHORIZED_FRAUD_RULE',
        'timestamp': '2024-01-15T10:30:00Z'
    }
    
    print("🚨 Fraud Detection Pipeline Demo")
    print("=" * 60)
    print(f"Processing Alert: {fraud_alert['alertId']}")
    print(f"Amount: ${fraud_alert['amount']}")
    print(f"Priority: {fraud_alert['priority']}")
    
    # Option 1: Use original pipeline (no memory)
    print("\n📊 Option 1: Original Pipeline (No Memory)")
    print("-" * 40)
    
    try:
        # This works exactly as before - your existing working code
        result_original = run_strands_multi_agent(fraud_alert, max_steps=3)
        print(f"✅ Original multi-agent completed")
        print(f"   Logs: {len(result_original.get('logs', []))} entries")
        print(f"   Responses: {len(result_original.get('agent_responses', []))} responses")
    except Exception as e:
        print(f"❌ Original pipeline error: {e}")
    
    # Option 2: Use enhanced pipeline (with memory)
    print("\n🧠 Option 2: Enhanced Pipeline (With AgentCore Memory)")
    print("-" * 50)
    
    try:
        # This adds memory capabilities while maintaining all existing functionality
        result_enhanced = run_strands_multi_agent_with_memory(fraud_alert, max_steps=3)
        print(f"✅ Enhanced multi-agent completed")
        print(f"   Logs: {len(result_enhanced.get('logs', []))} entries")
        print(f"   Responses: {len(result_enhanced.get('agent_responses', []))} responses")
        print(f"   Memory: Stored to AgentCore for case {fraud_alert['alertId']}")
        
        # Now you can retrieve the case history
        print(f"\n📖 Case History from Memory:")
        case_history = get_case_history(fraud_alert['alertId'])
        print(f"   {case_history}")
        
        # Search for specific patterns
        print(f"\n🔍 Searching for fraud patterns:")
        fraud_patterns = search_case_patterns(fraud_alert['alertId'], "fraud risk high")
        print(f"   Found {len(fraud_patterns)} relevant patterns")
        
    except Exception as e:
        print(f"❌ Enhanced pipeline error: {e}")

def demo_streaming_with_memory():
    """Demo streaming pipeline with memory"""
    
    print("\n🔄 Streaming Pipeline Demo with Memory")
    print("=" * 60)
    
    streaming_alert = {
        'alertId': 'STREAM_DEMO_001',
        'customerId': 'CUST_67890',
        'amount': 3500,
        'recipient': 'suspicious_account',
        'priority': 'MEDIUM',
        'ruleId': 'SOCIAL_ENGINEERING_RULE'
    }
    
    print(f"Streaming Alert: {streaming_alert['alertId']}")
    
    try:
        step_count = 0
        for state in stream_strands_steps_with_memory(streaming_alert):
            step_count += 1
            current_step = state.get('current_step', step_count)
            agent = state.get('streaming_agent', 'Processing')
            
            print(f"   Step {current_step}: {agent}")
            
            # Show latest response if available
            responses = state.get('agent_responses', [])
            if responses:
                latest_response = responses[-1]
                if isinstance(latest_response, str) and len(latest_response) > 0:
                    preview = latest_response[:100] + "..." if len(latest_response) > 100 else latest_response
                    print(f"      Response: {preview}")
        
        print(f"✅ Streaming completed after {step_count} steps")
        
        # Check what was stored in memory
        print(f"\n📚 Memory Summary for {streaming_alert['alertId']}:")
        memory_summary = get_case_history(streaming_alert['alertId'])
        print(f"   {memory_summary}")
        
    except Exception as e:
        print(f"❌ Streaming error: {e}")

def demo_memory_search():
    """Demo memory search capabilities"""
    
    print("\n🔍 Memory Search Demo")
    print("=" * 60)
    
    # Search across all cases for specific patterns
    search_queries = [
        "high risk transaction",
        "social engineering",
        "AnyDesk remote access",
        "fraud indicators"
    ]
    
    case_ids = ['DEMO_CASE_001', 'STREAM_DEMO_001']
    
    for case_id in case_ids:
        print(f"\nSearching case: {case_id}")
        for query in search_queries:
            try:
                results = search_case_patterns(case_id, query)
                print(f"   '{query}': {len(results)} matches")
            except Exception as e:
                print(f"   '{query}': Search error - {e}")

if __name__ == "__main__":
    print("🧠 AgentCore Memory Integration Demo")
    print("Demonstrates enhanced fraud detection with persistent memory")
    print()
    
    # Run all demos
    demo_original_vs_enhanced()
    demo_streaming_with_memory() 
    demo_memory_search()
    
    print("\n" + "=" * 60)
    print("🎉 Demo completed!")
    print()
    print("💡 Key Benefits of AgentCore Memory Integration:")
    print("   ✅ Persistent case history across sessions")
    print("   ✅ Semantic search across fraud patterns") 
    print("   ✅ Agent learning from previous cases")
    print("   ✅ Audit trail for regulatory compliance")
    print("   ✅ Drop-in replacement for existing code")
    print()
    print("🔧 Usage:")
    print("   # Original (no memory) - your existing working code")
    print("   from langgraph_multi_agent import stream_strands_steps, run_strands_multi_agent")
    print()
    print("   # Enhanced (with memory) - new memory-enabled version")
    print("   from enhanced_langgraph_with_memory import stream_strands_steps_with_memory")