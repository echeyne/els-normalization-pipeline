# Database Migrations

This directory contains SQL migration scripts for the ELS Normalization Pipeline database.

## Migration Files

### 001_initial_schema.sql

The initial database schema including all tables, indexes, and the pgvector extension. This schema includes country support from the start.

**Use this if:** You are setting up a new database from scratch.

### 002_add_country_columns.sql

Migration script to add country columns to an existing database that was created before country support was added.

**Use this if:** You have an existing database and need to add country support.

## Running Migrations

### For a New Database

1. Ensure PostgreSQL with pgvector extension is installed
2. Create the database:

   ```bash
   createdb els_pipeline
   ```

3. Run the initial schema:
   ```bash
   psql -d els_pipeline -f 001_initial_schema.sql
   ```

### For an Existing Database

If you already have a database without country support:

1. **Backup your database first:**

   ```bash
   pg_dump els_pipeline > backup_$(date +%Y%m%d).sql
   ```

2. Run the migration:

   ```bash
   psql -d els_pipeline -f 002_add_country_columns.sql
   ```

3. **Important:** The migration sets default country code to 'US' for existing records. You must manually update records for other countries:

   ```sql
   -- Example: Update California records to use correct country
   UPDATE documents SET country = 'US' WHERE state = 'CA';

   -- Update embeddings and recommendations will be automatically derived
   -- from the indicator's standard_id format
   ```

## Environment Variables

The database connection can be configured using environment variables:

- `DB_HOST`: Database host (default: localhost)
- `DB_PORT`: Database port (default: 5432)
- `DB_NAME`: Database name (default: els_pipeline)
- `DB_USER`: Database user (default: postgres)
- `DB_PASSWORD`: Database password (default: empty)

## Verifying the Migration

After running migrations, verify the schema:

```sql
-- Check that country columns exist
\d documents
\d embeddings
\d recommendations
\d pipeline_runs

-- Verify indexes
\di

-- Check that pgvector extension is installed
\dx
```

## Rollback

If you need to rollback the country column migration:

```sql
-- Remove country columns (WARNING: This will lose country data)
ALTER TABLE documents DROP COLUMN country;
ALTER TABLE embeddings DROP COLUMN country;
ALTER TABLE recommendations DROP COLUMN country;
ALTER TABLE pipeline_runs DROP COLUMN country;

-- Restore original unique constraint on documents
ALTER TABLE documents DROP CONSTRAINT documents_country_state_version_year_title_key;
ALTER TABLE documents ADD CONSTRAINT documents_state_version_year_title_key
    UNIQUE(state, version_year, title);
```

## Notes

- All migrations are idempotent where possible (using `IF NOT EXISTS` and `ON CONFLICT`)
- The pgvector extension must be installed in PostgreSQL before running migrations
- Country codes follow ISO 3166-1 alpha-2 format (two uppercase letters)
- Standard_ID format includes country: `{COUNTRY}-{STATE}-{YEAR}-{DOMAIN_CODE}-{INDICATOR_CODE}`
