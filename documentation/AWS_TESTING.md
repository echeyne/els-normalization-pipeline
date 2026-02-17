# AWS Deployment and Testing Guide - ELS Normalization Pipeline

## Overview

This guide provides step-by-step instructions for deploying and testing the ELS Normalization Pipeline on AWS. The pipeline processes early learning standards documents from multiple countries and states, normalizing them into a consistent format with country-based path structures.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Deployment Instructions](#deployment-instructions)
3. [Post-Deployment Verification](#post-deployment-verification)
4. [Testing the Core Pipeline](#testing-the-core-pipeline)
5. [Monitoring and Logging](#monitoring-and-logging)
6. [Troubleshooting](#troubleshooting)
7. [Cost Optimization](#cost-optimization)

---

## Pre-Deployment Checklist

### Prerequisites

Before deploying the ELS pipeline, ensure you have:

- [ ] AWS CLI installed and configured (version 2.x or later)
- [ ] Python 3.11 or later installed
- [ ] pip package manager installed
- [ ] Valid AWS credentials with appropriate permissions
- [ ] Access to the following AWS services:
  - S3
  - Lambda
  - Step Functions
  - Aurora PostgreSQL (Serverless v2)
  - Textract
  - Bedrock (with Claude Sonnet 4.5 and Titan Embed models enabled)
  - CloudWatch
  - SNS
  - Secrets Manager
  - IAM

### Required AWS Permissions

Your AWS user/role must have permissions to:

- Create and manage CloudFormation stacks
- Create and manage S3 buckets
- Create and manage Lambda functions and update function code
- Upload to S3 buckets (for Lambda code deployment)
- Create and manage Step Functions state machines
- Create and manage Aurora PostgreSQL clusters
- Create and manage IAM roles and policies
- Create and manage VPCs, subnets, and security groups
- Create and manage Secrets Manager secrets
- Create and manage SNS topics
- Invoke Bedrock models

### Bedrock Model Access

Ensure you have access to the following Bedrock models in your AWS region:

- `anthropic.claude-sonnet-4-5-20250929-v1:0` (for structure detection and recommendations)
- `amazon.titan-embed-text-v2:0` (for embeddings)

To request model access:

1. Navigate to AWS Bedrock console
2. Go to "Model access" in the left sidebar
3. Request access for Claude Sonnet 4.5 and Titan Embed Text v2
4. Wait for approval (usually instant for Titan, may take time for Claude)

---

## Deployment Instructions

### Step 1: Clone and Prepare the Repository

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd els-pipeline

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Create a `.env` file in the project root (or use the provided `.env.example` as a template):

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your preferred editor
nano .env
```

Required environment variables:

```bash
# AWS Configuration
AWS_REGION=us-east-1
ENVIRONMENT=dev  # or staging, prod

# Bedrock Model IDs
BEDROCK_STRUCTURE_MODEL=anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_RECOMMENDATION_MODEL=anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0

# Confidence Threshold
CONFIDENCE_THRESHOLD=0.7

# Country Code Validation
COUNTRY_CODE_VALIDATION=enabled
```

### Step 3: Validate CloudFormation Template

Before deploying, validate the CloudFormation template:

```bash
aws cloudformation validate-template \
  --template-body file://infra/template.yaml \
  --region us-east-1
```

Expected output: Template validation successful with parameters and capabilities listed.

### Step 4: Package Lambda Functions

The Lambda functions need to be packaged with their dependencies before deployment:

```bash
# Package Lambda functions and upload to S3
bash scripts/package_lambda.sh

# Or specify environment and region
ENVIRONMENT=dev AWS_REGION=us-east-1 bash scripts/package_lambda.sh
```

This script will:

- Install Python dependencies (boto3, pydantic, psycopg2-binary, python-dotenv)
- Copy source code from `src/els_pipeline/`
- Create a ZIP file with all dependencies
- Create an S3 bucket for Lambda code (if it doesn't exist): `els-lambda-code-{environment}-{account-id}`
- Upload the ZIP file to S3
- Update existing Lambda functions with the new code (if they exist)

Note: The deployment script (Step 5) automatically calls this packaging script, so you can skip this step if using the deployment script.

### Step 5: Deploy the Stack

Use the provided deployment script:

```bash
# Deploy to dev environment in us-east-1 (default)
./scripts/deploy.sh

# Deploy to staging environment in us-west-2
./scripts/deploy.sh -e staging -r us-west-2

# Deploy to production
./scripts/deploy.sh -e prod -r us-east-1
```

The deployment script will:

1. Check prerequisites (AWS CLI, Python, credentials)
2. Package Lambda functions (calls `package_lambda.sh`)
3. Validate the CloudFormation template
4. Deploy the stack with all resources
5. Display stack outputs (bucket names, ARNs, endpoints)
6. Create an environment-specific `.env` file
7. Verify deployment success

Deployment typically takes 10-15 minutes due to Aurora PostgreSQL cluster creation.

### Step 6: Note Stack Outputs

After deployment, save the following outputs for testing:

```bash
# Get all stack outputs
aws cloudformation describe-stacks \
  --stack-name els-pipeline-dev \
  --region us-east-1 \
  --query 'Stacks[0].Outputs' \
  --output table
```

Key outputs:

- `RawDocumentsBucketName`: S3 bucket for raw documents
- `ProcessedJsonBucketName`: S3 bucket for processed JSON
- `DatabaseClusterEndpoint`: Aurora PostgreSQL endpoint
- `DatabaseSecretArn`: Secrets Manager ARN for database credentials
- `PipelineStateMachineArn`: Step Functions state machine ARN
- `PipelineNotificationTopicArn`: SNS topic for notifications
- `IngesterLambdaFunctionArn`: ARN of the Ingester Lambda function
- `TextExtractorLambdaFunctionArn`: ARN of the Text Extractor Lambda function
- `StructureDetectorLambdaFunctionArn`: ARN of the Structure Detector Lambda function
- `HierarchyParserLambdaFunctionArn`: ARN of the Hierarchy Parser Lambda function
- `ValidatorLambdaFunctionArn`: ARN of the Validator Lambda function
- `PersistenceLambdaFunctionArn`: ARN of the Persistence Lambda function

---

## Post-Deployment Verification

### Verify S3 Buckets

```bash
# List raw documents bucket
aws s3 ls s3://els-raw-documents-dev-<account-id>/

# List processed JSON bucket
aws s3 ls s3://els-processed-json-dev-<account-id>/

# Verify bucket versioning is enabled
aws s3api get-bucket-versioning \
  --bucket els-raw-documents-dev-<account-id>
```

Expected: Both buckets should exist and have versioning enabled.

### Verify Aurora PostgreSQL Cluster

```bash
# Check cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier els-database-cluster-dev \
  --region us-east-1 \
  --query 'DBClusters[0].Status'
```

Expected output: `"available"`

### Verify Lambda Functions

```bash
# List all ELS Lambda functions
aws lambda list-functions \
  --region us-east-1 \
  --query 'Functions[?starts_with(FunctionName, `els-`)].FunctionName'
```

Expected: List of Lambda functions for each pipeline stage (ingester, extractor, detector, parser, validator, persistence).

### Verify Step Functions State Machine

```bash
# Describe state machine
aws stepfunctions describe-state-machine \
  --state-machine-arn <PipelineStateMachineArn> \
  --region us-east-1
```

Expected: State machine should be in `ACTIVE` status.

### Verify Database Schema

```bash
# Connect to Aurora PostgreSQL
# First, get database credentials from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id els-database-credentials-dev \
  --region us-east-1 \
  --query 'SecretString' \
  --output text

# Use the credentials to connect via psql
psql -h <DatabaseClusterEndpoint> \
     -U els_admin \
     -d els_pipeline \
     -c "\dt"
```

Expected: List of tables (documents, domains, subdomains, strands, indicators, embeddings, recommendations, pipeline_runs, pipeline_stages).

---

## Testing the Core Pipeline

### Test 1: Document Ingestion

Upload a test document to the raw bucket:

```bash
# Create a test PDF (or use an existing one)
echo "Test ELS Document" > test_standards.txt

# Upload to S3 with country-based path structure
aws s3 cp test_standards.txt \
  s3://els-raw-documents-dev-<account-id>/US/CA/2021/test_standards.pdf \
  --metadata country=US,state=CA,version_year=2021
```

Verify upload:

```bash
aws s3 ls s3://els-raw-documents-dev-<account-id>/US/CA/2021/
```

### Test 2: Manual Pipeline Execution

Start a pipeline execution using the Step Functions console or AWS CLI:

```bash
# Start execution
aws stepfunctions start-execution \
  --state-machine-arn <PipelineStateMachineArn> \
  --name "test-execution-$(date +%s)" \
  --input '{
    "run_id": "pipeline-US-CA-2021-test-001",
    "file_path": "US/CA/2021/test_standards.pdf",
    "country": "US",
    "state": "CA",
    "version_year": 2021,
    "source_url": "https://example.com/test_standards.pdf",
    "publishing_agency": "California Department of Education",
    "filename": "test_standards.pdf"
  }' \
  --region us-east-1
```

### Test 3: Monitor Execution

```bash
# Get execution status
aws stepfunctions describe-execution \
  --execution-arn <execution-arn> \
  --region us-east-1 \
  --query 'status'

# Get execution history
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn> \
  --region us-east-1 \
  --max-results 100
```

### Test 4: Verify Outputs

Check processed JSON bucket:

```bash
aws s3 ls s3://els-processed-json-dev-<account-id>/US/CA/2021/ --recursive
```

Expected: JSON files with Standard_IDs following the pattern `US-CA-2021-{DOMAIN}-{INDICATOR}.json`

### Test 5: Query Database

```bash
# Connect to database and query indicators
psql -h <DatabaseClusterEndpoint> \
     -U els_admin \
     -d els_pipeline \
     -c "SELECT standard_id, domain_id, indicator.code, indicator.description
         FROM indicators
         WHERE country = 'US' AND state = 'CA'
         LIMIT 10;"
```

### Test 6: Check SNS Notifications

```bash
# Subscribe to SNS topic for testing
aws sns subscribe \
  --topic-arn <PipelineNotificationTopicArn> \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-1

# Confirm subscription via email
# Then run a pipeline execution and check for notifications
```

---

## Monitoring and Logging

### CloudWatch Logs

View Lambda function logs:

```bash
# List log groups
aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/els- \
  --region us-east-1

# Tail logs for ingester Lambda
aws logs tail /aws/lambda/els-ingester-dev \
  --follow \
  --region us-east-1
```

View Step Functions logs:

```bash
aws logs tail /aws/vendedlogs/states/els-pipeline-dev \
  --follow \
  --region us-east-1
```

### CloudWatch Metrics

Monitor key metrics:

- Lambda invocations, errors, duration
- Step Functions execution count, success/failure rate
- S3 bucket size and object count
- Aurora PostgreSQL connections, CPU, memory

Create CloudWatch dashboard:

```bash
# Use AWS Console to create a dashboard with:
# - Lambda error rates
# - Step Functions execution status
# - S3 bucket metrics
# - Aurora PostgreSQL metrics
```

### X-Ray Tracing

Enable X-Ray tracing for Lambda functions to trace requests through the pipeline:

```bash
# Update Lambda function configuration
aws lambda update-function-configuration \
  --function-name els-ingester-dev \
  --tracing-config Mode=Active \
  --region us-east-1
```

---

## Troubleshooting

### Common Issues

#### Issue 1: CloudFormation Stack Creation Fails

**Symptoms**: Stack creation fails with IAM permission errors

**Solution**:

```bash
# Ensure you have CAPABILITY_NAMED_IAM capability
aws cloudformation create-stack \
  --stack-name els-pipeline-dev \
  --template-body file://infra/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

#### Issue 2: Lambda Function Timeout

**Symptoms**: Lambda functions timeout during execution

**Solution**:

- Increase Lambda timeout in CloudFormation template (default: 300 seconds for text extraction)
- Check Lambda memory allocation (increase if needed)
- Review CloudWatch logs for specific errors

#### Issue 3: Bedrock Access Denied

**Symptoms**: Lambda functions fail with Bedrock access denied errors

**Solution**:

```bash
# Verify Bedrock model access
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude`) || contains(modelId, `titan`)].modelId'

# Request model access if needed (via Bedrock console)
```

#### Issue 4: Aurora PostgreSQL Connection Failures

**Symptoms**: Lambda functions cannot connect to Aurora

**Solution**:

- Verify Lambda functions are in the same VPC as Aurora
- Check security group rules allow PostgreSQL traffic (port 5432)
- Verify database credentials in Secrets Manager
- Check Aurora cluster status

```bash
# Test database connection from Lambda
aws lambda invoke \
  --function-name els-persistence-dev \
  --payload '{"test": "connection"}' \
  --region us-east-1 \
  response.json
```

#### Issue 5: S3 Path Structure Issues

**Symptoms**: Documents not found or incorrect path structure

**Solution**:

- Verify country code is uppercase 2-letter ISO 3166-1 alpha-2 format
- Ensure path follows pattern: `{country}/{state}/{year}/{filename}`
- Check S3 bucket permissions

```bash
# Verify path structure
aws s3 ls s3://els-raw-documents-dev-<account-id>/US/CA/2021/
```

#### Issue 6: Step Functions Execution Fails

**Symptoms**: Step Functions execution fails at specific stage

**Solution**:

```bash
# Get detailed execution history
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn> \
  --region us-east-1 \
  --output json > execution_history.json

# Review failed state details
cat execution_history.json | jq '.events[] | select(.type == "TaskFailed")'
```

### Debugging Tips

1. **Enable verbose logging**: Set Lambda environment variable `LOG_LEVEL=DEBUG`
2. **Use Step Functions console**: Visual representation of execution flow
3. **Check IAM roles**: Ensure Lambda execution roles have required permissions
4. **Review CloudWatch Insights**: Query logs across multiple Lambda functions
5. **Test individual stages**: Invoke Lambda functions directly with test payloads

---

## Cost Optimization

### Estimated Monthly Costs (Dev Environment)

- **S3**: $5-10 (storage + requests)
- **Lambda**: $10-20 (based on execution frequency)
- **Aurora Serverless v2**: $30-50 (0.5-2 ACUs)
- **Step Functions**: $5-10 (based on state transitions)
- **Textract**: Variable (pay per page)
- **Bedrock**: Variable (pay per token)
- **CloudWatch**: $5-10 (logs + metrics)

**Total**: ~$60-100/month for dev environment with moderate usage

### Cost Optimization Strategies

1. **Use Aurora Serverless v2 auto-scaling**: Set min capacity to 0.5 ACU
2. **Enable S3 Intelligent-Tiering**: Automatically move infrequently accessed objects to cheaper storage
3. **Set CloudWatch log retention**: Reduce retention period for non-critical logs
4. **Use Lambda reserved concurrency**: Prevent runaway costs from errors
5. **Implement S3 lifecycle policies**: Archive old documents to Glacier
6. **Monitor Bedrock token usage**: Optimize prompts to reduce token count
7. **Use Step Functions Express Workflows**: For high-volume, short-duration workflows

### Cost Monitoring

```bash
# Enable AWS Cost Explorer
# Set up budget alerts for the ELS pipeline

# Tag all resources with Project=ELS-Pipeline
# Use Cost Allocation Tags to track costs by project
```

---

## Next Steps

After successful deployment and testing:

1. **Set up CI/CD pipeline**: Automate deployments using GitHub Actions or AWS CodePipeline
2. **Implement monitoring dashboards**: Create CloudWatch dashboards for key metrics
3. **Configure alarms**: Set up CloudWatch alarms for errors and performance issues
4. **Document operational procedures**: Create runbooks for common operations
5. **Plan for production**: Review security, compliance, and disaster recovery requirements
6. **Scale testing**: Test with larger documents and higher volumes
7. **Integrate embeddings and recommendations**: Deploy tasks 15-18 for full pipeline

---

## Support and Resources

- **AWS Documentation**: https://docs.aws.amazon.com/
- **Bedrock Documentation**: https://docs.aws.amazon.com/bedrock/
- **Step Functions Documentation**: https://docs.aws.amazon.com/step-functions/
- **Aurora PostgreSQL Documentation**: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/

For issues or questions, contact the development team or create an issue in the repository.
