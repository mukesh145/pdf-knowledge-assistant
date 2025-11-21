# PDF Knowledge Assistant
End-to-end implementation of a RAG-based knowledge assistant with a complete React frontend and FastAPI backend.

## Overview
A RAG (Retrieval-Augmented Generation) based PDF knowledge assistant that processes user queries and retrieves relevant information from PDF documents. Features a modern React SPA frontend with authentication and a FastAPI backend with JWT-based security.

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

### Authentication System
- **JWT-based Authentication**: Secure token-based authentication
- **User Management**: User registration, login, and profile management
- **Protected Routes**: Frontend routes protected by authentication
- **Password Hashing**: Bcrypt password hashing for security
- **Database Integration**: User data stored in PostgreSQL

### Frontend (React SPA)
- **Modern UI**: Built with React 19, Vite, and Tailwind CSS
- **Authentication Pages**: Login and registration with form validation
- **Chat Interface**: Real-time chat interface for querying documents
- **User Profile**: Profile management page
- **Protected Routes**: Route protection with authentication checks
- **API Integration**: Axios-based API client with JWT token management

### Project Structure
```
pdf-knowledge-assistant/
├── api/
│   └── app.py              # FastAPI application with auth endpoints
├── frontend/               # React SPA frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── contexts/      # React contexts (Auth)
│   │   ├── pages/         # Page components
│   │   └── utils/         # Utilities (API client)
│   └── package.json
├── src/
│   └── backend/
│       ├── auth.py         # JWT utilities and password hashing
│       ├── user_manager.py # User management
│       ├── query_processing.py
│       ├── intent_classifier.py
│       ├── orchestrator.py
│       └── utils.py
└── configs/
    └── backend_config.yaml
```

## Setup

### Backend Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
   - Copy `.env.example` to `.env`: `cp .env.example .env`
   - Edit `.env` and fill in your actual values:
```bash
DB_HOST=your_db_host
DB_PORT=5432
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
JWT_SECRET_KEY=your-secret-key-change-in-production  # Change this in production!
OPENAI_API_KEY=your_openai_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=test
ALLOWED_ORIGINS=http://localhost:5173  # Comma-separated for multiple origins
```

**Note**: All database tables (`users`, `conversation_history`, `logs`) are automatically created on startup.

3. Run the FastAPI server:
```bash
cd api
python app.py
# Or with uvicorn:
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env` file:
```bash
VITE_API_BASE_URL=http://localhost:8000
```

4. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## API Endpoints

### Authentication
- `POST /auth/register` - Register a new user
- `POST /auth/login` - Login and get JWT token
- `GET /auth/me` - Get current user information (requires authentication)

### Query
- `POST /query` - Query the knowledge assistant (requires authentication)

### Health Check
- `GET /health` - Health check endpoint that validates all dependencies (database, environment variables, Pinecone)

## Dependencies

### Backend
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `python-jose[cryptography]` - JWT token handling
- `passlib[bcrypt]` - Password hashing
- `langgraph` - Workflow orchestration
- `dspy-ai` - Intent classification
- `openai` - LLM integration
- `pyyaml` - Configuration parsing
- `python-dotenv` - Environment variable management
- `psycopg2-binary` - PostgreSQL adapter

### Frontend
- `react` - UI library
- `react-router-dom` - Routing
- `axios` - HTTP client
- `tailwindcss` - CSS framework

## Features

### V1 Improvements
- ✅ Automatic database table creation on startup
- ✅ Environment variable validation
- ✅ Enhanced health check endpoint
- ✅ Improved error handling and security
- ✅ CORS configuration via environment variables
- ✅ Query length validation
- ✅ Graceful handling of missing Pinecone configuration

## Production Deployment Notes

Before deploying to production:
1. **Change JWT_SECRET_KEY**: Generate a secure key with `openssl rand -hex 32`
2. **Set ALLOWED_ORIGINS**: Configure CORS to only allow your frontend domain(s)
3. **Use environment variables**: Never commit `.env` file to version control
4. **Database**: Ensure PostgreSQL is properly configured and accessible
5. **Pinecone**: Verify your Pinecone index is set up and accessible
6. **Monitoring**: Consider adding logging and monitoring (e.g., Sentry, CloudWatch)
