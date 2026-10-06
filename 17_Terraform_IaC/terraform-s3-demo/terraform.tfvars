aws_region    = "ap-south-1"
project       = "session18-terraform"
environment   = "dev"
bucket_prefix = "parth-tf-demo"

enable_versioning = true
force_destroy     = true # demo bucket, OK to delete with objects inside

# I ran everything against LocalStack (S3 emulator in Docker).
# Set to false (and run `aws configure`) to create the bucket in real AWS.
use_localstack = true
