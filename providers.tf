terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.2.0"
    }
  }
  required_version = "~> 1.7.0"

  backend "s3" {
    bucket = "lroquec-tf"
    key    = "prod/cost-optimization/ebs-cleaner/terraform.tfstate"
    region = "us-east-1"
    # For DynamoDB locking in production environments
    # dynamodb_table = "terraform-locks"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Environment = "prod"
      ManagedBy   = "terraform"
      Project     = "cost-optimization"
    }
  }
}