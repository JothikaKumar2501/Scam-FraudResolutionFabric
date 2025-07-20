# GenAI for Payments

## Project Overview

This project implements a multi-agent, context-aware AI system for analyzing, assessing, and managing payment-related data and anomalies. It leverages generative AI, vector search, and a modular agent architecture to automate and assist in risk assessment, anomaly detection, and decision support for payment transactions.

## Key Features
- **Multi-Agent System:** Modular agents for transaction context, customer info, merchant info, behavioral patterns, risk synthesis, policy decision, dialogue, risk assessment, and feedback collection.
- **Context Store:** Persistent storage of context and analysis results for each alert, user, and transaction, enabling stateful, explainable AI workflows.
- **Vector Search:** Semantic search over SOPs, questions, and historical data using Qdrant and vector embeddings.
- **Streamlit UI:** Interactive web interface for analysts to review, interact, and provide feedback on AI-generated insights.
- **Dataset Integration:** Uses real and synthetic datasets for customer demographics, transaction history, SOPs, and more.

## Architecture

- **UI Layer (`ui.py`):** Built with Streamlit, this is the main entry point for users. It loads datasets, initializes agents, and provides an interactive dashboard for reviewing alerts, contexts, and agent outputs.
- **Agent Layer (`agents_multi.py`, `agents.py`, `agent_base.py`):** Implements a supervisor agent and multiple specialized agents. Each agent is responsible for a specific aspect of the analysis pipeline (e.g., anomaly detection, risk synthesis, policy decision).
- **Context Management (`context_store.py`, `context_store/`):** Handles reading/writing context JSON files for each alert, user, and transaction. This enables persistent, explainable, and auditable AI workflows.
- **Vector Search (`vector_utils.py`, `qdrant.py`):** Provides semantic search capabilities over SOPs, questions, and historical data using Qdrant as the vector database.
- **AWS Bedrock Integration (`aws_bedrock.py`):** Connects to AWS Bedrock for LLM-powered analysis and conversation.
- **Workflow Orchestration (`workflow.py`):** Defines the end-to-end workflow for processing alerts and orchestrating agent collaboration.
- **Schemas (`schemas.py`):** Defines data structures for context, transactions, users, merchants, anomalies, risk summaries, and decisions.
- **Datasets (`datasets/`):** Contains all data files used for context, SOPs, questions, and more.

## Implementation Details

- **Agents:** Each agent is a Python class, inheriting from a base agent. Agents communicate via shared context and are orchestrated by a supervisor agent.
- **Context Store:** Context is stored as JSON files in the `context_store/` directory, with separate files for each alert, user, and transaction.
- **Vector Search:** Embeddings are generated and stored in Qdrant, enabling fast semantic retrieval of relevant SOPs, questions, and historical cases.
- **UI:** The Streamlit UI allows users to select alerts, view agent outputs, and provide feedback, which is then stored and used to improve future analyses.

## How to Run
1. Install dependencies from `requirements.txt` or `pyproject.toml`.
2. Launch the UI with `streamlit run ui.py`.
3. Interact with the dashboard to review alerts, agent outputs, and provide feedback.

## File/Folder Guide
- `ui.py`: Main Streamlit UI
- `agents_multi.py`, `agents.py`, `agent_base.py`: Agent logic
- `main_multi_agent.py`: Multi-agent system entry point
- `context_store.py`, `context_store/`: Context management
- `vector_utils.py`, `qdrant.py`: Vector search
- `aws_bedrock.py`: AWS Bedrock LLM integration
- `workflow.py`: Workflow orchestration
- `schemas.py`: Data schemas
- `datasets/`: Data files (SOPs, questions, customer/transaction data)
- `.gitignore`: Ignores non-essential and generated files

## Not Used / Ignored Files
- `aws_bedrock_docs.py`, `mcp_store.py`, `payments_pic.png`: Not referenced in code, ignored
- Unused datasets: See `.gitignore` for a list

## License
It's me
