#!/usr/bin/env python3
"""
Script to create the required IAM role for GitHub Actions.
This should be run once before the first deployment.
"""

import json
import boto3
import argparse

def create_github_actions_role(repo_name: str, org_name: str) -> str:
    """Create IAM role for GitHub Actions with required permissions"""
    
    iam = boto3.client('iam')
    
    # First check/create OIDC provider
    try:
        iam.get_open_id_connect_provider(OpenIDConnectProviderArn=f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:oidc-provider/token.actions.githubusercontent.com")
        print("✓ OIDC provider already exists")
    except iam.exceptions.NoSuchEntityException:
        thumbprint = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
        iam.create_open_id_connect_provider(
            Url='https://token.actions.githubusercontent.com',
            ClientIDList=['sts.amazonaws.com'],
            ThumbprintList=thumbprint
        )
        print("✓ Created OIDC provider")

    role_name = f"ebs-cleaner-deployer"
    
    # Create role with trust policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Federated": f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:oidc-provider/token.actions.githubusercontent.com"
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": f"repo:{org_name}/*:*"
                    },
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                    }
                }
            }
        ]
    }

    try:
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f"Role for GitHub Actions deployment of {repo_name}"
        )
        print(f"✓ Created role {role_name}")
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"✓ Role {role_name} already exists")
        role = iam.get_role(RoleName=role_name)

    # Attach required permissions
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "S3Permissions",
                "Effect": "Allow",
                "Action": [
                    "s3:CreateBucket",
                    "s3:DeleteBucket",
                    "s3:GetBucketPolicy",
                    "s3:PutBucketPolicy",
                    "s3:ListBucket",
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:DeleteObject",
                    "s3:PutBucketVersioning",
                    "s3:PutBucketEncryption",
                    "s3:PutPublicAccessBlock"
                ],
                "Resource": [
                    "arn:aws:s3:::ebs-cleaner-lambda-code-*",
                    "arn:aws:s3:::ebs-cleaner-lambda-code-*/*",
                    "arn:aws:s3:::lroquec-tf",
                    "arn:aws:s3:::lroquec-tf/*"
                ]
            },
            {
                "Sid": "LambdaPermissions",
                "Effect": "Allow",
                "Action": [
                    "lambda:CreateFunction",
                    "lambda:DeleteFunction",
                    "lambda:GetFunction",
                    "lambda:UpdateFunctionCode",
                    "lambda:UpdateFunctionConfiguration",
                    "lambda:AddPermission",
                    "lambda:RemovePermission",
                    "lambda:GetPolicy"
                ],
                "Resource": "arn:aws:lambda:*:*:function:ebs_cleaner"
            },
            {
                "Sid": "IAMPermissions",
                "Effect": "Allow",
                "Action": [
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:GetRole",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:GetRolePolicy",
                    "iam:PassRole"
                ],
                "Resource": "arn:aws:iam::*:role/ebs_cleaner_lambda_role"
            },
            {
                "Sid": "EventBridgePermissions",
                "Effect": "Allow",
                "Action": [
                    "events:PutRule",
                    "events:DeleteRule",
                    "events:DescribeRule",
                    "events:PutTargets",
                    "events:RemoveTargets"
                ],
                "Resource": "arn:aws:events:*:*:rule/trigger-ebs-cleaner-daily"
            },
            {
                "Sid": "CloudWatchLogsPermissions",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:DeleteLogGroup",
                    "logs:DescribeLogGroups",
                    "logs:PutRetentionPolicy"
                ],
                "Resource": "arn:aws:logs:*:*:/aws/lambda/ebs_cleaner"
            },
            {
                "Sid": "TerraformStateCheck",
                "Effect": "Allow",
                "Action": [
                    "s3:ListAllMyBuckets",
                    "s3:GetBucketLocation",
                    "s3:ListBucket"
                ],
                "Resource": "*"
            }
        ]
    }

    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=f"{role_name}-policy",
        PolicyDocument=json.dumps(policy)
    )
    print("✓ Attached permissions policy")

    return role['Role']['Arn']

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create GitHub Actions IAM role')
    parser.add_argument('--repo', required=True, help='Repository name (without org)')
    parser.add_argument('--org', required=True, help='GitHub organization/username')
    
    args = parser.parse_args()
    
    role_arn = create_github_actions_role(args.repo, args.org)
    print("\nSetup completed! 🎉")
    print(f"\nRole ARN: {role_arn}")
    print("\nAdd this ARN as a repository secret named 'AWS_ROLE_ARN' in your GitHub repository")