# Testing Guide for ELS Pipeline Ingester

This guide covers how to test the ingester module locally and with AWS.

## Quick Start

### Local Testing (No AWS Required)

```bash
# Run all tests
pytest tests/ -v

# Run just integration tests (uses mocked S3)
pytest tests/integration/test_ingester_integration.py -v

# Run property-based tests
pytest tests/property/test_ingestion_props.py -v

# Run with coverage
pytest tests/ --cov=els_pipeline.ingester --cov-report=term-missing
```

### AWS Testing (After Deployment)

```bash
# 1. Deploy CloudFormation stack
aws cloudformation deploy \
  --template-file infra/template.yaml \
  --stack-name els-pipeline-dev \
  --parameter-overrides EnvironmentName=dev \
  --capabilities CAPABILITY_NAMED_IAM

# 2. Get bucket name
aws cloudformation describe-stacks \
  --stack-name els-pipeline-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`RawDocumentsBucketName`].OutputValue' \
  --output text

# 3. Set environment variables (replace <account-id> with your AWS account ID)
export ELS_RAW_BUCKET="els-raw-documents-dev-<account-id>"
export AWS_REGION="us-east-1"

# 4. Run manual test
python scripts/test_ingester_manual.py
```

## Test Types

### 1. Property-Based Tests (`tests/property/`)

Uses Hypothesis to test properties across many generated inputs.

**What it tests:**

- Metadata completeness for all successful ingestions
- Format validation accepts `.pdf` and `.html`
- Format validation rejects other extensions

**Run:**

```bash
pytest tests/property/test_ingestion_props.py -v
```

### 2. Integration Tests (`tests/integration/`)

Uses moto to mock S3 locally for realistic testing without AWS.

**What it tests:**

- Successful PDF upload with metadata
- HTML file upload
- Unsupported format rejection
- File not found error handling
- S3 versioning with multiple uploads

**Run:**

```bash
pytest tests/integration/test_ingester_integration.py -v
```

### 3. Manual AWS Test (`scripts/test_ingester_manual.py`)

Tests against real AWS S3 after deployment.

**What it tests:**

- Real S3 upload with actual California standards PDF
- Actual AWS credentials and permissions
- CloudFormation infrastructure

**Run:**

```bash
python scripts/test_ingester_manual.py
```

## Environment Variables

### For Local Testing

No environment variables needed - tests use mocked S3.

### For AWS Testing

```bash
# Required
export ELS_RAW_BUCKET="els-raw-documents-dev-<account-id>"
export AWS_REGION="us-east-1"

# Optional (with defaults)
export ELS_PROCESSED_BUCKET="els-processed-json"
export ELS_EMBEDDINGS_BUCKET="els-embeddings"
export CONFIDENCE_THRESHOLD="0.7"
```

### Making Environment Variables Permanent

**macOS/Linux (bash/zsh):**

```bash
# Add to ~/.zshrc or ~/.bashrc
echo 'export ELS_RAW_BUCKET="els-raw-documents-dev-123456789012"' >> ~/.zshrc
echo 'export AWS_REGION="us-east-1"' >> ~/.zshrc
source ~/.zshrc
```

**Windows PowerShell:**

```powershell
# Set for current session
$env:ELS_RAW_BUCKET="els-raw-documents-dev-123456789012"
$env:AWS_REGION="us-east-1"

# Set permanently (requires admin)
[System.Environment]::SetEnvironmentVariable('ELS_RAW_BUCKET', 'els-raw-documents-dev-123456789012', 'User')
[System.Environment]::SetEnvironmentVariable('AWS_REGION', 'us-east-1', 'User')
```

## File Naming Convention

The ingester accepts any filename with supported extensions (`.pdf` or `.html`).

**Recommended convention:**

```
{state_name}_{document_type}_{year}.{ext}

Examples:
- california_all_standards_2021.pdf
- california_foundations_2021.pdf
- texas_guidelines_2022.pdf
- new_york_standards_2023.html
```

**S3 path structure:**

```
{state}/{year}/{filename}

Examples:
- CA/2021/california_all_standards_2021.pdf
- TX/2022/texas_guidelines_2022.pdf
- NY/2023/new_york_standards_2023.html
```

## Verification After Upload

### Using AWS CLI

```bash
# List files in bucket
aws s3 ls s3://els-raw-documents-dev-<account-id>/CA/2021/

# Get object metadata
aws s3api head-object \
  --bucket els-raw-documents-dev-<account-id> \
  --key CA/2021/california_all_standards_2021.pdf

# Download file to verify
aws s3 cp \
  s3://els-raw-documents-dev-<account-id>/CA/2021/california_all_standards_2021.pdf \
  /tmp/downloaded.pdf

# List all versions (if versioning enabled)
aws s3api list-object-versions \
  --bucket els-raw-documents-dev-<account-id> \
  --prefix CA/2021/california_all_standards_2021.pdf
```

### Using AWS Console

1. Navigate to S3 in AWS Console
2. Find bucket: `els-raw-documents-dev-<account-id>`
3. Browse to: `CA/2021/`
4. Click on file to view metadata and properties
5. Click "Versions" tab to see version history

## Troubleshooting

### "ModuleNotFoundError: No module named 'els_pipeline'"

```bash
# Install package in development mode
pip install -e .
```

### "NoSuchBucket" Error

- Verify bucket name: `aws s3 ls | grep els-raw`
- Check CloudFormation outputs
- Verify ELS_RAW_BUCKET environment variable

### "AccessDenied" Error

```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify IAM permissions
aws iam get-user
```

### "File not found" Error

- Ensure you're running from project root
- Verify file exists: `ls -la standards/california_all_standards_2021.pdf`

### Tests Fail with Import Errors

```bash
# Reinstall package
pip install -e .

# Verify installation
python -c "from els_pipeline.ingester import ingest_document; print('OK')"
```

## CI/CD Integration

For automated testing in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -e .
    pip install 'moto[s3]' pytest-cov
    pytest tests/ -v --cov=els_pipeline --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Next Steps

After verifying the ingester works:

1. Test with additional state documents
2. Monitor S3 bucket size and costs
3. Set up CloudWatch alarms for failed uploads
4. Implement Lambda function for automated ingestion
5. Add integration with Step Functions pipeline
