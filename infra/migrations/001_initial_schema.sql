-- Initial database schema for ELS Normalization Pipeline
-- This schema includes country support from the start

CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table stores metadata about source documents
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    country VARCHAR(2) NOT NULL,
    state VARCHAR(10) NOT NULL,
    title TEXT NOT NULL,
    version_year INTEGER NOT NULL,
    source_url TEXT,
    age_band VARCHAR(10) NOT NULL,
    publishing_agency TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(country, state, version_year, title)
);

-- Domains represent the top level of the hierarchy
CREATE TABLE domains (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    code VARCHAR(20) NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(document_id, code)
);

-- Subdomains represent the second level of the hierarchy
CREATE TABLE subdomains (
    id SERIAL PRIMARY KEY,
    domain_id INTEGER REFERENCES domains(id),
    code VARCHAR(30) NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(domain_id, code)
);

-- Strands represent the third level of the hierarchy
CREATE TABLE strands (
    id SERIAL PRIMARY KEY,
    subdomain_id INTEGER REFERENCES subdomains(id),
    code VARCHAR(40) NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(subdomain_id, code)
);

-- Indicators represent the lowest assessable unit (fourth level)
CREATE TABLE indicators (
    id SERIAL PRIMARY KEY,
    standard_id VARCHAR(100) UNIQUE NOT NULL,
    domain_id INTEGER REFERENCES domains(id) NOT NULL,
    subdomain_id INTEGER REFERENCES subdomains(id),
    strand_id INTEGER REFERENCES strands(id),
    code VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    source_page INTEGER,
    source_text TEXT,
    last_verified DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Embeddings store vector representations of indicators
CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    indicator_id VARCHAR(100) REFERENCES indicators(standard_id),
    country VARCHAR(2) NOT NULL,
    state VARCHAR(10) NOT NULL,
    vector vector(1536),
    embedding_model VARCHAR(100) NOT NULL,
    embedding_version VARCHAR(10) NOT NULL,
    input_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Recommendations store actionable suggestions for parents and teachers
CREATE TABLE recommendations (
    id SERIAL PRIMARY KEY,
    recommendation_id VARCHAR(100) UNIQUE NOT NULL,
    indicator_id VARCHAR(100) REFERENCES indicators(standard_id),
    country VARCHAR(2) NOT NULL,
    state VARCHAR(10) NOT NULL,
    audience VARCHAR(10) NOT NULL CHECK (audience IN ('parent', 'teacher')),
    activity_description TEXT NOT NULL,
    age_band VARCHAR(10) NOT NULL,
    generation_model VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Pipeline runs track execution of the full pipeline
CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) UNIQUE NOT NULL,
    document_s3_key TEXT NOT NULL,
    country VARCHAR(2) NOT NULL,
    state VARCHAR(10) NOT NULL,
    version_year INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    total_indicators INTEGER DEFAULT 0,
    total_validated INTEGER DEFAULT 0,
    total_embedded INTEGER DEFAULT 0,
    total_recommendations INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Pipeline stages track individual stage execution within a pipeline run
CREATE TABLE pipeline_stages (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) REFERENCES pipeline_runs(run_id),
    stage_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    duration_ms INTEGER,
    output_artifact TEXT,
    error TEXT,
    completed_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_indicators_standard_id ON indicators(standard_id);
CREATE INDEX idx_embeddings_country_state ON embeddings(country, state);
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_recommendations_country_state_indicator ON recommendations(country, state, indicator_id);
CREATE INDEX idx_recommendations_audience ON recommendations(audience);
CREATE INDEX idx_documents_country_state ON documents(country, state);
CREATE INDEX idx_pipeline_runs_country_state ON pipeline_runs(country, state);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
