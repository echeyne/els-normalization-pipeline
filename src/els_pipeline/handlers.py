"""
Lambda handler entry points for the ELS normalization pipeline.

Each handler wraps a pipeline stage function and provides consistent
error handling and logging for AWS Lambda execution.
"""

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Dict, Any

from botocore.exceptions import ClientError

from .ingester import ingest_document
from .extractor import extract_text
from .detector import detect_structure
from .parser import parse_hierarchy
from .validator import validate_record, serialize_record
from .models import IngestionRequest
from .config import Config
from .s3_helpers import save_json_to_s3, load_json_from_s3, construct_intermediate_key

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
        
        # Prepare extraction output JSON
        extraction_output = {
            "blocks": [block.model_dump() for block in result.blocks],
            "total_pages": result.total_pages,
            "total_blocks": len(result.blocks),
            "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_s3_key": s3_key,
            "source_version_id": s3_version_id
        }
        
        # Construct S3 key for extraction output
        output_key = construct_intermediate_key(
            event["country"],
            event["state"],
            event["version_year"],
            "extraction",
            event["run_id"]
        )
        
        # Save extraction output to S3
        try:
            save_json_to_s3(extraction_output, Config.S3_PROCESSED_BUCKET, output_key)
            logger.info(
                f"Saved extraction output to S3: {output_key}, "
                f"total_pages={result.total_pages}, total_blocks={len(result.blocks)}"
            )
        except ClientError as e:
            error_msg = f"Failed to save extraction output to S3: {output_key}"
            logger.error(f"{error_msg}: {e}")
            return _handle_error("text_extraction", Exception(error_msg), event)
        
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

        # Load extraction output from S3
        extraction_key = event["output_artifact"]

        try:
            extraction_output = load_json_from_s3(Config.S3_PROCESSED_BUCKET, extraction_key)
            blocks_data = extraction_output["blocks"]
            logger.info(f"Loaded {len(blocks_data)} blocks from S3: {extraction_key}")
            
            # Convert dictionary blocks to TextBlock instances
            from els_pipeline.models import TextBlock
            blocks = [TextBlock(**block_dict) for block_dict in blocks_data]
            logger.info(f"Converted {len(blocks)} blocks to TextBlock instances")
        except ClientError as e:
            error_msg = f"Failed to load extraction output from S3: {extraction_key}"
            logger.error(f"{error_msg} - {str(e)}")
            return _handle_error("structure_detection", Exception(error_msg), event)
        except Exception as e:
            error_msg = f"Failed to convert blocks to TextBlock instances: {str(e)}"
            logger.error(error_msg)
            return _handle_error("structure_detection", Exception(error_msg), event)

        # Detect structure
        result = detect_structure(blocks)

        if result.status == "error":
            return _handle_error("structure_detection", Exception(result.error), event)

        # Prepare detection output JSON
        detection_output = {
            "elements": [elem.model_dump() for elem in result.elements],  # Serialize Pydantic models to dicts
            "review_count": result.review_count,
            "detection_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_extraction_key": extraction_key
        }

        # Save detection output to S3
        output_key = construct_intermediate_key(
            event["country"],
            event["state"],
            event["version_year"],
            "detection",
            event["run_id"]
        )

        try:
            save_json_to_s3(detection_output, Config.S3_PROCESSED_BUCKET, output_key)
            logger.info(f"Saved detection output to S3: {output_key}")
        except ClientError as e:
            logger.error(f"Failed to save detection output to S3: {output_key} - {str(e)}")
            return _handle_error("structure_detection", e, event)

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

        # Load detection output from S3
        detection_key = event["output_artifact"]

        try:
            detection_output = load_json_from_s3(Config.S3_PROCESSED_BUCKET, detection_key)
            elements_data = detection_output["elements"]
            logger.info(f"Loaded {len(elements_data)} elements from S3: {detection_key}")

            # Convert dictionary elements to DetectedElement instances
            from els_pipeline.models import DetectedElement
            elements = [DetectedElement(**elem_dict) for elem_dict in elements_data]
            logger.info(f"Converted {len(elements)} elements to DetectedElement instances")
        except ClientError as e:
            error_msg = f"Failed to load detection output from S3: {detection_key}"
            logger.error(f"{error_msg} - {str(e)}")
            return _handle_error("hierarchy_parsing", Exception(error_msg), event)
        except Exception as e:
            error_msg = f"Failed to convert elements to DetectedElement instances: {str(e)}"
            logger.error(error_msg)
            return _handle_error("hierarchy_parsing", Exception(error_msg), event)

        # Parse hierarchy
        result = parse_hierarchy(
            elements=elements,
            country=event["country"],
            state=event["state"],
            version_year=event["version_year"]
        )

        if result.status == "error":
            return _handle_error("hierarchy_parsing", Exception(result.error), event)

        # Prepare parsing output JSON
        parsing_output = {
            "indicators": result.indicators,  # Already serialized in ParseResult
            "total_indicators": len(result.indicators),
            "parsing_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_detection_key": detection_key
        }

        # Save parsing output to S3
        output_key = construct_intermediate_key(
            event["country"],
            event["state"],
            event["version_year"],
            "parsing",
            event["run_id"]
        )

        try:
            save_json_to_s3(parsing_output, Config.S3_PROCESSED_BUCKET, output_key)
            logger.info(f"Saved parsing output to S3: {output_key}")
        except ClientError as e:
            logger.error(f"Failed to save parsing output to S3: {output_key} - {str(e)}")
            return _handle_error("hierarchy_parsing", e, event)

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
            "output_artifact": str (S3 key with validation summary),
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

        # Load parsing output from S3
        parsing_key = event["output_artifact"]

        try:
            parsing_output = load_json_from_s3(Config.S3_PROCESSED_BUCKET, parsing_key)
            indicators = parsing_output["indicators"]
            logger.info(f"Loaded {len(indicators)} indicators from S3: {parsing_key}")
        except ClientError as e:
            error_msg = f"Failed to load parsing output from S3: {parsing_key}"
            logger.error(f"{error_msg} - {str(e)}")
            return _handle_error("validation", Exception(error_msg), event)

        # Validate each indicator and save to S3
        validated_records = []
        validation_errors = []

        for indicator in indicators:
            # Validate the indicator (which is already in canonical JSON format)
            result = validate_record(indicator)

            if result.is_valid:
                # Extract standard_id from the indicator
                standard_id = indicator.get("standard", {}).get("standard_id")

                if not standard_id:
                    logger.error(f"Indicator missing standard_id: {indicator}")
                    validation_errors.append({
                        "indicator": indicator,
                        "error": "Missing standard_id"
                    })
                    continue

                # Save individual canonical record
                record_key = f"{event['country']}/{event['state']}/{event['version_year']}/{standard_id}.json"

                try:
                    save_json_to_s3(indicator, Config.S3_PROCESSED_BUCKET, record_key)
                    validated_records.append(record_key)
                    logger.info(f"Saved canonical record to S3: {record_key}")
                except ClientError as e:
                    logger.error(f"Failed to save canonical record {standard_id}: {e}")
                    validation_errors.append({
                        "standard_id": standard_id,
                        "error": str(e)
                    })
            else:
                # Collect validation errors
                validation_errors.append({
                    "indicator": indicator,
                    "errors": [{"field": err.field_path, "message": err.message, "type": err.error_type}
                              for err in result.errors]
                })
                logger.warning(f"Validation failed for indicator: {result.errors}")

        # Prepare validation summary
        validation_summary = {
            "validated_records": validated_records,
            "total_validated": len(validated_records),
            "validation_errors": validation_errors,
            "validation_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_parsing_key": parsing_key
        }

        # Save validation summary to S3
        output_key = construct_intermediate_key(
            event["country"],
            event["state"],
            event["version_year"],
            "validation",
            event["run_id"]
        )

        try:
            save_json_to_s3(validation_summary, Config.S3_PROCESSED_BUCKET, output_key)
            logger.info(f"Saved validation summary to S3: {output_key}")
        except ClientError as e:
            logger.error(f"Failed to save validation summary: {e}")
            return _handle_error("validation", e, event)

        logger.info(
            f"Validation completed: "
            f"total={len(indicators)}, "
            f"validated={len(validated_records)}, "
            f"errors={len(validation_errors)}"
        )

        return {
            "status": "success",
            "stage_name": "validation",
            "output_artifact": output_key,
            "total_indicators": len(indicators),
            "total_validated": len(validated_records),
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
