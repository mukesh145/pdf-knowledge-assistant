import dspy
from dotenv import load_dotenv
from typing import Optional, Iterator, Dict
from dspy import Signature, InputField, OutputField
from dspy import LM
import openai
import os
import json

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
    
    Outputs:
        answer: The generated answer to the user's query
        is_context_sufficient: Boolean indicating if the context or memory are sufficient/appropriate
    """
    user_query: str = InputField(desc="The user's query or question")
    retrieved_context: str = InputField(desc="Context retrieved from the knowledge base")
    past_conversation: str = InputField(desc="Previous conversation history")
    system_prompt: str = InputField(desc="System prompt with instructions for answer generation")
    answer: str = OutputField(desc="The generated answer to the user's query")
    is_context_sufficient: bool = OutputField(desc="True if the context or memory are sufficient and appropriate to generate an appropriate answer, False otherwise")


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
        Initialize the GPT-4o LLM using DSPy with token usage tracking enabled.
        
        Returns:
            Configured DSPy language model (GPT-4o)
        """
        # Initialize GPT-4o model
        lm = LM("openai/gpt-4o")
        # Enable token usage tracking
        dspy.configure(lm=lm, track_usage=True)
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
    ) -> Dict[str, any]:
        """
        Generate an appropriate response to the user's query using the retrieved context
        and past conversation history.
        
        Args:
            query: The user's query string
            context: Retrieved context from the knowledge base (can be None or empty string)
            past_conversation: Previous conversation history (can be None or empty string)
            
        Returns:
            Dictionary containing:
                - answer: Generated answer string
                - is_context_sufficient: Boolean indicating if context/memory are sufficient
                - input_tokens: Number of input tokens used
                - output_tokens: Number of output tokens used
        """
        # Handle None values by converting to empty strings
        context = context if context is not None else ""
        past_conversation = past_conversation if past_conversation is not None else ""
        
        # Generate an appropriate system prompt
        system_prompt = self._generate_system_prompt(context, past_conversation)
        
        # Build messages for OpenAI API to track tokens
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
        
        # Use DSPy to generate response with is_context_sufficient
        dspy_result = self.model(
            user_query=query,
            retrieved_context=context if context else "No context available.",
            past_conversation=past_conversation if past_conversation else "No previous conversation.",
            system_prompt=(
                f"{system_prompt}\n\n"
                "Evaluate whether the provided context and/or conversation history "
                "are sufficient and appropriate to answer the user's query accurately. "
                "Set is_context_sufficient to True only if the context or memory contain "
                "relevant information that allows you to provide an accurate answer."
            )
        )
        
        answer = dspy_result.answer
        is_context_sufficient = getattr(dspy_result, 'is_context_sufficient', False)
        
        # Get token usage from DSPy (tracked automatically when track_usage=True)
        input_tokens = 0
        output_tokens = 0
        try:
            usage_stats = dspy_result.get_lm_usage()
            # usage_stats is a dict mapping model names to usage info
            # For OpenAI models, it typically contains 'prompt_tokens' and 'completion_tokens'
            if usage_stats:
                # Get usage from the first (and typically only) model
                model_usage = list(usage_stats.values())[0] if usage_stats else {}
                if isinstance(model_usage, dict):
                    input_tokens = model_usage.get('prompt_tokens', 0)
                    output_tokens = model_usage.get('completion_tokens', 0)
                # Handle case where usage_stats might be in a different format
                elif hasattr(model_usage, 'prompt_tokens'):
                    input_tokens = model_usage.prompt_tokens or 0
                    output_tokens = model_usage.completion_tokens or 0
        except (AttributeError, IndexError, KeyError) as e:
            # Fallback: count tokens using tiktoken if DSPy usage tracking fails
            try:
                import tiktoken
                encoding = tiktoken.encoding_for_model("gpt-4o")
                # Count input tokens (all messages)
                input_text = "\n".join([msg["content"] for msg in messages])
                input_tokens = len(encoding.encode(input_text))
                # Count output tokens (the answer)
                output_tokens = len(encoding.encode(answer))
            except ImportError:
                # Final fallback estimation: ~4 characters per token
                input_text = "\n".join([msg["content"] for msg in messages])
                input_tokens = len(input_text) // 4
                output_tokens = len(answer) // 4
        
        return {
            "answer": answer,
            "is_context_sufficient": bool(is_context_sufficient),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }
    
    def generate_response_stream(
        self, 
        query: str, 
        context: Optional[str] = None, 
        past_conversation: Optional[str] = None
    ) -> Iterator[Dict[str, any]]:
        """
        Generate a streaming response to the user's query using OpenAI's streaming API.
        
        Note: This method uses OpenAI API directly (not DSPy) for streaming, so token tracking
        uses tiktoken or estimation. For non-streaming responses, use generate_response() which
        leverages DSPy's built-in token tracking.
        
        Args:
            query: The user's query string
            context: Retrieved context from the knowledge base (can be None or empty string)
            past_conversation: Previous conversation history (can be None or empty string)
            
        Yields:
            Dictionary chunks with:
                - "type": "token" or "metadata"
                - "data": token string (for "token") or dict with answer, is_context_sufficient, tokens (for "metadata")
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
        
        full_response = ""
        input_tokens = 0
        output_tokens = 0
        
        # Yield tokens as they arrive
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                token = chunk.choices[0].delta.content
                full_response += token
                yield {
                    "type": "token",
                    "data": token
                }
            
            # Usage information may come in a separate chunk after streaming completes
            # Check if this chunk has usage info
            if hasattr(chunk, 'usage') and chunk.usage is not None:
                input_tokens = chunk.usage.prompt_tokens or 0
                output_tokens = chunk.usage.completion_tokens or 0
        
        # If usage wasn't captured from the stream, count tokens using tiktoken
        if input_tokens == 0 and output_tokens == 0:
            try:
                import tiktoken
                encoding = tiktoken.encoding_for_model("gpt-4o")
                # Count input tokens (all messages)
                input_text = "\n".join([msg["content"] for msg in messages])
                input_tokens = len(encoding.encode(input_text))
                # Count output tokens (the full response)
                output_tokens = len(encoding.encode(full_response))
            except ImportError:
                # Fallback estimation: ~4 characters per token
                input_text = "\n".join([msg["content"] for msg in messages])
                input_tokens = len(input_text) // 4
                output_tokens = len(full_response) // 4
        
        # After streaming completes, determine is_context_sufficient using DSPy
        is_context_sufficient = False
        try:
            # Use DSPy to evaluate context sufficiency
            eval_result = self.model(
                user_query=query,
                retrieved_context=context if context else "No context available.",
                past_conversation=past_conversation if past_conversation else "No previous conversation.",
                system_prompt=(
                    f"{system_prompt}\n\n"
                    "Evaluate whether the provided context and/or conversation history "
                    "were sufficient and appropriate to answer the user's query accurately. "
                    "Set is_context_sufficient to True only if the context or memory contain "
                    "relevant information that allows you to provide an accurate answer."
                )
            )
            is_context_sufficient = getattr(eval_result, 'is_context_sufficient', False)
        except Exception as e:
            # Fallback: determine programmatically based on availability
            has_context = context and context.strip()
            has_memory = past_conversation and past_conversation.strip()
            # Consider sufficient if we have at least one source
            is_context_sufficient = has_context or has_memory
        
        # Yield metadata with final results
        yield {
            "type": "metadata",
            "data": {
                "answer": full_response,
                "is_context_sufficient": bool(is_context_sufficient),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }
        }
    
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

