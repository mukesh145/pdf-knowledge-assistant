# dags/ml_pipeline.py
from airflow.decorators import dag, task
from datetime import datetime, timedelta
import sys
from pathlib import Path



default_args = {
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

@dag(
    start_date=datetime(2025, 10, 10),
    schedule=None,  
    catchup=False,
    tags=["ml"],
    default_args=default_args,
)
def data_ingestion_pipeline():
    @task
    def fetch_data():
        """
        Fetch all PDF files from S3 bucket knowledge-assistant-bucket/raw-pdf-data/
        and download them to the local data directory.
        
        Returns:
            str: Path to the data directory containing downloaded PDFs
        """
        src_path = Path("/opt/airflow/src") if Path("/opt/airflow/src").exists() else Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))

        from knowledge.fetch_data import fetch_pdfs_from_s3
        
        return fetch_pdfs_from_s3()
    
    @task
    def extract_data(data_dir_path):
        """
        Extract text content from all PDF files in the data directory.
        Uses Extractor from knowledge_extractor.py which internally uses PostProcessor.
        
        Args:
            data_dir_path: Path to the data directory containing PDF files
            
        Returns:
            str: Path to the directory containing extracted data (JSON files)
        """
        import json
        
        src_path = Path("/opt/airflow/src") if Path("/opt/airflow/src").exists() else Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))
        
        from knowledge.knowledge_extractor import Extractor
        
        data_dir = Path(data_dir_path)
        if not data_dir.exists():
            raise ValueError(f"Data directory does not exist: {data_dir_path}")
        
        # Create output directory for extracted data
        extracted_dir = data_dir / "extracted"
        extracted_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all PDF files in the data directory
        pdf_files = list(data_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"No PDF files found in {data_dir}")
            return str(extracted_dir)
        
        print(f"Found {len(pdf_files)} PDF file(s) to extract")
        
        # Initialize extractor with post-processing enabled
        extractor = Extractor(enable_post_processing=True, verbose=True)
        
        # Extract text from each PDF
        extraction_results = {}
        for pdf_file in pdf_files:
            print(f"\nExtracting from: {pdf_file.name}")
            try:
                # Extract text from PDF
                extracted_texts = extractor.extract(str(pdf_file), preserve_structure=True)
                
                # Store extraction results
                extraction_results[pdf_file.name] = {
                    "pdf_path": str(pdf_file),
                    "extracted_texts": extracted_texts,
                    "num_chunks": len(extracted_texts),
                    "status": "success"
                }
                
                print(f"  ✓ Extracted {len(extracted_texts)} text chunks from {pdf_file.name}")
                
            except Exception as e:
                print(f"  ✗ Error extracting from {pdf_file.name}: {str(e)}")
                extraction_results[pdf_file.name] = {
                    "pdf_path": str(pdf_file),
                    "extracted_texts": [],
                    "num_chunks": 0,
                    "status": "error",
                    "error": str(e)
                }
        
        # Save extraction results to JSON file
        output_file = extracted_dir / "extracted_data.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(extraction_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Extraction complete. Results saved to: {output_file}")
        print(f"  Total PDFs processed: {len(pdf_files)}")
        print(f"  Successful extractions: {sum(1 for r in extraction_results.values() if r['status'] == 'success')}")
        print(f"  Failed extractions: {sum(1 for r in extraction_results.values() if r['status'] == 'error')}")
        
        return str(extracted_dir)
  
    
    @task
    def chunk_data(extracted_dir_path):
        """
        Chunk extracted text data into segments with overlap.
        Uses Chunker from chunker.py to process extracted texts.
        
        Args:
            extracted_dir_path: Path to the directory containing extracted data (JSON file)
            
        Returns:
            str: Path to the directory containing chunked data (JSON files)
        """
        import json
        
        src_path = Path("/opt/airflow/src") if Path("/opt/airflow/src").exists() else Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))
        
        from knowledge.chunker import Chunker
        
        extracted_dir = Path(extracted_dir_path)
        if not extracted_dir.exists():
            raise ValueError(f"Extracted data directory does not exist: {extracted_dir_path}")
        
        # Read extracted data
        extracted_file = extracted_dir / "extracted_data.json"
        if not extracted_file.exists():
            raise ValueError(f"Extracted data file not found: {extracted_file}")
        
        with open(extracted_file, 'r', encoding='utf-8') as f:
            extraction_results = json.load(f)
        
        # Create output directory for chunked data
        # Get parent data directory and create chunked subdirectory
        data_dir = extracted_dir.parent
        chunked_dir = data_dir / "chunked"
        chunked_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize chunker with default parameters
        chunker = Chunker()
        chunk_size = 300  # words per chunk
        overlap = 50      # overlapping words
        
        print(f"Chunking with parameters: chunk_size={chunk_size}, overlap={overlap}")
        
        # Chunk data for each PDF
        chunked_results = {}
        total_chunks = 0
        
        for pdf_name, pdf_data in extraction_results.items():
            print(f"\nChunking data from: {pdf_name}")
            
            if pdf_data.get('status') != 'success':
                print(f"  ⚠ Skipping {pdf_name} (status: {pdf_data.get('status')})")
                chunked_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "chunks": [],
                    "num_chunks": 0,
                    "status": "skipped",
                    "reason": pdf_data.get('status', 'unknown')
                }
                continue
            
            extracted_texts = pdf_data.get('extracted_texts', [])
            if not extracted_texts:
                print(f"  ⚠ No extracted texts found for {pdf_name}")
                chunked_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "chunks": [],
                    "num_chunks": 0,
                    "status": "skipped",
                    "reason": "no extracted texts"
                }
                continue
            
            try:
                # Chunk the extracted texts using chunk_paragraphs
                # This combines all paragraphs and chunks them with overlap
                chunks = chunker.chunk_paragraphs(
                    extracted_texts,
                    chunk_size=chunk_size,
                    overlap=overlap
                )
                
                chunked_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "chunks": chunks,
                    "num_chunks": len(chunks),
                    "chunk_size": chunk_size,
                    "overlap": overlap,
                    "original_extracted_count": len(extracted_texts),
                    "status": "success"
                }
                
                total_chunks += len(chunks)
                print(f"  ✓ Created {len(chunks)} chunks from {len(extracted_texts)} extracted texts")
                
            except Exception as e:
                print(f"  ✗ Error chunking {pdf_name}: {str(e)}")
                chunked_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "chunks": [],
                    "num_chunks": 0,
                    "status": "error",
                    "error": str(e)
                }
        
        # Save chunked results to JSON file
        output_file = chunked_dir / "chunked_data.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunked_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Chunking complete. Results saved to: {output_file}")
        print(f"  Total PDFs processed: {len(extraction_results)}")
        print(f"  Successful chunking: {sum(1 for r in chunked_results.values() if r['status'] == 'success')}")
        print(f"  Skipped: {sum(1 for r in chunked_results.values() if r['status'] == 'skipped')}")
        print(f"  Errors: {sum(1 for r in chunked_results.values() if r['status'] == 'error')}")
        print(f"  Total chunks created: {total_chunks}")
        
        return str(chunked_dir)
    
    @task
    def convert_to_embeddings(chunked_dir_path):
        """
        Convert chunked text data to embeddings.
        Uses QueryProcessor to process chunks and ContextRetriever to generate embeddings.
        
        Args:
            chunked_dir_path: Path to the directory containing chunked data (JSON file)
            
        Returns:
            str: Path to the directory containing embeddings data (JSON files)
        """
        import json
        import uuid
        
        src_path = Path("/opt/airflow/src") if Path("/opt/airflow/src").exists() else Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))
        
        from agent.query_processing import QueryProcessor
        from agent.context_retriever import ContextRetriever
        
        chunked_dir = Path(chunked_dir_path)
        if not chunked_dir.exists():
            raise ValueError(f"Chunked data directory does not exist: {chunked_dir_path}")
        
        # Read chunked data
        chunked_file = chunked_dir / "chunked_data.json"
        if not chunked_file.exists():
            raise ValueError(f"Chunked data file not found: {chunked_file}")
        
        with open(chunked_file, 'r', encoding='utf-8') as f:
            chunked_results = json.load(f)
        
        # Create output directory for embeddings data
        # Get parent data directory and create embeddings subdirectory
        data_dir = chunked_dir.parent
        embeddings_dir = data_dir / "embeddings"
        embeddings_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize processors
        query_processor = QueryProcessor()
        context_retriever = ContextRetriever()
        
        batch_size = 100  # Process embeddings in batches to avoid memory issues
        
        print(f"Converting chunks to embeddings (batch_size={batch_size})...")
        
        # Process embeddings for each PDF
        embeddings_results = {}
        total_embeddings = 0
        
        for pdf_name, pdf_data in chunked_results.items():
            print(f"\nProcessing embeddings for: {pdf_name}")
            
            if pdf_data.get('status') != 'success':
                print(f"  ⚠ Skipping {pdf_name} (status: {pdf_data.get('status')})")
                embeddings_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "embeddings": [],
                    "num_embeddings": 0,
                    "status": "skipped",
                    "reason": pdf_data.get('status', 'unknown')
                }
                continue
            
            chunks = pdf_data.get('chunks', [])
            if not chunks:
                print(f"  ⚠ No chunks found for {pdf_name}")
                embeddings_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "embeddings": [],
                    "num_embeddings": 0,
                    "status": "skipped",
                    "reason": "no chunks"
                }
                continue
            
            try:
                # Step 1: Process chunks using QueryProcessor
                print(f"  Processing {len(chunks)} chunks...")
                processed_chunks = []
                for chunk in chunks:
                    processed_chunk = query_processor.process(chunk)
                    processed_chunks.append(processed_chunk)
                
                # Step 2: Convert to embeddings in batches
                print(f"  Converting to embeddings...")
                pdf_embeddings = []
                num_batches = (len(processed_chunks) + batch_size - 1) // batch_size
                
                for batch_idx in range(num_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min((batch_idx + 1) * batch_size, len(processed_chunks))
                    batch_chunks = processed_chunks[start_idx:end_idx]
                    batch_original = chunks[start_idx:end_idx]  # Keep original for storage
                    
                    # Convert batch to embeddings
                    batch_embeddings = context_retriever.convert_batch_to_embeddings(batch_chunks)
                    
                    # Ensure embeddings is a 2D numpy array
                    if batch_embeddings.ndim == 1:
                        batch_embeddings = batch_embeddings.reshape(1, -1)
                    
                    # Store embeddings with metadata
                    for i in range(len(batch_chunks)):
                        # Get embedding for this chunk
                        if batch_embeddings.ndim == 2:
                            embedding = batch_embeddings[i]
                        else:
                            embedding = batch_embeddings
                        
                        # Generate unique ID for each vector
                        vector_id = str(uuid.uuid4())
                        
                        pdf_embeddings.append({
                            "id": vector_id,
                            "chunk_index": start_idx + i,
                            "embedding": embedding.tolist(),  # Convert numpy array to list
                            "original_text": batch_original[i],
                            "processed_text": batch_chunks[i]
                        })
                    
                    if (batch_idx + 1) % 10 == 0 or (batch_idx + 1) == num_batches:
                        print(f"    Processed batch {batch_idx + 1}/{num_batches}")
                
                embeddings_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "embeddings": pdf_embeddings,
                    "num_embeddings": len(pdf_embeddings),
                    "chunk_size": pdf_data.get("chunk_size", 300),
                    "overlap": pdf_data.get("overlap", 50),
                    "status": "success"
                }
                
                total_embeddings += len(pdf_embeddings)
                print(f"  ✓ Created {len(pdf_embeddings)} embeddings from {len(chunks)} chunks")
                
            except Exception as e:
                print(f"  ✗ Error creating embeddings for {pdf_name}: {str(e)}")
                embeddings_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "embeddings": [],
                    "num_embeddings": 0,
                    "status": "error",
                    "error": str(e)
                }
        
        # Save embeddings results to JSON file
        output_file = embeddings_dir / "embeddings_data.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(embeddings_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Embedding conversion complete. Results saved to: {output_file}")
        print(f"  Total PDFs processed: {len(chunked_results)}")
        print(f"  Successful conversions: {sum(1 for r in embeddings_results.values() if r['status'] == 'success')}")
        print(f"  Skipped: {sum(1 for r in embeddings_results.values() if r['status'] == 'skipped')}")
        print(f"  Errors: {sum(1 for r in embeddings_results.values() if r['status'] == 'error')}")
        print(f"  Total embeddings created: {total_embeddings}")
        
        return str(embeddings_dir)
    
    @task
    def upsert_to_pinecone(embeddings_dir_path):
        """
        Upsert embeddings to Pinecone vector database.
        Reads embeddings data and uploads vectors to Pinecone in batches.
        
        Args:
            embeddings_dir_path: Path to the directory containing embeddings data (JSON file)
            
        Returns:
            str: Path to the directory containing upsert results (JSON files)
        """
        import json
        import os
        
        src_path = Path("/opt/airflow/src") if Path("/opt/airflow/src").exists() else Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))
        
        from pinecone import Pinecone, ServerlessSpec
        
        embeddings_dir = Path(embeddings_dir_path)
        if not embeddings_dir.exists():
            raise ValueError(f"Embeddings data directory does not exist: {embeddings_dir_path}")
        
        # Read embeddings data
        embeddings_file = embeddings_dir / "embeddings_data.json"
        if not embeddings_file.exists():
            raise ValueError(f"Embeddings data file not found: {embeddings_file}")
        
        with open(embeddings_file, 'r', encoding='utf-8') as f:
            embeddings_results = json.load(f)
        
        # Create output directory for upsert results
        # Get parent data directory and create upserted subdirectory
        data_dir = embeddings_dir.parent
        upserted_dir = data_dir / "upserted"
        upserted_dir.mkdir(parents=True, exist_ok=True)
        
        # Get Pinecone configuration from environment variables
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        pinecone_index_name = os.getenv("PINECONE_INDEX_NAME", "pdf-knowledge-base")
        pinecone_environment = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
        
        if not pinecone_api_key:
            raise ValueError(
                "PINECONE_API_KEY environment variable is not set. "
                "Please set it before upserting to Pinecone."
            )
        
        # Initialize Pinecone client
        print(f"Initializing Pinecone connection...")
        pc = Pinecone(api_key=pinecone_api_key)
        
        # Check if index exists, create if it doesn't
        if pinecone_index_name not in pc.list_indexes().names():
            print(f"Creating new Pinecone index: {pinecone_index_name}")
            pc.create_index(
                name=pinecone_index_name,
                dimension=1024,  # BAAI/bge-m3 model dimension
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=pinecone_environment
                )
            )
            print(f"✓ Created new index: {pinecone_index_name}")
        else:
            print(f"✓ Index {pinecone_index_name} already exists")
        
        # Connect to the index
        index = pc.Index(pinecone_index_name)
        print(f"✓ Connected to index: {pinecone_index_name}")
        
        batch_size = 100  # Upsert in batches to avoid memory issues
        
        print(f"\nUpserting embeddings to Pinecone (batch_size={batch_size})...")
        
        # Upsert embeddings for each PDF
        upsert_results = {}
        total_upserted = 0
        
        for pdf_name, pdf_data in embeddings_results.items():
            print(f"\nUpserting embeddings for: {pdf_name}")
            
            if pdf_data.get('status') != 'success':
                print(f"  ⚠ Skipping {pdf_name} (status: {pdf_data.get('status')})")
                upsert_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "num_upserted": 0,
                    "status": "skipped",
                    "reason": pdf_data.get('status', 'unknown')
                }
                continue
            
            embeddings = pdf_data.get('embeddings', [])
            if not embeddings:
                print(f"  ⚠ No embeddings found for {pdf_name}")
                upsert_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "num_upserted": 0,
                    "status": "skipped",
                    "reason": "no embeddings"
                }
                continue
            
            try:
                # Prepare vectors for Pinecone in batches
                num_batches = (len(embeddings) + batch_size - 1) // batch_size
                pdf_upserted = 0
                
                for batch_idx in range(num_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min((batch_idx + 1) * batch_size, len(embeddings))
                    batch_embeddings = embeddings[start_idx:end_idx]
                    
                    # Prepare vectors in Pinecone format
                    vectors_to_upload = []
                    for emb_data in batch_embeddings:
                        vector_id = emb_data.get('id')
                        embedding_values = emb_data.get('embedding')
                        chunk_index = emb_data.get('chunk_index', 0)
                        original_text = emb_data.get('original_text', '')
                        processed_text = emb_data.get('processed_text', '')
                        
                        # Prepare metadata
                        metadata = {
                            "pdf_name": pdf_name,
                            "chunk_index": chunk_index,
                            "text": original_text,  # Store original text for retrieval
                            "processed_text": processed_text  # Store processed text for reference
                        }
                        
                        vectors_to_upload.append({
                            "id": vector_id,
                            "values": embedding_values,  # Already a list from embeddings_data.json
                            "metadata": metadata
                        })
                    
                    # Upsert batch to Pinecone
                    print(f"  Uploading batch {batch_idx + 1}/{num_batches} ({len(vectors_to_upload)} vectors)...")
                    index.upsert(vectors=vectors_to_upload)
                    pdf_upserted += len(vectors_to_upload)
                    
                    if (batch_idx + 1) % 10 == 0 or (batch_idx + 1) == num_batches:
                        print(f"    Uploaded {pdf_upserted} vectors so far...")
                
                upsert_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "num_upserted": pdf_upserted,
                    "status": "success"
                }
                
                total_upserted += pdf_upserted
                print(f"  ✓ Successfully upserted {pdf_upserted} vectors for {pdf_name}")
                
            except Exception as e:
                print(f"  ✗ Error upserting {pdf_name}: {str(e)}")
                upsert_results[pdf_name] = {
                    "pdf_path": pdf_data.get("pdf_path", ""),
                    "num_upserted": 0,
                    "status": "error",
                    "error": str(e)
                }
        
        # Save upsert results to JSON file
        output_file = upserted_dir / "upsert_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(upsert_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Pinecone upsert complete. Results saved to: {output_file}")
        print(f"  Total PDFs processed: {len(embeddings_results)}")
        print(f"  Successful upserts: {sum(1 for r in upsert_results.values() if r['status'] == 'success')}")
        print(f"  Skipped: {sum(1 for r in upsert_results.values() if r['status'] == 'skipped')}")
        print(f"  Errors: {sum(1 for r in upsert_results.values() if r['status'] == 'error')}")
        print(f"  Total vectors upserted: {total_upserted}")
        
        return str(upserted_dir)
    
    @task
    def clean_and_move_data(upserted_dir_path):
        """
        Move processed PDF files from raw-pdf-data/ to processed-pdf-data/ in S3.
        This marks the PDFs as processed after successful ingestion.
        
        Args:
            upserted_dir_path: Path to the directory containing upsert results (not directly used,
                              but helps track which PDFs were processed)
            
        Returns:
            str: Summary message indicating completion
        """
        import os
        import boto3
        from botocore.exceptions import ClientError
        
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
        
        # Configuration
        bucket_name = os.getenv("S3_BUCKET_NAME", "knowledge-assistant-project")
        source_prefix = "raw-pdf-data/"
        destination_prefix = "processed-pdf-data/"
        
        print(f"Connecting to S3 bucket: {bucket_name}")
        print(f"Moving PDFs from: {source_prefix} to {destination_prefix}")
        
        # List all PDF files in the source prefix
        pdf_files = []
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=source_prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        # Check if the file is a PDF
                        if key.lower().endswith('.pdf'):
                            pdf_files.append(key)
            
            if not pdf_files:
                print("No PDF files found in raw-pdf-data/ to move")
                return "No PDFs to move"
            
            print(f"\nFound {len(pdf_files)} PDF file(s) to move:")
            print("-" * 50)
            
            # Move each PDF file (copy to destination, then delete from source)
            moved_files = []
            failed_files = []
            
            for source_key in pdf_files:
                # Extract filename from source key
                filename = os.path.basename(source_key)
                destination_key = destination_prefix + filename
                
                print(f"Moving: {filename}")
                try:
                    # Copy object to destination
                    copy_source = {
                        'Bucket': bucket_name,
                        'Key': source_key
                    }
                    s3_client.copy_object(
                        CopySource=copy_source,
                        Bucket=bucket_name,
                        Key=destination_key
                    )
                    print(f"  ✓ Copied to {destination_key}")
                    
                    # Delete object from source
                    s3_client.delete_object(
                        Bucket=bucket_name,
                        Key=source_key
                    )
                    print(f"  ✓ Deleted from {source_key}")
                    
                    moved_files.append(filename)
                    
                except ClientError as e:
                    error_msg = str(e)
                    print(f"  ✗ Error moving {filename}: {error_msg}")
                    failed_files.append((filename, error_msg))
            
            print("-" * 50)
            print(f"\nMove operation complete:")
            print(f"  Successfully moved: {len(moved_files)} PDF file(s)")
            if moved_files:
                for filename in moved_files:
                    print(f"    - {filename}")
            
            if failed_files:
                print(f"  Failed to move: {len(failed_files)} PDF file(s)")
                for filename, error in failed_files:
                    print(f"    - {filename}: {error}")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                raise ValueError(f"S3 bucket '{bucket_name}' does not exist")
            elif error_code == 'AccessDenied':
                raise ValueError(f"Access denied to S3 bucket '{bucket_name}'. Check your AWS credentials.")
            else:
                raise Exception(f"Error accessing S3: {str(e)}")
        
        summary = f"Moved {len(moved_files)} PDF(s) from raw-pdf-data/ to processed-pdf-data/"
        if failed_files:
            summary += f" ({len(failed_files)} failed)"
        
        return summary
    

    
    data = fetch_data()
    data = extract_data(data)
    data = chunk_data(data)

    data = convert_to_embeddings(data)
    
    data = upsert_to_pinecone(data)

    data = clean_and_move_data(data)

data_ingestion_pipeline()