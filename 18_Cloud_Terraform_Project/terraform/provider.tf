terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # State is kept in a local terraform.tfstate file (default "local" backend).
  # For a team I would move it to S3 with locking:
  # backend "s3" {
  #   bucket       = "parth-tf-state"
  #   key          = "session19/terraform.tfstate"
  #   region       = "ap-south-1"
  #   use_lockfile = true
  # }
}

# use_localstack = true  -> every API call goes to the LocalStack container on localhost:4566
# use_localstack = false -> real AWS, credentials from `aws configure` / env vars
provider "aws" {
  region = var.aws_region

  access_key                  = var.use_localstack ? "test" : null
  secret_key                  = var.use_localstack ? "test" : null
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack
  s3_use_path_style           = var.use_localstack

  dynamic "endpoints" {
    for_each = var.use_localstack ? [1] : []
    content {
      ec2 = var.localstack_endpoint
      s3  = var.localstack_endpoint
      sts = var.localstack_endpoint
      iam = var.localstack_endpoint
    }
  }

  default_tags {
    tags = {
      Project   = var.project
      Env       = var.environment
      ManagedBy = "Terraform"
      Owner     = "Parth Dagia"
    }
  }
}
