"""
Mem0 Integration for ANZ Bank Fraud Detection System
====================================================

This module provides comprehensive memory management for the ANZ Bank fraud detection
application using Mem0. It stores memories, context summaries, and agent summaries
with best practices for production use.

Features:
- Memory storage for fraud detection cases
- Context summaries for agents
- Agent interaction histories
- Risk assessment memories
- Policy decision memories
- Customer interaction memories
- Compressed memory retrieval
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from dotenv import load_dotenv
import time
import re

load_dotenv()  # Reads the .env file and loads variables into the environment


try:
    from mem0 import MemoryClient, Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    print("Warning: Mem0 not available. Install with: pip install mem0ai")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MemoryType(Enum):
    """Types of memories stored in Mem0"""
    FRAUD_CASE = "fraud_case"
    CONTEXT_SUMMARY = "context_summary"
    AGENT_SUMMARY = "agent_summary"
    RISK_ASSESSMENT = "risk_assessment"
    POLICY_DECISION = "policy_decision"
    CUSTOMER_INTERACTION = "customer_interaction"
    COMPRESSED_SUMMARY = "compressed_summary"
    AGENT_LOG = "agent_log"

@dataclass
class MemoryMetadata:
    """Metadata for Mem0 memories"""
    memory_type: str
    case_id: str
    agent_name: str
    timestamp: str
    priority: str = "normal"
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

class Mem0Manager:
    """Comprehensive Mem0 memory manager for ANZ Bank fraud detection"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Mem0 manager with API key"""
        if not MEM0_AVAILABLE:
            raise ImportError("Mem0 not available. Install with: pip install mem0ai")
        
        # Get API key from environment or parameter
        # use from .env dotenv()
        self.api_key = os.getenv('MEM0_API_KEY')
        if not self.api_key:
            raise ValueError("MEM0_API_KEY not found in environment variables")
        
        # Initialize Mem0 client (texts)
        self.client = MemoryClient(api_key=self.api_key)
        # Initialize Mem0 Graph (Neo4j) best-effort per docs_md/mem0_docs.md
        try:
            neo4j_uri = os.getenv("NEO4J_URI")
            neo4j_user = os.getenv("NEO4J_USERNAME")
            neo4j_pass = os.getenv("NEO4J_PASSWORD")
            neo4j_db = os.getenv("NEO4J_DATABASE", "neo4j")
            if neo4j_uri and neo4j_user and neo4j_pass:
                # Mem0's Bedrock integration expects a modelId (not an inference profile ARN) for the "model" field.
                mem0_llm_model = (
                    os.getenv("AWS_CLAUDE_MODEL_ID")
                    or "anthropic.claude-sonnet-4-20250514-v1:0"
                )
                cfg = {
                    "llm": {
                        "provider": "aws_bedrock",
                        "config": {
                            "model": mem0_llm_model,
                            "temperature": 0.1,
                            "region_name": os.getenv("AWS_REGION", "us-east-1")
                        }
                    },
                    "embedder": {
                        "provider": "aws_bedrock",
                        "config": {
                            "model": os.getenv("AWS_TITAN_MODEL_ID", "amazon.titan-embed-text-v2:0"),
                            "region_name": os.getenv("AWS_REGION", "us-east-1")
                        }
                    },
                    "graph_store": {
                        "provider": "neo4j",
                        "config": {
                            "url": neo4j_uri,
                            "username": neo4j_user,
                            "password": neo4j_pass,
                            "database": neo4j_db
                        },
                        # Use a low-temp LLM for graph operations if available
                        "llm": {
                            "provider": "aws_bedrock",
                            "config": {
                                "model": mem0_llm_model,
                                "temperature": 0.0,
                                "region_name": os.getenv("AWS_REGION", "us-east-1")
                            }
                        }
                    }
                }
                self.graph_memory = Memory.from_config(config_dict=cfg)
            else:
                self.graph_memory = None
        except Exception as e:
            logger.warning(f"Mem0 Graph init failed: {e}")
            self.graph_memory = None
        logger.info("Mem0 manager initialized successfully")
    
    def _to_messages(self, content: Any, role: str = "assistant") -> List[Dict[str, Any]]:
        """Normalize input content into Mem0 message list format.
        - If content is already a list of {role, content} dicts, return as-is.
        - If content is a string, wrap it as a single assistant message.
        - Otherwise, coerce to JSON string and wrap.
        """
        if isinstance(content, list) and all(isinstance(m, dict) and "role" in m and "content" in m for m in content):
            return content
        if isinstance(content, str):
            return [{"role": role, "content": content}]
        # Fallback: stringify non-string content safely
        try:
            serialized = json.dumps(content, ensure_ascii=False)
        except Exception:
            serialized = str(content)
        return [{"role": role, "content": serialized}]
    
    def _generate_user_id(self, case_id: str, agent_name: str = None) -> str:
        """Generate consistent user ID for memory organization"""
        if agent_name:
            return f"anz_fraud_{case_id}_{agent_name}"
        return f"anz_fraud_{case_id}"
    
    def _generate_agent_id(self, agent_name: str) -> str:
        """Generate agent ID for memory organization"""
        return f"anz_agent_{agent_name}"
    
    def _validate_and_sanitize_query(self, query: str, fallback: str = "fraud case") -> str:
        """Validate and sanitize search query to prevent API errors"""
        try:
            # Ensure query is a string
            if not isinstance(query, str):
                return fallback
            
            # Remove leading/trailing whitespace
            query = query.strip()
            
            # Ensure query is not empty
            if not query or len(query) == 0:
                return fallback
            
            # Ensure query has minimum length (mem0 requires meaningful queries)
            if len(query) < 3:
                return fallback
            
            # Remove any potentially problematic characters that might cause API issues
            # Keep alphanumeric, spaces, and common punctuation
            sanitized = re.sub(r'[^\w\s\-.,!?]', '', query)
            
            # Ensure sanitized query is not empty
            if not sanitized.strip():
                return fallback
            
            return sanitized.strip()
            
        except Exception as e:
            logger.warning(f"Query validation failed: {e}, using fallback")
            return fallback
    
    def store_fraud_case_memory(self, case_id: str, case_data: Dict[str, Any]) -> bool:
        """Store fraud case memory with comprehensive metadata"""
        try:
            memory_content = f"""
ANZ Bank Fraud Case: {case_id}
Transaction: ${case_data.get('amount', 'Unknown')} to {case_data.get('payee', 'Unknown')}
Risk Level: {case_data.get('risk_level', 'Unknown')}
Scam Typology: {case_data.get('scam_typology', 'Unknown')}
Status: {case_data.get('status', 'Unknown')}
Timestamp: {datetime.now().isoformat()}
            """.strip()
            
            metadata = MemoryMetadata(
                memory_type=MemoryType.FRAUD_CASE.value,
                case_id=case_id,
                agent_name="system",
                timestamp=datetime.now().isoformat(),
                priority="high",
                tags=["fraud_case", "anz_bank", case_data.get('scam_typology', 'unknown')]
            )
            
            self.client.add(
                messages=self._to_messages(memory_content),
                user_id=self._generate_user_id(case_id),
                metadata=asdict(metadata),
                version="v2"
            )
            # Best-effort: add to graph memory for relationship queries
            try:
                if self.graph_memory:
                    self.graph_memory.add(self._to_messages(memory_content), user_id=self._generate_user_id(case_id))
            except Exception:
                pass
            
            logger.info(f"Stored fraud case memory for case {case_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store fraud case memory: {e}")
            return False
    
    def store_context_summary(self, case_id: str, agent_name: str, context_summary: str) -> bool:
        """Store compressed context summary for an agent"""
        try:
            memory_content = f"""
Context Summary for {agent_name} - Case {case_id}:
{context_summary}
Timestamp: {datetime.now().isoformat()}
            """.strip()
            
            metadata = MemoryMetadata(
                memory_type=MemoryType.CONTEXT_SUMMARY.value,
                case_id=case_id,
                agent_name=agent_name,
                timestamp=datetime.now().isoformat(),
                priority="medium",
                tags=["context_summary", agent_name, case_id]
            )
            
            self.client.add(
                messages=self._to_messages(memory_content),
                user_id=self._generate_user_id(case_id),
                agent_id=self._generate_agent_id(agent_name),
                metadata=asdict(metadata),
                version="v2"
            )
            try:
                if self.graph_memory:
                    self.graph_memory.add(self._to_messages(memory_content), user_id=self._generate_user_id(case_id))
            except Exception:
                pass
            
            logger.info(f"Stored context summary for {agent_name} in case {case_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store context summary: {e}")
            return False
    
    def store_agent_summary(self, case_id: str, agent_name: str, agent_summary: str) -> bool:
        """Store agent interaction summary"""
        try:
            memory_content = f"""
Agent Summary for {agent_name} - Case {case_id}:
{agent_summary}
Timestamp: {datetime.now().isoformat()}
            """.strip()
            
            metadata = MemoryMetadata(
                memory_type=MemoryType.AGENT_SUMMARY.value,
                case_id=case_id,
                agent_name=agent_name,
                timestamp=datetime.now().isoformat(),
                priority="medium",
                tags=["agent_summary", agent_name, case_id]
            )
            
            self.client.add(
                messages=self._to_messages(memory_content),
                user_id=self._generate_user_id(case_id),
                agent_id=self._generate_agent_id(agent_name),
                metadata=asdict(metadata),
                version="v2"
            )
            try:
                if self.graph_memory:
                    self.graph_memory.add(self._to_messages(memory_content), user_id=self._generate_user_id(case_id))
            except Exception:
                pass
            
            logger.info(f"Stored agent summary for {agent_name} in case {case_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store agent summary: {e}")
            return False
    
    def store_risk_assessment(self, case_id: str, risk_assessment: str, confidence: float) -> bool:
        """Store risk assessment memory"""
        try:
            memory_content = f"""
Risk Assessment - Case {case_id}:
{risk_assessment}
Confidence: {confidence:.2f}
Timestamp: {datetime.now().isoformat()}
            """.strip()
            
            metadata = MemoryMetadata(
                memory_type=MemoryType.RISK_ASSESSMENT.value,
                case_id=case_id,
                agent_name="RiskAssessorAgent",
                timestamp=datetime.now().isoformat(),
                priority="high",
                tags=["risk_assessment", "anz_bank", case_id]
            )
            
            self.client.add(
                messages=self._to_messages(memory_content),
                user_id=self._generate_user_id(case_id),
                agent_id=self._generate_agent_id("RiskAssessorAgent"),
                metadata=asdict(metadata),
                version="v2"
            )
            try:
                if self.graph_memory:
                    self.graph_memory.add(self._to_messages(memory_content), user_id=self._generate_user_id(case_id))
            except Exception:
                pass
            
            logger.info(f"Stored risk assessment for case {case_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store risk assessment: {e}")
            return False
    
    def store_policy_decision(self, case_id: str, policy_decision: str) -> bool:
        """Store policy decision memory"""
        try:
            memory_content = f"""
Policy Decision - Case {case_id}:
{policy_decision}
Timestamp: {datetime.now().isoformat()}
            """.strip()
            
            metadata = MemoryMetadata(
                memory_type=MemoryType.POLICY_DECISION.value,
                case_id=case_id,
                agent_name="PolicyDecisionAgent",
                timestamp=datetime.now().isoformat(),
                priority="high",
                tags=["policy_decision", "anz_bank", case_id]
            )
            
            self.client.add(
                messages=self._to_messages(memory_content),
                user_id=self._generate_user_id(case_id),
                agent_id=self._generate_agent_id("PolicyDecisionAgent"),
                metadata=asdict(metadata),
                version="v2"
            )
            try:
                if self.graph_memory:
                    self.graph_memory.add(self._to_messages(memory_content), user_id=self._generate_user_id(case_id))
            except Exception:
                pass
            
            logger.info(f"Stored policy decision for case {case_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store policy decision: {e}")
            return False
    
    def store_customer_interaction(self, case_id: str, interaction: str) -> bool:
        """Store customer interaction memory"""
        try:
            memory_content = f"""
Customer Interaction - Case {case_id}:
{interaction}
Timestamp: {datetime.now().isoformat()}
            """.strip()
            
            metadata = MemoryMetadata(
                memory_type=MemoryType.CUSTOMER_INTERACTION.value,
                case_id=case_id,
                agent_name="DialogueAgent",
                timestamp=datetime.now().isoformat(),
                priority="medium",
                tags=["customer_interaction", "anz_bank", case_id]
            )
            
            self.client.add(
                messages=self._to_messages(memory_content),
                user_id=self._generate_user_id(case_id),
                agent_id=self._generate_agent_id("DialogueAgent"),
                metadata=asdict(metadata),
                version="v2"
            )
            try:
                if self.graph_memory:
                    self.graph_memory.add(self._to_messages(memory_content), user_id=self._generate_user_id(case_id))
            except Exception:
                pass
            
            logger.info(f"Stored customer interaction for case {case_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store customer interaction: {e}")
            return False
    
    def store_compressed_summary(self, case_id: str, summary_type: str, compressed_summary: str) -> bool:
        """Store compressed summary for efficient retrieval"""
        try:
            memory_content = f"""
Compressed Summary - {summary_type} - Case {case_id}:
{compressed_summary}
Timestamp: {datetime.now().isoformat()}
            """.strip()
            
            metadata = MemoryMetadata(
                memory_type=MemoryType.COMPRESSED_SUMMARY.value,
                case_id=case_id,
                agent_name="system",
                timestamp=datetime.now().isoformat(),
                priority="medium",
                tags=["compressed_summary", summary_type, case_id]
            )
            
            self.client.add(
                messages=self._to_messages(memory_content),
                user_id=self._generate_user_id(case_id),
                metadata=asdict(metadata),
                version="v2"
            )
            try:
                if self.graph_memory:
                    self.graph_memory.add(self._to_messages(memory_content), user_id=self._generate_user_id(case_id))
            except Exception:
                pass
            
            logger.info(f"Stored compressed summary for {summary_type} in case {case_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store compressed summary: {e}")
            return False
    
    def retrieve_case_memories(self, case_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve all memories for a specific case"""
        try:
            user_id = self._generate_user_id(case_id)
            # Prefer v2-style retrieval with filters, then fallback
            filters = {"AND": [{"user_id": user_id}]}
            for _ in range(5):
                try:
                    memories = self.client.get_all(version="v2", filters=filters, page=1, page_size=limit)
                    if isinstance(memories, dict) and isinstance(memories.get("results"), list):
                        results = memories.get("results")
                        if results:
                            return results[:limit]
                    elif isinstance(memories, list) and memories:
                        return memories[:limit]
                except Exception:
                    # Fallback to v1 style
                    memories = self.client.get_all(user_id=user_id, limit=limit)
                    if isinstance(memories, dict) and isinstance(memories.get("results"), list):
                        results = memories.get("results")
                        if results:
                            return results[:limit]
                    elif isinstance(memories, list) and memories:
                        return memories[:limit]
                time.sleep(1.0)
            # Final fallback: keyword search by case_id without filters; try graph search as well
            try:
                # Use a proper search query instead of case_id as query
                search_query = f"case {case_id} transaction fraud"
                search_query = self._validate_and_sanitize_query(search_query, "fraud case transaction")
                search_res = self.client.search(search_query, version="v2", limit=limit)
                if isinstance(search_res, dict) and isinstance(search_res.get("results"), list):
                    return search_res.get("results")[:limit]
                if isinstance(search_res, list):
                    return search_res[:limit]
                if self.graph_memory:
                    g = self.graph_memory.search(search_query, user_id=self._generate_user_id(case_id))
                    if isinstance(g, dict) and isinstance(g.get("results"), list) and g["results"]:
                        return g["results"][:limit]
            except Exception:
                pass
            return []
        except Exception as e:
            logger.error(f"Failed to retrieve case memories: {e}")
            return []

    def search_graph_memories(self, case_id: Optional[str], query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search graph memories using Neo4j-backed Mem0 graph store when available."""
        try:
            if not self.graph_memory:
                return []
            query = self._validate_and_sanitize_query(query, f"case {case_id or ''} fraud transaction")
            user_id = self._generate_user_id(case_id) if case_id else None
            res = self.graph_memory.search(query, user_id=user_id) if user_id else self.graph_memory.search(query)
            if isinstance(res, dict) and isinstance(res.get("results"), list):
                return res["results"][:limit]
            if isinstance(res, list):
                return res[:limit]
            return []
        except Exception as e:
            logger.debug(f"Graph search failed: {e}")
            return []

    def add_graph_memory(self, case_id: str, messages: List[Dict[str, Any]]) -> bool:
        """Add messages to graph memory if available; fallback to text client."""
        try:
            user = self._generate_user_id(case_id)
            if self.graph_memory:
                self.graph_memory.add(messages, user_id=user)
                return True
            # Fallback: store via text client
            self.client.add(messages=messages, user_id=user, version="v2")
            return True
        except Exception as e:
            logger.error(f"Failed to add graph memory: {e}")
            return False

    def delete_case_memories(self, case_id: str) -> bool:
        """Best-effort deletion of case memories by user_id across providers."""
        try:
            user = self._generate_user_id(case_id)
            ok = False
            # Try v2 delete with filters if available
            try:
                if hasattr(self.client, "delete"):
                    self.client.delete(version="v2", filters={"AND": [{"user_id": user}]})
                    ok = True
            except Exception:
                pass
            # Fallback: no direct delete, add a tombstone note
            if not ok:
                self.client.add(messages=[{"role": "system", "content": f"[TOMBSTONE] Cleared by request for {user}"}], user_id=user, version="v2")
            # Graph memory purge best-effort (not all versions support delete); ignore errors
            try:
                if self.graph_memory and hasattr(self.graph_memory, "delete"):
                    self.graph_memory.delete(filters={"AND": [{"user_id": user}]})
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Failed to delete case memories: {e}")
            return False
    
    def search_case_memories(self, case_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant memories in a case with proper error handling and fallbacks"""
        try:
            user_id = self._generate_user_id(case_id)
            
            # Validate and sanitize the query
            fallback_query = f"case {case_id} transaction fraud"
            query = self._validate_and_sanitize_query(query, fallback_query)
            
            # Try v1 API first (more stable)
            try:
                logger.debug(f"Attempting v1 search for case {case_id} with query: {query}")
                memories = self.client.search(query, user_id=user_id, limit=limit)
                if isinstance(memories, dict) and isinstance(memories.get("results"), list):
                    results = memories.get("results")
                    if results:
                        logger.debug(f"v1 search successful, found {len(results)} results")
                        return results[:limit]
                elif isinstance(memories, list) and memories:
                    logger.debug(f"v1 search successful, found {len(memories)} results")
                    return memories[:limit]
            except Exception as e:
                logger.debug(f"v1 search failed: {e}")
            
            # Try v2 API with proper filter format
            try:
                logger.debug(f"Attempting v2 search for case {case_id} with query: {query}")
                # Use proper v2 filter format based on Mem0 documentation
                filters = {
                    "AND": [
                        {"user_id": user_id}
                    ]
                }
                memories = self.client.search(
                    query=query,
                    version="v2",
                    filters=filters,
                    limit=limit
                )
                if isinstance(memories, dict) and isinstance(memories.get("results"), list):
                    results = memories.get("results")
                    if results:
                        logger.debug(f"v2 search successful, found {len(results)} results")
                        return results[:limit]
                elif isinstance(memories, list) and memories:
                    logger.debug(f"v2 search successful, found {len(memories)} results")
                    return memories[:limit]
            except Exception as e:
                logger.debug(f"v2 search failed: {e}")
            
            # Final fallback: search without any filters
            try:
                logger.debug(f"Attempting fallback search for case {case_id}")
                memories = self.client.search(query, limit=limit)
                if isinstance(memories, dict) and isinstance(memories.get("results"), list):
                    results = memories.get("results")
                    if results:
                        logger.debug(f"Fallback search successful, found {len(results)} results")
                        return results[:limit]
                elif isinstance(memories, list) and memories:
                    logger.debug(f"Fallback search successful, found {len(memories)} results")
                    return memories[:limit]
            except Exception as e:
                logger.debug(f"Fallback search failed: {e}")
            
            logger.warning(f"No search method worked for case {case_id}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to search case memories for case {case_id}: {e}")
            return []
    
    def retrieve_agent_memories(self, agent_name: str, case_id: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve memories for a specific agent with proper error handling and fallbacks"""
        try:
            agent_id = self._generate_agent_id(agent_name)
            
            if case_id:
                user_id = self._generate_user_id(case_id, agent_name)
                
                # Try v1 API first (more stable)
                try:
                    logger.debug(f"Attempting v1 get_all for agent {agent_name} in case {case_id}")
                    memories = self.client.get_all(user_id=user_id, agent_id=agent_id, limit=limit)
                    if isinstance(memories, list) and memories:
                        logger.debug(f"v1 get_all successful, found {len(memories)} results")
                        return memories[:limit]
                    if isinstance(memories, dict):
                        results = memories.get('results')
                        if isinstance(results, list) and results:
                            logger.debug(f"v1 get_all successful, found {len(results)} results")
                            return results[:limit]
                except Exception as e:
                    logger.debug(f"v1 get_all failed: {e}")
                
                # Try v2 API with proper filter format
                try:
                    logger.debug(f"Attempting v2 get_all for agent {agent_name} in case {case_id}")
                    filters = {
                        "AND": [
                            {"user_id": user_id},
                            {"agent_id": agent_id}
                        ]
                    }
                    memories = self.client.get_all(
                        version="v2",
                        filters=filters,
                        page=1,
                        page_size=limit
                    )
                    if isinstance(memories, list) and memories:
                        logger.debug(f"v2 get_all successful, found {len(memories)} results")
                        return memories[:limit]
                    if isinstance(memories, dict):
                        results = memories.get('results')
                        if isinstance(results, list) and results:
                            logger.debug(f"v2 get_all successful, found {len(results)} results")
                            return results[:limit]
                except Exception as e:
                    logger.debug(f"v2 get_all failed: {e}")
                
            else:
                # Get memories for agent across all cases
                # Try v1 API first
                try:
                    logger.debug(f"Attempting v1 get_all for agent {agent_name} across all cases")
                    memories = self.client.get_all(agent_id=agent_id, limit=limit)
                    if isinstance(memories, list) and memories:
                        logger.debug(f"v1 get_all successful, found {len(memories)} results")
                        return memories[:limit]
                    if isinstance(memories, dict):
                        results = memories.get('results')
                        if isinstance(results, list) and results:
                            logger.debug(f"v1 get_all successful, found {len(results)} results")
                            return results[:limit]
                except Exception as e:
                    logger.debug(f"v1 get_all failed: {e}")
                
                # Try v2 API
                try:
                    logger.debug(f"Attempting v2 get_all for agent {agent_name} across all cases")
                    filters = {
                        "AND": [
                            {"agent_id": agent_id}
                        ]
                    }
                    memories = self.client.get_all(
                        version="v2",
                        filters=filters,
                        page=1,
                        page_size=limit
                    )
                    if isinstance(memories, list) and memories:
                        logger.debug(f"v2 get_all successful, found {len(memories)} results")
                        return memories[:limit]
                    if isinstance(memories, dict):
                        results = memories.get('results')
                        if isinstance(results, list) and results:
                            logger.debug(f"v2 get_all successful, found {len(results)} results")
                            return results[:limit]
                except Exception as e:
                    logger.debug(f"v2 get_all failed: {e}")
            
            # Final fallback: get all without filters
            try:
                logger.debug(f"Attempting fallback get_all for agent {agent_name}")
                memories = self.client.get_all(limit=limit)
                if isinstance(memories, list) and memories:
                    logger.debug(f"Fallback get_all successful, found {len(memories)} results")
                    return memories[:limit]
                if isinstance(memories, dict):
                    results = memories.get('results')
                    if isinstance(results, list) and results:
                        logger.debug(f"Fallback get_all successful, found {len(results)} results")
                        return results[:limit]
            except Exception as e:
                logger.debug(f"Fallback get_all failed: {e}")
            
            logger.warning(f"No get_all method worked for agent {agent_name}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to retrieve agent memories for agent {agent_name}: {e}")
            return []
    
    def search_agent_memories(self, agent_name: str, query: str, case_id: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant memories for a specific agent with proper error handling and fallbacks"""
        try:
            agent_id = self._generate_agent_id(agent_name)
            
            # Validate and sanitize the query
            fallback_query = f"agent {agent_name}"
            query = self._validate_and_sanitize_query(query, fallback_query)
            
            if case_id:
                user_id = self._generate_user_id(case_id, agent_name)
                
                # Try v1 API first (more stable)
                try:
                    logger.debug(f"Attempting v1 search for agent {agent_name} in case {case_id}")
                    memories = self.client.search(query, user_id=user_id, agent_id=agent_id, limit=limit)
                    if isinstance(memories, list) and memories:
                        logger.debug(f"v1 search successful, found {len(memories)} results")
                        return memories[:limit]
                    if isinstance(memories, dict):
                        results = memories.get('results')
                        if isinstance(results, list) and results:
                            logger.debug(f"v1 search successful, found {len(results)} results")
                            return results[:limit]
                except Exception as e:
                    logger.debug(f"v1 search failed: {e}")
                
                # Try v2 API with proper filter format
                try:
                    logger.debug(f"Attempting v2 search for agent {agent_name} in case {case_id}")
                    filters = {
                        "AND": [
                            {"user_id": user_id},
                            {"agent_id": agent_id}
                        ]
                    }
                    memories = self.client.search(
                        query=query,
                        version="v2",
                        filters=filters,
                        limit=limit
                    )
                    if isinstance(memories, list) and memories:
                        logger.debug(f"v2 search successful, found {len(memories)} results")
                        return memories[:limit]
                    if isinstance(memories, dict):
                        results = memories.get('results')
                        if isinstance(results, list) and results:
                            logger.debug(f"v2 search successful, found {len(results)} results")
                            return results[:limit]
                except Exception as e:
                    logger.debug(f"v2 search failed: {e}")
                
            else:
                # Search for agent across all cases
                # Try v1 API first
                try:
                    logger.debug(f"Attempting v1 search for agent {agent_name} across all cases")
                    memories = self.client.search(query, agent_id=agent_id, limit=limit)
                    if isinstance(memories, list) and memories:
                        logger.debug(f"v1 search successful, found {len(memories)} results")
                        return memories[:limit]
                    if isinstance(memories, dict):
                        results = memories.get('results')
                        if isinstance(results, list) and results:
                            logger.debug(f"v1 search successful, found {len(results)} results")
                            return results[:limit]
                except Exception as e:
                    logger.debug(f"v1 search failed: {e}")
                
                # Try v2 API
                try:
                    logger.debug(f"Attempting v2 search for agent {agent_name} across all cases")
                    filters = {
                        "AND": [
                            {"agent_id": agent_id}
                        ]
                    }
                    memories = self.client.search(
                        query=query,
                        version="v2",
                        filters=filters,
                        limit=limit
                    )
                    if isinstance(memories, list) and memories:
                        logger.debug(f"v2 search successful, found {len(memories)} results")
                        return memories[:limit]
                    if isinstance(memories, dict):
                        results = memories.get('results')
                        if isinstance(results, list) and results:
                            logger.debug(f"v2 search successful, found {len(results)} results")
                            return results[:limit]
                except Exception as e:
                    logger.debug(f"v2 search failed: {e}")
            
            # Final fallback: search without filters
            try:
                logger.debug(f"Attempting fallback search for agent {agent_name}")
                memories = self.client.search(query, limit=limit)
                if isinstance(memories, list) and memories:
                    logger.debug(f"Fallback search successful, found {len(memories)} results")
                    return memories[:limit]
                if isinstance(memories, dict):
                    results = memories.get('results')
                    if isinstance(results, list) and results:
                        logger.debug(f"Fallback search successful, found {len(results)} results")
                        return results[:limit]
            except Exception as e:
                logger.debug(f"Fallback search failed: {e}")
            
            logger.warning(f"No search method worked for agent {agent_name}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to search agent memories for agent {agent_name}: {e}")
            return []
    
    def get_case_summary(self, case_id: str) -> str:
        """Get comprehensive case summary from memories"""
        try:
            memories = self.retrieve_case_memories(case_id, limit=20)
            if not memories:
                return f"No memories found for case {case_id}"
            
            summary_parts = [f"Case Summary for {case_id}:"]
            
            # Group memories by type
            memory_groups = {}
            for memory in memories:
                memory_type = 'unknown'
                try:
                    if isinstance(memory, dict):
                        md = memory.get('metadata', {})
                        if isinstance(md, dict):
                            memory_type = md.get('memory_type', 'unknown')
                except Exception:
                    memory_type = 'unknown'
                if memory_type not in memory_groups:
                    memory_groups[memory_type] = []
                memory_groups[memory_type].append(memory)
            
            # Build summary by type
            for memory_type, memories_list in memory_groups.items():
                summary_parts.append(f"\n{memory_type.upper()}:")
                for memory in memories_list[:3]:  # Limit to 3 per type
                    content = ''
                    if isinstance(memory, dict):
                        try:
                            content = str(memory.get('memory', ''))[:200]
                        except Exception:
                            content = ''
                    summary_parts.append(f"- {content}")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Failed to get case summary: {e}")
            return f"Error retrieving case summary for {case_id}: {e}"
    
    def clear_case_memories(self, case_id: str) -> bool:
        """Clear all memories for a specific case"""
        try:
            user_id = self._generate_user_id(case_id)
            # Note: This would require implementing a delete method
            # For now, we'll just log the request
            logger.info(f"Requested to clear memories for case {case_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear case memories: {e}")
            return False

# Global Mem0 manager instance
_mem0_manager = None

def get_mem0_manager() -> Optional[Mem0Manager]:
    """Get the global Mem0 manager instance"""
    global _mem0_manager
    if _mem0_manager is None and MEM0_AVAILABLE:
        try:
            _mem0_manager = Mem0Manager()
        except Exception as e:
            logger.error(f"Failed to initialize Mem0 manager: {e}")
            return None
    return _mem0_manager

def store_memory(memory_type: MemoryType, case_id: str, content: str, **kwargs) -> bool:
    """Convenience function to store memory"""
    manager = get_mem0_manager()
    if not manager:
        return False
    
    try:
        if memory_type == MemoryType.FRAUD_CASE:
            return manager.store_fraud_case_memory(case_id, content)
        elif memory_type == MemoryType.CONTEXT_SUMMARY:
            return manager.store_context_summary(case_id, kwargs.get('agent_name', 'unknown'), content)
        elif memory_type == MemoryType.AGENT_SUMMARY:
            return manager.store_agent_summary(case_id, kwargs.get('agent_name', 'unknown'), content)
        elif memory_type == MemoryType.RISK_ASSESSMENT:
            return manager.store_risk_assessment(case_id, content, kwargs.get('confidence', 0.0))
        elif memory_type == MemoryType.POLICY_DECISION:
            return manager.store_policy_decision(case_id, content)
        elif memory_type == MemoryType.CUSTOMER_INTERACTION:
            return manager.store_customer_interaction(case_id, content)
        elif memory_type == MemoryType.COMPRESSED_SUMMARY:
            return manager.store_compressed_summary(case_id, kwargs.get('summary_type', 'unknown'), content)
        else:
            logger.warning(f"Unknown memory type: {memory_type}")
            return False
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        return False

def retrieve_memories(case_id: str, query: str = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Convenience function to retrieve memories"""
    manager = get_mem0_manager()
    if not manager:
        return []
    
    try:
        if query:
            return manager.search_case_memories(case_id, query, limit)
        else:
            return manager.retrieve_case_memories(case_id, limit)
    except Exception as e:
        logger.error(f"Failed to retrieve memories: {e}")
        return []

def search_graph(case_id: Optional[str], query: str, limit: int = 5) -> List[Dict[str, Any]]:
    manager = get_mem0_manager()
    if not manager:
        return []
    try:
        # Primary: Neo4j graph search
        results = manager.search_graph_memories(case_id, query, limit)
        if results:
            return results
        # Fallback: text memory search scoped to case when graph is unavailable or empty
        try:
            return manager.search_case_memories(case_id or "", query, limit)
        except Exception:
            return []
    except Exception as e:
        logger.error(f"Failed to search graph: {e}")
        return []

def add_graph(case_id: str, content: str) -> bool:
    manager = get_mem0_manager()
    if not manager:
        return False
    try:
        return manager.add_graph_memory(case_id, messages=[{"role": "assistant", "content": content}])
    except Exception as e:
        logger.error(f"Failed to add graph memory: {e}")
        return False

def clear_case(case_id: str) -> bool:
    manager = get_mem0_manager()
    if not manager:
        return False
    try:
        return manager.delete_case_memories(case_id)
    except Exception as e:
        logger.error(f"Failed to clear case: {e}")
        return False

# Test function
def test_mem0_integration():
    """Test the Mem0 integration"""
    try:
        manager = get_mem0_manager()
        if not manager:
            print("Mem0 not available - skipping test")
            return
        
        # Test storing a fraud case
        case_data = {
            'amount': 5000,
            'payee': 'John Smith',
            'risk_level': 'HIGH',
            'scam_typology': 'Business Email Compromise',
            'status': 'investigating'
        }
        
        success = manager.store_fraud_case_memory("TEST-001", case_data)
        print(f"Stored fraud case: {success}")
        
        # Test storing context summary
        context_summary = "TXN: $5000 to John Smith (BEC-001) | RISK: HIGH | INDICATORS: SCAM, FRAUD"
        success = manager.store_context_summary("TEST-001", "RiskAssessorAgent", context_summary)
        print(f"Stored context summary: {success}")
        
        # Add a concrete user message to ensure memory extraction
        try:
            messages = [
                {"role": "user", "content": "My test name is Alice and I love playing badminton."}
            ]
            manager.client.add(messages=messages, user_id=manager._generate_user_id("TEST-001"), version="v2")
        except Exception as e:
            logger.error(f"Failed to add user message for test: {e}")

        # Test retrieving memories (retry a few times to allow processing)
        retrieved = []
        for _ in range(5):
            memories = manager.retrieve_case_memories("TEST-001", limit=10)
            if memories:
                retrieved = memories
                break
            time.sleep(1.0)
        print(f"Retrieved {len(retrieved)} memories")
        
        # Test searching memories for a known token
        found = []
        for _ in range(5):
            search_results = manager.search_case_memories("TEST-001", "Alice", limit=5)
            if search_results:
                found = search_results
                break
            time.sleep(1.0)
        print(f"Search results: {len(found)} memories")
        
        print("Mem0 integration test completed successfully!")
        
    except Exception as e:
        print(f"Mem0 integration test failed: {e}")

if __name__ == "__main__":
    test_mem0_integration() 