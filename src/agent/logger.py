import os
import psycopg2
from datetime import datetime
from typing import Dict, Any
from psycopg2.extras import Json
from .db_connection_manager import get_connection_manager


class Logger:
    """
    A class for logging queries, LLM responses, and state information to the database.
    """
    
    def __init__(self):
        """
        Initialize the Logger with database connection manager.
        """
        self._connection_manager = get_connection_manager()
    
    def _get_db_connection(self):
        """
        Get a database connection using the connection manager (with failover).
        
        Returns:
            psycopg2 connection object
        """
        return self._connection_manager.get_connection()
    
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
        self._connection_manager.close_connection()

