import dspy
from typing import Optional
from .memory_retriever import MemoryRetriever
from dspy import Signature, InputField, OutputField


class QueryOptimizationSignature(Signature):
    """
    Signature for optimizing user queries for vector database retrieval.
    
    Inputs:
        processed_query: The processed and normalized user query
        past_conversations: Previous conversation history for context
        optimization_instructions: Instructions for query optimization
    
    Output:
        optimized_query: The optimized query suitable for vector database retrieval
    """
    processed_query: str = InputField(desc="The processed and normalized user query")
    past_conversations: str = InputField(desc="Previous conversation history for context")
    optimization_instructions: str = InputField(desc="Instructions for query optimization")
    optimized_query: str = OutputField(desc="The optimized query suitable for vector database retrieval")


class QueryProcessor:
    """
    A class for processing query strings with various normalization steps.
    Designed to be extensible for future processing steps.
    Includes query optimization using LLM and past conversation history.
    """
    
    def __init__(self):
        """
        Initialize the QueryProcessor with memory retriever and LLM for optimization.
        """
        self.memory_retriever = MemoryRetriever()
        self._llm = None
        self._optimization_model = None
    
    def to_lowercase(self, text: str) -> str:
        """
        Convert every character in the input string to lowercase.
        
        Args:
            text: Input string to process
            
        Returns:
            String with all characters converted to lowercase
        """
        return text.lower()
    
    def normalize_whitespace(self, text: str) -> str:
        """
        Trim leading/trailing spaces and collapse multiple spaces into single spaces.
        
        Args:
            text: Input string to process
            
        Returns:
            String with normalized whitespace
        """
        # Remove leading and trailing whitespace
        text = text.strip()
        # Collapse multiple spaces into single space
        import re
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def _initialize_llm(self):
        """
        Initialize the LLM for query optimization using DSPy.
        Uses GPT-4o model similar to LLMOrchestrator.
        
        Returns:
            Configured DSPy language model
        """
        if self._llm is None:
            from dspy import LM
            self._llm = LM("openai/gpt-4o")
            dspy.configure(lm=self._llm)
        return self._llm
    
    def _get_optimization_model(self):
        """
        Get or create the DSPy Predict model for query optimization.
        
        Returns:
            Configured dspy.Predict model with QueryOptimizationSignature
        """
        if self._optimization_model is None:
            self._initialize_llm()
            self._optimization_model = dspy.Predict(QueryOptimizationSignature)
        return self._optimization_model
    
    def optimize_query(self, processed_query: str, past_conversations: str) -> str:
        """
        Optimize a processed query using LLM and past conversation history.
        The optimization makes the query more suitable for vector database retrieval.
        
        Args:
            processed_query: The processed and normalized query
            past_conversations: Past conversation history as a string
            
        Returns:
            Optimized query string suitable for vector database retrieval
        """
        # If no past conversations, return the processed query as-is
        if not past_conversations or not past_conversations.strip():
            return processed_query
        
        try:
            # Get the optimization model
            model = self._get_optimization_model()
            
            # Create optimization instructions
            optimization_instructions = (
                "Optimize the user's query to make it more effective for vector database retrieval. "
                "Consider the context from past conversations to: "
                "1. Expand abbreviations and resolve references (e.g., 'it', 'that', 'the above') "
                "2. Add relevant context from past conversations to make the query self-contained, only if necessary."
                "3. Use more specific and descriptive terms that would match better in a vector search, but do not make it over complicated."
                "4. Maintain the original intent while making it more searchable "
                "5. If the query is already clear and self-contained, return it with minimal changes"
            )
            
            # Call the optimization model
            result = model(
                processed_query=processed_query,
                past_conversations=past_conversations if past_conversations else "No previous conversation.",
                optimization_instructions=optimization_instructions
            )
            
            optimized = result.optimized_query.strip()
            
            # If optimization failed or returned empty, return the original processed query
            if not optimized:
                return processed_query
            
            return optimized
            
        except Exception as e:
            # If optimization fails, return the processed query as fallback
            print(f"Warning: Query optimization failed: {str(e)}. Using processed query as-is.")
            return processed_query
    
    def process(self, query: str, user_id: Optional[int] = None, optimize: bool = True, return_memory: bool = False):
        """
        Apply all processing steps to the input query.
        Optionally optimizes the query using LLM and past conversation history.
        
        Args:
            query: Input query string to process
            user_id: Optional user ID for retrieving past conversations for optimization
            optimize: Whether to optimize the query using LLM (default: True)
            return_memory: If True, returns a tuple (processed_query, past_conversations). 
                          If False, returns just processed_query (default: False)
            
        Returns:
            If return_memory is False: Processed (and optionally optimized) query string
            If return_memory is True: Tuple of (processed_query, past_conversations)
                                     past_conversations will be empty string if not retrieved
        """
        if not isinstance(query, str):
            raise TypeError("Input must be a string")
        
        # Step 1: Convert to lowercase
        processed = self.to_lowercase(query)
        
        # Step 2: Normalize whitespace
        processed = self.normalize_whitespace(processed)
        
        past_conversations = ""
        
        # Step 3: Optimize query using LLM and past conversations (if user_id provided and optimize=True)
        if optimize and user_id is not None:
            try:
                # Retrieve past conversations
                past_conversations = self.memory_retriever.get_past_conversations(user_id)
                
                # Optimize the query
                processed = self.optimize_query(processed, past_conversations)
                
            except Exception as e:
                # If optimization fails, continue with the processed query
                print(f"Warning: Failed to optimize query with past conversations: {str(e)}")
            finally:
                # Note: We don't close the connection here if return_memory is True,
                # as the connection might be needed elsewhere. The caller should handle cleanup.
                if not return_memory:
                    try:
                        self.memory_retriever.close_connection()
                    except:
                        pass
        
        if return_memory:
            return processed, past_conversations
        return processed

