"""
Database setup module for creating all required tables.
"""
import os
import psycopg2
from typing import Optional
from .db_connection_manager import get_connection_manager


class DatabaseSetup:
    """Handles creation of all database tables required by the application."""
    
    def __init__(self):
        """Initialize the DatabaseSetup with database connection manager."""
        self._connection_manager = get_connection_manager()
    
    def _get_db_connection(self):
        """Get a database connection using the connection manager (with failover)."""
        return self._connection_manager.get_connection()
    
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
    
    def _create_tables_on_connection(self, conn, db_type: str):
        """
        Create all tables on a specific database connection.
        
        Args:
            conn: Database connection
            db_type: Type of database ('rds' or 'local')
        """
        cursor = conn.cursor()
        
        try:
            # Check and create users table
            users_exists = self._table_exists_on_connection(conn, "users")
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
                print(f"✓ [{db_type.upper()}] Users table already exists (verified)")
            else:
                print(f"✓ [{db_type.upper()}] Users table created")
            
            # Check and create conversation_history table
            conv_exists = self._table_exists_on_connection(conn, "conversation_history")
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
                print(f"✓ [{db_type.upper()}] Conversation_history table already exists (verified)")
            else:
                print(f"✓ [{db_type.upper()}] Conversation_history table created")
            
            # Check and create logs table
            logs_exists = self._table_exists_on_connection(conn, "logs")
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
                print(f"✓ [{db_type.upper()}] Logs table already exists (verified)")
            else:
                print(f"✓ [{db_type.upper()}] Logs table created")
            
            conn.commit()
            
        except psycopg2.Error as e:
            conn.rollback()
            raise Exception(f"Database error while creating tables on {db_type}: {e}")
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating tables on {db_type}: {e}")
        finally:
            cursor.close()
    
    def _table_exists_on_connection(self, conn, table_name: str) -> bool:
        """
        Check if a table exists on a specific connection.
        
        Args:
            conn: Database connection
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
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
        Create all required database tables on both RDS and local databases.
        
        Safe to run on existing databases - uses IF NOT EXISTS to avoid errors.
        Existing tables and data will not be affected.
        """
        # Create tables on the active database (via connection manager)
        try:
            conn = self._get_db_connection()
            db_type = self._connection_manager.get_current_db_type() or 'unknown'
            self._create_tables_on_connection(conn, db_type)
        except Exception as e:
            print(f"⚠ Warning: Failed to create tables on active database: {e}")
        
        # Also create tables on local standby database (always ensure it's set up)
        try:
            standby_conn = self._connection_manager.get_standby_connection()
            self._create_tables_on_connection(standby_conn, 'local')
            standby_conn.close()
        except Exception as e:
            print(f"⚠ Warning: Failed to create tables on local standby database: {e}")
        
        # Try to create tables on RDS if available (for schema sync)
        # This ensures both databases have the same schema
        try:
            import os
            import psycopg2
            db_host = os.getenv("DB_HOST")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME")
            db_user = os.getenv("DB_USER")
            db_password = os.getenv("DB_PASSWORD")
            
            if all([db_host, db_name, db_user, db_password]):
                rds_conn = psycopg2.connect(
                    host=db_host,
                    port=db_port,
                    database=db_name,
                    user=db_user,
                    password=db_password,
                    connect_timeout=3
                )
                rds_conn.autocommit = False
                self._create_tables_on_connection(rds_conn, 'rds')
                rds_conn.close()
        except Exception as e:
            print(f"⚠ Warning: Failed to create tables on RDS (may be unavailable): {e}")
    
    def get_active_db_type(self) -> Optional[str]:
        """
        Get the type of database currently active.
        
        Returns:
            'rds', 'local', or None
        """
        return self._connection_manager.get_current_db_type()
    
    def close_connection(self):
        """Close the database connection if it exists."""
        self._connection_manager.close_connection()

