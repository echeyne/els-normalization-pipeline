# Implementation Tasks: Pipeline S3 Integration Fix

## Phase 1: S3 Helper Module

- [x] 1. Create S3 helper module
  - [x] 1.1 Create `src/els_pipeline/s3_helpers.py` file
  - [x] 1.2 Implement `save_json_to_s3(data, bucket, key)` function
  - [x] 1.3 Implement `load_json_from_s3(bucket, key)` function
  - [x] 1.4 Implement `construct_intermediate_key(country, state, year, stage, run_id)` function
  - [x] 1.5 Add error handling for ClientError exceptions
  - [x] 1.6 Add logging for all S3 operations

- [x] 2. Write unit tests for S3 helpers
  - [x] 2.1 Create `tests/unit/test_s3_helpers.py`
  - [x] 2.2 Test `save_json_to_s3` with mocked boto3
  - [x] 2.3 Test `load_json_from_s3` with mocked boto3
  - [x] 2.4 Test `construct_intermediate_key` with various inputs
  - [x] 2.5 Test error handling for S3 failures
  - [x] 2.6 Run unit tests and verify they pass

## Phase 2: Update Data Models

- [x] 3. Update extraction result model
  - [x] 3.1 Add `blocks` field to `ExtractionResult` dataclass in `src/els_pipeline/models.py`
  - [x] 3.2 Update `extract_text` function in `src/els_pipeline/extractor.py` to populate blocks
  - [x] 3.3 Verify extractor returns blocks in result

- [x] 4. Update detection result model
  - [x] 4.1 Add `elements` field to `DetectionResult` dataclass in `src/els_pipeline/models.py`
  - [x] 4.2 Update `detect_structure` function in `src/els_pipeline/detector.py` to populate elements
  - [x] 4.3 Verify detector returns elements in result

- [x] 5. Update parsing result model
  - [x] 5.1 Add `indicators` field to `ParsingResult` dataclass in `src/els_pipeline/models.py`
  - [x] 5.2 Update `parse_hierarchy` function in `src/els_pipeline/parser.py` to populate indicators
  - [x] 5.3 Verify parser returns indicators in result

## Phase 3: Update Extraction Handler

- [x] 6. Implement extraction S3 persistence
  - [x] 6.1 Import S3 helpers in `src/els_pipeline/handlers.py`
  - [x] 6.2 Update `extraction_handler` to prepare extraction output JSON
  - [x] 6.3 Update `extraction_handler` to save extraction output to S3
  - [x] 6.4 Update `extraction_handler` to return S3 key in `output_artifact`
  - [x] 6.5 Add error handling for S3 save failures
  - [x] 6.6 Add logging for S3 operations

- [x] 7. Test extraction handler
  - [x] 7.1 Package and deploy Lambda functions
  - [x] 7.2 Run `python scripts/test_pipeline_manual.py`
  - [x] 7.3 Verify extraction stage completes successfully
  - [x] 7.4 Verify extraction output JSON is saved to S3
  - [x] 7.5 Download and inspect extraction output JSON

## Phase 4: Update Detection Handler

- [x] 8. Implement detection S3 loading and persistence
  - [x] 8.1 Update `detection_handler` to load extraction output from S3
  - [x] 8.2 Update `detection_handler` to extract blocks from loaded JSON
  - [x] 8.3 Update `detection_handler` to pass blocks to `detect_structure`
  - [x] 8.4 Update `detection_handler` to prepare detection output JSON
  - [x] 8.5 Update `detection_handler` to save detection output to S3
  - [x] 8.6 Update `detection_handler` to return S3 key in `output_artifact`
  - [x] 8.7 Add error handling for S3 load and save failures
  - [x] 8.8 Add logging for S3 operations

- [x] 9. Test detection handler
  - [x] 9.1 Package and deploy Lambda functions
  - [x] 9.2 Run `python scripts/test_pipeline_manual.py`
  - [x] 9.3 Verify detection stage completes successfully
  - [x] 9.4 Verify detection output JSON is saved to S3
  - [x] 9.5 Download and inspect detection output JSON
  - [x] 9.6 Verify blocks were loaded from extraction output

## Phase 5: Update Parsing Handler

- [x] 10. Implement parsing S3 loading and persistence
  - [x] 10.1 Update `parsing_handler` to load detection output from S3
  - [x] 10.2 Update `parsing_handler` to extract elements from loaded JSON
  - [x] 10.3 Update `parsing_handler` to pass elements to `parse_hierarchy`
  - [x] 10.4 Update `parsing_handler` to prepare parsing output JSON
  - [x] 10.5 Update `parsing_handler` to save parsing output to S3
  - [x] 10.6 Update `parsing_handler` to return S3 key in `output_artifact`
  - [x] 10.7 Add error handling for S3 load and save failures
  - [x] 10.8 Add logging for S3 operations

- [x] 11. Test parsing handler
  - [x] 11.1 Package and deploy Lambda functions
  - [x] 11.2 Run `python scripts/test_pipeline_manual.py`
  - [x] 11.3 Verify parsing stage completes successfully
  - [x] 11.4 Verify parsing output JSON is saved to S3
  - [x] 11.5 Download and inspect parsing output JSON
  - [x] 11.6 Verify elements were loaded from detection output

## Phase 6: Update Validation Handler

- [x] 12. Implement validation S3 loading and persistence
  - [x] 12.1 Update `validation_handler` to load parsing output from S3
  - [x] 12.2 Update `validation_handler` to extract indicators from loaded JSON
  - [x] 12.3 Update `validation_handler` to validate each indicator
  - [x] 12.4 Update `validation_handler` to save each canonical record to S3
  - [x] 12.5 Update `validation_handler` to prepare validation summary JSON
  - [x] 12.6 Update `validation_handler` to save validation summary to S3
  - [x] 12.7 Update `validation_handler` to return S3 key in `output_artifact`
  - [x] 12.8 Add error handling for S3 load and save failures
  - [x] 12.9 Add logging for S3 operations

- [x] 13. Test validation handler
  - [x] 13.1 Package and deploy Lambda functions
  - [x] 13.2 Run `python scripts/test_pipeline_manual.py`
  - [x] 13.3 Verify validation stage completes successfully
  - [x] 13.4 Verify validation summary JSON is saved to S3
  - [x] 13.5 Verify canonical record JSONs are saved to S3
  - [x] 13.6 Download and inspect validation output and canonical records
  - [x] 13.7 Verify indicators were loaded from parsing output

## Phase 7: Update IAM Policies

- [x] 14. Update CloudFormation template with S3 permissions
  - [x] 14.1 Add S3 PutObject permission for TextExtractor role (extraction output)
  - [x] 14.2 Add S3 GetObject permission for StructureDetector role (extraction input)
  - [x] 14.3 Add S3 PutObject permission for StructureDetector role (detection output)
  - [x] 14.4 Add S3 GetObject permission for HierarchyParser role (detection input)
  - [x] 14.5 Add S3 PutObject permission for HierarchyParser role (parsing output)
  - [x] 14.6 Add S3 GetObject permission for Validator role (parsing input)
  - [x] 14.7 Verify Validator role already has PutObject for canonical records

- [x] 15. Deploy IAM policy updates
  - [x] 15.1 Validate CloudFormation template
  - [x] 15.2 Deploy CloudFormation stack update
  - [x] 15.3 Verify stack update completes successfully
  - [x] 15.4 Verify Lambda roles have updated permissions

## Phase 8: End-to-End Testing

- [x] 16. Run end-to-end pipeline test
  - [x] 16.1 Run `python scripts/test_pipeline_manual.py`
  - [x] 16.2 Verify pipeline completes all stages successfully
  - [x] 16.3 Verify no "No text blocks provided" errors
  - [x] 16.4 Verify all intermediate files are created in S3
  - [x] 16.5 Verify final canonical records are created in S3
  - [x] 16.6 Check CloudWatch logs for any errors or warnings

- [x] 17. Verify S3 bucket structure
  - [x] 17.1 List S3 objects in processed bucket
  - [x] 17.2 Verify intermediate/extraction/{run_id}.json exists
  - [x] 17.3 Verify intermediate/detection/{run_id}.json exists
  - [x] 17.4 Verify intermediate/parsing/{run_id}.json exists
  - [x] 17.5 Verify intermediate/validation/{run_id}.json exists
  - [x] 17.6 Verify {standard_id}.json files exist for canonical records

- [x] 18. Inspect intermediate data
  - [x] 18.1 Download extraction output and verify blocks structure
  - [x] 18.2 Download detection output and verify elements structure
  - [x] 18.3 Download parsing output and verify indicators structure
  - [x] 18.4 Download validation summary and verify validated records list
  - [x] 18.5 Download a canonical record and verify schema compliance

## Phase 9: Documentation and Cleanup

- [x] 19. Update documentation
  - [x] 19.1 Update `documentation/AWS_TESTING.md` with S3 integration details
  - [x] 19.2 Update `documentation/COMPREHENSIVE_TESTING.md` with new test procedures
  - [x] 19.3 Document S3 bucket structure and intermediate file formats
  - [x] 19.4 Add troubleshooting guide for S3-related errors

- [x] 20. Clean up temporary files
  - [x] 20.1 Remove `update_state_machine.py` (no longer needed)
  - [x] 20.2 Update `.gitignore` to exclude intermediate test files
  - [x] 20.3 Commit all changes to git

## Success Criteria

- [ ] All tasks completed
- [ ] Pipeline runs end-to-end without errors
- [ ] All intermediate files are created in S3
- [ ] CloudWatch logs show successful S3 operations
- [ ] No IAM permission errors
- [ ] Documentation is updated
