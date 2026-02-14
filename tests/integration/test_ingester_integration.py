"""Integration tests for document ingestion with mocked S3.

These tests use moto to simulate S3 locally, providing more realistic
testing than unit tests with mocks.
"""

import tempfile
import os
from moto import mock_aws
import boto3
import pytest

from els_pipeline.ingester import ingest_document
from els_pipeline.models import IngestionRequest
from els_pipeline.config import Config


@mock_aws
def test_ingester_with_mocked_s3_success():
    """Integration test: successful ingestion with mocked S3."""
    # Create mock S3 bucket with versioning
    s3 = boto3.client("s3", region_name=Config.AWS_REGION)
    s3.create_bucket(Bucket=Config.S3_RAW_BUCKET)
    s3.put_bucket_versioning(
        Bucket=Config.S3_RAW_BUCKET,
        VersioningConfiguration={'Status': 'Enabled'}
    )
    
    # Create test file
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as tmp:
        tmp.write(b"Test PDF content for California standards")
        tmp_path = tmp.name
    
    try:
        request = IngestionRequest(
            file_path=tmp_path,
            country="US",
            state="CA",
            version_year=2021,
            source_url="https://www.cde.ca.gov/sp/cd/re/documents/ptklfataglance.pdf",
            publishing_agency="California Department of Education",
            filename="california_standards_2021.pdf"
        )
        
        result = ingest_document(request)
        
        # Verify result
        assert result.status == "success"
        assert result.s3_key == "US/CA/2021/california_standards_2021.pdf"
        assert result.s3_version_id != ""
        assert result.error is None
        
        # Verify metadata
        assert result.metadata["country"] == "US"
        assert result.metadata["state"] == "CA"
        assert result.metadata["version_year"] == "2021"
        assert result.metadata["source_url"] == "https://www.cde.ca.gov/sp/cd/re/documents/ptklfataglance.pdf"
        assert result.metadata["publishing_agency"] == "California Department of Education"
        assert "upload_timestamp" in result.metadata
        
        # Verify file exists in S3
        response = s3.head_object(Bucket=Config.S3_RAW_BUCKET, Key=result.s3_key)
        assert response['Metadata']['country'] == "US"
        assert response['Metadata']['state'] == "CA"
        assert response['Metadata']['version_year'] == "2021"
        
        # Verify file content
        obj = s3.get_object(Bucket=Config.S3_RAW_BUCKET, Key=result.s3_key)
        content = obj['Body'].read()
        assert content == b"Test PDF content for California standards"
        
    finally:
        os.unlink(tmp_path)


@mock_aws
def test_ingester_with_mocked_s3_html_format():
    """Integration test: HTML file ingestion."""
    # Create mock S3 bucket with versioning
    s3 = boto3.client("s3", region_name=Config.AWS_REGION)
    s3.create_bucket(Bucket=Config.S3_RAW_BUCKET)
    s3.put_bucket_versioning(
        Bucket=Config.S3_RAW_BUCKET,
        VersioningConfiguration={'Status': 'Enabled'}
    )
    
    # Create test HTML file
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".html", delete=False) as tmp:
        tmp.write(b"<html><body>Test HTML standards</body></html>")
        tmp_path = tmp.name
    
    try:
        request = IngestionRequest(
            file_path=tmp_path,
            country="US",
            state="TX",
            version_year=2022,
            source_url="https://example.com/standards.html",
            publishing_agency="Texas Education Agency",
            filename="texas_standards_2022.html"
        )
        
        result = ingest_document(request)
        
        assert result.status == "success"
        assert result.s3_key == "US/TX/2022/texas_standards_2022.html"
        assert result.error is None
        
    finally:
        os.unlink(tmp_path)


@mock_aws
def test_ingester_with_mocked_s3_unsupported_format():
    """Integration test: unsupported file format rejection."""
    # Create mock S3 bucket (won't be used but needed for consistency)
    s3 = boto3.client("s3", region_name=Config.AWS_REGION)
    s3.create_bucket(Bucket=Config.S3_RAW_BUCKET)
    
    # Create test file with unsupported extension
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".docx", delete=False) as tmp:
        tmp.write(b"Test document content")
        tmp_path = tmp.name
    
    try:
        request = IngestionRequest(
            file_path=tmp_path,
            country="US",
            state="CA",
            version_year=2021,
            source_url="https://example.com/standards.docx",
            publishing_agency="Test Agency",
            filename="test_standards.docx"
        )
        
        result = ingest_document(request)
        
        assert result.status == "error"
        assert result.error is not None
        assert ".docx" in result.error.lower()
        assert "unsupported" in result.error.lower()
        
    finally:
        os.unlink(tmp_path)


@mock_aws
def test_ingester_file_not_found():
    """Integration test: file not found error handling."""
    # Create mock S3 bucket
    s3 = boto3.client("s3", region_name=Config.AWS_REGION)
    s3.create_bucket(Bucket=Config.S3_RAW_BUCKET)
    
    request = IngestionRequest(
        file_path="/nonexistent/path/to/file.pdf",
        country="US",
        state="CA",
        version_year=2021,
        source_url="https://example.com/standards.pdf",
        publishing_agency="Test Agency",
        filename="nonexistent.pdf"
    )
    
    result = ingest_document(request)
    
    assert result.status == "error"
    assert result.error is not None
    assert "not found" in result.error.lower()


@mock_aws
def test_ingester_multiple_uploads_same_key():
    """Integration test: versioning with multiple uploads to same key."""
    # Create mock S3 bucket with versioning
    s3 = boto3.client("s3", region_name=Config.AWS_REGION)
    s3.create_bucket(Bucket=Config.S3_RAW_BUCKET)
    s3.put_bucket_versioning(
        Bucket=Config.S3_RAW_BUCKET,
        VersioningConfiguration={'Status': 'Enabled'}
    )
    
    # First upload
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as tmp:
        tmp.write(b"Version 1 content")
        tmp_path = tmp.name
    
    try:
        request1 = IngestionRequest(
            file_path=tmp_path,
            country="US",
            state="CA",
            version_year=2021,
            source_url="https://example.com/v1.pdf",
            publishing_agency="Test Agency",
            filename="test.pdf"
        )
        
        result1 = ingest_document(request1)
        assert result1.status == "success"
        version_id_1 = result1.s3_version_id
        
    finally:
        os.unlink(tmp_path)
    
    # Second upload (same key, different content)
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as tmp:
        tmp.write(b"Version 2 content - updated")
        tmp_path = tmp.name
    
    try:
        request2 = IngestionRequest(
            file_path=tmp_path,
            country="US",
            state="CA",
            version_year=2021,
            source_url="https://example.com/v2.pdf",
            publishing_agency="Test Agency",
            filename="test.pdf"
        )
        
        result2 = ingest_document(request2)
        assert result2.status == "success"
        version_id_2 = result2.s3_version_id
        
        # Version IDs should be different
        assert version_id_1 != version_id_2
        
        # Both versions should exist
        obj1 = s3.get_object(
            Bucket=Config.S3_RAW_BUCKET,
            Key=result1.s3_key,
            VersionId=version_id_1
        )
        assert obj1['Body'].read() == b"Version 1 content"
        
        obj2 = s3.get_object(
            Bucket=Config.S3_RAW_BUCKET,
            Key=result2.s3_key,
            VersionId=version_id_2
        )
        assert obj2['Body'].read() == b"Version 2 content - updated"
        
    finally:
        os.unlink(tmp_path)
