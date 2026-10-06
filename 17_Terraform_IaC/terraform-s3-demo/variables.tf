variable "aws_region" {
  description = "AWS region to create the bucket in"
  type        = string
  default     = "ap-south-1"
}

variable "use_localstack" {
  description = "true = send API calls to LocalStack instead of real AWS"
  type        = bool
  default     = false
}

variable "localstack_endpoint" {
  description = "LocalStack edge URL (only used when use_localstack = true)"
  type        = string
  default     = "http://localhost:4566"
}

variable "project" {
  description = "Project name, used in the bucket name and tags"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, stage, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "stage", "prod"], var.environment)
    error_message = "environment must be one of: dev, stage, prod."
  }
}

variable "bucket_prefix" {
  description = "Start of the bucket name; a random suffix is added because S3 names are global"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{2,40}$", var.bucket_prefix))
    error_message = "bucket_prefix must be 3-41 chars of lowercase letters, digits and hyphens."
  }
}

variable "enable_versioning" {
  description = "Keep old versions of objects when they are overwritten or deleted"
  type        = bool
  default     = true
}

variable "force_destroy" {
  description = "Allow terraform destroy to delete the bucket even if it still has objects"
  type        = bool
  default     = false
}
