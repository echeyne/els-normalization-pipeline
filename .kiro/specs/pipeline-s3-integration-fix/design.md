# Design Document: Pipeline S3 Integration Fix

## Overview

This design addresses the implementation gaps in the ELS pipeline where Lambda handlers have placeholder code for S3 data persistence. We'll implement S3 save/load operations for intermediate pipeline data, ensuring each stage can pass data to the next stage through S3.

## Architecture

### Data Flow

```
Ingestion → [S3: raw PDF] → Extraction → [S3: blocks JSON] → Detection → [S3: elements JSON] →
Parsing → [S3: indicators JSON] → Validation → [S3: canonical records] → Persistence → [DB]
```

### S3 Bucket Structure

```
els-processed-json-{env}-{account}/
├── {country}/{state}/{year}/
│   ├── intermediate/
│   │   ├── extraction/
│   │   │   └── {run_id}.json          # Textract blocks
│   │   ├── detection/
│   │   │   └── {run_id}.json          # Detected elements
│   │   ├── parsing/
│   │   │   └── {run_id}.json          # Parsed indicators
│   │   └── validation/
│   │       └── {run_id}.json          # Validation summary
│   └── {standard_id}.json             # Final canonical records
```

## Component Design

### 1. S3 Helper Module

**Location:** `src/els_pipeline/s3_helpers.py`

**Functions:**

```python
def save_json_to_s3(data: dict, bucket: str, key: str) -> None:
    """
    Save JSON data to S3.

    Args:
        data: Dictionary to serialize and save
        bucket: S3 bucket name
        key: S3 object key

    Raises:
        ClientError: If S3 operation fails
    """

def load_json_from_s3(bucket: str, key: str) -> dict:
    """
    Load JSON data from S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Deserialized JSON as dictionary

    Raises:
        ClientError: If S3 operation fails
    """

def construct_intermediate_key(
    country: str,
    state: str,
    year: int,
    stage: str,
    run_id: str
) -> str:
    """
    Construct S3 key for intermediate data.

    Args:
        country: Country code
        state: State code
        year: Version year
        stage: Pipeline stage (extraction, detection, parsing, validation)
        run_id: Pipeline run ID

    Returns:
        S3 key following pattern: {country}/{state}/{year}/intermediate/{stage}/{run_id}.json
    """
```

**Implementation Notes:**

- Use `boto3.client('s3')` with region from `Config.AWS_REGION`
- Use `json.dumps(data, indent=2)` for readable output
- Use `json.loads(response['Body'].read())` for loading
- Wrap boto3 operations in try/except for ClientError
- Log all S3 operations with bucket, key, and operation type

### 2. Extraction Handler Updates

**File:** `src/els_pipeline/handlers.py`

**Changes:**

```python
def extraction_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    # ... existing code ...

    # Extract text
    result = extract_text(s3_key, s3_version_id)

    if result.status == "error":
        return _handle_error("text_extraction", Exception(result.error), event)

    # NEW: Prepare extraction output
    extraction_output = {
        "blocks": result.blocks,  # List of Textract block dicts
        "total_pages": result.total_pages,
        "total_blocks": len(result.blocks),
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_s3_key": s3_key,
        "source_version_id": s3_version_id
    }

    # NEW: Save to S3
    output_key = construct_intermediate_key(
        event["country"],
        event["state"],
        event["version_year"],
        "extraction",
        event["run_id"]
    )

    try:
        save_json_to_s3(extraction_output, Config.S3_PROCESSED_BUCKET, output_key)
        logger.info(f"Saved extraction output to S3: {output_key}")
    except ClientError as e:
        return _handle_error("text_extraction", e, event)

    return {
        "status": "success",
        "stage_name": "text_extraction",
        "output_artifact": output_key,  # Changed from placeholder
        "total_pages": result.total_pages,
        "country": event["country"],
        "state": event["state"],
        "version_year": event["version_year"],
        "run_id": event.get("run_id")
    }
```

**Extractor Module Updates:**

The `extract_text` function in `src/els_pipeline/extractor.py` needs to return blocks:

```python
@dataclass
class ExtractionResult:
    status: str
    blocks: List[Dict[str, Any]]  # NEW: Add blocks field
    total_pages: int
    error: Optional[str] = None
```

### 3. Detection Handler Updates

**File:** `src/els_pipeline/handlers.py`

**Changes:**

```python
def detection_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    # ... existing code ...

    # NEW: Load extraction output from S3
    extraction_key = event["output_artifact"]

    try:
        extraction_output = load_json_from_s3(Config.S3_PROCESSED_BUCKET, extraction_key)
        blocks = extraction_output["blocks"]
        logger.info(f"Loaded {len(blocks)} blocks from S3: {extraction_key}")
    except ClientError as e:
        error_msg = f"Failed to load extraction output from S3: {extraction_key}"
        return _handle_error("structure_detection", Exception(error_msg), event)

    # Detect structure
    result = detect_structure(blocks)  # Changed from empty list

    if result.status == "error":
        return _handle_error("structure_detection", Exception(result.error), event)

    # NEW: Prepare detection output
    detection_output = {
        "elements": result.elements,  # List of detected element dicts
        "review_count": result.review_count,
        "detection_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_extraction_key": extraction_key
    }

    # NEW: Save to S3
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
        return _handle_error("structure_detection", e, event)

    return {
        "status": "success",
        "stage_name": "structure_detection",
        "output_artifact": output_key,  # Changed from placeholder
        "review_count": result.review_count,
        "country": event["country"],
        "state": event["state"],
        "version_year": event["version_year"],
        "run_id": event.get("run_id")
    }
```

**Detector Module Updates:**

The `detect_structure` function needs to return elements:

```python
@dataclass
class DetectionResult:
    status: str
    elements: List[Dict[str, Any]]  # NEW: Add elements field
    review_count: int
    error: Optional[str] = None
```

### 4. Parsing Handler Updates

**File:** `src/els_pipeline/handlers.py`

**Changes:**

```python
def parsing_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    # ... existing code ...

    # NEW: Load detection output from S3
    detection_key = event["output_artifact"]

    try:
        detection_output = load_json_from_s3(Config.S3_PROCESSED_BUCKET, detection_key)
        elements = detection_output["elements"]
        logger.info(f"Loaded {len(elements)} elements from S3: {detection_key}")
    except ClientError as e:
        error_msg = f"Failed to load detection output from S3: {detection_key}"
        return _handle_error("hierarchy_parsing", Exception(error_msg), event)

    # Parse hierarchy
    result = parse_hierarchy(elements)  # Changed from empty list

    if result.status == "error":
        return _handle_error("hierarchy_parsing", Exception(result.error), event)

    # NEW: Prepare parsing output
    parsing_output = {
        "indicators": result.indicators,  # List of indicator dicts
        "total_indicators": len(result.indicators),
        "parsing_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_detection_key": detection_key
    }

    # NEW: Save to S3
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
        return _handle_error("hierarchy_parsing", e, event)

    return {
        "status": "success",
        "stage_name": "hierarchy_parsing",
        "output_artifact": output_key,  # Changed from placeholder
        "total_indicators": len(result.indicators),
        "country": event["country"],
        "state": event["state"],
        "version_year": event["version_year"],
        "run_id": event.get("run_id")
    }
```

### 5. Validation Handler Updates

**File:** `src/els_pipeline/handlers.py`

**Changes:**

```python
def validation_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    # ... existing code ...

    # NEW: Load parsing output from S3
    parsing_key = event["output_artifact"]

    try:
        parsing_output = load_json_from_s3(Config.S3_PROCESSED_BUCKET, parsing_key)
        indicators = parsing_output["indicators"]
        logger.info(f"Loaded {len(indicators)} indicators from S3: {parsing_key}")
    except ClientError as e:
        error_msg = f"Failed to load parsing output from S3: {parsing_key}"
        return _handle_error("validation", Exception(error_msg), event)

    # Validate each indicator and save to S3
    validated_records = []
    validation_errors = []

    for indicator in indicators:
        result = validate_canonical_json(indicator)

        if result.status == "success":
            # Save individual canonical record
            standard_id = indicator["standard"]["standard_id"]
            record_key = f"{event['country']}/{event['state']}/{event['version_year']}/{standard_id}.json"

            try:
                save_json_to_s3(indicator, Config.S3_PROCESSED_BUCKET, record_key)
                validated_records.append(record_key)
            except ClientError as e:
                logger.error(f"Failed to save canonical record {standard_id}: {e}")
                validation_errors.append({
                    "standard_id": standard_id,
                    "error": str(e)
                })
        else:
            validation_errors.append({
                "indicator": indicator,
                "errors": result.errors
            })

    # NEW: Save validation summary
    validation_summary = {
        "validated_records": validated_records,
        "total_validated": len(validated_records),
        "validation_errors": validation_errors,
        "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_parsing_key": parsing_key
    }

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
        return _handle_error("validation", e, event)

    return {
        "status": "success",
        "stage_name": "validation",
        "output_artifact": output_key,
        "total_validated": len(validated_records),
        "country": event["country"],
        "state": event["state"],
        "version_year": event["version_year"],
        "run_id": event.get("run_id")
    }
```

## IAM Policy Updates

### CloudFormation Template Changes

**File:** `infra/template.yaml`

Add S3 permissions for intermediate data to each Lambda role:

```yaml
# TextExtractor role - add write permission for extraction output
- Effect: Allow
  Action:
    - s3:PutObject
  Resource: !Sub "${ProcessedJsonBucket.Arn}/*/intermediate/extraction/*"

# StructureDetector role - add read/write permissions
- Effect: Allow
  Action:
    - s3:GetObject
  Resource: !Sub "${ProcessedJsonBucket.Arn}/*/intermediate/extraction/*"
- Effect: Allow
  Action:
    - s3:PutObject
  Resource: !Sub "${ProcessedJsonBucket.Arn}/*/intermediate/detection/*"

# HierarchyParser role - add read/write permissions
- Effect: Allow
  Action:
    - s3:GetObject
  Resource: !Sub "${ProcessedJsonBucket.Arn}/*/intermediate/detection/*"
- Effect: Allow
  Action:
    - s3:PutObject
  Resource: !Sub "${ProcessedJsonBucket.Arn}/*/intermediate/parsing/*"
# Validator role - already has full access to processed bucket
```

## Testing Strategy

### Unit Tests

1. Test S3 helper functions with mocked boto3 client
2. Test each handler's S3 save/load logic with mocked S3 operations
3. Test error handling for S3 failures (AccessDenied, NoSuchKey, etc.)

### Integration Tests

1. Test extraction → detection data flow with real S3
2. Test detection → parsing data flow with real S3
3. Test parsing → validation data flow with real S3
4. Test end-to-end pipeline with real S3 and verify all intermediate files are created

### Manual Testing

1. Run `python scripts/test_pipeline_manual.py` and verify it completes successfully
2. Inspect S3 bucket to verify intermediate files are created at each stage
3. Download and inspect intermediate JSON files to verify data structure
4. Verify CloudWatch logs show successful S3 operations

## Rollout Plan

1. **Phase 1:** Implement S3 helper module and unit tests
2. **Phase 2:** Update extraction handler and test with manual script
3. **Phase 3:** Update detection handler and test extraction → detection flow
4. **Phase 4:** Update parsing handler and test detection → parsing flow
5. **Phase 5:** Update validation handler and test parsing → validation flow
6. **Phase 6:** Update IAM policies in CloudFormation template
7. **Phase 7:** Deploy all changes and run end-to-end test
8. **Phase 8:** Monitor production pipeline for any issues

## Risks and Mitigations

| Risk                                            | Impact | Mitigation                                                           |
| ----------------------------------------------- | ------ | -------------------------------------------------------------------- |
| S3 costs increase due to intermediate files     | Low    | Implement lifecycle policy to delete intermediate files after 7 days |
| Large documents create large intermediate files | Medium | Consider implementing compression or pagination for very large files |
| S3 operations add latency to pipeline           | Low    | S3 operations are fast; monitor CloudWatch metrics                   |
| IAM permission errors after deployment          | High   | Test IAM policies in dev environment before production deployment    |

## Success Metrics

- Pipeline completes end-to-end without "No text blocks provided" errors
- All intermediate files are created in S3 at expected locations
- CloudWatch logs show successful S3 save/load operations
- No IAM permission errors in CloudWatch logs
- Pipeline execution time increases by less than 10% (S3 operations are fast)
