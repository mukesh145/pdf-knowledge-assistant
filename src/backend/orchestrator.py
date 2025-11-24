from typing import TypedDict, Union, Iterator
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
        memory: Retrieved conversation history
        llm_response: The LLM-generated response to the user's query
    """
    query: str
    processed_query: str
    is_rag_required: bool
    is_prev_memory_required: bool
    user_id: int
    context: str
    memory: str
    llm_response: str


def process_query_node(state: QueryState) -> QueryState:
    """
    Node function that processes the query and adds processed_query to the state.
    
    Args:
        state: The current state containing the query
        
    Returns:
        Updated state with processed_query added
    """
    
    processed_query = query_processor.process(state["query"])
    
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
    
    Args:
        state: The current state containing user_id
        
    Returns:
        Updated state with memory containing past conversation history
    """
    # Initialize memory retriever
    # memory_retriever = MemoryRetriever()
    
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
        Updated state with context retrieved from vector database
    """
    # Initialize context retriever
    # context_retriever = ContextRetriever()
    
    # Retrieve context using the processed query
    # retrieve_context returns a list of context strings
    contexts = context_retriever.retrieve_context(state["processed_query"], top_k=5)
    
    # Join the list of contexts into a single string
    # Use newlines to separate different context chunks
    context_string = "\n\n".join(contexts) if contexts else ""
    
    return {
        "context": context_string
    }


def llm_orchestrator_node(state: QueryState) -> QueryState:
    """
    Node function that generates an LLM response using the query, context, and memory.
    
    Args:
        state: The current state containing query, context, and memory
        
    Returns:
        Updated state with llm_response added
    """
    # Get the query, context, and memory from state
    query = state.get("query", "")
    context = state.get("context", "")
    memory = state.get("memory", "")
    
    # Generate response using LLMOrchestrator
    # Handle None or empty strings appropriately
    response = llm_orchestrator.generate_response(
        query=query,
        context=context if context else None,
        past_conversation=memory if memory else None
    )
    
    return {
        "llm_response": response
    }


def logger_node(state: QueryState) -> QueryState:
    """
    Node function that logs the data to the logs db and adds query and llm_response
    to the conversation_history table.
    
    Args:
        state: The current state containing query, llm_response, and other workflow data
        
    Returns:
        State unchanged (returns empty dict to maintain state as-is)
    """
    try:
        # Get user_id, query, and llm_response from state
        user_id = state.get("user_id")
        query = state.get("query", "")
        llm_response = state.get("llm_response", "")
        
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
        
    except Exception as e:
        # If there's an error logging, we don't want to fail the workflow
        # In production, you might want to log this error to a separate error log
        pass
    finally:
        # Clean up the database connection
        logger.close_connection()
    
    # Return empty dict to maintain state as-is
    return {}


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
    workflow.add_node("logger", logger_node)
    
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
    
    # llm_orchestrator leads to logger, and logger is the final node before END
    workflow.add_edge("llm_orchestrator", "logger")
    workflow.add_edge("logger", END)
    
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
        "memory": "", # Will be populated by the memory node
        "llm_response": "", # Will be populated by the llm_orchestrator node
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
    # Initial state
    state = {
        "query": query,
        "processed_query": "",
        "is_rag_required": False,
        "is_prev_memory_required": False,
        "user_id": user_id,
        "context": "",
        "memory": "",
        "llm_response": "",
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
    try:
        for token in llm_orchestrator.generate_response_stream(
            query=query_text,
            context=context_text if context_text else None,
            past_conversation=memory_text if memory_text else None
        ):
            full_response += token
            yield {
                "type": "token",
                "data": token
            }
    except Exception as e:
        # Yield error if streaming fails
        yield {
            "type": "error",
            "data": {"message": str(e)}
        }
        return
    
    # Update state with full response for logging
    state["llm_response"] = full_response
    
    # Log the conversation (run logger node)
    try:
        logger_node(state)
    except Exception as e:
        # Don't fail if logging fails, but log the error
        print(f"Warning: Failed to log conversation: {e}")
    
    # Yield final message
    yield {
        "type": "done",
        "data": {}
    }

