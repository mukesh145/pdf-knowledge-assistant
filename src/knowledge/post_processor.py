"""
Post-Processing Module

This module provides the PostProcessor class for cleaning and processing
extracted text from PDFs to improve quality and accuracy.
"""

import re
import string
from typing import List, Tuple


class PostProcessor:
    """
    A class for post-processing extracted text from PDFs.
    
    This class handles:
    - Text cleaning (whitespace, encoding, OCR errors)
    - Sentence structure preservation
    - Broken paragraph detection and merging
    - Text quality validation
    """
    
    def __init__(self):
        """Initialize the PostProcessor."""
        # Common OCR error patterns (character substitutions)
        # Note: These are applied carefully to avoid false positives
        self.ocr_fixes = [
            # (pattern, replacement, description)
            # These are commented out by default as they can be too aggressive
            # Uncomment and adjust based on your specific PDF quality
            # (r'\b0\b', 'o', 'Standalone 0 -> o in words'),
            # (r'\brn\b', 'm', 'rn -> m (common OCR error)'),
        ]
        
        # Sentence ending patterns
        self.sentence_endings = re.compile(r'[.!?]\s+')
        
        # Track validation statistics
        self.validation_stats = {
            'total_processed': 0,
            'removed_empty': 0,
            'removed_non_printable': 0,
            'removed_excessive_digits': 0,
            'removed_excessive_punctuation': 0,
            'removed_character_repetition': 0,
            'removed_few_words': 0,
            'removed_low_alphabetic_ratio': 0,
        }
    
    def clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing extra whitespace, fixing encoding issues,
        and applying common OCR error corrections.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text string
        """
        if not text:
            return ""
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Remove zero-width characters and other invisible characters
        text = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]', '', text)
        
        # Normalize different types of spaces to regular space
        text = re.sub(r'[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]', ' ', text)
        
        # Remove excessive line breaks (more than 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Fix broken words (words split with hyphen and newline)
        # Pattern: word-\nword -> wordword (common PDF line break issue)
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
        
        # Fix words split across lines without hyphen
        # Pattern: word\nword (where first word doesn't end with punctuation)
        text = re.sub(r'(\w+)\s*\n\s*(\w+)', r'\1 \2', text)
        
        # Collapse multiple spaces into single space
        text = re.sub(r' +', ' ', text)
        
        # Fix multiple consecutive punctuation (except ellipsis)
        text = re.sub(r'([.!?]){2,}', r'\1', text)
        
        # Remove excessive punctuation (more than 3 consecutive)
        text = re.sub(r'[^\w\s]{4,}', '', text)
        
        # Fix common OCR errors (be careful with these - they might be too aggressive)
        # Only apply in specific contexts to avoid false positives
        for pattern, replacement, _ in self.ocr_fixes:
            # Apply OCR fixes more carefully - only in word boundaries
            text = re.sub(pattern, replacement, text)
        
        # Remove control characters except newlines and tabs
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # Normalize quotes (convert smart quotes to regular quotes)
        text = text.replace('\u201c', '"').replace('\u201d', '"')
        text = text.replace('\u2018', "'").replace('\u2019', "'")
        text = text.replace('\u2013', '-').replace('\u2014', '--')
        
        # Final trim
        text = text.strip()
        
        return text
    
    def detect_broken_paragraphs(self, texts: List[str]) -> List[Tuple[str, bool]]:
        """
        Detect potentially broken paragraphs that should be merged.
        A paragraph is considered broken if it:
        - Doesn't end with sentence-ending punctuation
        - Is very short and the next paragraph starts with lowercase
        - Ends with a comma or semicolon (might be continuation)
        
        Args:
            texts: List of text strings to analyze
            
        Returns:
            List of tuples (text, should_merge_with_next)
        """
        if not texts:
            return []
        
        results = []
        for i, text in enumerate(texts):
            should_merge = False
            
            # Skip headings and titles (they're usually complete)
            if i < len(texts) - 1:  # Not the last item
                text_stripped = text.strip()
                next_text = texts[i + 1].strip() if i + 1 < len(texts) else ""
                
                # Check if current text doesn't end with sentence punctuation
                if text_stripped and not re.search(r'[.!?]\s*$', text_stripped):
                    # If next text starts with lowercase, likely continuation
                    if next_text and next_text[0].islower():
                        should_merge = True
                    # If current text is short and ends with comma/semicolon
                    elif len(text_stripped.split()) < 15 and re.search(r'[,;]\s*$', text_stripped):
                        should_merge = True
                    # If current text is very short (less than 5 words) and next starts lowercase
                    elif len(text_stripped.split()) < 5 and next_text and next_text[0].islower():
                        should_merge = True
            
            results.append((text, should_merge))
        
        return results
    
    def merge_broken_paragraphs(self, texts: List[str]) -> List[str]:
        """
        Merge broken paragraphs that were incorrectly split.
        
        Args:
            texts: List of text strings that may contain broken paragraphs
            
        Returns:
            List of merged text strings
        """
        if not texts:
            return []
        
        # Detect which paragraphs should be merged
        merge_flags = self.detect_broken_paragraphs(texts)
        
        merged = []
        i = 0
        while i < len(texts):
            current_text = texts[i]
            
            # Check if this paragraph should be merged with the next one(s)
            j = i
            while j < len(merge_flags) and merge_flags[j][1]:
                j += 1
                if j < len(texts):
                    # Merge with next paragraph
                    current_text = current_text + " " + texts[j]
            
            merged.append(current_text)
            i = j + 1
        
        return merged
    
    def validate_text_quality(self, text: str) -> Tuple[bool, str]:
        """
        Validate text quality and detect potential issues.
        Uses relaxed thresholds to minimize data loss.
        
        Args:
            text: Text to validate
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if not text or len(text.strip()) == 0:
            self.validation_stats['removed_empty'] += 1
            return False, "Empty text"
        
        # Check for excessive non-printable characters (relaxed threshold)
        non_printable_ratio = sum(1 for c in text if c not in string.printable) / len(text) if text else 0
        if non_printable_ratio > 0.2:  # Relaxed from 10% to 20%
            self.validation_stats['removed_non_printable'] += 1
            return False, "Too many non-printable characters"
        
        # Check for excessive numbers (relaxed - allow more digits for technical content)
        digit_ratio = sum(1 for c in text if c.isdigit()) / len(text) if text else 0
        if digit_ratio > 0.7:  # Relaxed from 50% to 70% (allow technical content with numbers)
            self.validation_stats['removed_excessive_digits'] += 1
            return False, "Too many digits (likely corrupted)"
        
        # Check for excessive special characters (relaxed)
        special_char_ratio = sum(1 for c in text if c in string.punctuation) / len(text) if text else 0
        if special_char_ratio > 0.5:  # Relaxed from 30% to 50%
            self.validation_stats['removed_excessive_punctuation'] += 1
            return False, "Too many special characters"
        
        # Check for repeated characters (more lenient)
        if re.search(r'(.)\1{20,}', text):  # Relaxed from 10+ to 20+ repetitions
            self.validation_stats['removed_character_repetition'] += 1
            return False, "Excessive character repetition"
        
        # Check for valid word ratio (very relaxed - allow technical content)
        words = text.split()
        if words:
            alphabetic_words = sum(1 for w in words if any(c.isalpha() for c in w))
            if alphabetic_words / len(words) < 0.1:  # Relaxed from 30% to 10%
                self.validation_stats['removed_low_alphabetic_ratio'] += 1
                return False, "Too few valid words"
        
        # Check minimum word count (very relaxed - allow single words)
        if len(words) < 1:  # Relaxed from 3 to 1
            self.validation_stats['removed_few_words'] += 1
            return False, "Too few words"
        
        return True, ""
    
    def preserve_sentence_structure(self, text: str) -> str:
        """
        Ensure proper sentence structure by fixing spacing around punctuation.
        
        Args:
            text: Text to process
            
        Returns:
            Text with proper sentence structure
        """
        if not text:
            return ""
        
        # Ensure space after sentence-ending punctuation
        text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)
        
        # Fix spacing around commas
        text = re.sub(r'\s*,\s*', ', ', text)
        
        # Fix spacing around colons and semicolons
        text = re.sub(r'\s*:\s*', ': ', text)
        text = re.sub(r'\s*;\s*', '; ', text)
        
        # Remove space before punctuation
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)
        
        # Ensure single space after punctuation
        text = re.sub(r'([,.!?;:])\s*', r'\1 ', text)
        text = re.sub(r'([,.!?;:])\s+', r'\1 ', text)
        
        return text.strip()
    
    def process(self, texts: List[str], verbose: bool = False) -> List[str]:
        """
        Apply comprehensive post-processing to extracted texts.
        
        This method orchestrates the complete post-processing pipeline:
        1. Clean text (whitespace, encoding, OCR errors)
        2. Validate text quality
        3. Preserve sentence structure
        4. Merge broken paragraphs
        
        Args:
            texts: List of raw extracted text strings
            verbose: Whether to print debugging information
            
        Returns:
            List of cleaned and processed text strings
        """
        if not texts:
            return []
        
        # Reset validation stats
        self.validation_stats = {
            'total_processed': 0,
            'removed_empty': 0,
            'removed_non_printable': 0,
            'removed_excessive_digits': 0,
            'removed_excessive_punctuation': 0,
            'removed_character_repetition': 0,
            'removed_few_words': 0,
            'removed_low_alphabetic_ratio': 0,
        }
        
        processed = []
        removed_reasons = {}
        
        for text in texts:
            self.validation_stats['total_processed'] += 1
            
            # Step 1: Clean text (whitespace, encoding, OCR errors)
            cleaned = self.clean_text(text)
            
            if not cleaned:
                removed_reasons['empty_after_cleaning'] = removed_reasons.get('empty_after_cleaning', 0) + 1
                continue
            
            # Step 2: Validate text quality
            is_valid, reason = self.validate_text_quality(cleaned)
            if not is_valid:
                removed_reasons[reason] = removed_reasons.get(reason, 0) + 1
                if verbose:
                    print(f"  Removed text: {reason[:50]}...")
                continue
            
            # Step 3: Preserve sentence structure
            cleaned = self.preserve_sentence_structure(cleaned)
            
            processed.append(cleaned)
        
        # Step 4: Merge broken paragraphs
        before_merge = len(processed)
        processed = self.merge_broken_paragraphs(processed)
        
        if verbose:
            print(f"\nPost-processing statistics:")
            print(f"  Total texts processed: {self.validation_stats['total_processed']}")
            print(f"  Texts removed: {sum(removed_reasons.values())}")
            for reason, count in removed_reasons.items():
                print(f"    - {reason}: {count}")
            print(f"  Texts after validation: {before_merge}")
            print(f"  Texts after merging: {len(processed)}")
            print(f"  Final output: {len(processed)} texts")
        
        return processed

