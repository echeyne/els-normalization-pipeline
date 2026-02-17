# Requirements Document: Pipeline S3 Integration Fix

## Introduction

This spec addresses critical implementation gaps in the ELS normalization pipeline where Lambda handlers have placeholder code for S3 data persistence. Currently, the extraction handler extracts text blocks but doesn't save them to S3, and the detection handler expects to load blocks from S3 but receives an empty list. This causes the pipeline to fail at the structure detection stage with "No text blocks provided" even though extraction succeeds.

## Problem Statement

The pipeline currently fails after successful text extraction because:

1. The `extraction_handler` extracts 19,631 blocks from 70 pages but doesn't persist them to S3
2. The `detection_handler` expects to load blocks from S3 but has placeholder code that passes an empty list
3. Similar gaps exist in subsequent stages (parser, validator) where data should be persisted and loaded from S3

## Glossary

- **Intermediate_Data**: JSON data passed between pipeline stages (extracted blocks, detected elements, parsed hierarchy, validated records)
- **S3_Intermediate_Bucket**: S3 bucket for storing intermediate pipeline data (could be the processed bucket with a different prefix)
- **Stage_Output_Key**: S3 key pattern for intermediate data: `{country}/{state}/{year}/intermediate/{stage_name}/{run_id}.json`
- **Extraction_Output**: JSON containing text blocks from Textract with metadata (page numbers, confidence, geometry)
- **Detection_Output**: JSON containing detected structure elements with hierarchy levels and confidence scores
- **Parsing_Output**: JSON containing the normalized hierarchy tree before validation
- **Validation_Output**: The final Canonical_JSON records ready for persistence

## Requirements

### Requirement 1: Text Extraction S3 Persistence

**User Story:** As a pipeline developer, I want the extraction handler to save extracted text blocks to S3, so that the detection handler can load and process them.

#### Acceptance Criteria

1.1. WHEN the extraction handler successfully extracts text blocks, IT SHALL serialize the blocks to JSON and save to S3 at `{country}/{state}/{year}/intermediate/extraction/{run_id}.json`

1.2. THE extraction output JSON SHALL include:

- `blocks`: Array of text block objects from Textract
- `total_pages`: Total number of pages processed
- `total_blocks`: Total number of blocks extracted
- `extraction_timestamp`: ISO 8601 timestamp of extraction
- `source_s3_key`: The S3 key of the source document
- `source_version_id`: The S3 version ID of the source document

1.3. WHEN saving to S3, THE extraction handler SHALL use the processed bucket (`ELS_PROCESSED_BUCKET`) with the intermediate prefix

1.4. THE extraction handler SHALL return the S3 key of the saved extraction output in the `output_artifact` field

1.5. IF S3 save fails, THE extraction handler SHALL return an error status with a descriptive error message

### Requirement 2: Structure Detection S3 Loading and Persistence

**User Story:** As a pipeline developer, I want the detection handler to load extraction output from S3 and save detection results to S3, so that the parser can process detected elements.

#### Acceptance Criteria

2.1. WHEN the detection handler receives an `output_artifact` S3 key, IT SHALL load the extraction output JSON from S3

2.2. THE detection handler SHALL extract the `blocks` array from the loaded JSON and pass it to the `detect_structure` function

2.3. WHEN structure detection completes successfully, THE detection handler SHALL serialize the detection results to JSON and save to S3 at `{country}/{state}/{year}/intermediate/detection/{run_id}.json`

2.4. THE detection output JSON SHALL include:

- `elements`: Array of detected structure elements with hierarchy levels
- `review_count`: Number of elements flagged for review (confidence < 0.7)
- `detection_timestamp`: ISO 8601 timestamp of detection
- `source_extraction_key`: The S3 key of the extraction output used as input

2.5. THE detection handler SHALL return the S3 key of the saved detection output in the `output_artifact` field

2.6. IF S3 load fails, THE detection handler SHALL return an error status with message "Failed to load extraction output from S3: {key}"

2.7. IF S3 save fails, THE detection handler SHALL return an error status with a descriptive error message

### Requirement 3: Hierarchy Parsing S3 Loading and Persistence

**User Story:** As a pipeline developer, I want the parsing handler to load detection output from S3 and save parsed hierarchy to S3, so that the validator can process normalized records.

#### Acceptance Criteria

3.1. WHEN the parsing handler receives an `output_artifact` S3 key, IT SHALL load the detection output JSON from S3

3.2. THE parsing handler SHALL extract the `elements` array from the loaded JSON and pass it to the `parse_hierarchy` function

3.3. WHEN hierarchy parsing completes successfully, THE parsing handler SHALL serialize the parsing results to JSON and save to S3 at `{country}/{state}/{year}/intermediate/parsing/{run_id}.json`

3.4. THE parsing output JSON SHALL include:

- `indicators`: Array of normalized indicator objects with full hierarchy paths
- `total_indicators`: Total number of indicators parsed
- `parsing_timestamp`: ISO 8601 timestamp of parsing
- `source_detection_key`: The S3 key of the detection output used as input

3.5. THE parsing handler SHALL return the S3 key of the saved parsing output in the `output_artifact` field

3.6. IF S3 load fails, THE parsing handler SHALL return an error status with message "Failed to load detection output from S3: {key}"

3.7. IF S3 save fails, THE parsing handler SHALL return an error status with a descriptive error message

### Requirement 4: Validation S3 Loading and Persistence

**User Story:** As a pipeline developer, I want the validation handler to load parsing output from S3 and save validated records to S3, so that the persistence handler can store them in the database.

#### Acceptance Criteria

4.1. WHEN the validation handler receives an `output_artifact` S3 key, IT SHALL load the parsing output JSON from S3

4.2. THE validation handler SHALL extract the `indicators` array from the loaded JSON and validate each indicator

4.3. WHEN validation completes successfully, THE validation handler SHALL save each validated Canonical_JSON record to S3 at `{country}/{state}/{year}/{standard_id}.json`

4.4. THE validation handler SHALL also save a summary JSON to S3 at `{country}/{state}/{year}/intermediate/validation/{run_id}.json` containing:

- `validated_records`: Array of S3 keys for saved Canonical_JSON records
- `total_validated`: Total number of records validated and saved
- `validation_errors`: Array of validation errors (if any)
- `validation_timestamp`: ISO 8601 timestamp of validation

4.5. THE validation handler SHALL return the S3 key of the validation summary in the `output_artifact` field

4.6. IF S3 load fails, THE validation handler SHALL return an error status with message "Failed to load parsing output from S3: {key}"

4.7. IF S3 save fails for any record, THE validation handler SHALL log the error but continue processing remaining records

### Requirement 5: S3 Helper Functions

**User Story:** As a pipeline developer, I want reusable helper functions for S3 operations, so that all handlers use consistent patterns for loading and saving data.

#### Acceptance Criteria

5.1. THE pipeline SHALL provide a helper function `save_json_to_s3(data: dict, bucket: str, key: str) -> None` that serializes and saves JSON to S3

5.2. THE pipeline SHALL provide a helper function `load_json_from_s3(bucket: str, key: str) -> dict` that loads and deserializes JSON from S3

5.3. THE helper functions SHALL handle boto3 ClientError exceptions and raise descriptive errors

5.4. THE helper functions SHALL use the AWS region from Config.AWS_REGION

5.5. THE save helper SHALL use `json.dumps()` with `indent=2` for readable output

5.6. THE load helper SHALL use `json.loads()` to deserialize the S3 object body

### Requirement 6: IAM Permissions

**User Story:** As a DevOps engineer, I want Lambda functions to have appropriate S3 permissions, so that they can read and write intermediate data.

#### Acceptance Criteria

6.1. THE TextExtractor Lambda role SHALL have `s3:PutObject` permission on the processed bucket with prefix `*/intermediate/extraction/*`

6.2. THE StructureDetector Lambda role SHALL have `s3:GetObject` permission on the processed bucket with prefix `*/intermediate/extraction/*`

6.3. THE StructureDetector Lambda role SHALL have `s3:PutObject` permission on the processed bucket with prefix `*/intermediate/detection/*`

6.4. THE HierarchyParser Lambda role SHALL have `s3:GetObject` permission on the processed bucket with prefix `*/intermediate/detection/*`

6.5. THE HierarchyParser Lambda role SHALL have `s3:PutObject` permission on the processed bucket with prefix `*/intermediate/parsing/*`

6.6. THE Validator Lambda role SHALL have `s3:GetObject` permission on the processed bucket with prefix `*/intermediate/parsing/*`

6.7. THE Validator Lambda role SHALL have `s3:PutObject` permission on the processed bucket for both intermediate validation summaries and final Canonical_JSON records

### Requirement 7: Error Handling and Logging

**User Story:** As a pipeline operator, I want clear error messages and logs when S3 operations fail, so that I can quickly diagnose and fix issues.

#### Acceptance Criteria

7.1. WHEN an S3 load operation fails, THE handler SHALL log the error with the S3 key, bucket, and error message

7.2. WHEN an S3 save operation fails, THE handler SHALL log the error with the S3 key, bucket, and error message

7.3. THE error logs SHALL include the run_id for correlation with pipeline executions

7.4. IF an S3 operation fails due to AccessDenied, THE error message SHALL indicate that IAM permissions may need to be updated

7.5. IF an S3 operation fails due to NoSuchKey, THE error message SHALL indicate that the expected intermediate data was not found

## Out of Scope

- Implementing data compression for intermediate files (can be added later if needed)
- Implementing S3 lifecycle policies for intermediate data cleanup (can be added later)
- Implementing retry logic for S3 operations (boto3 handles this automatically)
- Modifying the core extraction, detection, parsing, or validation logic (only fixing S3 integration)

## Success Criteria

The pipeline S3 integration fix is successful when:

1. The extraction handler saves blocks to S3 and the detection handler successfully loads them
2. The detection handler saves elements to S3 and the parser successfully loads them
3. The parser saves indicators to S3 and the validator successfully loads them
4. The validator saves Canonical_JSON records to S3 in the correct location
5. The pipeline completes end-to-end without "No text blocks provided" or similar errors
6. All intermediate data is properly persisted and can be inspected for debugging
