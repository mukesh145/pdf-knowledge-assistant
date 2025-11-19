from typing import TypedDict, Union
from langgraph.graph import StateGraph, START, END
from .query_processing import QueryProcessor
from .intent_classifier import IntentClassifier
from .context_retriever import ContextRetriever
from .memory_retriever import MemoryRetriever

query_processor = QueryProcessor()
intent_classifier = IntentClassifier()
context_retriever = ContextRetriever()
memory_retriever = MemoryRetriever()

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
    """
    query: str
    processed_query: str
    is_rag_required: bool
    is_prev_memory_required: bool
    user_id: int
    context: str
    memory: str


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
    
    # If neither is required, go to END
    if not nodes_to_execute:
        return END
    
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
    
    # Define the flow: START -> process_query -> intent_classifier -> (conditional routing)
    workflow.add_edge(START, "process_query")
    workflow.add_edge("process_query", "intent_classifier")
    
    # Conditional routing after intent classification
    # Routes to get_memory and/or get_context based on flags, or END if neither is needed
    # When both flags are true, both nodes execute in parallel
    workflow.add_conditional_edges(
        "intent_classifier",
        route_after_classification,
        {
            "get_memory": "get_memory",
            "get_context": "get_context",
            END: END
        }
    )
    
    # Both get_memory and get_context can run in parallel and both lead to END
    workflow.add_edge("get_memory", END)
    workflow.add_edge("get_context", END)
    
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
    }
    
    # Run the workflow
    result = app.invoke(initial_state)
    
    return result

