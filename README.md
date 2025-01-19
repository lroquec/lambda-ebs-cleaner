# Project Setup

## Prerequisites
- AWS CLI configured with sufficient permissions to create IAM roles
- Python 3.x
- boto3 (`pip install boto3`)

## Initial Setup

1. Run the setup script to create the required IAM role:
```bash
python scripts/setup_github_role.py --repo ebs-cleaner --org your-github-org
```

2. Add the generated Role ARN as a repository secret:
   - Go to your repository settings
   - Navigate to Secrets and variables > Actions
   - Create a new secret named `AWS_ROLE_ARN` with the value printed by the setup script

Once these steps are completed, the GitHub Actions workflow will be able to deploy the infrastructure.
