# EBS Cleaner

An AWS Lambda function that automatically cleans up unused EBS volumes and their associated snapshots to optimize costs.

## Features

- Identifies and removes unused EBS volumes
- Cleans up orphaned EBS snapshots
- Configurable retention period
- Runs automatically on a daily schedule
- Comprehensive logging
- Secure IAM permissions

## Architecture

- AWS Lambda function written in Python
- EventBridge (CloudWatch Events) for scheduling
- Infrastructure as Code using Terraform
- CI/CD pipeline using GitHub Actions

## Prerequisites

- AWS CLI configured with sufficient permissions
- Python 3.11 or higher
- Terraform 1.7.0 or higher
- boto3 (`pip install boto3`)
- An S3 bucket for Terraform state (referenced in `providers.tf`)

## Initial Setup

1. Run the setup script to create the required IAM role:
```bash
python scripts/setup_github_role.py --repo ebs-cleaner --org your-github-org
```

2. Add the generated Role ARN as a repository secret:
   - Go to your repository settings
   - Navigate to Secrets and variables > Actions
   - Create a new secret named `AWS_ROLE_ARN` with the value printed by the setup script

## Configuration

### Lambda Function

The Lambda function accepts the following event parameters:
- `retention_days`: Number of days to retain volumes and snapshots (default: 7)

Example event:
```json
{
    "retention_days": 14
}
```

### Terraform Variables

The following variables can be customized in `variables.tf`:

- `region`: AWS region (default: "us-east-1")
- `lambda_name`: Name for the Lambda function (default: "ebs_cleaner")
- `lambda_log_retention`: CloudWatch Logs retention in days (default: 7)
- `s3_bucket_prefix`: Prefix for the S3 bucket name (default: "lambda-ebs-cleaner")

## Deployment

The project uses GitHub Actions for automated deployment. The workflow includes:

1. Running tests and linting
2. Terraform plan on pull requests
3. Terraform apply on merges to main

Manual deployment can be done using:
```bash
cd infrastructure/ebs-cleaner
terraform init
terraform plan
terraform apply
```

## Infrastructure Components

- S3 bucket for Lambda code storage
  - Versioning enabled
  - Server-side encryption
  - Public access blocked
- Lambda function
  - 256MB memory
  - 5 minute timeout
  - Python 3.11 runtime
- CloudWatch Log Group
- IAM roles and policies
- EventBridge rule (daily at 3 AM)

## Security

- All resources use AWS best practices for security
- S3 bucket is encrypted and blocks public access
- IAM roles follow principle of least privilege
- OIDC authentication for GitHub Actions

## Development

### Local Testing
1. Install dependencies:
```bash
pip install pytest pytest-cov pylint boto3
```

2. Run tests:
```bash
pytest
```

3. Run linting:
```bash
pylint --rcfile=.pylintrc src/app.py
```

### Adding New Features

1. Create a new branch
2. Make changes and test locally
3. Create a pull request
4. CI/CD will run tests and create a Terraform plan
5. After review and approval, changes will be deployed automatically
