# Database Migrations

This directory contains SQL migration scripts for the ELS Normalization Pipeline database.

## Migration Files

### 001_initial_schema.sql

The initial database schema including all tables, indexes, and the pgvector extension. This schema includes country support from the start.

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

## Notes

- All migrations are idempotent where possible (using `IF NOT EXISTS` and `ON CONFLICT`)
- The pgvector extension must be installed in PostgreSQL before running migrations
- Country codes follow ISO 3166-1 alpha-2 format (two uppercase letters)
- Standard_ID format includes country: `{COUNTRY}-{STATE}-{YEAR}-{DOMAIN_CODE}-{INDICATOR_CODE}`
