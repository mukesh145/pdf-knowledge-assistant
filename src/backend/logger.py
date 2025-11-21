import os
import psycopg2
from datetime import datetime
from typing import Dict, Any
from psycopg2.extras import Json


class Logger:
    """
    A class for logging queries, LLM responses, and state information to the database.
    """
    
    def __init__(self):
        """
        Initialize the Logger by connecting to the database.
        """
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
    
    def _get_db_connection(self):
        """
        Return the database connection, reconnecting if it's closed.
        
        Returns:
            psycopg2 connection object
        """
        if self._db_connection is None or self._db_connection.closed:
            # Reconnect if connection is closed
            db_host = os.getenv("DB_HOST")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME")
            db_user = os.getenv("DB_USER")
            db_password = os.getenv("DB_PASSWORD")
            
            self._db_connection = psycopg2.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password
            )
            self._db_connection.autocommit = False
        
        return self._db_connection
    
    def save_conversation(self, user_id: int, query: str, llm_response: str) -> None:
        """
        Save the query and LLM response to the 'conversation_history' table.
        
        Args:
            user_id: The user ID
            query: The user's query
            llm_response: The LLM-generated response
        """
        conn = None
        cursor = None
        
        try:
            # Get database connection
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Insert query and response into conversation_history table
            insert_query = """
                INSERT INTO conversation_history (user_id, timestamp, user_query, llm_response)
                VALUES (%s, %s, %s, %s)
            """
            
            timestamp = datetime.now()
            cursor.execute(insert_query, (user_id, timestamp, query, llm_response))
            
            # Commit the transaction
            conn.commit()
            
        except psycopg2.Error as e:
            # Handle database-specific errors
            if conn:
                conn.rollback()
            raise Exception(f"Database error while saving conversation: {e}")
        
        except Exception as e:
            # Handle any other errors
            if conn:
                conn.rollback()
            raise Exception(f"Error saving conversation: {e}")
        
        finally:
            # Clean up cursor (connection is kept for reuse)
            if cursor:
                cursor.close()
    
    def save_logs(self, state: Dict[str, Any]) -> None:
        """
        Save relevant workflow information present in the state to the 'logs' table,
        matching the current schema.

        The 'logs' table has the following columns:
          - u_id (INT)
          - query (TEXT)
          - processed_query (TEXT)
          - context (TEXT)
          - past_memory (TEXT or JSON-encoded string)
          - llm_response (TEXT)

        Args:
            state: The state dictionary containing all workflow information
        """
        conn = None
        cursor = None

        try:
            # Get database connection
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Prepare data according to the logs table schema
            u_id = state.get("u_id")
            query = state.get("query")
            processed_query = state.get("processed_query")
            context_value = state.get("context")
            past_memory = state.get("past_memory", "[]")
            llm_response = state.get("llm_response")

            insert_query = """
                INSERT INTO logs (u_id, query, processed_query, context, past_memory, llm_response)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(
                insert_query,
                (u_id, query, processed_query, context_value, past_memory, llm_response)
            )

            # Commit the transaction
            conn.commit()

        except psycopg2.Error as e:
            # Handle database-specific errors
            if conn:
                conn.rollback()
            raise Exception(f"Database error while saving logs: {e}")

        except Exception as e:
            # Handle any other errors
            if conn:
                conn.rollback()
            raise Exception(f"Error saving logs: {e}")

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

