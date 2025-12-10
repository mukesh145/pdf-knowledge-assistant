"""
Knowledge Base Creator Module

This module provides the KnowledgeExtractor class for processing extracted PDF content,
chunking it, converting to embeddings, and storing in Pinecone vector database.
"""

import os
import uuid
from pathlib import Path
from typing import List, Optional
import numpy as np
from pinecone import Pinecone, ServerlessSpec

from src.agent.query_processing import QueryProcessor
from src.agent.context_retriever import ContextRetriever
from src.knowledge.knowledge_extractor import Extractor
from src.knowledge.chunker import Chunker


class KnowledgeExtractor:
    """
    A class for extracting knowledge from PDF files and storing them in Pinecone vector database.
    
    This class handles the complete pipeline:
    1. Extract paragraphs from PDF files
    2. Chunk text into segments with overlap
    3. Process chunks using QueryProcessor
    4. Convert to embeddings using ContextRetriever
    5. Upload to Pinecone vector database
    """
    
    def __init__(
        self,
        pinecone_api_key: Optional[str] = None,
        pinecone_index_name: Optional[str] = None,
        pinecone_environment: Optional[str] = None
    ):
        """
        Initialize the KnowledgeExtractor.
        
        Args:
            pinecone_api_key: Pinecone API key (defaults to PINECONE_API_KEY env var)
            pinecone_index_name: Pinecone index name (defaults to PINECONE_INDEX_NAME env var or "pdf-knowledge-base")
            pinecone_environment: Pinecone environment/region (defaults to PINECONE_ENVIRONMENT env var or "us-east-1")
        """
        # Get configuration from parameters or environment variables
        self.pinecone_api_key = pinecone_api_key or os.getenv("PINECONE_API_KEY")
        self.pinecone_index_name = pinecone_index_name or os.getenv("PINECONE_INDEX_NAME", "pdf-knowledge-base")
        self.pinecone_environment = pinecone_environment or os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
        
        if not self.pinecone_api_key:
            raise ValueError(
                "Pinecone API key is required. "
                "Provide it as a parameter or set PINECONE_API_KEY environment variable."
            )
        
        # Initialize Pinecone client
        self.pc = Pinecone(api_key=self.pinecone_api_key)
        
        # Initialize or connect to Pinecone index
        self.index = self._initialize_pinecone_index()
        
        # Initialize processors
        self.query_processor = QueryProcessor()
        self.context_retriever = ContextRetriever()
        
        # Initialize PDF extractor
        self.extractor = Extractor()
        
        # Initialize chunker
        self.chunker = Chunker()
    
    def _initialize_pinecone_index(self):
        """
        Initialize or connect to Pinecone index.
        Creates the index if it doesn't exist.
        
        Returns:
            Pinecone Index object
        """
        # Check if index exists
        if self.pinecone_index_name not in self.pc.list_indexes().names():
            # Create index with dimension 1024 (BAAI/bge-m3 model dimension)
            self.pc.create_index(
                name=self.pinecone_index_name,
                dimension=1024,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=self.pinecone_environment
                )
            )
            print(f"Created new index: {self.pinecone_index_name}")
        else:
            print(f"Index {self.pinecone_index_name} already exists")
        
        # Connect to the index
        index = self.pc.Index(self.pinecone_index_name)
        print(f"Connected to index: {self.pinecone_index_name}")
        
        return index
    
    def extract(
        self,
        pdf_path: str,
        chunk_size: int = 300,
        overlap: int = 50,
        batch_size: int = 100
    ) -> dict:
        """
        Main method to extract paragraphs from PDF, chunk them into segments,
        process them, convert to embeddings, and upload to Pinecone DB.
        
        Args:
            pdf_path: Path to the PDF file (can be relative or absolute)
            chunk_size: Number of words per chunk (default: 300)
            overlap: Number of overlapping words between consecutive chunks (default: 50)
            batch_size: Number of chunks to process and upload in each batch (default: 100)
            
        Returns:
            Dictionary with extraction results including:
                - total_uploaded: Number of vectors uploaded
                - pdf_name: Name of the PDF file
                - num_paragraphs: Number of paragraphs extracted
                - num_chunks: Number of chunks created
        """
        # Resolve PDF path relative to project root
        if not Path(pdf_path).is_absolute():
            # If relative path, resolve relative to project root
            project_root = Path(__file__).parent.parent.parent
            pdf_path = project_root / pdf_path
        else:
            pdf_path = Path(pdf_path)
        
        pdf_path = pdf_path.resolve()
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Get PDF name for metadata
        pdf_name = pdf_path.stem
        
        print(f"Processing PDF: {pdf_name}")
        print(f"PDF path: {pdf_path}")
        print("-" * 50)
        
        # Step 1: Extract paragraphs from PDF using Extractor
        print("Step 1: Extracting paragraphs from PDF...")
        paragraphs = self.extractor.extract(str(pdf_path))
        print(f"Extracted {len(paragraphs)} paragraphs")
        
        if len(paragraphs) == 0:
            print("Warning: No paragraphs extracted from PDF. Exiting.")
            return {
                "total_uploaded": 0,
                "pdf_name": pdf_name,
                "num_paragraphs": 0,
                "num_chunks": 0
            }
        
        # Step 2: Chunk paragraphs into segments of specified size with overlap
        print(f"\nStep 2: Chunking paragraphs into {chunk_size}-word segments with {overlap}-word overlap...")
        chunked_segments = self.chunker.chunk_paragraphs(paragraphs, chunk_size=chunk_size, overlap=overlap)
        print(f"Created {len(chunked_segments)} chunks")
        
        # Step 3: Process chunks using QueryProcessor
        print("\nStep 3: Processing chunks...")
        processed_chunks = self.extractor.process_paragraphs(chunked_segments)
        print(f"Processed {len(processed_chunks)} chunks")
        
        # Step 4: Convert to embeddings using ContextRetriever
        print("\nStep 4: Converting chunks to embeddings...")
        
        # Process in batches to avoid memory issues
        total_uploaded = 0
        num_batches = (len(processed_chunks) + batch_size - 1) // batch_size
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(processed_chunks))
            batch_chunks = processed_chunks[start_idx:end_idx]
            batch_original = chunked_segments[start_idx:end_idx]  # Keep original for storage
            
            print(f"Processing batch {batch_idx + 1}/{num_batches} ({len(batch_chunks)} chunks)...")
            
            # Convert batch to embeddings
            embeddings = self.context_retriever.convert_batch_to_embeddings(batch_chunks)
            
            # Ensure embeddings is a 2D numpy array
            if embeddings.ndim == 1:
                embeddings = embeddings.reshape(1, -1)
            
            # Step 5: Prepare vectors for Pinecone upload
            vectors_to_upload = []
            for i in range(len(batch_chunks)):
                # Get embedding for this chunk (handle both 1D and 2D arrays)
                if embeddings.ndim == 2:
                    embedding = embeddings[i]
                else:
                    embedding = embeddings
                
                # Generate unique ID for each vector
                vector_id = str(uuid.uuid4())
                
                # Prepare metadata
                metadata = {
                    "pdf_name": pdf_name,
                    "chunk_index": start_idx + i,
                    "text": batch_original[i],  # Store original text for retrieval
                    "processed_text": batch_chunks[i]  # Store processed text for reference
                }
                
                vectors_to_upload.append({
                    "id": vector_id,
                    "values": embedding.tolist(),  # Convert numpy array to list
                    "metadata": metadata
                })
            
            # Upload batch to Pinecone
            print(f"Uploading batch {batch_idx + 1} to Pinecone...")
            self.index.upsert(vectors=vectors_to_upload)
            total_uploaded += len(vectors_to_upload)
            print(f"Uploaded {len(vectors_to_upload)} vectors (Total: {total_uploaded})")
        
        print("\n" + "=" * 50)
        print(f"Successfully uploaded {total_uploaded} vectors to Pinecone!")
        print(f"PDF: {pdf_name}")
        print(f"Chunk size: {chunk_size} words, Overlap: {overlap} words")
        print("=" * 50)
        
        return {
            "total_uploaded": total_uploaded,
            "pdf_name": pdf_name,
            "num_paragraphs": len(paragraphs),
            "num_chunks": len(chunked_segments)
        }

