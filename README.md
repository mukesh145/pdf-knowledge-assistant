# pdf-knowledge-assistant
end-to-end implementation of a RAG based knowledge asistant.

## Overview
A RAG (Retrieval-Augmented Generation) based PDF knowledge assistant that processes user queries and retrieves relevant information from PDF documents.

## What's Implemented So Far

### Query Processing Pipeline
- **QueryProcessor**: A processing module that normalizes user queries by:
  - Converting text to lowercase
  - Normalizing whitespace (trimming and collapsing multiple spaces)
  
### Intent Classification
- **IntentClassifier**: Uses DSPy framework to classify user queries and determine:
  - `is_rag_required`: Whether RAG search is needed for domain-specific/internal document queries
  - `is_prev_memory_required`: Whether previous conversation context is needed
  - Configured via `backend_config.yaml` to use OpenAI models (default: `gpt-3.5-turbo`)

### LangGraph Orchestrator
- **Workflow Engine**: Built using LangGraph to orchestrate the query processing pipeline
  - State-based workflow management with `QueryState` TypedDict
  - Conditional routing based on intent classification results
  - DAG structure: START → process_query → intent_classifier → (conditional routing) → get_memory/get_context → END
  - Supports parallel execution of memory and context retrieval nodes when both are required
  - Placeholder nodes for memory retrieval (`get_memory_node`) and context retrieval (`get_context_node`)

### Utilities
- **Config Loader**: Utility module for loading YAML configuration files
- **Configuration**: YAML-based configuration for model settings (`configs/backend_config.yaml`)

### Project Structure
```
src/
  backend/
    - query_processing.py  # Query normalization logic
    - intent_classifier.py # DSPy-based intent classification
    - orchestrator.py      # LangGraph workflow orchestration
    - utils.py             # Configuration loading utilities
configs/
  - backend_config.yaml    # Model and system configuration
```

## Dependencies
- `langgraph` - For building and managing the query processing workflow
- `dspy-ai` - For intent classification using LLM-based signatures
- `openai` - For LLM integration (used by DSPy)
- `pyyaml` - For configuration file parsing
- `python-dotenv` - For environment variable management

## Next Steps
- Implement memory retrieval node (`get_memory_node`) for RAG search
- Implement context retrieval node (`get_context_node`) for previous conversation context
- PDF document ingestion and vectorization
- Embedding generation and storage
- Semantic search and retrieval
- Response generation with LLM integration
