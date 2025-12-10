"""
Module for fetching PDF files from S3 bucket.
"""
import os
from pathlib import Path
import boto3
from botocore.exceptions import ClientError


def fetch_pdfs_from_s3(bucket_name: str = "knowledge-assistant-project", 
                       s3_prefix: str = "raw-pdf-data/",
                       data_dir: str = "/opt/airflow/data") -> str:
    """
    Fetch all PDF files from S3 bucket and download them to the local data directory.
    
    Args:
        bucket_name: Name of the S3 bucket (default: "knowledge-assistant-project")
        s3_prefix: S3 prefix/path where PDFs are stored (default: "raw-pdf-data/")
        data_dir: Local directory path to save downloaded PDFs (default: "/opt/airflow/data")
    
    Returns:
        str: Path to the data directory containing downloaded PDFs
    
    Raises:
        ValueError: If AWS credentials are missing or bucket doesn't exist
        Exception: For other S3 access errors
    """
    # Get AWS credentials from environment variables
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in environment variables")
    
    # Initialize S3 client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region
    )
    
    data_path = Path(data_dir)
    
    # Create data directory if it doesn't exist
    data_path.mkdir(parents=True, exist_ok=True)
    
    # List all objects in the S3 prefix
    print(f"Connecting to S3 bucket: {bucket_name}")
    print(f"Fetching PDFs from path: {s3_prefix}")
    
    pdf_files = []
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix)
        
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    # Check if the file is a PDF
                    if key.lower().endswith('.pdf'):
                        pdf_files.append(key)
        
        if not pdf_files:
            print("No PDF files found in the specified S3 path")
            return str(data_path)
        
        print(f"\nFound {len(pdf_files)} PDF file(s) in S3:")
        print("-" * 50)
        
        # Download each PDF file
        downloaded_files = []
        for pdf_key in pdf_files:
            # Extract filename from S3 key
            filename = os.path.basename(pdf_key)
            local_path = data_path / filename
            
            print(f"Downloading: {filename}")
            try:
                s3_client.download_file(bucket_name, pdf_key, str(local_path))
                downloaded_files.append(filename)
                print(f"  ✓ Successfully downloaded: {filename}")
            except ClientError as e:
                print(f"  ✗ Error downloading {filename}: {str(e)}")
        
        print("-" * 50)
        print(f"\nDownloaded {len(downloaded_files)} PDF file(s):")
        for filename in downloaded_files:
            print(f"  - {filename}")
        print(f"\nAll PDFs saved to: {data_path}")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            raise ValueError(f"S3 bucket '{bucket_name}' does not exist")
        elif error_code == 'AccessDenied':
            raise ValueError(f"Access denied to S3 bucket '{bucket_name}'. Check your AWS credentials.")
        else:
            raise Exception(f"Error accessing S3: {str(e)}")
    
    return str(data_path)

