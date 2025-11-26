"""
PDF Extractor Module

This module provides the Extractor class for extracting text content from PDF files.
"""

import re
from pathlib import Path
from typing import List, Optional
from unstructured.partition.pdf import partition_pdf

from src.agent.query_processing import QueryProcessor
from src.knowledge.post_processor import PostProcessor


class Extractor:
    """
    A class for extracting text content from PDF files.
    
    This class handles:
    - Extracting multiple element types from PDF files (text, headings, lists, tables)
    - Converting tables to readable text format
    - Processing paragraphs using QueryProcessor
    """
    
    def __init__(self, enable_post_processing: bool = True, verbose: bool = False):
        """
        Initialize the Extractor.
        
        Args:
            enable_post_processing: Whether to apply post-processing (default: True)
            verbose: Whether to print debugging information (default: False)
        """
        self.query_processor = QueryProcessor()
        self.post_processor = PostProcessor()
        self.enable_post_processing = enable_post_processing
        self.verbose = verbose
        
        # Define element categories to extract
        self.extracted_categories = {
            'NarrativeText',  # Regular paragraphs
            'Title',          # Document titles
            'Heading',        # Section headings
            'ListItem',       # Bulleted/numbered lists
            'Table',          # Tables
            'FigureCaption',  # Figure captions
        }
    
    
    def _group_elements_by_structure(self, elements) -> List[tuple]:
        """
        Group elements by document structure (sections, pages, headings).
        Combines consecutive narrative text, list items, and figure captions into coherent sections.
        Uses headings/titles as section boundaries.
        
        Args:
            elements: List of elements from unstructured
            
        Returns:
            List of tuples (text, category, metadata_dict)
        """
        grouped_items = []
        current_section = []
        current_section_category = None
        current_page = None
        
        for element in elements:
            # Get element metadata
            category = getattr(element, 'category', None) if hasattr(element, 'category') else None
            page_number = None
            if hasattr(element, 'metadata') and element.metadata:
                page_number = getattr(element.metadata, 'page_number', None)
            
            # Check if this is a section boundary (heading or title)
            is_section_boundary = category in ['Title', 'Heading']
            
            # If we hit a section boundary, finalize current section
            if is_section_boundary and current_section:
                # Combine all elements in current section
                combined_text = ' '.join(current_section)
                if combined_text.strip():
                    grouped_items.append((combined_text, current_section_category or 'NarrativeText', {
                        'page': current_page,
                        'is_section': True
                    }))
                current_section = []
                current_section_category = None
            
            # Handle the current element
            if category == 'Table':
                # Tables are always separate - finalize current section first
                if current_section:
                    combined_text = ' '.join(current_section)
                    if combined_text.strip():
                        grouped_items.append((combined_text, current_section_category or 'NarrativeText', {
                            'page': current_page,
                            'is_section': True
                        }))
                    current_section = []
                    current_section_category = None
                
                # Add table separately
                table_text = self._convert_table_to_text(element)
                if table_text:
                    grouped_items.append((table_text, 'Table', {'page': page_number}))
            elif hasattr(element, 'text') and element.text:
                text = element.text.strip()
                if text:
                    if is_section_boundary:
                        # Headings/titles start a new section - add them separately
                        grouped_items.append((text, category, {'page': page_number, 'is_heading': True}))
                        current_section = []
                        current_section_category = None
                    else:
                        # Add to current section for grouping (includes NarrativeText, ListItem, FigureCaption, etc.)
                        current_section.append(text)
                        if not current_section_category:
                            # Use the first category in the section, or default to NarrativeText
                            current_section_category = category or 'NarrativeText'
                        if current_page is None:
                            current_page = page_number
        
        # Finalize any remaining section
        if current_section:
            combined_text = ' '.join(current_section)
            if combined_text.strip():
                grouped_items.append((combined_text, current_section_category or 'NarrativeText', {
                    'page': current_page,
                    'is_section': True
                }))
        
        return grouped_items
    
    def _convert_table_to_text(self, table_element) -> str:
        """
        Convert a table element to readable text format.
        
        Args:
            table_element: Table element from unstructured
            
        Returns:
            String representation of the table in readable format
        """
        # Try to get text representation from the table
        if hasattr(table_element, 'text') and table_element.text:
            # If table has a text attribute, use it
            return table_element.text.strip()
        
        # Try to get HTML representation and convert to text
        if hasattr(table_element, 'metadata') and table_element.metadata:
            if hasattr(table_element.metadata, 'text_as_html') and table_element.metadata.text_as_html:
                # Convert HTML table to readable text
                # This is a simple conversion - could be enhanced with proper HTML parsing
                html_text = table_element.metadata.text_as_html
                # Remove HTML tags and clean up
                text = re.sub(r'<[^>]+>', ' | ', html_text)
                text = re.sub(r'\s*\|\s*', ' | ', text)  # Normalize separators
                text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
                return text.strip()
        
        # Fallback: return empty string if no text representation available
        return ""
    
    def extract(self, pdf_path: str, preserve_structure: bool = True) -> List[str]:
        """
        Extract text content from a PDF file using unstructured.
        Extracts multiple element types: paragraphs, headings, lists, tables, and captions.
        
        Args:
            pdf_path: Path to the PDF file (can be relative or absolute)
            preserve_structure: Whether to group elements by document structure (default: True).
                                When True, consecutive narrative text elements are combined into
                                coherent sections, preserving document structure.
            
        Returns:
            List of text strings extracted from the PDF (paragraphs, headings, lists, tables, etc.)
            
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
        
        # Partition PDF with table structure inference enabled
        elements = partition_pdf(
            filename=str(pdf_path),
            strategy="hi_res",  # High resolution for better text extraction
            infer_table_structure=True,  # Enable table structure inference
            extract_images_in_pdf=False,  # We only want text
        )
        
        if self.verbose:
            print(f"Total elements found in PDF: {len(elements)}")
        
        # Group elements by structure if requested
        if preserve_structure:
            grouped_items = self._group_elements_by_structure(elements)
            if self.verbose:
                print(f"Grouped into {len(grouped_items)} structured sections")
            
            # Extract texts from grouped items
            extracted_items = []
            for text, category, metadata in grouped_items:
                if text and text.strip():
                    # Apply relaxed filtering based on category
                    words = text.split()
                    if category in ['Title', 'Heading']:
                        # Always include headings/titles
                        extracted_items.append((text, category))
                    elif category == 'Table':
                        # Always include tables
                        extracted_items.append((text, category))
                    elif len(words) >= 1:
                        # Include any other grouped text with at least 1 word
                        extracted_items.append((text, category))
        else:
            # Original extraction logic (individual elements)
            extracted_items = []
            category_counts = {}
            
            for element in elements:
                # Get element category
                category = getattr(element, 'category', None) if hasattr(element, 'category') else None
                category_counts[category] = category_counts.get(category, 0) + 1
                
                # Handle Table elements specially
                if category == 'Table':
                    table_text = self._convert_table_to_text(element)
                    if table_text:  # Include any non-empty table
                        extracted_items.append((table_text, 'Table'))
                    continue
                
                # Handle ALL other element types - be very inclusive
                if hasattr(element, 'text') and element.text:
                    text = element.text.strip()
                    if text:  # Include ANY non-empty text, regardless of category or length
                        # For known categories, use relaxed thresholds
                        if category in self.extracted_categories:
                            # For headings and titles, include all (they're important)
                            if category in ['Title', 'Heading']:
                                extracted_items.append((text, category))
                            # For list items, include all (even single words)
                            elif category == 'ListItem':
                                extracted_items.append((text, category))
                            # For figure captions, include all
                            elif category == 'FigureCaption':
                                extracted_items.append((text, category))
                            # For narrative text, include if at least 3 words (relaxed from 10)
                            elif category == 'NarrativeText':
                                if len(text.split()) >= 3:  # Reduced from 10 to 3
                                    extracted_items.append((text, category))
                        else:
                            # Include ANY unknown category if it has at least 1 word (very permissive)
                            if len(text.split()) >= 1:
                                extracted_items.append((text, category or 'Unknown'))
            
            if self.verbose:
                print(f"Category distribution: {category_counts}")
                print(f"Extracted items before filtering: {len(extracted_items)}")
        
        # Final filtering: very relaxed - only remove completely empty texts
        # Keep headings/titles always, keep others if they have at least 1 word
        filtered_texts = []
        for text, cat in extracted_items:
            words = text.split()
            # Keep headings/titles always (they provide important context)
            if cat in ['Title', 'Heading']:
                if text:
                    filtered_texts.append(text)
            # Keep other texts if they have at least 1 word (very permissive)
            elif len(words) >= 1:
                filtered_texts.append(text)
        
        if self.verbose:
            print(f"Filtered texts before post-processing: {len(filtered_texts)}")
            print(f"Texts removed by filtering: {len(extracted_items) - len(filtered_texts)}")
        
        # Apply post-processing if enabled
        if self.enable_post_processing:
            processed_texts = self.post_processor.process(filtered_texts, verbose=self.verbose)
            if self.verbose:
                print(f"Final processed texts: {len(processed_texts)}")
                print(f"Texts removed by post-processing: {len(filtered_texts) - len(processed_texts)}")
        else:
            processed_texts = filtered_texts
            if self.verbose:
                print(f"Post-processing disabled, returning {len(processed_texts)} texts")
        
        return processed_texts
    
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

