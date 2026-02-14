# Requirements Document

## Introduction

This feature defines a machine-readable, cross-state Early Learning Standards (ELS) normalization corpus. State Departments of Education publish early learning standards in varied formats (PDF, HTML) with inconsistent terminology and hierarchy depths. This pipeline ingests raw documents, extracts text, detects hierarchical structure via LLM-assisted parsing, normalizes to a canonical four-level hierarchy (Domain → Subdomain → Strand → Indicator), validates the output, generates embeddings for the lowest assessable unit, and stores everything in a versioned, queryable data store. The goal is a state-agnostic, age-band-aware corpus that supports future crosswalk mapping between states.

## Glossary

- **ELS_Corpus**: The complete collection of normalized early learning standards across all ingested states
- **Raw_Document**: An original PDF or HTML document published by a state Department of Education containing early learning standards
- **Text_Extractor**: The component responsible for converting raw documents (PDF, images, tables) into machine-readable text using AWS Textract
- **Structure_Detector**: The LLM-assisted component that identifies hierarchy levels, numbering patterns, heading levels, bullet structures, and table rows within extracted text
- **Hierarchy_Parser**: The component that assembles detected structure elements into a normalized four-level tree (Domain → Subdomain → Strand → Indicator)
- **Canonical_JSON**: The validated, normalized JSON representation of a single standard record conforming to the schema defined in this specification
- **Validator**: The component that checks Canonical_JSON records against the schema and business rules before persistence
- **Embedding_Generator**: The component that produces vector embeddings for indicator descriptions with contextual metadata
- **Domain**: The top level of the normalized hierarchy representing a broad developmental area (e.g., "Language and Literacy Development")
- **Subdomain**: The second level of the normalized hierarchy representing a narrower focus area within a Domain
- **Strand**: The third level of the normalized hierarchy representing a specific topic within a Subdomain
- **Indicator**: The lowest assessable unit in the hierarchy — one measurable child-facing skill statement
- **Age_Band**: A defined age range (e.g., "3-5", "0-3") to which a set of standards applies
- **Standard_ID**: A deterministic, unique identifier for each indicator following the pattern `{STATE}-{YEAR}-{DOMAIN_CODE}-{INDICATOR_CODE}`
- **Confidence_Score**: A numeric value (0.0–1.0) representing the Structure_Detector's certainty about a detected hierarchy element
- **Crosswalk**: A future mapping between equivalent or related indicators across different states (out of scope for this feature, but the schema must support it)
- **S3_Raw_Bucket**: The S3 bucket `els-raw-documents` storing original unmodified source documents
- **S3_Processed_Bucket**: The S3 bucket `els-processed-json` storing validated Canonical_JSON output
- **S3_Embeddings_Bucket**: The S3 bucket `els-embeddings` storing generated embedding records
- **Vector_Store**: Aurora PostgreSQL with pgvector extension used for storing and querying embeddings
- **Recommendation_Generator**: The LLM-assisted component that produces actionable, audience-specific (parent or teacher) recommendations based on indicators and their hierarchy context
- **Pipeline_Orchestrator**: The component that executes and coordinates the full pipeline stages in order, tracks status, and supports re-running individual stages

## Requirements

### Requirement 1: Raw Document Ingestion and Storage

**User Story:** As a data engineer, I want to store raw early learning standards documents in a versioned, organized manner, so that I can trace every processed record back to its original source.

#### Acceptance Criteria

1. WHEN a Raw_Document is uploaded, THE Raw_Document_Ingester SHALL store the document in S3_Raw_Bucket under the path `{state}/{year}/{filename}` with S3 versioning enabled
2. WHEN a Raw_Document is stored, THE Raw_Document_Ingester SHALL record metadata including state, version_year, source_url, publishing_agency, and upload_timestamp
3. IF a Raw_Document with the same state, year, and filename already exists, THEN THE Raw_Document_Ingester SHALL create a new S3 version rather than overwriting the existing object
4. WHEN a Raw_Document is stored, THE Raw_Document_Ingester SHALL validate that the file is a supported format (PDF or HTML) and reject unsupported formats with a descriptive error

### Requirement 2: Text Extraction

**User Story:** As a data engineer, I want to extract machine-readable text from PDF documents that contain tables, images, and mixed layouts, so that downstream components receive clean text for structure detection.

#### Acceptance Criteria

1. WHEN a Raw_Document in PDF format is submitted for extraction, THE Text_Extractor SHALL use AWS Textract to extract text content including text embedded in tables and images
2. WHEN extraction completes, THE Text_Extractor SHALL produce an ordered sequence of text blocks preserving the reading order of the original document
3. WHEN a text block originates from a table, THE Text_Extractor SHALL preserve row and column structure in the extracted output
4. WHEN extraction completes, THE Text_Extractor SHALL record the source page number for each extracted text block
5. IF text extraction fails or produces empty output for a document, THEN THE Text_Extractor SHALL log the failure with document identifiers and a descriptive error message

### Requirement 3: LLM-Assisted Structure Detection

**User Story:** As a data engineer, I want to detect the hierarchical structure (headings, numbering, bullets, table rows) within extracted text, so that I can map raw content to the normalized hierarchy.

#### Acceptance Criteria

1. WHEN extracted text blocks are submitted, THE Structure_Detector SHALL send structured chunks to an LLM via Amazon Bedrock to identify each element's hierarchy level, label, and content type
2. WHEN the LLM returns a classification, THE Structure_Detector SHALL include a Confidence_Score (0.0–1.0) for each detected element
3. WHEN the Structure_Detector classifies an element, THE Structure_Detector SHALL assign one of the following hierarchy levels: domain, subdomain, strand, or indicator
4. IF the Confidence_Score for a detected element falls below 0.7, THEN THE Structure_Detector SHALL flag the element for manual review rather than including it in automated output
5. WHEN processing a document, THE Structure_Detector SHALL detect heading levels, numbering patterns, bullet structures, and table rows as potential hierarchy elements

### Requirement 4: Hierarchy Parsing and Normalization

**User Story:** As a data engineer, I want to normalize varying state terminology and hierarchy depths into a consistent four-level structure, so that all states conform to a single queryable schema.

#### Acceptance Criteria

1. THE Hierarchy_Parser SHALL normalize all state-specific terminology (e.g., Topic, Goal, Benchmark, Competency) into the canonical four-level hierarchy: Domain → Subdomain → Strand → Indicator
2. WHEN a state document contains only two hierarchy levels, THE Hierarchy_Parser SHALL map the top level to Domain, the bottom level to Indicator, and set Subdomain and Strand to null
3. WHEN a state document contains three hierarchy levels, THE Hierarchy_Parser SHALL map the top level to Domain, the middle level to Subdomain, the bottom level to Indicator, and set Strand to null
4. WHEN a state document contains four or more hierarchy levels, THE Hierarchy_Parser SHALL map the top level to Domain, the second level to Subdomain, the third level to Strand, and the lowest assessable level to Indicator
5. THE Hierarchy_Parser SHALL generate a deterministic Standard_ID for each Indicator following the pattern `{STATE}-{YEAR}-{DOMAIN_CODE}-{INDICATOR_CODE}`
6. WHEN assembling the hierarchy tree, THE Hierarchy_Parser SHALL validate that every Indicator has exactly one parent path to a Domain (no orphaned indicators)

### Requirement 5: Canonical JSON Schema and Validation

**User Story:** As a data engineer, I want every processed standard record to conform to a strict schema, so that downstream consumers can rely on consistent data structure.

#### Acceptance Criteria

1. THE Validator SHALL enforce that every Canonical_JSON record contains the required top-level fields: state, document, standard, and metadata
2. THE Validator SHALL enforce that the document object contains: title, version_year, source_url, age_band, and publishing_agency
3. THE Validator SHALL enforce that the standard object contains: standard_id, domain (with code and name), and indicator (with code and description)
4. THE Validator SHALL allow subdomain and strand to be null when the source hierarchy has fewer than four levels
5. WHEN a Canonical_JSON record passes validation, THE Validator SHALL store the record in S3_Processed_Bucket under the path `{state}/{year}/{standard_id}.json`
6. IF a Canonical_JSON record fails validation, THEN THE Validator SHALL return all validation errors with field paths and descriptions
7. THE Validator SHALL enforce that standard_id values are unique within a given state and version_year combination
8. THE Validator SHALL serialize Canonical_JSON records to JSON and THE Validator SHALL deserialize JSON back to Canonical_JSON records (round-trip fidelity)

### Requirement 6: Embedding Generation

**User Story:** As a data scientist, I want vector embeddings generated for each indicator's description with contextual metadata, so that I can perform semantic similarity searches across states.

#### Acceptance Criteria

1. WHEN generating an embedding for an Indicator, THE Embedding_Generator SHALL construct the input text by concatenating: domain name, subdomain name (if present), strand name (if present), indicator description, and age band
2. WHEN an embedding is generated, THE Embedding_Generator SHALL use the Amazon Titan Embed Text v2 model via Amazon Bedrock
3. WHEN an embedding is generated, THE Embedding_Generator SHALL store an embedding record containing: indicator_id, state, vector, embedding_model identifier, embedding_version, and created_at timestamp
4. WHEN an embedding record is stored, THE Embedding_Generator SHALL store the record in S3_Embeddings_Bucket and persist the vector to the Vector_Store
5. IF the embedding model or version changes, THEN THE Embedding_Generator SHALL assign a new embedding_version and retain previous embedding records for traceability

### Requirement 7: Data Persistence and Querying

**User Story:** As a data consumer, I want normalized standards and embeddings stored in a queryable database with vector search capability, so that I can retrieve and compare standards across states.

#### Acceptance Criteria

1. THE Vector_Store SHALL use Aurora PostgreSQL with the pgvector extension to store indicator embeddings alongside relational standard data
2. WHEN a Canonical_JSON record is persisted, THE Vector_Store SHALL store the full normalized hierarchy (domain, subdomain, strand, indicator) in relational tables
3. WHEN a vector similarity query is executed, THE Vector_Store SHALL return matching indicators ranked by cosine similarity
4. THE Vector_Store SHALL support filtering query results by state, age_band, domain, and version_year
5. WHEN schema migrations are applied, THE Vector_Store SHALL use versioned migration scripts to maintain data integrity

### Requirement 8: Recommendation Generation for Parents and Teachers

**User Story:** As a parent or teacher, I want to receive actionable recommendations based on specific domains, subdomains, strands, and indicators, so that I can support a child's development with targeted activities and strategies.

#### Acceptance Criteria

1. WHEN a user requests recommendations for a given Indicator, THE Recommendation_Generator SHALL produce at least one parent-facing recommendation and at least one teacher-facing recommendation
2. WHEN generating a recommendation, THE Recommendation_Generator SHALL use the Indicator description, its parent hierarchy (Domain, Subdomain, Strand), and the Age_Band as context input to an LLM via Amazon Bedrock
3. WHEN a recommendation is generated, THE Recommendation_Generator SHALL include the target audience (parent or teacher), the linked indicator_id, a plain-language activity or strategy description, and the age band
4. WHEN recommendations are generated for a Domain or Subdomain level, THE Recommendation_Generator SHALL aggregate relevant Indicators under that level and produce holistic recommendations that span the grouped skills
5. IF the LLM returns a recommendation that does not reference a concrete, actionable activity, THEN THE Recommendation_Generator SHALL retry with a refined prompt specifying that the output must describe a specific activity or strategy
6. WHEN a recommendation is stored, THE Recommendation_Generator SHALL persist the recommendation record with a link to the source Indicator, the generation model identifier, and a created_at timestamp
7. WHEN generating recommendations, THE Recommendation_Generator SHALL scope all context and output to the single state specified in the request and exclude indicators from other states

### Requirement 9: Pipeline Orchestration and Traceability

**User Story:** As a data engineer, I want the full pipeline (ingestion → extraction → detection → parsing → validation → embedding → storage) to execute as an orchestrated workflow with full traceability, so that I can monitor progress and debug failures.

#### Acceptance Criteria

1. WHEN a pipeline run is initiated for a Raw_Document, THE Pipeline_Orchestrator SHALL execute the stages in order: ingestion, text extraction, structure detection, hierarchy parsing, validation, embedding generation, recommendation generation, and data persistence
2. WHEN each pipeline stage completes, THE Pipeline_Orchestrator SHALL record the stage name, status (success or failure), duration, and output artifact location
3. IF any pipeline stage fails, THEN THE Pipeline_Orchestrator SHALL halt execution, record the failure details, and make the partial results available for inspection
4. WHEN a pipeline run completes successfully, THE Pipeline_Orchestrator SHALL record the total number of indicators extracted, validated, and embedded for the document
5. THE Pipeline_Orchestrator SHALL support re-running individual pipeline stages for a given document without re-executing the entire pipeline
