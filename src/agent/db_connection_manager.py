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
        # Check if we should try RDS again (periodic recovery check)
        current_time = time.time()
        should_check_rds = (
            self._current_db_type == 'local' and 
            (current_time - self._last_rds_check) > self._rds_check_interval
        )
        
        # Try RDS first (or if we're checking for recovery)
        if self._current_db_type != 'local' or should_check_rds:
            if self._try_rds_connection():
                rds_conn = self._create_rds_connection()
                if rds_conn:
                    print("✓ Connected to RDS database")
                    self._last_rds_check = current_time
                    return rds_conn, 'rds'
        
        # Fall back to local PostgreSQL
        print("⚠ RDS unavailable, using local standby database")
        local_conn = self._create_local_connection()
        if local_conn:
            if should_check_rds:
                self._last_rds_check = current_time
            return local_conn, 'local'
        
        # Both failed
        raise Exception(
            "Failed to connect to both RDS and local PostgreSQL. "
            "Please check your database configuration."
        )
    
    def _try_rds_connection(self) -> bool:
        """
        Test if RDS connection is available.
        
        Returns:
            True if RDS is available, False otherwise
        """
        if not all([self._rds_host, self._rds_name, self._rds_user, self._rds_password]):
            return False
        
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
            return True
        except Exception as e:
            print(f"DEBUG: RDS connection test failed: {str(e)}")
            return False
    
    def _create_rds_connection(self) -> Optional[psycopg2.extensions.connection]:
        """
        Create a connection to RDS.
        
        Returns:
            psycopg2 connection object or None if connection fails
        """
        if not all([self._rds_host, self._rds_name, self._rds_user, self._rds_password]):
            return None
        
        try:
            conn = psycopg2.connect(
                host=self._rds_host,
                port=self._rds_port,
                database=self._rds_name,
                user=self._rds_user,
                password=self._rds_password
            )
            conn.autocommit = False
            return conn
        except Exception as e:
            print(f"DEBUG: Failed to create RDS connection: {str(e)}")
            return None
    
    def _create_local_connection(self) -> Optional[psycopg2.extensions.connection]:
        """
        Create a connection to local PostgreSQL.
        
        Returns:
            psycopg2 connection object or None if connection fails
        """
        try:
            conn = psycopg2.connect(
                host=self._standby_host,
                port=self._standby_port,
                database=self._standby_name,
                user=self._standby_user,
                password=self._standby_password
            )
            conn.autocommit = False
            return conn
        except Exception as e:
            print(f"DEBUG: Failed to create local connection: {str(e)}")
            return None
    
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

