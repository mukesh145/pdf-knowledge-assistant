"""
Database connection manager with automatic failover between RDS and local PostgreSQL.
"""
import os
import psycopg2
import time
from typing import Optional, Tuple
from threading import Lock


class DatabaseConnectionManager:
    """
    Manages database connections with automatic failover from RDS to local PostgreSQL.
    
    Tries to connect to RDS first. If RDS is unavailable, automatically falls back
    to a local PostgreSQL instance running in the same container.
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        self._connection = None
        self._current_db_type = None  # 'rds' or 'local'
        self._last_rds_check = 0
        self._rds_check_interval = 60  # Check RDS every 60 seconds for recovery
        self._lock = Lock()
        
        # RDS connection parameters
        self._rds_host = os.getenv("DB_HOST")
        self._rds_port = os.getenv("DB_PORT", "5432")
        self._rds_name = os.getenv("DB_NAME")
        self._rds_user = os.getenv("DB_USER")
        self._rds_password = os.getenv("DB_PASSWORD")
        
        # Standby (local) connection parameters
        self._standby_host = os.getenv("DB_STANDBY_HOST", "localhost")
        self._standby_port = os.getenv("DB_STANDBY_PORT", "5432")
        self._standby_name = os.getenv("DB_STANDBY_NAME", "app_standby")
        self._standby_user = os.getenv("DB_STANDBY_USER", "app_user")
        self._standby_password = os.getenv("DB_STANDBY_PASSWORD", "app_password")
    
    def get_connection(self):
        """
        Get a working database connection.
        
        Tries RDS first, falls back to local PostgreSQL if RDS is unavailable.
        Periodically checks if RDS has recovered.
        
        Returns:
            psycopg2 connection object
            
        Raises:
            ValueError: If connection parameters are missing
            Exception: If both RDS and local connections fail
        """
        with self._lock:
            # Check if we have a valid cached connection
            if self._connection is not None and not self._connection.closed:
                try:
                    # Test if connection is still alive
                    cursor = self._connection.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    return self._connection
                except (psycopg2.OperationalError, psycopg2.InterfaceError):
                    # Connection is dead, reset it
                    print("DEBUG: Cached database connection is dead, creating new connection")
                    try:
                        self._connection.close()
                    except:
                        pass
                    self._connection = None
                    self._current_db_type = None
            
            # Try to get a new connection
            connection, db_type = self._get_working_connection()
            self._connection = connection
            self._current_db_type = db_type
            return connection
    
    def _get_working_connection(self) -> Tuple[psycopg2.extensions.connection, str]:
        """
        Get a working connection, trying RDS first, then local.
        
        Returns:
            Tuple of (connection, db_type) where db_type is 'rds' or 'local'
            
        Raises:
            ValueError: If connection parameters are missing
            Exception: If both connections fail
        """
        rds_error = None
        local_error = None
        
        # Check if we should try RDS again (periodic recovery check)
        current_time = time.time()
        should_check_rds = (
            self._current_db_type == 'local' and 
            (current_time - self._last_rds_check) > self._rds_check_interval
        )
        
        # Try RDS first (or if we're checking for recovery)
        if self._current_db_type != 'local' or should_check_rds:
            rds_test_result, rds_test_error = self._try_rds_connection_with_error()
            if rds_test_result:
                rds_conn, rds_conn_error = self._create_rds_connection_with_error()
                if rds_conn:
                    print("✓ Connected to RDS database")
                    self._last_rds_check = current_time
                    return rds_conn, 'rds'
                else:
                    rds_error = f"RDS connection test passed but connection creation failed: {rds_conn_error or 'Unknown error'}"
            else:
                rds_error = f"RDS connection test failed: {rds_test_error or 'Connection timeout or unreachable'}"
        
        # Fall back to local PostgreSQL
        print("⚠ RDS unavailable, attempting to use local standby database")
        local_conn, local_error = self._create_local_connection_with_error()
        if local_conn:
            if should_check_rds:
                self._last_rds_check = current_time
            print("✓ Connected to local standby database")
            return local_conn, 'local'
        
        # Both failed - provide detailed error message
        error_parts = ["Failed to connect to both RDS and local PostgreSQL."]
        if rds_error:
            error_parts.append(f"RDS error: {rds_error}")
        if local_error:
            error_parts.append(f"Local PostgreSQL error: {local_error}")
        error_parts.append("Please check your database configuration.")
        
        raise Exception(" ".join(error_parts))
    
    def _try_rds_connection(self) -> bool:
        """
        Test if RDS connection is available.
        
        Returns:
            True if RDS is available, False otherwise
        """
        result, _ = self._try_rds_connection_with_error()
        return result
    
    def _try_rds_connection_with_error(self) -> Tuple[bool, Optional[str]]:
        """
        Test if RDS connection is available and return error details.
        
        Returns:
            Tuple of (is_available, error_message) where error_message is None on success
        """
        if not all([self._rds_host, self._rds_name, self._rds_user, self._rds_password]):
            return False, "Missing RDS connection parameters (DB_HOST, DB_NAME, DB_USER, or DB_PASSWORD)"
        
        try:
            test_conn = psycopg2.connect(
                host=self._rds_host,
                port=self._rds_port,
                database=self._rds_name,
                user=self._rds_user,
                password=self._rds_password,
                connect_timeout=3  # Short timeout for quick failover
            )
            test_conn.close()
            return True, None
        except psycopg2.OperationalError as e:
            error_msg = f"Operational error: {str(e)}"
            print(f"DEBUG: RDS connection test failed - {error_msg}")
            return False, error_msg
        except psycopg2.Error as e:
            error_msg = f"PostgreSQL error: {str(e)}"
            print(f"DEBUG: RDS connection test failed - {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            print(f"DEBUG: RDS connection test failed - {error_msg}")
            return False, error_msg
    
    def _create_rds_connection(self) -> Optional[psycopg2.extensions.connection]:
        """
        Create a connection to RDS.
        
        Returns:
            psycopg2 connection object or None if connection fails
        """
        conn, _ = self._create_rds_connection_with_error()
        return conn
    
    def _create_rds_connection_with_error(self) -> Tuple[Optional[psycopg2.extensions.connection], Optional[str]]:
        """
        Create a connection to RDS and return error details.
        
        Returns:
            Tuple of (connection, error_message) where error_message is None on success
        """
        if not all([self._rds_host, self._rds_name, self._rds_user, self._rds_password]):
            return None, "Missing RDS connection parameters (DB_HOST, DB_NAME, DB_USER, or DB_PASSWORD)"
        
        try:
            conn = psycopg2.connect(
                host=self._rds_host,
                port=self._rds_port,
                database=self._rds_name,
                user=self._rds_user,
                password=self._rds_password
            )
            conn.autocommit = False
            return conn, None
        except psycopg2.OperationalError as e:
            error_msg = f"Operational error: {str(e)}"
            print(f"DEBUG: Failed to create RDS connection - {error_msg}")
            return None, error_msg
        except psycopg2.Error as e:
            error_msg = f"PostgreSQL error: {str(e)}"
            print(f"DEBUG: Failed to create RDS connection - {error_msg}")
            return None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            print(f"DEBUG: Failed to create RDS connection - {error_msg}")
            return None, error_msg
    
    def _create_local_connection(self) -> Optional[psycopg2.extensions.connection]:
        """
        Create a connection to local PostgreSQL.
        
        Returns:
            psycopg2 connection object or None if connection fails
        """
        conn, _ = self._create_local_connection_with_error()
        return conn
    
    def _create_local_connection_with_error(self) -> Tuple[Optional[psycopg2.extensions.connection], Optional[str]]:
        """
        Create a connection to local PostgreSQL and return error details.
        
        Returns:
            Tuple of (connection, error_message) where error_message is None on success
        """
        try:
            print(f"DEBUG: Attempting local PostgreSQL connection: host={self._standby_host}, port={self._standby_port}, db={self._standby_name}, user={self._standby_user}")
            conn = psycopg2.connect(
                host=self._standby_host,
                port=self._standby_port,
                database=self._standby_name,
                user=self._standby_user,
                password=self._standby_password,
                connect_timeout=5  # Add timeout for local connection too
            )
            conn.autocommit = False
            print(f"DEBUG: Successfully connected to local PostgreSQL")
            return conn, None
        except psycopg2.OperationalError as e:
            error_msg = f"Operational error: {str(e)}"
            print(f"DEBUG: Failed to create local connection - {error_msg}")
            return None, error_msg
        except psycopg2.Error as e:
            error_msg = f"PostgreSQL error: {str(e)}"
            print(f"DEBUG: Failed to create local connection - {error_msg}")
            return None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            print(f"DEBUG: Failed to create local connection - {error_msg}")
            return None, error_msg
    
    def get_current_db_type(self) -> Optional[str]:
        """
        Get the type of database currently in use.
        
        Returns:
            'rds', 'local', or None if no connection exists
        """
        return self._current_db_type
    
    def test_connection(self, host: str, port: str, db: str, user: str, password: str) -> bool:
        """
        Test a database connection.
        
        Args:
            host: Database host
            port: Database port
            db: Database name
            user: Database user
            password: Database password
            
        Returns:
            True if connection succeeds, False otherwise
        """
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=db,
                user=user,
                password=password,
                connect_timeout=3
            )
            conn.close()
            return True
        except Exception:
            return False
    
    def close_connection(self):
        """Close the current database connection."""
        with self._lock:
            if self._connection is not None and not self._connection.closed:
                try:
                    self._connection.close()
                except:
                    pass
                self._connection = None
                self._current_db_type = None
    
    def get_standby_connection(self):
        """
        Get a connection specifically to the standby (local) database.
        Useful for schema initialization.
        
        Returns:
            psycopg2 connection object to local database
        """
        conn = self._create_local_connection()
        if not conn:
            raise Exception("Failed to connect to local standby database")
        return conn


# Global instance
_connection_manager = None


def get_connection_manager() -> DatabaseConnectionManager:
    """
    Get the global database connection manager instance.
    
    Returns:
        DatabaseConnectionManager instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = DatabaseConnectionManager()
    return _connection_manager

