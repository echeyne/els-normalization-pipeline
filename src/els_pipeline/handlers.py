"""
Lambda handler entry points for the ELS normalization pipeline.

Each handler wraps a pipeline stage function and provides consistent
error handling and logging for AWS Lambda execution.
"""

import json
import logging
import traceback
from typing import Dict, Any

from .ingester import ingest_document
from .extractor import extract_text
from .detector import detect_structure
from .parser import parse_hierarchy
from .validator import validate_record, serialize_record
from .models import IngestionRequest

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _handle_error(stage_name: str, error: Exception, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Common error handler for all Lambda functions.
    
    Args:
        stage_name: Name of the pipeline stage
        error: The exception that occurred
        event: The Lambda event that triggered the error
    
    Returns:
        Error response dictionary
    """
    error_message = str(error)
    error_trace = traceback.format_exc()
    
    logger.error(
        f"Error in {stage_name}: {error_message}\n"
        f"Event: {json.dumps(event)}\n"
        f"Traceback: {error_trace}"
    )
    
    return {
        "status": "error",
        "stage_name": stage_name,
        "error": error_message,
        "error_type": type(error).__name__,
        "run_id": event.get("run_id", "unknown")
    }


def ingestion_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for document ingestion stage.
    
    Expected event structure:
    {
        "run_id": str,
        "file_path": str,
        "country": str,
        "state": str,
        "version_year": int,
        "source_url": str,
        "publishing_agency": str,
        "filename": str
    }
    
    Returns:
        {
            "status": "success" | "error",
            "stage_name": "ingestion",
            "output_artifact": str (S3 key),
            "s3_version_id": str,
            "country": str,
            "state": str,
            "version_year": int,
            "error": str (optional)
        }
    """
    try:
        logger.info(f"Starting ingestion: run_id={event.get('run_id')}, country={event.get('country')}")
        
        # Create ingestion request
        request = IngestionRequest(
            file_path=event["file_path"],
            country=event["country"],
            state=event["state"],
            version_year=event["version_year"],
            source_url=event["source_url"],
            publishing_agency=event["publishing_agency"],
            filename=event["filename"]
        )
        
        # Perform ingestion
        result = ingest_document(request)
        
        if result.status == "error":
            return _handle_error("ingestion", Exception(result.error), event)
        
        logger.info(f"Ingestion completed: s3_key={result.s3_key}")
        
        return {
            "status": "success",
            "stage_name": "ingestion",
            "output_artifact": result.s3_key,
            "s3_version_id": result.s3_version_id,
            "country": event["country"],
            "state": event["state"],
            "version_year": event["version_year"],
            "run_id": event.get("run_id")
        }
        
    except Exception as e:
        return _handle_error("ingestion", e, event)


def extraction_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for text extraction stage.
    
    Expected event structure:
    {
        "run_id": str,
        "output_artifact": str (S3 key from previous stage),
        "s3_version_id": str,
        "country": str,
        "state": str,
        "version_year": int
    }
    
    Returns:
        {
            "status": "success" | "error",
            "stage_name": "text_extraction",
            "output_artifact": str (S3 key with extracted text),
            "total_pages": int,
            "country": str,
            "state": str,
            "version_year": int,
            "error": str (optional)
        }
    """
    try:
        logger.info(f"Starting text extraction: run_id={event.get('run_id')}, country={event.get('country')}")
        
        s3_key = event["output_artifact"]
        s3_version_id = event.get("s3_version_id")
        
        # Extract text
        result = extract_text(s3_key, s3_version_id)
        
        if result.status == "error":
            return _handle_error("text_extraction", Exception(result.error), event)
        
        # Store extracted blocks to S3 for next stage
        # In production, this would write to S3
        output_key = f"{s3_key}.extracted.json"
        
        logger.info(f"Text extraction completed: total_pages={result.total_pages}")
        
        return {
            "status": "success",
            "stage_name": "text_extraction",
            "output_artifact": output_key,
            "total_pages": result.total_pages,
            "country": event["country"],
            "state": event["state"],
            "version_year": event["version_year"],
            "run_id": event.get("run_id")
        }
        
    except Exception as e:
        return _handle_error("text_extraction", e, event)


def detection_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for structure detection stage.
    
    Expected event structure:
    {
        "run_id": str,
        "output_artifact": str (S3 key with extracted text),
        "country": str,
        "state": str,
        "version_year": int
    }
    
    Returns:
        {
            "status": "success" | "error",
            "stage_name": "structure_detection",
            "output_artifact": str (S3 key with detected elements),
            "review_count": int,
            "country": str,
            "state": str,
            "version_year": int,
            "error": str (optional)
        }
    """
    try:
        logger.info(f"Starting structure detection: run_id={event.get('run_id')}, country={event.get('country')}")
        
        # In production, read blocks from S3
        # For now, assume blocks are in event or read from S3
        blocks = []  # Would load from event["output_artifact"]
        
        # Detect structure
        result = detect_structure(blocks)
        
        if result.status == "error":
            return _handle_error("structure_detection", Exception(result.error), event)
        
        # Store detected elements to S3
        output_key = f"{event['output_artifact']}.detected.json"
        
        logger.info(f"Structure detection completed: review_count={result.review_count}")
        
        return {
            "status": "success",
            "stage_name": "structure_detection",
            "output_artifact": output_key,
            "review_count": result.review_count,
            "country": event["country"],
            "state": event["state"],
            "version_year": event["version_year"],
            "run_id": event.get("run_id")
        }
        
    except Exception as e:
        return _handle_error("structure_detection", e, event)


def parsing_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for hierarchy parsing stage.
    
    Expected event structure:
    {
        "run_id": str,
        "output_artifact": str (S3 key with detected elements),
        "country": str,
        "state": str,
        "version_year": int
    }
    
    Returns:
        {
            "status": "success" | "error",
            "stage_name": "hierarchy_parsing",
            "output_artifact": str (S3 key with parsed standards),
            "total_indicators": int,
            "orphaned_count": int,
            "country": str,
            "state": str,
            "version_year": int,
            "error": str (optional)
        }
    """
    try:
        logger.info(f"Starting hierarchy parsing: run_id={event.get('run_id')}, country={event.get('country')}")
        
        # In production, read detected elements from S3
        elements = []  # Would load from event["output_artifact"]
        
        # Parse hierarchy
        result = parse_hierarchy(
            elements=elements,
            country=event["country"],
            state=event["state"],
            version_year=event["version_year"]
        )
        
        if result.status == "error":
            return _handle_error("hierarchy_parsing", Exception(result.error), event)
        
        # Store parsed standards to S3
        output_key = f"{event['output_artifact']}.parsed.json"
        
        logger.info(
            f"Hierarchy parsing completed: "
            f"total_indicators={len(result.standards)}, "
            f"orphaned={len(result.orphaned_elements)}"
        )
        
        return {
            "status": "success",
            "stage_name": "hierarchy_parsing",
            "output_artifact": output_key,
            "total_indicators": len(result.standards),
            "orphaned_count": len(result.orphaned_elements),
            "country": event["country"],
            "state": event["state"],
            "version_year": event["version_year"],
            "run_id": event.get("run_id")
        }
        
    except Exception as e:
        return _handle_error("hierarchy_parsing", e, event)


def validation_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for validation stage.
    
    Expected event structure:
    {
        "run_id": str,
        "output_artifact": str (S3 key with parsed standards),
        "total_indicators": int,
        "country": str,
        "state": str,
        "version_year": int
    }
    
    Returns:
        {
            "status": "success" | "error",
            "stage_name": "validation",
            "output_artifact": str (S3 key with validated records),
            "total_indicators": int,
            "total_validated": int,
            "country": str,
            "state": str,
            "version_year": int,
            "error": str (optional)
        }
    """
    try:
        logger.info(f"Starting validation: run_id={event.get('run_id')}, country={event.get('country')}")
        
        # In production, read parsed standards from S3
        standards = []  # Would load from event["output_artifact"]
        
        validated_count = 0
        # Validate each standard
        for standard in standards:
            # Serialize to canonical JSON
            record = serialize_record(standard, {}, {})
            
            # Validate
            validation_result = validate_record(record)
            if validation_result.is_valid:
                validated_count += 1
                # Store to S3 processed bucket
        
        output_key = f"{event['output_artifact']}.validated.json"
        
        logger.info(
            f"Validation completed: "
            f"total={event.get('total_indicators', 0)}, "
            f"validated={validated_count}"
        )
        
        return {
            "status": "success",
            "stage_name": "validation",
            "output_artifact": output_key,
            "total_indicators": event.get("total_indicators", 0),
            "total_validated": validated_count,
            "country": event["country"],
            "state": event["state"],
            "version_year": event["version_year"],
            "run_id": event.get("run_id")
        }
        
    except Exception as e:
        return _handle_error("validation", e, event)


def embedding_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for embedding generation stage.
    
    Expected event structure:
    {
        "run_id": str,
        "output_artifact": str (S3 key with validated records),
        "total_validated": int,
        "country": str,
        "state": str,
        "version_year": int
    }
    
    Returns:
        {
            "status": "success" | "error",
            "stage_name": "embedding_generation",
            "output_artifact": str (S3 key with embeddings),
            "total_validated": int,
            "total_embedded": int,
            "country": str,
            "state": str,
            "version_year": int,
            "error": str (optional)
        }
    """
    try:
        logger.info(f"Starting embedding generation: run_id={event.get('run_id')}, country={event.get('country')}")
        
        # In production, read validated standards from S3 and generate embeddings
        # This is a placeholder
        total_embedded = event.get("total_validated", 0)
        
        output_key = f"{event['output_artifact']}.embeddings.json"
        
        logger.info(f"Embedding generation completed: total_embedded={total_embedded}")
        
        return {
            "status": "success",
            "stage_name": "embedding_generation",
            "output_artifact": output_key,
            "total_validated": event.get("total_validated", 0),
            "total_embedded": total_embedded,
            "country": event["country"],
            "state": event["state"],
            "version_year": event["version_year"],
            "run_id": event.get("run_id")
        }
        
    except Exception as e:
        return _handle_error("embedding_generation", e, event)


def recommendation_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for recommendation generation stage.
    
    Expected event structure:
    {
        "run_id": str,
        "output_artifact": str (S3 key with embeddings),
        "total_embedded": int,
        "country": str,
        "state": str,
        "version_year": int
    }
    
    Returns:
        {
            "status": "success" | "error",
            "stage_name": "recommendation_generation",
            "output_artifact": str (S3 key with recommendations),
            "total_embedded": int,
            "total_recommendations": int,
            "country": str,
            "state": str,
            "version_year": int,
            "error": str (optional)
        }
    """
    try:
        logger.info(f"Starting recommendation generation: run_id={event.get('run_id')}, country={event.get('country')}")
        
        # In production, read validated standards and generate recommendations
        # This is a placeholder - assume 2 recommendations per indicator (parent + teacher)
        total_recommendations = event.get("total_embedded", 0) * 2
        
        output_key = f"{event['output_artifact']}.recommendations.json"
        
        logger.info(f"Recommendation generation completed: total_recommendations={total_recommendations}")
        
        return {
            "status": "success",
            "stage_name": "recommendation_generation",
            "output_artifact": output_key,
            "total_embedded": event.get("total_embedded", 0),
            "total_recommendations": total_recommendations,
            "country": event["country"],
            "state": event["state"],
            "version_year": event["version_year"],
            "run_id": event.get("run_id")
        }
        
    except Exception as e:
        return _handle_error("recommendation_generation", e, event)


def persistence_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for data persistence stage.
    
    Expected event structure:
    {
        "run_id": str,
        "output_artifact": str (S3 key with recommendations),
        "total_indicators": int,
        "total_validated": int,
        "total_embedded": int,
        "total_recommendations": int,
        "country": str,
        "state": str,
        "version_year": int
    }
    
    Returns:
        {
            "status": "success" | "error",
            "stage_name": "data_persistence",
            "output_artifact": str (database reference),
            "total_indicators": int,
            "total_validated": int,
            "total_embedded": int,
            "total_recommendations": int,
            "country": str,
            "state": str,
            "version_year": int,
            "error": str (optional)
        }
    """
    try:
        logger.info(f"Starting data persistence: run_id={event.get('run_id')}, country={event.get('country')}")
        
        # In production, persist all data to Aurora PostgreSQL
        # This is a placeholder
        
        output_key = f"db://pipeline_runs/{event.get('run_id')}"
        
        logger.info(
            f"Data persistence completed: "
            f"indicators={event.get('total_indicators', 0)}, "
            f"validated={event.get('total_validated', 0)}, "
            f"embedded={event.get('total_embedded', 0)}, "
            f"recommendations={event.get('total_recommendations', 0)}"
        )
        
        return {
            "status": "success",
            "stage_name": "data_persistence",
            "output_artifact": output_key,
            "total_indicators": event.get("total_indicators", 0),
            "total_validated": event.get("total_validated", 0),
            "total_embedded": event.get("total_embedded", 0),
            "total_recommendations": event.get("total_recommendations", 0),
            "country": event["country"],
            "state": event["state"],
            "version_year": event["version_year"],
            "run_id": event.get("run_id")
        }
        
    except Exception as e:
        return _handle_error("data_persistence", e, event)
