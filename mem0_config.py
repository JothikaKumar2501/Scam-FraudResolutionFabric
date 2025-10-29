"""
Mem0 Configuration for XYZ Bank Fraud Detection System
=====================================================

This module handles Mem0 configuration and environment variables.
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()  # Reads the .env file and loads variables into the environment

def get_mem0_api_key() -> Optional[str]:
    """Get Mem0 API key from environment variables"""
    return os.getenv('MEM0_API_KEY')

def is_mem0_available() -> bool:
    """Check if Mem0 is available and configured"""
    api_key = get_mem0_api_key()
    if not api_key:
        print("Warning: MEM0_API_KEY not found in environment variables")
        print("To use Mem0 memory features, set your API key:")
        print("export MEM0_API_KEY=m0-your-api-key-here")
        return False
    
    # Check if the API key looks valid
    if not api_key.startswith('m0-'):
        print("Warning: MEM0_API_KEY format appears invalid")
        print("Expected format: m0-xxxxxxxxxxxxxxxx")
        return False
    
    return True

def get_mem0_config() -> dict:
    """Get Mem0 configuration"""
    return {
        'api_key': get_mem0_api_key(),
        'available': is_mem0_available(),
        'memory_types': {
            'fraud_case': 'fraud_case',
            'context_summary': 'context_summary',
            'agent_summary': 'agent_summary',
            'risk_assessment': 'risk_assessment',
            'policy_decision': 'policy_decision',
            'customer_interaction': 'customer_interaction',
            'compressed_summary': 'compressed_summary',
            'agent_log': 'agent_log'
        }
    }

# Test function
def test_mem0_config():
    """Test Mem0 configuration"""
    config = get_mem0_config()
    print("Mem0 Configuration:")
    print(f"Available: {config['available']}")
    print(f"API Key Set: {'Yes' if config['api_key'] else 'No'}")
    
    if config['available']:
        print("✅ Mem0 is properly configured")
    else:
        print("❌ Mem0 is not properly configured")
        print("\nTo configure Mem0:")
        print("1. Get your API key from https://mem0.ai")
        print("2. Set the environment variable:")
        print("   export MEM0_API_KEY=m0-your-api-key-here")
        print("3. Restart your application")

if __name__ == "__main__":
    test_mem0_config() 