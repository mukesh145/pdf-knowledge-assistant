# pdf-knowledge-assistant
end-to-end implementation of a RAG based knowledge asistant.

## Overview
A RAG (Retrieval-Augmented Generation) based PDF knowledge assistant that processes user queries and retrieves relevant information from PDF documents.

## What's Implemented So Far

### Query Processing Pipeline
- **QueryProcessor**: A processing module that normalizes user queries by:
  - Converting text to lowercase
  - Normalizing whitespace (trimming and collapsing multiple spaces)
  
### LangGraph Orchestrator
- **Workflow Engine**: Built using LangGraph to orchestrate the query processing pipeline
  - State-based workflow management
  - Extensible architecture for future processing steps
  - Simple DAG structure: START → process_query → END

### Project Structure
```
src/
  backend/
    - query_processing.py  # Query normalization logic
    - orchestrator.py      # LangGraph workflow orchestration
```

## Dependencies
- `langgraph` - For building and managing the query processing workflow

## Next Steps
- PDF document ingestion and vectorization
- Embedding generation and storage
- Semantic search and retrieval
- Response generation with LLM integration
