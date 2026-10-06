variable "aws_region" {
  description = "AWS region for every resource"
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
  description = "Project name, used as a prefix for resource names and in tags"
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

variable "vpc_cidr" {
  description = "CIDR block of the VPC"
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR, e.g. 10.0.0.0/16."
  }
}

variable "public_subnet_cidr" {
  description = "CIDR block of the public subnet (must sit inside vpc_cidr)"
  type        = string
  default     = "10.0.1.0/24"
}

variable "instance_type" {
  description = "EC2 instance size"
  type        = string
  default     = "t3.micro"
}

variable "allowed_ssh_cidr" {
  description = "Only this CIDR may SSH to the instance (use your own IP/32)"
  type        = string
  default     = "0.0.0.0/0"
}

variable "bucket_prefix" {
  description = "Start of the S3 bucket name; a random suffix is added because names are global"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{2,40}$", var.bucket_prefix))
    error_message = "bucket_prefix must be 3-41 chars of lowercase letters, digits and hyphens."
  }
}
