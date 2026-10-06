# Latest Ubuntu AMI from Canonical (owner 099720109477). Works on real AWS and on LocalStack's mock AMIs.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd*/ubuntu-*-amd64-server-*"]
  }
}

# IAM role so the instance can read the bucket without access keys on disk
resource "aws_iam_role" "ec2" {
  name = "${local.name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "s3_read" {
  name = "read-assets-bucket"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:ListBucket"]
      Resource = [aws_s3_bucket.assets.arn, "${aws_s3_bucket.assets.arn}/*"]
    }]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${local.name}-ec2-profile"
  role = aws_iam_role.ec2.name
}

resource "aws_instance" "web" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name

  # Boot script: install nginx and serve the page stored in S3
  user_data = <<-EOF
    #!/bin/bash
    apt-get update -y
    apt-get install -y nginx awscli
    aws s3 cp s3://${aws_s3_bucket.assets.id}/${aws_s3_object.index.key} /var/www/html/index.html
    systemctl enable --now nginx
  EOF

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens = "required" # IMDSv2 only
  }

  # Explicit dependencies: nothing in the arguments above references these,
  # but the boot script needs a route to the internet (apt, S3) and the IAM
  # policy in place before it runs.
  depends_on = [
    aws_route_table_association.public,
    aws_iam_role_policy.s3_read,
  ]

  tags = { Name = "${local.name}-web" }
}
