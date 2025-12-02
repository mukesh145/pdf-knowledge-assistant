"""
User management for authentication and user operations.
"""
import os
import psycopg2
from typing import Optional, Dict
import warnings
import sys
from pathlib import Path

# Add the src directory to the path to import agent modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from agent.db_connection_manager import get_connection_manager

# Suppress bcrypt version warnings
warnings.filterwarnings("ignore", category=UserWarning, module="passlib")
warnings.filterwarnings("ignore", message=".*bcrypt.*")


class UserManager:
    """Manages user operations including registration, authentication, and retrieval."""
    
    def __init__(self):
        """Initialize the UserManager with database connection manager."""
        self._connection_manager = get_connection_manager()
    
    def _get_db_connection(self):
        """Get a database connection using the connection manager (with failover)."""
        return self._connection_manager.get_connection()
    
    def create_user_table_if_not_exists(self):
        """Create the users table if it doesn't exist."""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        create_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        cursor.execute(create_table_query)
        conn.commit()
        cursor.close()
    
    def register_user(self, email: str, password: str, full_name: Optional[str] = None) -> Dict:
        """Register a new user."""
        from .auth import get_password_hash
        
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if user already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                raise ValueError("User with this email already exists")
            
            # Hash password
            print(f"DEBUG: Hashing password (length: {len(password)} chars, {len(password.encode('utf-8'))} bytes)")
            password_hash = get_password_hash(password)
            print("DEBUG: Password hashed successfully")
            
            # Insert new user
            insert_query = """
            INSERT INTO users (email, password_hash, full_name)
            VALUES (%s, %s, %s)
            RETURNING id, email, full_name, created_at
            """
            cursor.execute(insert_query, (email, password_hash, full_name))
            result = cursor.fetchone()
            conn.commit()
            
            return {
                "id": result[0],
                "email": result[1],
                "full_name": result[2],
                "created_at": result[3].isoformat() if result[3] else None
            }
        except psycopg2.IntegrityError:
            conn.rollback()
            raise ValueError("User with this email already exists")
        except Exception as e:
            conn.rollback()
            raise
        finally:
            cursor.close()
    
    def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate a user and return user data if successful."""
        from .auth import verify_password
        
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Get user by email
            cursor.execute(
                "SELECT id, email, password_hash, full_name FROM users WHERE email = %s",
                (email,)
            )
            result = cursor.fetchone()
            
            if not result:
                return None
            
            user_id, user_email, password_hash, full_name = result
            
            # Verify password
            if not verify_password(password, password_hash):
                return None
            
            return {
                "id": user_id,
                "email": user_email,
                "full_name": full_name
            }
        finally:
            cursor.close()
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute(
                    "SELECT id, email, full_name, created_at FROM users WHERE id = %s",
                    (user_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    print(f"DEBUG: No user found with ID: {user_id}")
                    return None
                
                user_dict = {
                    "id": result[0],
                    "email": result[1],
                    "full_name": result[2],
                    "created_at": result[3].isoformat() if result[3] else None
                }
                print(f"DEBUG: User found: {user_dict.get('email', 'N/A')}")
                return user_dict
            finally:
                cursor.close()
        except psycopg2.Error as e:
            print(f"DEBUG: Database error in get_user_by_id: {type(e).__name__}: {str(e)}")
            raise
        except Exception as e:
            print(f"DEBUG: Unexpected error in get_user_by_id: {type(e).__name__}: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise
    
    def close_connection(self):
        """Close the database connection."""
        self._connection_manager.close_connection()

