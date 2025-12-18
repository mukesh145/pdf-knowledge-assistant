import os
import json
import psycopg2
import boto3
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from botocore.exceptions import ClientError
from psycopg2.extras import Json
from .db_connection_manager import get_connection_manager


class Logger:
    """
    A class for logging queries, LLM responses, and state information to the database.
    Also handles uploading drift detection metrics to S3.
    """
    
    def __init__(self):
        """
        Initialize the Logger with database connection manager.
        """
        self._connection_manager = get_connection_manager()
        self._s3_client = None
        self._s3_bucket_name = None
        self._load_s3_config()
    
    def _load_s3_config(self):
        """
        Load S3 bucket configuration from backend_config.yaml.
        """
        try:
            # Try to find config file relative to this module
            config_path = Path(__file__).parent.parent.parent / "configs" / "backend_config.yaml"
            if not config_path.exists():
                # Try alternative path
                config_path = Path("/opt/airflow/configs/backend_config.yaml")
            
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    s3_config = config.get("s3", {})
                    self._s3_bucket_name = s3_config.get("drift_logs_bucket")
        except Exception as e:
            # If config loading fails, S3 upload will be skipped
            print(f"Warning: Could not load S3 config: {e}")
            self._s3_bucket_name = None
    
    def _get_s3_client(self):
        """
        Get or create S3 client using AWS credentials from environment variables.
        
        Returns:
            boto3 S3 client or None if credentials are missing
        """
        if self._s3_client is not None:
            return self._s3_client
        
        # Get AWS credentials from environment variables
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        if not aws_access_key_id or not aws_secret_access_key:
            print("Warning: AWS credentials not found. Skipping S3 upload.")
            return None
        
        try:
            self._s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region
            )
            return self._s3_client
        except Exception as e:
            print(f"Warning: Failed to create S3 client: {e}")
            return None
    
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

    def upload_drift_metrics_to_s3(self, user_id: int, drift_metrics: Dict[str, Any]) -> None:
        """
        Upload drift detection metrics JSON file to S3 bucket.
        
        The file is saved with the following structure:
        - Folder/directory: present day's date (YYYY-MM-DD format)
        - File name: {user_id}_{timestamp}.json
        
        Args:
            user_id: The user ID for the current user
            drift_metrics: Dictionary containing drift detection metrics:
                - context_retrieval_time: Time taken for context retrieval in milliseconds
                - confidence_scores: List of confidence scores for retrieved contexts
                - is_context_sufficient: Boolean indicating if context is sufficient
                - llm_input_tokens_length: Number of input tokens used by LLM
                - llm_output_tokens_length: Number of output tokens used by LLM
                - total_time_for_forward_run: Total time for the entire forward run in milliseconds
        """
        if not self._s3_bucket_name:
            print("Warning: S3 bucket name not configured. Skipping drift metrics upload.")
            return
        
        s3_client = self._get_s3_client()
        if not s3_client:
            return
        
        try:
            # Get current date in YYYY-MM-DD format
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Generate timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            
            # Create file name: {user_id}_{timestamp}.json
            filename = f"{user_id}_{timestamp}.json"
            
            # S3 key: {date}/{filename}
            s3_key = f"{current_date}/{filename}"
            
            # Convert metrics to JSON string
            json_content = json.dumps(drift_metrics, indent=2)
            
            # Upload to S3
            s3_client.put_object(
                Bucket=self._s3_bucket_name,
                Key=s3_key,
                Body=json_content.encode('utf-8'),
                ContentType='application/json'
            )
            
            print(f"Successfully uploaded drift metrics to s3://{self._s3_bucket_name}/{s3_key}")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                print(f"Warning: S3 bucket '{self._s3_bucket_name}' does not exist. Skipping upload.")
            elif error_code == 'AccessDenied':
                print(f"Warning: Access denied to S3 bucket '{self._s3_bucket_name}'. Skipping upload.")
            else:
                print(f"Warning: Error uploading drift metrics to S3: {e}")
        except Exception as e:
            # Don't fail the workflow if S3 upload fails
            print(f"Warning: Failed to upload drift metrics to S3: {e}")
    
    def close_connection(self):
        """
        Close the database connection if it exists.
        """
        self._connection_manager.close_connection()

