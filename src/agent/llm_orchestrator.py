import dspy
from dotenv import load_dotenv
from typing import Optional, Iterator
from dspy import Signature, InputField, OutputField
from dspy import LM
import openai
import os

# Load environment variables from .env file
load_dotenv()


class AnswerGenerationSignature(Signature):
    """
    Signature for generating answers to user queries using retrieved context and conversation history.
    
    Inputs:
        user_query: The user's query/question
        retrieved_context: Context retrieved from the knowledge base
        past_conversation: Previous conversation history
        system_prompt: System prompt providing instructions for answer generation
    
    Output:
        answer: The generated answer to the user's query
    """
    user_query: str = InputField(desc="The user's query or question")
    retrieved_context: str = InputField(desc="Context retrieved from the knowledge base")
    past_conversation: str = InputField(desc="Previous conversation history")
    system_prompt: str = InputField(desc="System prompt with instructions for answer generation")
    answer: str = OutputField(desc="The generated answer to the user's query")


class LLMOrchestrator:
    """
    A class for orchestrating LLM-based answer generation using DSPy.
    Uses GPT-4o to generate responses based on user queries, retrieved context, and conversation history.
    """
    
    def __init__(self):
        """
        Initialize the LLMOrchestrator by setting up the GPT-4o LLM and Predict module.
        """
        self.lm = self._initialize_llm()
        self.model = self._create_predict_model()
    
    def _initialize_llm(self):
        """
        Initialize the GPT-4o LLM using DSPy.
        
        Returns:
            Configured DSPy language model (GPT-4o)
        """
        # Initialize GPT-4o model
        lm = LM("openai/gpt-4o")
        dspy.configure(lm=lm)
        return lm
    
    def _create_predict_model(self):
        """
        Create a DSPy Predict model for answer generation.
        
        Returns:
            Configured dspy.Predict model with AnswerGenerationSignature
        """
        # Create and return the Predict model with the signature
        model = dspy.Predict(AnswerGenerationSignature)
        return model
    
    def generate_response(
        self, 
        query: str, 
        context: Optional[str] = None, 
        past_conversation: Optional[str] = None
    ) -> str:
        """
        Generate an appropriate response to the user's query using the retrieved context
        and past conversation history.
        
        Args:
            query: The user's query string
            context: Retrieved context from the knowledge base (can be None or empty string)
            past_conversation: Previous conversation history (can be None or empty string)
            
        Returns:
            Generated answer string
        """
        # Handle None values by converting to empty strings
        context = context if context is not None else ""
        past_conversation = past_conversation if past_conversation is not None else ""
        
        # Generate an appropriate system prompt
        system_prompt = self._generate_system_prompt(context, past_conversation)
        
        # Call the Predict model with all inputs
        result = self.model(
            user_query=query,
            retrieved_context=context if context else "No context available.",
            past_conversation=past_conversation if past_conversation else "No previous conversation.",
            system_prompt=system_prompt
        )
        
        return result.answer
    
    def generate_response_stream(
        self, 
        query: str, 
        context: Optional[str] = None, 
        past_conversation: Optional[str] = None
    ) -> Iterator[str]:
        """
        Generate a streaming response to the user's query using OpenAI's streaming API.
        
        Args:
            query: The user's query string
            context: Retrieved context from the knowledge base (can be None or empty string)
            past_conversation: Previous conversation history (can be None or empty string)
            
        Yields:
            Token chunks as they are generated
        """
        # Handle None values by converting to empty strings
        context = context if context is not None else ""
        past_conversation = past_conversation if past_conversation is not None else ""
        
        # Generate an appropriate system prompt
        system_prompt = self._generate_system_prompt(context, past_conversation)
        
        # Build messages for OpenAI API
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add past conversation if available
        if past_conversation and past_conversation.strip():
            messages.append({
                "role": "system", 
                "content": f"Previous conversation history:\n{past_conversation}"
            })
        
        # Add context if available
        user_content = query
        if context and context.strip():
            user_content = f"Context from knowledge base:\n{context}\n\nUser query: {query}"
        
        messages.append({"role": "user", "content": user_content})
        
        # Get OpenAI API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        # Call OpenAI API with streaming
        client = openai.OpenAI(api_key=api_key)
        
        stream = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            stream=True,
            temperature=0.7
        )
        
        # Yield tokens as they arrive
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
    
    def _generate_system_prompt(self, context: str, past_conversation: str) -> str:
        """
        Generate an appropriate system prompt based on available context and conversation history.
        
        Args:
            context: Retrieved context from the knowledge base (empty string if not available)
            past_conversation: Previous conversation history (empty string if not available)
        
        Returns:
            System prompt string
        """
        base_prompt = (
            "You are a helpful AI assistant that answers questions based on the provided context "
            "and conversation history. Your goal is to provide accurate, clear, and helpful responses."
        )
        
        # Check if context and past_conversation are non-empty strings
        has_context = context and context.strip()
        has_past_conversation = past_conversation and past_conversation.strip()
        
        if has_context and has_past_conversation:
            system_prompt = (
                f"{base_prompt}\n\n"
                "You have access to both retrieved context from the knowledge base and previous "
                "conversation history. Use both sources to provide a comprehensive answer. "
                "If the context and conversation history are relevant, incorporate them into your response. "
                "If the user's query refers to previous conversation, make sure to reference it appropriately."
            )
        elif has_context:
            system_prompt = (
                f"{base_prompt}\n\n"
                "You have access to retrieved context from the knowledge base. "
                "Use this context to answer the user's query accurately. "
                "If the context is relevant, base your answer on it. If not, provide a general helpful response."
            )
        elif has_past_conversation:
            system_prompt = (
                f"{base_prompt}\n\n"
                "You have access to previous conversation history. "
                "Use this history to provide context-aware responses. "
                "If the user's query refers to previous conversation, reference it appropriately."
            )
        else:
            system_prompt = (
                f"{base_prompt}\n\n"
                "Answer the user's query to the best of your ability based on your general knowledge."
            )
        
        return system_prompt

