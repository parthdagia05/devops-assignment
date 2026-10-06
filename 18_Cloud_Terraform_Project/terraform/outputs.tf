output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "ID of the public subnet"
  value       = aws_subnet.public.id
}

output "availability_zone" {
  description = "AZ the subnet and instance live in"
  value       = aws_subnet.public.availability_zone
}

output "security_group_id" {
  description = "ID of the web security group"
  value       = aws_security_group.web.id
}

output "ami_id" {
  description = "AMI chosen by the aws_ami data source"
  value       = data.aws_ami.ubuntu.id
}

output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.web.id
}

output "instance_public_ip" {
  description = "Public IP of the EC2 instance"
  value       = aws_instance.web.public_ip
}

output "website_url" {
  description = "URL served by nginx on the instance"
  value       = "http://${aws_instance.web.public_ip}"
}

output "bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.assets.id
}

output "bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.assets.arn
}
