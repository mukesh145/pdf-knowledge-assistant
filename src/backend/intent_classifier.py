import dspy
from dotenv import load_dotenv
from dspy import Signature, InputField, OutputField
from dspy import LM
from pathlib import Path
from .utils import load_config

# Load environment variables from .env file
load_dotenv()


class TaskClassificationSignature(Signature):
    """
    Signature for task classification with two boolean outputs.
    rag is required if the query is related to internal documents, or any domain specific information, which might not be publicly available.
    previous memory is required , if the query is related to the previous conversation.

    Input:
        query: a processed query string

    Output:
        is_rag_required: is rag search required for the query (True or False). If the query is domain specific, then it is required.
        is_prev_memory_required: is previous memory required for the query (True or False). If the query is about the previous conversation, then it is required.
    """
    query: str = InputField(desc="A processed query string to be classified")
    is_rag_required: bool = OutputField(desc="Is RAG search required for the query? (True or False)")
    is_prev_memory_required: bool = OutputField(desc="Is previous memory required for the query? (True or False)")


class IntentClassifier:
    """
    A class for classifying user intents to determine if RAG search or previous memory is required.
    """
    
    def __init__(self):
        """
        Initialize the IntentClassifier by setting up the LLM and classification model.
        """
        self.lm = self._initialize_llm()
        self.model = self._create_classification_model()
    
    def _initialize_llm(self):
        """
        Initialize the LLM using the model name from the config file.
        
        Returns:
            Configured DSPy language model
        """
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "configs" / "backend_config.yaml"
    
        # Load configuration
        config = load_config(config_path)
        
        # Get model name from config
        model_name = config.get("intent_classification_model", {}).get("name", "openai/gpt-3.5-turbo")
        
        # Initialize OpenAI model with the configured name
        lm = LM(model_name)
        dspy.configure(lm=lm)
        return lm
    
    def _create_classification_model(self):
        """
        Create a DSPy Predict model for task classification.
        
        Returns:
            Configured dspy.Predict model
        """
        # Create and return the Predict model with the signature
        model = dspy.Predict(TaskClassificationSignature)
        return model
    
    def classify(self, query: str) -> dict:
        """
        Classify a query to determine if RAG search and/or previous memory is required.

        Args:
            query: A query string to be classified
            
        Returns:
            Dictionary containing is_rag_required and is_prev_memory_required (both boolean)
        """
        result = self.model(query=query)
        
        return {
            "is_rag_required": result.is_rag_required,
            "is_prev_memory_required": result.is_prev_memory_required
        }
    
    def classify_task(self, prompt: str) -> dict:
        """
        Classify a task using the DSPy model.
        (Legacy method name for backward compatibility)
        
        Args:
            prompt: A prompt defining the task
            
        Returns:
            Dictionary containing is_rag_required and is_prev_memory_required (both boolean)
        """
        return self.classify(prompt)
