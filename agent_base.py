import logging
from vector_utils import search_similar
from aws_bedrock import converse_with_claude_stream

class Agent:
    def __init__(self, name, context_store):
        self.name = name
        self.context_store = context_store

    def act(self, message, context):
        """
        Perform agent action. To be implemented by subclasses.
        Args:
            message (str): Message or instruction for the agent.
            context (dict): Context relevant to the agent.
        Returns:
            dict: Updated context or result.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def retrieve_knowledge(self, query):
        """
        Placeholder for agentic RAG retrieval (SOPs, past cases, etc.).
        To be implemented by subclasses or extended for Titan embedding search.
        """
        return [] 