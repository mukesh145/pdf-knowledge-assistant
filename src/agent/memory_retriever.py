import os
import psycopg2
from .db_connection_manager import get_connection_manager


class MemoryRetriever:
    """
    A class for retrieving past conversation history from database (RDS or local standby).
    """
    
    def __init__(self):
        """
        Initialize the MemoryRetriever with database connection manager.
        """
        self._connection_manager = get_connection_manager()
    
    def _get_db_connection(self):
        """
        Get a database connection using the connection manager (with failover).
        
        Returns:
            psycopg2 connection object
        """
        return self._connection_manager.get_connection()
    
    def get_past_conversations(self, user_id: int) -> str:
        """
        Fetches the past 3 conversations for a particular user ID from the RDS DB
        and converts them into a single string.
        
        Args:
            user_id: The user ID to fetch conversations for
            
        Returns:
            A single string containing the past 3 conversations formatted as:
            "User: [query]\nAssistant: [response]\n\n" for each conversation
        """
        conn = None
        cursor = None
        
        try:
            # Get database connection
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Query to fetch the past 3 conversations for the user
            # Ordered by timestamp DESC to get the most recent first
            query = """
                SELECT user_query, llm_response, timestamp
                FROM conversation_history
                WHERE user_id = %s
                ORDER BY timestamp DESC
                LIMIT 3;
            """
            
            # Execute the query
            cursor.execute(query, (user_id,))
            
            # Fetch all results
            results = cursor.fetchall()
            
            # Convert results to a single string
            conversation_strings = []
            for user_query, llm_response, timestamp in results:
                # Format each conversation as a readable string
                conversation_str = f"User: {user_query}\nAssistant: {llm_response}"
                conversation_strings.append(conversation_str)
            
            # Join all conversations with double newlines for separation
            combined_string = "\n\n".join(conversation_strings)
            
            return combined_string
            
        except psycopg2.Error as e:
            # Handle database-specific errors
            if conn:
                conn.rollback()
            raise Exception(f"Database error while fetching conversations: {e}")
        
        except Exception as e:
            # Handle any other errors
            if conn:
                conn.rollback()
            raise Exception(f"Error fetching past conversations: {e}")
        
        finally:
            # Clean up cursor (connection is kept for reuse)
            if cursor:
                cursor.close()
    
    def close_connection(self):
        """
        Close the database connection if it exists.
        """
        self._connection_manager.close_connection()

