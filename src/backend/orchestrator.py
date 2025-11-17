from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .query_processing import QueryProcessor


class QueryState(TypedDict):
    """
    State for the query processing workflow.
    
    Attributes:
        query: The original query string
        processed_query: The processed query string
    """
    query: str
    processed_query: str


def process_query_node(state: QueryState) -> QueryState:
    """
    Node function that processes the query and adds processed_query to the state.
    
    Args:
        state: The current state containing the query
        
    Returns:
        Updated state with processed_query added
    """
    query_processor = QueryProcessor()
    processed_query = query_processor.process(state["query"])
    
    return {
        "query": state["query"],
        "processed_query": processed_query
    }


def create_query_processing_dag():
    """
    Creates and compiles the query processing DAG.
    
    Returns:
        Compiled LangGraph workflow
    """
    # Create the graph
    workflow = StateGraph(QueryState)
    
    # Add the query processing node
    workflow.add_node("process_query", process_query_node)
    
    # Define the flow: START -> process_query -> END
    workflow.add_edge(START, "process_query")
    workflow.add_edge("process_query", END)
    
    # Compile the graph
    app = workflow.compile()
    
    return app


def run_ka_dag(query: str) -> dict:
    """
    Callable function to trigger the query processing DAG.
    
    Args:
        query: The input query string to process
        
    Returns:
        Dictionary containing the final state with query and processed_query
    """
    # Create the DAG
    app = create_query_processing_dag()
    
    # Initial state
    initial_state = {
        "query": query,
        "processed_query": ""  # Will be populated by the processing node
    }
    
    # Run the workflow
    result = app.invoke(initial_state)
    
    return result

