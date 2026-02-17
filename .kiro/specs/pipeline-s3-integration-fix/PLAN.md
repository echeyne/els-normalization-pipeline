# Pipeline S3 Integration Fix - Implementation Plan

## Executive Summary

The ELS normalization pipeline currently fails at the structure detection stage because Lambda handlers have placeholder code for S3 data persistence. This spec provides a comprehensive plan to implement S3 save/load operations for all intermediate pipeline data.

## Problem

**Current State:**

- Extraction handler extracts 19,631 blocks but doesn't save them to S3
- Detection handler expects blocks from S3 but receives an empty list
- Pipeline fails with "No text blocks provided" error
- Similar gaps exist in parsing and validation stages

**Root Cause:**
Handlers have placeholder comments like "In production, this would write to S3" but no actual implementation.

## Solution Overview

Implement S3 persistence layer for all pipeline stages:

```
Extraction → [S3: blocks] → Detection → [S3: elements] → Parsing → [S3: indicators] → Validation → [S3: records]
```

## Key Components

### 1. S3 Helper Module (`s3_helpers.py`)

- `save_json_to_s3()` - Serialize and save JSON to S3
- `load_json_from_s3()` - Load and deserialize JSON from S3
- `construct_intermediate_key()` - Build S3 keys for intermediate data

### 2. Handler Updates

Each handler will:

- Load input data from S3 (using previous stage's output_artifact)
- Process the data
- Save output data to S3
- Return the S3 key in output_artifact

### 3. Data Model Updates

Add fields to result dataclasses:

- `ExtractionResult.blocks` - Textract blocks
- `DetectionResult.elements` - Detected structure elements
- `ParsingResult.indicators` - Parsed indicators

### 4. IAM Policy Updates

Grant Lambda roles permissions to read/write intermediate data in S3.

## S3 Bucket Structure

```
els-processed-json-{env}-{account}/
├── US/CA/2021/
│   ├── intermediate/
│   │   ├── extraction/
│   │   │   └── pipeline-US-CA-2021-abc123.json
│   │   ├── detection/
│   │   │   └── pipeline-US-CA-2021-abc123.json
│   │   ├── parsing/
│   │   │   └── pipeline-US-CA-2021-abc123.json
│   │   └── validation/
│   │       └── pipeline-US-CA-2021-abc123.json
│   └── US-CA-2021-LLD-1.2.json  (canonical records)
```

## Implementation Phases

### Phase 1: Foundation (Tasks 1-2)

- Create S3 helper module
- Write unit tests

### Phase 2: Data Models (Tasks 3-5)

- Update result dataclasses
- Update core functions to populate new fields

### Phase 3: Extraction (Tasks 6-7)

- Implement S3 save in extraction handler
- Test and verify

### Phase 4: Detection (Tasks 8-9)

- Implement S3 load/save in detection handler
- Test and verify

### Phase 5: Parsing (Tasks 10-11)

- Implement S3 load/save in parsing handler
- Test and verify

### Phase 6: Validation (Tasks 12-13)

- Implement S3 load/save in validation handler
- Test and verify

### Phase 7: IAM (Tasks 14-15)

- Update CloudFormation template
- Deploy policy updates

### Phase 8: Testing (Tasks 16-18)

- Run end-to-end tests
- Verify S3 structure
- Inspect intermediate data

### Phase 9: Documentation (Tasks 19-20)

- Update docs
- Clean up

## Testing Strategy

### Unit Tests

- Mock boto3 S3 operations
- Test error handling
- Test helper functions

### Integration Tests

- Test each stage with real S3
- Verify data flow between stages

### Manual Testing

- Run `python scripts/test_pipeline_manual.py`
- Inspect S3 bucket contents
- Review CloudWatch logs

## Success Criteria

✅ Pipeline completes end-to-end without errors
✅ All intermediate files created in S3
✅ CloudWatch logs show successful S3 operations
✅ No IAM permission errors
✅ Documentation updated

## Risks and Mitigations

| Risk              | Mitigation                                       |
| ----------------- | ------------------------------------------------ |
| S3 costs increase | Implement lifecycle policy (delete after 7 days) |
| Large files       | Consider compression if needed                   |
| IAM errors        | Test in dev before production                    |
| Latency increase  | S3 operations are fast; monitor metrics          |

## Timeline Estimate

- Phase 1-2 (Foundation): 2-3 hours
- Phase 3-6 (Handlers): 4-6 hours
- Phase 7 (IAM): 1 hour
- Phase 8 (Testing): 2-3 hours
- Phase 9 (Docs): 1 hour

**Total: 10-14 hours**

## Next Steps

1. Review and approve this spec
2. Start with Phase 1: Create S3 helper module
3. Proceed through phases sequentially
4. Test after each phase
5. Deploy and verify end-to-end

## Files to Create/Modify

**New Files:**

- `src/els_pipeline/s3_helpers.py`
- `tests/unit/test_s3_helpers.py`

**Modified Files:**

- `src/els_pipeline/handlers.py` (all handlers)
- `src/els_pipeline/models.py` (result dataclasses)
- `src/els_pipeline/extractor.py` (return blocks)
- `src/els_pipeline/detector.py` (return elements)
- `src/els_pipeline/parser.py` (return indicators)
- `infra/template.yaml` (IAM policies)
- `documentation/AWS_TESTING.md`
- `documentation/COMPREHENSIVE_TESTING.md`

## Questions?

- Should we implement compression for large intermediate files?
- Should we add S3 lifecycle policies now or later?
- Do we need to support pagination for very large documents?

## Approval

- [ ] Requirements approved
- [ ] Design approved
- [ ] Ready to implement
