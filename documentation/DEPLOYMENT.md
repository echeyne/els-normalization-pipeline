# Deployment Guide

This document describes how to deploy the ELS Pipeline to AWS using GitHub Actions.

## Prerequisites

- AWS Account with appropriate permissions
- GitHub repository with Actions enabled
- Python 3.9 or higher

## GitHub Secrets Configuration

You need to configure the following secrets in your GitHub repository:

### Required Secrets

Navigate to: `Settings > Secrets and variables > Actions > New repository secret`

| Secret Name             | Description                                    | Example Value                              |
| ----------------------- | ---------------------------------------------- | ------------------------------------------ |
| `AWS_ACCESS_KEY_ID`     | AWS IAM access key with deployment permissions | `AKIAIOSFODNN7EXAMPLE`                     |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret access key                      | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `ENVIRONMENT_NAME`      | Target environment (dev, staging, or prod)     | `dev`                                      |

### AWS IAM Permissions Required

The IAM user/role associated with the access keys needs the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:GetTemplate",
        "cloudformation:ValidateTemplate",
        "s3:CreateBucket",
        "s3:PutBucketVersioning",
        "s3:PutBucketEncryption",
        "s3:PutBucketPublicAccessBlock",
        "s3:PutBucketTagging",
        "s3:PutObject",
        "s3:GetObject",
        "iam:CreateRole",
        "iam:PutRolePolicy",
        "iam:AttachRolePolicy",
        "iam:GetRole",
        "iam:PassRole",
        "iam:TagRole",
        "ssm:PutParameter",
        "ssm:GetParameter"
      ],
      "Resource": "*"
    }
  ]
}
```

## Deployment Workflow

### Automatic Deployment

The deployment happens automatically when:

- Code is pushed to the `master` branch
- All tests pass successfully

### Workflow Steps

1. **Test Stage** (runs on all PRs and pushes)
   - Runs unit tests
   - Runs property-based tests
   - Runs integration tests

2. **Deploy Stage** (only on master branch pushes)
   - Builds Python package
   - Deploys CloudFormation stack
   - Uploads artifacts to S3 (if configured)
   - Outputs deployment summary

### Manual Deployment

To deploy manually from your local machine:

```bash
# Configure AWS credentials
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1

# Deploy the stack
aws cloudformation deploy \
  --template-file infra/template.yaml \
  --stack-name els-pipeline-dev \
  --parameter-overrides \
    EnvironmentName=dev \
    Region=us-east-1 \
  --capabilities CAPABILITY_NAMED_IAM

# Get the bucket name
aws cloudformation describe-stacks \
  --stack-name els-pipeline-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`RawDocumentsBucketName`].OutputValue' \
  --output text
```

## Environment Configuration

### Development Environment

- Stack name: `els-pipeline-dev`
- Set `ENVIRONMENT_NAME` secret to: `dev`

### Staging Environment

- Stack name: `els-pipeline-staging`
- Set `ENVIRONMENT_NAME` secret to: `staging`

### Production Environment

- Stack name: `els-pipeline-prod`
- Set `ENVIRONMENT_NAME` secret to: `prod`

## Post-Deployment Steps

After successful deployment:

1. **Get Stack Outputs**

   ```bash
   aws cloudformation describe-stacks \
     --stack-name els-pipeline-dev \
     --query 'Stacks[0].Outputs'
   ```

2. **Update .env file**
   - Copy `.env.example` to `.env`
   - Update `ELS_RAW_BUCKET` with the deployed bucket name
   - Configure other environment-specific variables

3. **Verify Deployment**

   ```bash
   # Check S3 bucket
   aws s3 ls s3://els-raw-documents-dev-{account-id}/

   # Check IAM role
   aws iam get-role --role-name els-ingester-lambda-role-dev
   ```

## Troubleshooting

### Deployment Fails with Permission Errors

- Verify IAM permissions for the AWS credentials
- Check CloudFormation events: `aws cloudformation describe-stack-events --stack-name els-pipeline-dev`

### Tests Fail in CI

- Run tests locally: `pytest tests/ -v`
- Check test logs in GitHub Actions

### Stack Already Exists

- The workflow uses `--no-fail-on-empty-changeset` to handle updates
- To delete and recreate: `aws cloudformation delete-stack --stack-name els-pipeline-dev`

## Monitoring

After deployment, monitor:

- CloudFormation stack status in AWS Console
- GitHub Actions workflow runs
- CloudWatch logs (when Lambda functions are added)

## Rollback

To rollback a deployment:

```bash
# List stack events to find the last successful version
aws cloudformation describe-stack-events --stack-name els-pipeline-dev

# Rollback is automatic on CloudFormation failures
# Manual rollback: redeploy previous version or delete stack
aws cloudformation delete-stack --stack-name els-pipeline-dev
```

## Security Best Practices

1. Use separate AWS accounts or IAM roles for different environments
2. Rotate AWS access keys regularly
3. Use AWS Secrets Manager for sensitive configuration
4. Enable CloudTrail for audit logging
5. Review IAM policies regularly and follow least privilege principle

## Cost Considerations

Current infrastructure costs (approximate):

- S3 storage: ~$0.023 per GB/month
- CloudFormation: Free
- IAM: Free
- SSM Parameter Store: Free (standard parameters)

Future additions will include Lambda and Aurora costs.
