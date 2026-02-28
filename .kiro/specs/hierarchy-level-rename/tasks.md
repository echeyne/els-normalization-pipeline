# Implementation Plan: Hierarchy Level Rename

## Overview

Systematic rename of hierarchy levels from Domain → Subdomain → Strand → Indicator to Domain → Strand → Sub-strand → Indicator across the entire ELS pipeline codebase. Changes are ordered to avoid name collisions: rename old `strand` → `sub_strand` first, then old `subdomain` → `strand`.

## Tasks

- [x] 1. Update core data models in `src/els_pipeline/models.py`
  - [x] 1.1 Rename HierarchyLevelEnum: SUBDOMAIN="subdomain" → STRAND="strand", STRAND="strand" → SUB_STRAND="sub_strand"
    - Careful ordering: first rename old STRAND to SUB_STRAND, then rename old SUBDOMAIN to STRAND
    - _Requirements: 1.1, 1.2_
  - [x] 1.2 Rename NormalizedStandard fields: `subdomain` → `strand`, `strand` → `sub_strand`
    - Both fields remain Optional[HierarchyLevel]
    - _Requirements: 2.1, 2.2, 2.3_
  - [x] 1.3 Rename RecommendationRequest field: `subdomain_code` → `strand_code`
    - _Requirements: 3.1_

- [x] 2. Update parser in `src/els_pipeline/parser.py`
  - [x] 2.1 Update `normalize_hierarchy_mapping()` to return new enum values
    - 3 levels: index 1 → HierarchyLevelEnum.STRAND (was SUBDOMAIN)
    - 4+ levels: index 1 → HierarchyLevelEnum.STRAND, index 2 → HierarchyLevelEnum.SUB_STRAND
    - _Requirements: 4.1, 4.2, 4.3_
  - [x] 2.2 Update `assign_canonical_levels()`, `build_hierarchy_tree()`, `extract_standards_from_tree()`, and `parse_hierarchy()`
    - Rename all variable names: `subdomain` → `strand`, `strand` → `sub_strand`, `current_subdomain` → `current_strand`, `current_strand` → `current_sub_strand`
    - Rename dict keys: `"subdomains"` → `"strands"`, `"strands"` → `"sub_strands"`
    - Update all HierarchyLevelEnum references: SUBDOMAIN → STRAND, STRAND → SUB_STRAND
    - Update NormalizedStandard constructor calls: `subdomain=` → `strand=`, `strand=` → `sub_strand=`
    - _Requirements: 4.4_

- [x] 3. Update detector in `src/els_pipeline/detector.py`
  - [x] 3.1 Update `build_detection_prompt()` LLM prompt text
    - Replace all "subdomain" references with "strand" and "strand" references with "sub_strand" in hierarchy level descriptions
    - Update JSON output format to `"level": "domain|strand|sub_strand|indicator"`
    - Update all example mappings to use new level names
    - Update confidence guidance text
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 4. Update validator in `src/els_pipeline/validator.py`
  - [x] 4.1 Update CANONICAL_SCHEMA dict: rename `"subdomain"` key to `"strand"`, `"strand"` key to `"sub_strand"`
    - _Requirements: 6.1_
  - [x] 4.2 Update `_validate_schema()` function: all field path references from `standard.subdomain` to `standard.strand`, `standard.strand` to `standard.sub_strand`
    - _Requirements: 6.4_
  - [x] 4.3 Update `serialize_record()`: output `"strand"` and `"sub_strand"` keys, read from `standard.strand` and `standard.sub_strand`
    - _Requirements: 6.2_
  - [x] 4.4 Update `deserialize_record()`: read `"strand"` and `"sub_strand"` keys from JSON, pass to `strand=` and `sub_strand=` constructor args
    - _Requirements: 6.3_

- [x] 5. Update database layer in `src/els_pipeline/db.py`
  - [x] 5.1 Update `persist_standard()`: insert into `strands` table (was `subdomains`), `sub_strands` table (was `strands`), update column references in `indicators` insert
    - _Requirements: 7.3_
  - [x] 5.2 Update `get_indicators_by_country_state()`: rename parameter `subdomain_code` → `strand_code`, update table aliases and column names in SQL query
    - _Requirements: 7.4_
  - [x] 5.3 Update `query_similar_indicators()`: update any table joins/aliases if applicable
    - _Requirements: 7.5_

- [x] 6. Update database migration in `infra/migrations/001_initial_schema.sql`
  - [x] 6.1 Rename `subdomains` table to `strands`, `strands` table to `sub_strands`
    - Update all foreign key references, column names, and unique constraints
    - `sub_strands.strand_id` references `strands(id)` (was `strands.subdomain_id` references `subdomains(id)`)
    - `indicators`: rename `subdomain_id` → `strand_id`, `strand_id` → `sub_strand_id`
    - _Requirements: 7.1, 7.2_

- [x] 7. Checkpoint - Verify core pipeline code compiles
  - Ensure all source files in `src/els_pipeline/` have no import errors or type issues
  - Ensure all tests pass, ask the user if questions arise.

- [-] 8. Update property tests
  - [x] 8.1 Update `tests/property/test_detection_props.py`: replace SUBDOMAIN → STRAND, STRAND → SUB_STRAND in strategies and assertions
    - _Requirements: 8.1_
  - [x] 8.2 Update `tests/property/test_parser_props.py`: rename hierarchy level references, update strategy names and generated data
    - _Requirements: 8.1, 8.2_
  - [x] 8.3 Update `tests/property/test_validator_props.py`: rename `subdomain` → `strand`, `strand` → `sub_strand` in strategies and assertions
    - _Requirements: 8.2, 8.3_
  - [x] 8.4 Update `tests/property/test_data_model_props.py`, `test_query_props.py`, `test_recommendation_props.py`: rename any hierarchy references
    - _Requirements: 8.1_

- [x] 9. Update integration tests
  - [x] 9.1 Update `tests/integration/test_parser_integration.py`: rename SUBDOMAIN → STRAND, subdomain → strand in all test data and assertions
    - _Requirements: 8.1, 8.2_
  - [x] 9.2 Update `tests/integration/test_validator_integration.py`: rename field names in sample data and assertions
    - _Requirements: 8.2, 8.3_
  - [x] 9.3 Update `tests/integration/test_detector_integration.py`: rename level values in mock LLM responses
    - _Requirements: 8.1_
  - [x] 9.4 Update `tests/integration/test_db_integration.py`: rename table/column references and field names
    - _Requirements: 8.4_
  - [x] 9.5 Update `tests/integration/test_pipeline_e2e.py`: rename hierarchy fields in test data
    - _Requirements: 8.2_
  - [x] 9.6 Update `tests/unit/test_db.py`: rename any hierarchy references
    - _Requirements: 8.4_

- [x] 10. Update manual test scripts
  - [x] 10.1 Update `scripts/test_detector_manual.py`: rename level names in output labels and summary
    - _Requirements: 9.1_
  - [x] 10.2 Update `scripts/test_parser_manual.py`: rename field names in sample data, print statements, and assertions
    - _Requirements: 9.1_
  - [x] 10.3 Update `scripts/test_validator_manual.py`: rename field names in sample data and print statements
    - _Requirements: 9.1_
  - [x] 10.4 Update `scripts/test_db_manual.py`: rename field names in sample data and SQL cleanup queries
    - _Requirements: 9.1_
  - [x] 10.5 Update `scripts/download_and_inspect_validation_output.py`: rename "Subdomain" → "Strand", "Strand" → "Sub-strand" in print output
    - _Requirements: 9.2_

- [x] 11. Update documentation
  - [x] 11.1 Update `documentation/AWS_TESTING.md`: rename hierarchy level references
    - _Requirements: 9.3_
  - [x] 11.2 Update `documentation/COMPREHENSIVE_TESTING.md`: rename hierarchy level references
    - _Requirements: 9.3_

- [x] 12. Final checkpoint - Run all tests and verify no old references remain
  - Run full test suite to verify all tests pass
  - Run `grep -r "subdomain\|SUBDOMAIN" src/ tests/ scripts/ infra/` to confirm no old references remain (excluding comments)
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- The rename order within each file matters: rename old `strand` → `sub_strand` first, then old `subdomain` → `strand` to avoid collisions.
- The database migration file (001_initial_schema.sql) is the initial schema DDL, so it's updated in place rather than creating an incremental migration.
- Existing property tests in `tests/property/` already cover serialization round-trips and depth normalization — they just need the names updated.
- No new functionality is being added; this is purely a terminology rename for consistency.
