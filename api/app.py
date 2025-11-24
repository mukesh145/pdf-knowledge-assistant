from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
import sys
import os
import json
from pathlib import Path

# Add the src directory to the path to import backend modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from backend.orchestrator import run_ka_dag, run_ka_dag_stream
    from backend.auth import create_access_token, decode_access_token
    from backend.user_manager import UserManager
    from backend.db_setup import DatabaseSetup
    print("✓ Successfully imported backend modules")
except ImportError as e:
    print(f"✗ Error importing backend modules: {e}")
    import traceback
    print(traceback.format_exc())
    raise

# Initialize FastAPI app
app = FastAPI(
    title="PDF Knowledge Assistant API",
    description="RAG-based knowledge assistant API for querying PDF documents",
    version="1.0.0"
)

# CORS configuration - use environment variable or default to localhost for development
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Initialize user manager (handles all user operations with the 'users' table)
user_manager = UserManager()

# Initialize database setup
db_setup = DatabaseSetup()


def validate_environment_variables():
    """Validate that all required environment variables are set."""
    required_vars = {
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD"),
        "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "PINECONE_API_KEY": os.getenv("PINECONE_API_KEY"),
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}. "
            "Please set these in your .env file or environment."
        )
    
    # Warn if using default JWT secret
    if required_vars["JWT_SECRET_KEY"] == "your-secret-key-change-in-production":
        print("⚠ WARNING: Using default JWT_SECRET_KEY. Change this in production!")
    
    # Optional but recommended
    if not os.getenv("PINECONE_INDEX_NAME"):
        print("⚠ WARNING: PINECONE_INDEX_NAME not set, will use default 'test'")


@app.on_event("startup")
async def startup_event():
    """Initialize database tables and validate environment on startup."""
    try:
        print("Starting up API...")
        
        # Validate environment variables
        validate_environment_variables()
        print("✓ Environment variables validated")
        
        # Create all database tables (safe for existing databases)
        # Uses IF NOT EXISTS - won't affect existing tables or data
        db_setup.create_all_tables()
        print("✓ Database setup complete")
        
        # Print registered routes for debugging
        print(f"✓ Registered {len(app.routes)} routes")
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                print(f"  - {list(route.methods)} {route.path}")
    except ValueError as e:
        # Environment validation errors - fail fast
        print(f"✗ Environment validation failed: {str(e)}")
        raise
    except Exception as e:
        print(f"✗ Error during startup: {str(e)}")
        import traceback
        print(traceback.format_exc())
        # Don't raise - allow app to start, but log the error


# Authentication Models
class RegisterRequest(BaseModel):
    """Request model for user registration."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password", min_length=6, max_length=72)
    full_name: Optional[str] = Field(None, description="User's full name")
    
    @validator('password')
    def validate_password_length(cls, v):
        """Validate password doesn't exceed bcrypt's 72-byte limit."""
        if isinstance(v, str):
            password_bytes = v.encode('utf-8')
            byte_length = len(password_bytes)
            if byte_length > 72:
                # Provide helpful error message
                char_length = len(v)
                raise ValueError(
                    f"Password is too long. Your password is {char_length} characters long, "
                    f"but when encoded it is {byte_length} bytes. "
                    f"Bcrypt can only handle passwords up to 72 bytes. "
                    f"Please use a shorter password or avoid special characters/emojis."
                )
        return v

class LoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

class TokenResponse(BaseModel):
    """Response model for authentication tokens."""
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserResponse(BaseModel):
    """Response model for user information."""
    id: int
    email: str
    full_name: Optional[str] = None
    created_at: Optional[str] = None

# Query Models
class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    query: str = Field(
        ..., 
        description="The user's query or question", 
        min_length=1,
        max_length=5000  # Reasonable limit to prevent abuse
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the main topic of the document?"
            }
        }


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    query: str = Field(..., description="The original query")
    response: str = Field(..., description="The LLM-generated response")
    processed_query: Optional[str] = Field(None, description="The processed query string")
    context_used: bool = Field(..., description="Whether RAG context was used")
    memory_used: bool = Field(..., description="Whether previous conversation memory was used")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the main topic of the document?",
                "response": "The main topic of the document is...",
                "processed_query": "main topic document",
                "context_used": True,
                "memory_used": False
            }
        }


# Dependency to get current user from JWT token
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Extract and validate user from JWT token.
    
    Retrieves user information from the 'users' table based on the user_id in the JWT token.
    """
    try:
        # Extract token from Authorization header (prioritize manual extraction for reliability)
        token = None
        auth_header = request.headers.get("Authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
        elif credentials and credentials.credentials:
            # Fallback to HTTPBearer if manual extraction didn't work
            token = credentials.credentials
        
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        payload = decode_access_token(token)
        
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Convert string user_id back to integer
        try:
            user_id: int = int(user_id_str)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user from the 'users' table by ID
        user = user_manager.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log unexpected errors
        print(f"ERROR: Unexpected error in get_current_user: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/")
async def root():
    """Root endpoint to check if the API is running."""
    # Get all registered routes for debugging
    routes = [{"path": route.path, "methods": list(route.methods)} for route in app.routes]
    return {
        "message": "PDF Knowledge Assistant API is running",
        "version": "1.0.0",
        "endpoints": {
            "auth": {
                "register": "/auth/register",
                "login": "/auth/login",
                "me": "/auth/me"
            },
            "query": "/query",
            "query_stream": "/query/stream",
            "health": "/health"
        },
        "registered_routes": routes
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint that validates all dependencies.
    
    Returns:
        Dictionary with health status and dependency checks
    """
    health_status = {
        "status": "healthy",
        "dependencies": {}
    }
    
    # Check database connection
    try:
        db_setup._get_db_connection()
        health_status["dependencies"]["database"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["database"] = f"error: {str(e)}"
    
    # Check required environment variables
    required_vars = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "JWT_SECRET_KEY", "OPENAI_API_KEY", "PINECONE_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["environment"] = f"missing: {', '.join(missing_vars)}"
    else:
        health_status["dependencies"]["environment"] = "ok"
    
    # Check Pinecone (optional - don't fail if not configured)
    try:
        pinecone_key = os.getenv("PINECONE_API_KEY")
        if pinecone_key:
            health_status["dependencies"]["pinecone"] = "configured"
        else:
            health_status["dependencies"]["pinecone"] = "not configured"
    except Exception:
        health_status["dependencies"]["pinecone"] = "unknown"
    
    return health_status


# Authentication Endpoints
# Test route to verify routing works
@app.get("/auth/test")
async def auth_test():
    """Test endpoint to verify auth routes are registered."""
    return {"message": "Auth routes are working", "status": "ok"}

# Register route - this print confirms the route decorator is executed
print("Registering /auth/register route...")
@app.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """
    Register a new user.
    
    Creates a new user in the 'users' table with hashed password.
    Returns a JWT access token upon successful registration.
    """
    print(f"DEBUG: Register endpoint called with email: {request.email}")
    print(f"DEBUG: Password length: {len(request.password)} characters")
    try:
        # Register user in the 'users' table (password is automatically hashed)
        print("DEBUG: Calling user_manager.register_user...")
        user = user_manager.register_user(
            email=request.email,
            password=request.password,
            full_name=request.full_name
        )
        print(f"DEBUG: User registered successfully with ID: {user.get('id')}")
        
        # Create access token (sub must be a string for JWT)
        access_token = create_access_token(data={"sub": str(user["id"])})
        
        return TokenResponse(
            access_token=access_token,
            user=user
        )
    except ValueError as e:
        # User already exists, validation error, or password length error
        error_msg = str(e)
        # Pass through the detailed error message from validator
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_msg = str(e)
        print(f"Registration error: {error_msg}")
        print(traceback.format_exc())
        
        # Handle bcrypt password length error
        if "72 bytes" in error_msg or "truncate manually" in error_msg.lower() or "too long" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg if "Password is too long" in error_msg else "Password is too long. Bcrypt can only handle passwords up to 72 bytes when encoded. Please use a shorter password."
            )
        
        # Sanitize error message - don't expose internal details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while registering. Please try again later."
        )


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Login and get access token.
    
    Authenticates user against the 'users' table by verifying email and password.
    Returns a JWT access token upon successful authentication.
    """
    # Authenticate user from the 'users' table
    user = user_manager.authenticate_user(request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token (sub must be a string for JWT)
    access_token = create_access_token(data={"sub": str(user["id"])})
    
    return TokenResponse(
        access_token=access_token,
        user=user
    )


@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(**current_user)


@app.post("/query", response_model=QueryResponse)
async def query_knowledge_assistant(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Query the RAG-based knowledge assistant.
    
    This endpoint processes a user query through the orchestrator workflow,
    which includes query processing, intent classification, context retrieval,
    memory retrieval, and LLM response generation.
    
    Args:
        request: QueryRequest containing the query
        current_user: Current authenticated user (from JWT token)
        
    Returns:
        QueryResponse containing the response and metadata
        
    Raises:
        HTTPException: If there's an error processing the query
    """
    try:
        # Get user_id from authenticated user
        user_id = current_user["id"]
        
        # Run the orchestrator DAG
        result = run_ka_dag(
            query=request.query,
            user_id=user_id
        )
        
        # Extract the response and metadata
        response = QueryResponse(
            query=result.get("query", request.query),
            response=result.get("llm_response", ""),
            processed_query=result.get("processed_query"),
            context_used=result.get("is_rag_required", False),
            memory_used=result.get("is_prev_memory_required", False)
        )
        
        return response
        
    except Exception as e:
        # Log the full error for debugging (in production, use proper logging)
        import traceback
        error_message = str(e)
        print(f"ERROR: Query processing failed: {error_message}")
        print(traceback.format_exc())
        
        # Sanitize error message for client - don't expose internal details
        # Check for specific error types and provide user-friendly messages
        if "Pinecone" in error_message or "vector" in error_message.lower():
            client_message = "Vector database error. Please try again later."
        elif "OpenAI" in error_message or "API" in error_message:
            client_message = "AI service error. Please try again later."
        elif "database" in error_message.lower() or "connection" in error_message.lower():
            client_message = "Database error. Please try again later."
        else:
            client_message = "An error occurred while processing your query. Please try again."
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=client_message
        )


@app.post("/query/stream")
async def query_knowledge_assistant_stream(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Query the RAG-based knowledge assistant with streaming response.
    
    This endpoint processes a user query and streams the response token by token
    as it's being generated by the LLM using Server-Sent Events (SSE).
    
    Args:
        request: QueryRequest containing the query
        current_user: Current authenticated user (from JWT token)
        
    Returns:
        StreamingResponse with Server-Sent Events (SSE) format
    """
    try:
        # Get user_id from authenticated user
        user_id = current_user["id"]
        
        def generate_stream():
            """Generator function that yields SSE-formatted data."""
            try:
                for chunk in run_ka_dag_stream(
                    query=request.query,
                    user_id=user_id
                ):
                    # Format as Server-Sent Events
                    data = json.dumps(chunk)
                    yield f"data: {data}\n\n"
            except Exception as e:
                # Send error as SSE event
                import traceback
                error_message = str(e)
                print(f"ERROR: Streaming query processing failed: {error_message}")
                print(traceback.format_exc())
                
                error_chunk = {
                    "type": "error",
                    "data": {"message": "An error occurred while processing your query. Please try again."}
                }
                data = json.dumps(error_chunk)
                yield f"data: {data}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable buffering in nginx
            }
        )
        
    except Exception as e:
        import traceback
        error_message = str(e)
        print(f"ERROR: Streaming endpoint error: {error_message}")
        print(traceback.format_exc())
        
        # Return error as SSE
        def error_stream():
            error_chunk = {
                "type": "error",
                "data": {"message": "An error occurred while processing your query. Please try again."}
            }
            data = json.dumps(error_chunk)
            yield f"data: {data}\n\n"
        
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)




