"""Raw document ingestion module for the ELS pipeline."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from .models import IngestionRequest, IngestionResult
from .config import Config


# Supported file formats
SUPPORTED_FORMATS = {".pdf", ".html"}


def validate_format(filename: str) -> tuple[bool, Optional[str]]:
    """
    Validate that the file format is supported.
    
    Args:
        filename: The filename to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))
        return False, f"Unsupported file format '{ext}'. Supported formats: {supported}"
    return True, None


def construct_s3_path(state: str, year: int, filename: str) -> str:
    """
    Construct S3 path following the pattern {state}/{year}/{filename}.
    
    Args:
        state: Two-letter state code
        year: Version year
        filename: Document filename
        
    Returns:
        S3 key path without leading slashes
    """
    # Ensure no leading/trailing slashes and no double slashes
    state = state.strip("/")
    filename = filename.strip("/")
    return f"{state}/{year}/{filename}"


def ingest_document(request: IngestionRequest) -> IngestionResult:
    """
    Ingest a raw document into S3 with metadata.
    
    Validates file format, constructs S3 path, uploads to S3 with versioning,
    and records metadata tags.
    
    Args:
        request: IngestionRequest containing file path and metadata
        
    Returns:
        IngestionResult with S3 key, version ID, metadata, and status
    """
    # Validate file format
    is_valid, error_msg = validate_format(request.filename)
    if not is_valid:
        return IngestionResult(
            s3_key="",
            s3_version_id="",
            metadata={},
            status="error",
            error=error_msg
        )
    
    # Construct S3 path
    s3_key = construct_s3_path(request.state, request.version_year, request.filename)
    
    # Prepare metadata
    upload_timestamp = datetime.utcnow().isoformat() + "Z"
    metadata = {
        "state": request.state,
        "version_year": str(request.version_year),
        "source_url": request.source_url,
        "publishing_agency": request.publishing_agency,
        "upload_timestamp": upload_timestamp
    }
    
    # Upload to S3
    try:
        s3_client = boto3.client("s3", region_name=Config.AWS_REGION)
        
        # Read file content
        with open(request.file_path, "rb") as f:
            file_content = f.read()
        
        # Upload with metadata
        response = s3_client.put_object(
            Bucket=Config.S3_RAW_BUCKET,
            Key=s3_key,
            Body=file_content,
            Metadata=metadata
        )
        
        # Get version ID (will be None if versioning is not enabled)
        version_id = response.get("VersionId", "")
        
        return IngestionResult(
            s3_key=s3_key,
            s3_version_id=version_id,
            metadata=metadata,
            status="success",
            error=None
        )
        
    except FileNotFoundError:
        return IngestionResult(
            s3_key=s3_key,
            s3_version_id="",
            metadata=metadata,
            status="error",
            error=f"File not found: {request.file_path}"
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return IngestionResult(
            s3_key=s3_key,
            s3_version_id="",
            metadata=metadata,
            status="error",
            error=f"S3 upload failed ({error_code}): {error_msg}"
        )
    except Exception as e:
        return IngestionResult(
            s3_key=s3_key,
            s3_version_id="",
            metadata=metadata,
            status="error",
            error=f"Unexpected error during ingestion: {str(e)}"
        )
