from typing import List
import os
import numpy as np
from FlagEmbedding import FlagModel
from pinecone import Pinecone
from pathlib import Path
from .utils import load_config


class ContextRetriever:
    """
    A class for retrieving context by converting queries to vector embeddings.
    Uses BAAI/bge-m3 model from Hugging Face for generating embeddings.
    """
    
    def __init__(self):
        """
        Initialize the ContextRetriever by loading the embedding model from config.
        """
        self.model = self._initialize_embedding_model()
        self._pinecone_index = self._initialize_pinecone_index()
    
    def _initialize_embedding_model(self):
        """
        Initialize the embedding model using the model name from the config file.
        
        Returns:
            Configured FlagModel for embeddings
        """
        # Load configuration
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "configs" / "backend_config.yaml"
        config = load_config(config_path)
        
        # Get model name from config
        model_name = config.get("embeddings_model", {}).get("name", "BAAI/bge-m3")
        
        # Initialize FlagModel with the configured name
        model = FlagModel(model_name, use_fp16=True)
        return model
    
    def convert_to_embeddings(self, processed_query: str) -> np.ndarray:
        """
        Convert a processed query to vector embeddings.
        
        Args:
            processed_query: The processed query string to convert to embeddings
            
        Returns:
            numpy array containing the vector embeddings
        """
        # Generate embeddings for the query
        embeddings = self.model.encode(processed_query)
        
        # Convert to numpy array if not already
        if not isinstance(embeddings, np.ndarray):
            embeddings = np.array(embeddings)
        
        return embeddings
    
    def convert_batch_to_embeddings(self, processed_queries: List[str]) -> np.ndarray:
        """
        Convert a batch of processed queries to vector embeddings.
        
        Args:
            processed_queries: List of processed query strings to convert to embeddings
            
        Returns:
            numpy array containing the vector embeddings for all queries
        """
        # Generate embeddings for the batch of queries
        embeddings = self.model.encode(processed_queries)
        
        # Convert to numpy array if not already
        if not isinstance(embeddings, np.ndarray):
            embeddings = np.array(embeddings)
        
        return embeddings
    
    def _initialize_pinecone_index(self):
        """
        Initialize Pinecone index connection. Uses environment variables for configuration.
        
        Returns:
            Pinecone Index object
        """
        # Get Pinecone configuration from environment variables
        api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME", "test")
        
        if api_key is None:
            raise ValueError(
                "PINECONE_API_KEY environment variable is not set. "
                "Please set it before querying the vector database."
            )
        
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key)
        
        # Connect to the index
        pinecone_index = pc.Index(index_name)
        
        return pinecone_index
    def retrieve_context(self, query: str, top_k: int = 5) -> List[dict]:
        """
        Convert query to embeddings, query the vector DB, and return top results.
        
        Args:
            query: The query string to search for
            top_k: Number of top results to retrieve (default: 5)
            
        Returns:
            List of dictionaries containing the top search results with metadata
        """
        # Step 1: Convert query to embeddings
        query_embedding = self.convert_to_embeddings(query)
        
        # Step 2: Initialize Pinecone index if not already done
        index = self._pinecone_index
        
        # Step 3: Query Pinecone vector database
        results = index.query(
            vector=query_embedding.tolist(),
            top_k=top_k,
            include_metadata=True
        )

        # print(results)
        
        contexts = []
        for context in results.get('matches', []):
            contexts.append(context.get('metadata',"").get('text',""))

        # Step 4: Extract and return the matches
        return contexts

