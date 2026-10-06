# S3 bucket names are global, so add a random suffix
resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "assets" {
  bucket        = "${var.bucket_prefix}-${var.environment}-${random_id.suffix.hex}"
  force_destroy = true # demo bucket: let destroy remove it with its objects

  tags = { Name = "${local.name}-assets" }
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# The web page the EC2 instance downloads at boot
resource "aws_s3_object" "index" {
  bucket       = aws_s3_bucket.assets.id
  key          = "site/index.html"
  content_type = "text/html"
  content      = <<-HTML
    <h1>Session 19: Cloud &amp; Terraform in Action</h1>
    <p>Served by EC2 in ${var.public_subnet_cidr}, page pulled from S3. Parth Dagia (24BCS10414)</p>
  HTML
}
