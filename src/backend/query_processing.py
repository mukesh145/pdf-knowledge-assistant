class QueryProcessor:
    """
    A class for processing query strings with various normalization steps.
    Designed to be extensible for future processing steps.
    """
    
    def __init__(self):
        """Initialize the QueryProcessor."""
        pass
    
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
    
    def process(self, query: str) -> str:
        """
        Apply all processing steps to the input query.
        This method can be extended to include additional processing steps in the future.
        
        Args:
            query: Input query string to process
            
        Returns:
            Processed query string
        """
        if not isinstance(query, str):
            raise TypeError("Input must be a string")
        
        # Step 1: Convert to lowercase
        processed = self.to_lowercase(query)
        
        # Step 2: Normalize whitespace
        processed = self.normalize_whitespace(processed)
        
        # Future processing steps can be added here
        
        return processed

