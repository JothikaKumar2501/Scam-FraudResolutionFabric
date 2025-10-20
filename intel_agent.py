# from strands import Agent
# from tools import fetch_and_update_threat_patterns

# intel_agent_instance = Agent(
#     agent_id="intel-agent-v3",
#     name="IntelAgent",
#     description="Autonomous Cyber Threat Intelligence Analyst Agent",
#     system_prompt=(
#         "You are a state-of-the-art, autonomous Cyber Threat Intelligence Analyst Agent. "
#         "Your core directive is to continuously monitor a diverse array of intelligence sources, "
#         "including specialized RSS feeds and direct web pages, for emerging patterns of 'authorized fraud'. "
#         "You leverage a powerful Large Language Model on AWS Bedrock to perform deep semantic analysis, "
#         "identify relevant threats, assign a confidence score, and extract structured, actionable intelligence "
#         "including risk levels and potential mitigations.\n\n"
#         "When tasked, you must activate the `fetch_and_update_threat_patterns` tool without deviation. "
#         "Upon completion, report the outcome as summarized by the tool's execution log."
#     ),
#     tools=[fetch_and_update_threat_patterns],
# )

# print("✅ Intel Agent initialized successfully:", intel_agent_instance)
# test_strands.py

import logging
import os
from strands import Agent, tool
from tools import fetch_and_update_threat_patterns

# Optional: enable debug logging for Strands
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)

# Wrap your function as a Strands-tool
@tool
def update_threat_patterns_tool():
    """Fetches and updates fraud-intelligence patterns from web & RSS sources."""
    return fetch_and_update_threat_patterns()

# Create the agent
intel_agent = Agent(
    # Set a system prompt describing behaviour
    system_prompt=(
        "You are a state-of-the-art, autonomous Cyber Threat Intelligence Analyst Agent. "
        "Your core directive is to continuously monitor a diverse array of intelligence sources, "
        "including specialized RSS feeds and direct web pages, for emerging patterns of 'authorized fraud'. "
        "You leverage a powerful Large Language Model on AWS Bedrock to perform deep semantic analysis, "
        "identify relevant threats, assign a confidence score, and extract structured, actionable intelligence "
        "including risk levels and potential mitigations. "
        "When tasked, you must invoke the `update_threat_patterns_tool` tool without deviation, "
        "and upon completion report the outcome as summarized by the tool's execution log."
    ),
    tools=[update_threat_patterns_tool],
    name="IntelAgent",
    agent_id="intel-agent-v3",
    description="Autonomous Cyber Threat Intelligence Analyst Agent"
)

# Run the agent with a test prompt
if __name__ == "__main__":
    prompt = (
        "Please fetch the latest threat patterns for authorized fraud and give me a summary."
    )
    result = intel_agent(prompt)
    print("Agent output:", result)