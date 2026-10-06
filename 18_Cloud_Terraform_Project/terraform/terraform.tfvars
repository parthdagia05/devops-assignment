use_localstack = true

project            = "session19-cloud-tf"
environment        = "dev"
aws_region         = "ap-south-1"
vpc_cidr           = "10.0.0.0/16"
public_subnet_cidr = "10.0.1.0/24"
instance_type      = "t3.micro"
allowed_ssh_cidr   = "203.0.113.10/32"
bucket_prefix      = "parth-s19-assets"
