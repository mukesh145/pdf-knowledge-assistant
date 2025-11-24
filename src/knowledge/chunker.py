"""
Text Chunker Module

This module provides the Chunker class for splitting text into chunks with overlap.
"""

from typing import List


class Chunker:
    """
    A class for chunking text into segments with overlap.
    
    This class handles:
    - Splitting text into chunks of specified word size with overlap
    - Chunking paragraphs into segments
    """
    
    def __init__(self):
        """Initialize the Chunker."""
        pass
    
    def chunk_text_with_overlap(
        self,
        text: str,
        chunk_size: int = 300,
        overlap: int = 50
    ) -> List[str]:
        """
        Split text into chunks of specified word size with overlap.
        
        Args:
            text: Input text to chunk
            chunk_size: Number of words per chunk (default: 300)
            overlap: Number of overlapping words between consecutive chunks (default: 50)
            
        Returns:
            List of text chunks
        """
        # Split text into words
        words = text.split()
        
        if len(words) <= chunk_size:
            # If text is smaller than chunk size, return as single chunk
            return [text]
        
        chunks = []
        start_idx = 0
        
        while start_idx < len(words):
            # Get chunk of words
            end_idx = min(start_idx + chunk_size, len(words))
            chunk_words = words[start_idx:end_idx]
            chunk_text = ' '.join(chunk_words)
            chunks.append(chunk_text)
            
            # Move start index forward by (chunk_size - overlap) to create overlap
            start_idx += (chunk_size - overlap)
            
            # If we're at the end, break
            if end_idx >= len(words):
                break
        
        return chunks
    
    def chunk_paragraphs(
        self,
        paragraphs: List[str],
        chunk_size: int = 300,
        overlap: int = 50
    ) -> List[str]:
        """
        Combine paragraphs and chunk them into segments of specified word size with overlap.
        
        Args:
            paragraphs: List of paragraph strings
            chunk_size: Number of words per chunk (default: 300)
            overlap: Number of overlapping words between consecutive chunks (default: 50)
            
        Returns:
            List of chunked text segments
        """
        # Combine all paragraphs into one continuous text
        combined_text = ' '.join(paragraphs)
        
        # Chunk the combined text
        chunks = self.chunk_text_with_overlap(combined_text, chunk_size, overlap)
        
        return chunks

