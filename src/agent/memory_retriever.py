import os
import psycopg2


class MemoryRetriever:
    """
    A class for retrieving past conversation history from RDS PostgreSQL database.
    """
    
    def __init__(self):
        """
        Initialize the MemoryRetriever by setting up database connection parameters.
        """
        self._db_connection = None
    
    def _get_db_connection(self):
        """
        Create and return a database connection using environment variables.
        
        Returns:
            psycopg2 connection object
        """
        if self._db_connection is None or self._db_connection.closed:
            # Get database configuration from environment variables
            db_host = os.getenv("DB_HOST")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME")
            db_user = os.getenv("DB_USER")
            db_password = os.getenv("DB_PASSWORD")
            
            # Validate required environment variables
            if not all([db_host, db_name, db_user, db_password]):
                raise ValueError(
                    "Database connection parameters are missing. "
                    "Please set DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD environment variables."
                )
            
            # Create database connection
            self._db_connection = psycopg2.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password
            )
            self._db_connection.autocommit = False
        
        return self._db_connection
    
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
        if self._db_connection and not self._db_connection.closed:
            self._db_connection.close()
            self._db_connection = None

