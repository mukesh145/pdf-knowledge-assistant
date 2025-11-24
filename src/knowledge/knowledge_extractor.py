"""
PDF Extractor Module

This module provides the Extractor class for extracting text content from PDF files.
"""

from pathlib import Path
from typing import List
from unstructured.partition.pdf import partition_pdf

from src.backend.query_processing import QueryProcessor


class Extractor:
    """
    A class for extracting text content from PDF files.
    
    This class handles:
    - Extracting paragraphs from PDF files using unstructured library
    - Processing paragraphs using QueryProcessor
    """
    
    def __init__(self):
        """Initialize the Extractor."""
        self.query_processor = QueryProcessor()
    
    def extract(self, pdf_path: str) -> List[str]:
        """
        Extract paragraphs from a PDF file using unstructured.
        Only extracts text content, no other elements.
        
        Args:
            pdf_path: Path to the PDF file (can be relative or absolute)
            
        Returns:
            List of paragraph strings extracted from the PDF
            
        Raises:
            FileNotFoundError: If the PDF file doesn't exist
        """
        # Resolve PDF path relative to project root if needed
        if not Path(pdf_path).is_absolute():
            # If relative path, resolve relative to project root
            project_root = Path(__file__).parent.parent.parent
            pdf_path = project_root / pdf_path
        else:
            pdf_path = Path(pdf_path)
        
        pdf_path = pdf_path.resolve()
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Partition PDF and extract only text elements
        elements = partition_pdf(
            filename=str(pdf_path),
            strategy="hi_res",  # High resolution for better text extraction
            infer_table_structure=False,  # We only want text
            extract_images_in_pdf=False,  # We only want text
        )
        
        # Extract text from elements and filter out empty strings
        paragraphs = []
        
        for element in elements:
            # Get text content from element
            if hasattr(element, 'text') and element.text:
                text = element.text.strip()
                if text:
                    # If element type is a paragraph or similar, add it
                    if hasattr(element, 'category') and element.category == 'NarrativeText':
                        paragraphs.append(text)
                    elif text:  # Fallback: add any non-empty text
                        # Check if it's a substantial paragraph (more than just a few words)
                        if len(text.split()) > 5:  # At least 5 words
                            paragraphs.append(text)
        
        # Filter out very short paragraphs (likely headers or noise)
        paragraphs = [p for p in paragraphs if len(p.split()) >= 10]  # At least 10 words
        
        return paragraphs
    
    def process_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """
        Process paragraphs using the same algorithm as query processing.
        Applies lowercase conversion and whitespace normalization.
        
        Args:
            paragraphs: List of raw paragraph strings
            
        Returns:
            List of processed paragraph strings
        """
        processed_paragraphs = []
        for paragraph in paragraphs:
            processed = self.query_processor.process(paragraph)
            processed_paragraphs.append(processed)
        
        return processed_paragraphs

