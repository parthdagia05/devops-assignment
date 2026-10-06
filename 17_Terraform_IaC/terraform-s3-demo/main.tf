# S3 bucket names are global across all AWS accounts, so add a random suffix.
resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  bucket_name = "${var.bucket_prefix}-${var.environment}-${random_id.suffix.hex}"
}

resource "aws_s3_bucket" "demo" {
  bucket        = local.bucket_name
  force_destroy = var.force_destroy

  tags = {
    Name = local.bucket_name
  }
}

resource "aws_s3_bucket_versioning" "demo" {
  bucket = aws_s3_bucket.demo.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

# Encrypt every object at rest with S3 managed keys (SSE-S3 / AES256).
resource "aws_s3_bucket_server_side_encryption_configuration" "demo" {
  bucket = aws_s3_bucket.demo.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Nothing in this bucket should ever be public.
resource "aws_s3_bucket_public_access_block" "demo" {
  bucket = aws_s3_bucket.demo.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# A small object so the bucket is not empty and we can see it in `terraform show`.
resource "aws_s3_object" "hello" {
  bucket       = aws_s3_bucket.demo.id
  key          = "hello.txt"
  content      = "Hello from Terraform! Session 18, Parth Dagia (24BCS10414)\n"
  content_type = "text/plain"

  depends_on = [aws_s3_bucket_versioning.demo]
}
