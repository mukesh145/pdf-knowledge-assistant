"""
Database setup module for creating all required tables.
"""
import os
import psycopg2
from typing import Optional


class DatabaseSetup:
    """Handles creation of all database tables required by the application."""
    
    def __init__(self):
        """Initialize the DatabaseSetup with database connection parameters."""
        self._db_connection = None
    
    def _get_db_connection(self):
        """Create and return a database connection using environment variables."""
        if self._db_connection is None or self._db_connection.closed:
            db_host = os.getenv("DB_HOST")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME")
            db_user = os.getenv("DB_USER")
            db_password = os.getenv("DB_PASSWORD")
            
            if not all([db_host, db_name, db_user, db_password]):
                raise ValueError(
                    "Database connection parameters are missing. "
                    "Please set DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD environment variables."
                )
            
            self._db_connection = psycopg2.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password
            )
            self._db_connection.autocommit = False
        
        return self._db_connection
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, (table_name,))
            exists = cursor.fetchone()[0]
            return exists
        finally:
            cursor.close()
    
    def create_all_tables(self):
        """
        Create all required database tables if they don't exist.
        
        Safe to run on existing databases - uses IF NOT EXISTS to avoid errors.
        Existing tables and data will not be affected.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check and create users table
            users_exists = self.table_exists("users")
            create_users_table = """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            cursor.execute(create_users_table)
            if users_exists:
                print("✓ Users table already exists (verified)")
            else:
                print("✓ Users table created")
            
            # Check and create conversation_history table
            conv_exists = self.table_exists("conversation_history")
            create_conversation_history_table = """
            CREATE TABLE IF NOT EXISTS conversation_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                user_query TEXT NOT NULL,
                llm_response TEXT NOT NULL
            );
            """
            cursor.execute(create_conversation_history_table)
            if conv_exists:
                print("✓ Conversation_history table already exists (verified)")
            else:
                print("✓ Conversation_history table created")
            
            # Check and create logs table
            logs_exists = self.table_exists("logs")
            create_logs_table = """
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                u_id INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                query TEXT,
                processed_query TEXT,
                context TEXT,
                past_memory TEXT,
                llm_response TEXT
            );
            """
            cursor.execute(create_logs_table)
            if logs_exists:
                print("✓ Logs table already exists (verified)")
            else:
                print("✓ Logs table created")
            
            conn.commit()
            
        except psycopg2.Error as e:
            conn.rollback()
            raise Exception(f"Database error while creating tables: {e}")
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating tables: {e}")
        finally:
            cursor.close()
    
    def close_connection(self):
        """Close the database connection if it exists."""
        if self._db_connection and not self._db_connection.closed:
            self._db_connection.close()
            self._db_connection = None

