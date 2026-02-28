# Requirements Document

## Introduction

The ELS pipeline currently uses a 4-level hierarchy named Domain → Subdomain → Strand → Indicator. This feature renames the hierarchy levels to Domain → Strand → Sub-strand → Indicator. The rename affects all layers of the system: data models, enum values, LLM prompts, JSON schemas, database schema, SQL queries, serialization/deserialization logic, and all test files. The mapping is: "Subdomain" becomes "Strand", and "Strand" becomes "Sub-strand" (or `sub_strand` in code identifiers). "Domain" and "Indicator" remain unchanged. Depth-based normalization rules must also be updated so that 3-level documents map to Domain + Strand + Indicator and 2-level documents map to Domain + Indicator.

## Glossary

- **Pipeline**: The ELS normalization pipeline system that ingests, detects, parses, validates, persists, and embeds early learning standards.
- **HierarchyLevelEnum**: The Python enum in `models.py` that defines valid hierarchy level names.
- **NormalizedStandard**: The Pydantic data model representing a fully normalized standard with hierarchy levels.
- **Canonical_JSON**: The JSON format used for validated standard records stored in S3 and exchanged between pipeline stages.
- **Detector**: The pipeline module (`detector.py`) that uses an LLM to classify document elements into hierarchy levels.
- **Parser**: The pipeline module (`parser.py`) that assigns canonical hierarchy levels based on detected depth and builds the hierarchy tree.
- **Validator**: The pipeline module (`validator.py`) that validates Canonical_JSON records against a schema and handles serialization/deserialization.
- **DB_Layer**: The pipeline module (`db.py`) that persists standards, embeddings, and recommendations to Aurora PostgreSQL.
- **Migration**: The SQL schema file (`001_initial_schema.sql`) that defines database tables and constraints.

## Requirements

### Requirement 1: Rename Enum Values in HierarchyLevelEnum

**User Story:** As a developer, I want the HierarchyLevelEnum to use the new level names (STRAND, SUB_STRAND), so that the enum reflects the updated hierarchy terminology.

#### Acceptance Criteria

1. THE HierarchyLevelEnum SHALL define exactly four values: DOMAIN="domain", STRAND="strand", SUB_STRAND="sub_strand", and INDICATOR="indicator".
2. WHEN any pipeline module references a hierarchy level by enum name, THE Pipeline SHALL use STRAND in place of the former SUBDOMAIN and SUB_STRAND in place of the former STRAND.

### Requirement 2: Rename Fields in NormalizedStandard Data Model

**User Story:** As a developer, I want the NormalizedStandard model fields to match the new hierarchy names, so that the data model is consistent with the updated terminology.

#### Acceptance Criteria

1. THE NormalizedStandard model SHALL have fields named `domain`, `strand`, `sub_strand`, and `indicator` (replacing the former `subdomain` and `strand` fields).
2. THE NormalizedStandard `strand` field SHALL be Optional and represent the second hierarchy level (formerly `subdomain`).
3. THE NormalizedStandard `sub_strand` field SHALL be Optional and represent the third hierarchy level (formerly `strand`).

### Requirement 3: Update RecommendationRequest Data Model

**User Story:** As a developer, I want the RecommendationRequest model to use the new field names, so that API requests use consistent terminology.

#### Acceptance Criteria

1. THE RecommendationRequest model SHALL have a field named `strand_code` in place of the former `subdomain_code` field.

### Requirement 4: Update Depth-Based Normalization in Parser

**User Story:** As a developer, I want the parser's depth normalization to use the new level names, so that documents with varying hierarchy depths are correctly mapped.

#### Acceptance Criteria

1. WHEN the Parser detects 2 hierarchy levels, THE Parser SHALL map them to Domain (level 0) and Indicator (level 1), with strand and sub_strand set to None.
2. WHEN the Parser detects 3 hierarchy levels, THE Parser SHALL map them to Domain (level 0), Strand (level 1), and Indicator (level 2), with sub_strand set to None.
3. WHEN the Parser detects 4 or more hierarchy levels, THE Parser SHALL map them to Domain (level 0), Strand (level 1), Sub_strand (level 2), and Indicator (level 3).
4. THE Parser functions `build_hierarchy_tree` and `extract_standards_from_tree` SHALL use the field names `strand` and `sub_strand` in place of `subdomain` and `strand` respectively.

### Requirement 5: Update LLM Prompt in Detector

**User Story:** As a developer, I want the LLM detection prompt to describe the hierarchy using the new level names, so that the LLM classifies elements with the correct terminology.

#### Acceptance Criteria

1. THE Detector prompt SHALL describe the four hierarchy levels as: "domain" (depth 1), "strand" (depth 2), "sub_strand" (depth 3), and "indicator" (depth 4).
2. THE Detector prompt SHALL instruct the LLM to output `"level": "domain|strand|sub_strand|indicator"` in the JSON response.
3. THE Detector prompt examples SHALL use the new level names (strand instead of subdomain, sub_strand instead of strand).

### Requirement 6: Update Canonical JSON Schema in Validator

**User Story:** As a developer, I want the Canonical JSON schema and serialization logic to use the new field names, so that persisted records reflect the updated hierarchy.

#### Acceptance Criteria

1. THE Validator CANONICAL_SCHEMA SHALL define `strand` (formerly `subdomain`) and `sub_strand` (formerly `strand`) as optional fields under the `standard` object.
2. THE `serialize_record` function SHALL output `strand` and `sub_strand` keys in the Canonical_JSON instead of `subdomain` and `strand`.
3. THE `deserialize_record` function SHALL read `strand` and `sub_strand` keys from Canonical_JSON and map them to the corresponding NormalizedStandard fields.
4. THE `_validate_schema` function SHALL validate `strand` and `sub_strand` fields instead of `subdomain` and `strand`.

### Requirement 7: Update Database Schema and Queries

**User Story:** As a developer, I want the database tables and queries to use the new hierarchy names, so that the persistence layer is consistent with the rest of the pipeline.

#### Acceptance Criteria

1. THE Migration SHALL rename the `subdomains` table to `strands` and the `strands` table to `sub_strands`.
2. THE Migration SHALL update all foreign key references: `sub_strands.strand_id` SHALL reference `strands(id)`, and `indicators.strand_id` and `indicators.sub_strand_id` SHALL reference the renamed tables.
3. THE `persist_standard` function SHALL insert into `strands` (formerly `subdomains`) and `sub_strands` (formerly `strands`) tables.
4. THE `get_indicators_by_country_state` function SHALL accept a `strand_code` parameter instead of `subdomain_code` and join against the renamed tables.
5. THE `query_similar_indicators` function SHALL join against the renamed tables using the updated aliases.

### Requirement 8: Update All Test Files

**User Story:** As a developer, I want all test files to use the new hierarchy names, so that tests validate the renamed hierarchy correctly.

#### Acceptance Criteria

1. WHEN test files reference HierarchyLevelEnum values, THE test files SHALL use STRAND and SUB_STRAND instead of SUBDOMAIN and STRAND.
2. WHEN test files construct NormalizedStandard objects, THE test files SHALL use `strand` and `sub_strand` field names instead of `subdomain` and `strand`.
3. WHEN test files assert on hierarchy field names in serialized output, THE test files SHALL check for `strand` and `sub_strand` keys instead of `subdomain` and `strand`.
4. WHEN test files reference database table names or column names, THE test files SHALL use the renamed table and column names.

### Requirement 9: Update Scripts and Documentation

**User Story:** As a developer, I want scripts and documentation to reflect the new hierarchy names, so that all project artifacts are consistent.

#### Acceptance Criteria

1. THE manual test scripts (`test_detector_manual.py`, `test_parser_manual.py`, `test_validator_manual.py`, `test_db_manual.py`) SHALL use the new hierarchy level names in all output labels, assertions, and sample data.
2. THE `download_and_inspect_validation_output.py` script SHALL print "Strand" and "Sub-strand" instead of "Subdomain" and "Strand".
3. THE documentation files (`AWS_TESTING.md`, `COMPREHENSIVE_TESTING.md`) SHALL reference the new hierarchy level names.
