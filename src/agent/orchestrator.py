from typing import TypedDict, Union, Iterator, List
import time
from langgraph.graph import StateGraph, START, END
from .query_processing import QueryProcessor
from .intent_classifier import IntentClassifier
from .context_retriever import ContextRetriever
from .memory_retriever import MemoryRetriever
from .llm_orchestrator import LLMOrchestrator
from .logger import Logger

query_processor = QueryProcessor()
intent_classifier = IntentClassifier()
context_retriever = ContextRetriever()
memory_retriever = MemoryRetriever()
llm_orchestrator = LLMOrchestrator()
logger = Logger()

class QueryState(TypedDict):
    """
    State for the query processing workflow.
    
    Attributes:
        query: The original query string
        processed_query: The processed query string
        is_rag_required: Whether RAG search is required for the query
        is_prev_memory_required: Whether previous memory is required for the query
        user_id: The user ID for retrieving conversation history
        context: Retrieved context from vector database
        confidence_scores: List of confidence scores for retrieved contexts
        retrieval_time_ms: Time taken for context retrieval in milliseconds
        memory: Retrieved conversation history
        llm_response: The LLM-generated response to the user's query
        is_context_sufficient: Boolean indicating if context/memory are sufficient
        input_tokens: Number of input tokens used by LLM
        output_tokens: Number of output tokens used by LLM
        total_time_ms: Total time taken for the entire forward run in milliseconds
        start_time: Timestamp when the forward run started (for internal tracking)
    """
    query: str
    processed_query: str
    is_rag_required: bool
    is_prev_memory_required: bool
    user_id: int
    context: str
    confidence_scores: List[float]
    retrieval_time_ms: float
    memory: str
    llm_response: str
    is_context_sufficient: bool
    input_tokens: int
    output_tokens: int
    total_time_ms: float
    start_time: float


def process_query_node(state: QueryState) -> QueryState:
    """
    Node function that processes the query and adds processed_query to the state.
    Optionally optimizes the query using LLM and past conversation history.
    Also retrieves and stores past conversations in memory to avoid duplicate RDS fetches.
    
    Args:
        state: The current state containing the query and user_id
        
    Returns:
        Updated state with processed_query and memory (if user_id is available) added
    """
    
    # Get user_id from state for query optimization
    user_id = state.get("user_id")
    
    # Process and optimize the query, and retrieve past conversations
    # This avoids fetching from RDS again in get_memory_node
    if user_id is not None:
        processed_query, past_conversations = query_processor.process(
            query=state["query"],
            user_id=user_id,
            optimize=True,
            return_memory=True
        )
        
        # Clean up database connection after retrieving memory
        try:
            query_processor.memory_retriever.close_connection()
        except:
            pass
        
        return {
            "processed_query": processed_query,
            "memory": past_conversations
        }
    else:
        # No user_id, so just process the query without optimization
        processed_query = query_processor.process(
            query=state["query"],
            user_id=None,
            optimize=False
        )
        
        return {
            "processed_query": processed_query
        }


def intent_classifier_node(state: QueryState) -> QueryState:
    """
    Node function that classifies the intent and sets is_rag_required and is_prev_memory_required.
    
    Args:
        state: The current state containing the processed query
        
    Returns:
        Updated state with is_rag_required and is_prev_memory_required set
    """
    # intent_classifier = IntentClassifier()
    classification = intent_classifier.classify(state["processed_query"])
    
    return {
        "is_rag_required": classification["is_rag_required"],
        "is_prev_memory_required": classification["is_prev_memory_required"]
    }


def get_memory_node(state: QueryState) -> QueryState:
    """
    Node function that retrieves past conversation history for the user.
    If memory is already in state (from process_query_node), skips RDS fetch.
    
    Args:
        state: The current state containing user_id and potentially memory
    
    Returns:
        Updated state with memory containing past conversation history
    """
    # Check if memory is already in state (retrieved during query processing)
    existing_memory = state.get("memory", "")
    
    if existing_memory:
        # Memory already retrieved in process_query_node, no need to fetch again
        return {}
    
    # Get user_id from state
    user_id = state.get("user_id")
    
    if user_id is None:
        # If user_id is not provided, return empty memory
        return {
            "memory": ""
        }
    
    try:
        # Retrieve past conversations for the user
        past_conversations = memory_retriever.get_past_conversations(user_id)
        
        return {
            "memory": past_conversations
        }
    except Exception as e:
        # If there's an error retrieving memory, return empty string
        # In production, you might want to log this error
        return {
            "memory": ""
        }
    finally:
        # Clean up the database connection
        memory_retriever.close_connection()



def get_context_node(state: QueryState) -> QueryState:
    """
    Node function that retrieves context from the vector database using RAG.
    
    Args:
        state: The current state containing the processed query
        
    Returns:
        Updated state with context retrieved from vector database, confidence scores, and retrieval time
    """
    # Initialize context retriever
    # context_retriever = ContextRetriever()
    
    # Retrieve context using the processed query
    # retrieve_context now returns a dictionary with contexts, confidence_scores, and retrieval_time_ms
    retrieval_result = context_retriever.retrieve_context(state["processed_query"], top_k=5)
    
    # Extract the results
    contexts = retrieval_result.get("contexts", [])
    confidence_scores = retrieval_result.get("confidence_scores", [])
    retrieval_time_ms = retrieval_result.get("retrieval_time_ms", 0.0)
    
    # Join the list of contexts into a single string
    # Use newlines to separate different context chunks
    context_string = "\n\n".join(contexts) if contexts else ""
    
    return {
        "context": context_string,
        "confidence_scores": confidence_scores,
        "retrieval_time_ms": retrieval_time_ms
    }


def llm_orchestrator_node(state: QueryState) -> QueryState:
    """
    Node function that generates an LLM response using the query, context, and memory.
    
    Args:
        state: The current state containing query, context, and memory
        
    Returns:
        Updated state with llm_response, is_context_sufficient, input_tokens, and output_tokens added.
        All fields returned from LLMOrchestrator.generate_response() are stored in the state.
    """
    # Get the query, context, and memory from state
    query = state.get("query", "")
    context = state.get("context", "")
    memory = state.get("memory", "")
    
    # Generate response using LLMOrchestrator
    # Handle None or empty strings appropriately
    # Returns a dict with: answer, is_context_sufficient, input_tokens, output_tokens
    result = llm_orchestrator.generate_response(
        query=query,
        context=context if context else None,
        past_conversation=memory if memory else None
    )
    
    # Extract all fields from the result and store them in state
    # Ensure all fields are properly typed and have default values
    # All fields returned from generate_response() are explicitly stored:
    # - answer -> llm_response
    # - is_context_sufficient -> is_context_sufficient
    # - input_tokens -> input_tokens
    # - output_tokens -> output_tokens
    updated_state = {
        "llm_response": result.get("answer", ""),
        "is_context_sufficient": bool(result.get("is_context_sufficient", False)),
        "input_tokens": int(result.get("input_tokens", 0)),
        "output_tokens": int(result.get("output_tokens", 0))
    }
    
    return updated_state


def log_conversation_async(state: QueryState) -> None:
    """
    Asynchronous logging function that logs the data to the logs db and adds query and llm_response
    to the conversation_history table. Also generates drift detection JSON and uploads to S3.
    
    This function is designed to be called asynchronously (e.g., via FastAPI BackgroundTasks)
    AFTER the response has been returned to the user, to avoid adding latency.
    
    Args:
        state: The current state containing query, llm_response, and other workflow data
    """
    try:
        # Get user_id, query, and llm_response from state
        user_id = state.get("user_id")
        query = state.get("query", "")
        llm_response = state.get("llm_response", "")
        
        # Calculate total time for forward run
        start_time = state.get("start_time")
        total_time_ms = 0.0
        if start_time:
            total_time_ms = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Save conversation to conversation_history table
        if user_id is not None and query and llm_response:
            logger.save_conversation(user_id, query, llm_response)
        
        # Prepare state for logs table (maps user_id -> u_id and memory -> past_memory)
        logs_state = {
            "u_id": state.get("user_id"),
            "query": state.get("query", ""),
            "processed_query": state.get("processed_query", ""),
            "context": state.get("context", ""),
            "past_memory": state.get("memory", ""),
            "llm_response": state.get("llm_response", "")
        }
        
        # Save logs to logs table
        logger.save_logs(logs_state)
        
        # Generate drift detection JSON and upload to S3
        drift_metrics = {
            "context_retrieval_time": state.get("retrieval_time_ms", 0.0),
            "confidence_scores": state.get("confidence_scores", []),
            "is_context_sufficient": state.get("is_context_sufficient", False),
            "llm_input_tokens_length": state.get("input_tokens", 0),
            "llm_output_tokens_length": state.get("output_tokens", 0),
            "total_time_for_forward_run": total_time_ms
        }
        
        # Upload to S3 if user_id is available
        if user_id is not None:
            logger.upload_drift_metrics_to_s3(user_id, drift_metrics)
        
    except Exception as e:
        # If there's an error logging, we don't want to fail the workflow
        # In production, you might want to log this error to a separate error log
        print(f"Warning: Failed to log conversation asynchronously: {e}")
    finally:
        # Clean up the database connection
        logger.close_connection()


def route_after_classification(state: QueryState) -> Union[str, list[str]]:
    """
    Conditional routing function that determines which nodes to execute
    based on the classification results.
    
    Args:
        state: The current state with classification results
        
    Returns:
        String or list of node names to execute. Returns list for parallel execution.
    """
    nodes_to_execute = []
    
    if state.get("is_rag_required", False):
        nodes_to_execute.append("get_context")
    
    if state.get("is_prev_memory_required", False):
        nodes_to_execute.append("get_memory")
    
    # If neither is required, go directly to llm_orchestrator
    if not nodes_to_execute:
        return "llm_orchestrator"
    
    # If only one node is needed, return as string
    if len(nodes_to_execute) == 1:
        return nodes_to_execute[0]
    
    # If both are needed, return list for parallel execution
    return nodes_to_execute


def create_dag():
    """
    Creates and compiles the query processing DAG.
    
    Returns:
        Compiled LangGraph workflow
    """
    # Create the graph
    workflow = StateGraph(QueryState)
    
    # Add nodes
    workflow.add_node("process_query", process_query_node)
    workflow.add_node("intent_classifier", intent_classifier_node)
    workflow.add_node("get_memory", get_memory_node)
    workflow.add_node("get_context", get_context_node)
    workflow.add_node("llm_orchestrator", llm_orchestrator_node)
    # Note: Logger node removed - logging happens asynchronously after response is returned
    
    # Define the flow: START -> process_query -> intent_classifier -> (conditional routing)
    workflow.add_edge(START, "process_query")
    workflow.add_edge("process_query", "intent_classifier")
    
    # Conditional routing after intent classification
    # Routes to get_memory and/or get_context based on flags, or llm_orchestrator if neither is needed
    # When both flags are true, both nodes execute in parallel
    workflow.add_conditional_edges(
        "intent_classifier",
        route_after_classification,
        {
            "get_memory": "get_memory",
            "get_context": "get_context",
            "llm_orchestrator": "llm_orchestrator"
        }
    )
    
    # Both get_memory and get_context can run in parallel and both lead to llm_orchestrator
    workflow.add_edge("get_memory", "llm_orchestrator")
    workflow.add_edge("get_context", "llm_orchestrator")
    
    # llm_orchestrator leads directly to END (logging happens asynchronously after response is returned)
    workflow.add_edge("llm_orchestrator", END)
    
    # Compile the graph
    app = workflow.compile()
    
    return app


def run_ka_dag(query: str, user_id: int) -> dict:
    """
    Callable function to trigger the query processing DAG.
    
    Args:
        query: The input query string to process
        user_id: The user ID for retrieving conversation history
        
    Returns:
        Dictionary containing the final state with query and processed_query
    """
    # Start timer for entire forward run
    start_time = time.time()
    
    # Create the DAG
    app = create_dag()
    
    # Initial state
    initial_state = {
        "query": query,
        "processed_query": "",  # Will be populated by the processing node
        "is_rag_required": False,  # Will be set by the intent classifier
        "is_prev_memory_required": False,  # Will be set by the intent classifier
        "user_id": user_id,  # User ID for memory retrieval
        "context": "", # Will be populated by the context node
        "confidence_scores": [], # Will be populated by the context node
        "retrieval_time_ms": 0.0, # Will be populated by the context node
        "memory": "", # Will be populated by the memory node
        "llm_response": "", # Will be populated by the llm_orchestrator node
        "is_context_sufficient": False, # Will be populated by the llm_orchestrator node
        "input_tokens": 0, # Will be populated by the llm_orchestrator node
        "output_tokens": 0, # Will be populated by the llm_orchestrator node
        "total_time_ms": 0.0, # Will be calculated in logger_node
        "start_time": start_time, # Store start time for logger_node
    }
    
    # Run the workflow
    result = app.invoke(initial_state)
    
    return result


def run_ka_dag_stream(query: str, user_id: int) -> Iterator[dict]:
    """
    Callable function to trigger the query processing DAG with streaming LLM response.
    
    This function processes the query up to the LLM generation step, then streams
    the response token by token instead of waiting for the complete response.
    
    Args:
        query: The input query string to process
        user_id: The user ID for retrieving conversation history
        
    Yields:
        Dictionary chunks containing streaming response data:
        - {"type": "metadata", "data": {...}} - Query processing metadata
        - {"type": "token", "data": "..."} - Individual tokens from LLM
        - {"type": "done", "data": {}} - Stream completion signal
    """
    # Start timer for entire forward run
    start_time = time.time()
    
    # Initial state
    state = {
        "query": query,
        "processed_query": "",
        "is_rag_required": False,
        "is_prev_memory_required": False,
        "user_id": user_id,
        "context": "",
        "confidence_scores": [],
        "retrieval_time_ms": 0.0,
        "memory": "",
        "llm_response": "",
        "is_context_sufficient": False,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_time_ms": 0.0,
        "start_time": start_time,
    }
    
    # Process query
    state.update(process_query_node(state))
    
    # Classify intent
    state.update(intent_classifier_node(state))
    
    # Get memory if needed
    if state.get("is_prev_memory_required", False):
        state.update(get_memory_node(state))
    
    # Get context if needed
    if state.get("is_rag_required", False):
        state.update(get_context_node(state))
    
    # First, yield metadata about the query processing
    yield {
        "type": "metadata",
        "data": {
            "query": state.get("query", query),
            "processed_query": state.get("processed_query"),
            "context_used": state.get("is_rag_required", False),
            "memory_used": state.get("is_prev_memory_required", False)
        }
    }
    
    # Stream LLM response
    query_text = state.get("query", "")
    context_text = state.get("context", "")
    memory_text = state.get("memory", "")
    
    full_response = ""
    is_context_sufficient = False
    input_tokens = 0
    output_tokens = 0
    
    try:
        for chunk in llm_orchestrator.generate_response_stream(
            query=query_text,
            context=context_text if context_text else None,
            past_conversation=memory_text if memory_text else None
        ):
            if chunk.get("type") == "token":
                token = chunk.get("data", "")
                full_response += token
                yield {
                    "type": "token",
                    "data": token
                }
            elif chunk.get("type") == "metadata":
                # Extract all metadata from the streaming response
                # This includes: answer, is_context_sufficient, input_tokens, output_tokens
                metadata = chunk.get("data", {})
                if metadata:
                    # Store all metadata fields in state
                    is_context_sufficient = bool(metadata.get("is_context_sufficient", False))
                    input_tokens = int(metadata.get("input_tokens", 0))
                    output_tokens = int(metadata.get("output_tokens", 0))
                    # Also update full_response from metadata if available (as backup)
                    if "answer" in metadata:
                        full_response = metadata.get("answer", full_response)
    except Exception as e:
        # Yield error if streaming fails
        yield {
            "type": "error",
            "data": {"message": str(e)}
        }
        return
    
    # Update state with all fields received from LLM orchestrator
    # Ensure all fields are properly stored in state for logging and downstream processing
    state["llm_response"] = full_response
    state["is_context_sufficient"] = is_context_sufficient
    state["input_tokens"] = input_tokens
    state["output_tokens"] = output_tokens
    
    # Update state with total_time_ms before logging
    if start_time:
        state["total_time_ms"] = (time.time() - start_time) * 1000  # Convert to milliseconds
    
    # Yield final message with state for async logging (logging will happen asynchronously)
    # The state is included so the API endpoint can trigger logging after response is sent
    yield {
        "type": "done",
        "data": {
            "state": state  # Include full state for async logging
        }
    }
    
    # Note: Logging should be triggered asynchronously by the API endpoint after stream completes
    # This ensures the response is returned to the user first, then logging happens in background

