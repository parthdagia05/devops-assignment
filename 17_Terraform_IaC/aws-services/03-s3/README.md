# 03. S3 - Storage

**Name:** Parth Dagia
**Roll No:** 24BCS10414

These are my notes on Amazon S3 (Simple Storage Service). S3 is object storage: you put files (objects) into containers (buckets) and get them back over HTTPS using a key. There are no folders, disks or servers to manage, and you pay for what you store and how you access it. The notes cover buckets, objects, storage classes, versioning, lifecycle rules, encryption and bucket policies. The Terraform demo for this session ([../../terraform-s3-demo/main.tf](../../terraform-s3-demo/main.tf)) creates a real bucket with versioning, SSE-S3 encryption and a public access block, so most of the ideas below show up there in code.

## Contents

- [What is S3?](#what-is-s3)
- [Buckets](#buckets)
- [Objects](#objects)
- [Storage classes](#storage-classes)
- [Versioning](#versioning)
- [Lifecycle policies](#lifecycle-policies)
- [Encryption](#encryption)
- [Bucket policies and access control](#bucket-policies-and-access-control)
- [Common use cases](#common-use-cases)
- [Key takeaways](#key-takeaways)
- [References](#references)

---

## What is S3?

S3 is a managed object store. Every object is stored as a whole blob plus some metadata, and you read or write the whole object through an API call (`PutObject`, `GetObject`, `DeleteObject` and so on). You cannot edit 10 bytes in the middle of a file like on a normal disk, you upload a new version of the object instead.

| Type | Example | How you use it |
|---|---|---|
| Block storage | EBS | Attached to one EC2 instance as a disk, has a file system on it |
| File storage | EFS | Mounted over NFS, many instances share it |
| Object storage | S3 | Accessed over HTTPS with an API, no mounting |

Things worth remembering:

- S3 is designed for 99.999999999% (11 nines) durability. Data in most storage classes is copied across at least 3 Availability Zones.
- Since December 2020 S3 has **strong read-after-write consistency**. After a successful PUT, the next GET returns the new data. Old notes that talk about "eventual consistency" are out of date.
- Storage is practically unlimited. You never pre-allocate size.
- It is a regional service: a bucket lives in one region and data does not leave that region unless you copy or replicate it.

## Buckets

A bucket is the top-level container for objects. The full address of an object is the bucket plus the key, for example `s3://my-bucket/reports/2026/jan.csv`.

### Naming rules

Bucket names are **globally unique** across all AWS accounts in a partition (the normal `aws` partition is one namespace). If someone else already took `test-bucket`, I cannot use it. That is why the Terraform demo adds a `random_id` suffix to the name.

Rules for general purpose buckets:

- 3 to 63 characters long.
- Only lowercase letters, numbers, dots (`.`) and hyphens (`-`).
- Must start and end with a letter or number.
- Must not look like an IP address (for example `192.168.5.4`).
- Must not start with `xn--` or `sthree-`, and must not end with `-s3alias` or `--ol-s3` (reserved by AWS).
- Avoid dots if you want virtual-hosted HTTPS URLs, because a dot breaks the TLS wildcard certificate match.
- A name cannot be changed later. You have to create a new bucket and copy the data.

### Regional

Even though the name is global, the bucket itself is created in **one region** that you choose. Pick the region close to users or the compute that reads it, and for data residency rules. By default an account can have up to 10,000 general purpose buckets (this was raised from 100 in late 2024, and can be increased further with a quota request).

```bash
# Create a bucket in Mumbai (outside us-east-1 you must pass a LocationConstraint)
aws s3api create-bucket \
  --bucket parth-notes-demo-1234 \
  --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1

aws s3 ls                                   # list buckets
aws s3 cp notes.txt s3://parth-notes-demo-1234/notes/notes.txt
aws s3 ls s3://parth-notes-demo-1234/notes/
```

## Objects

An object is made of:

| Part | Meaning |
|---|---|
| Key | The full name of the object inside the bucket, e.g. `images/2026/cat.png` |
| Value | The actual bytes (the file content) |
| Metadata | Name-value pairs. System metadata (`Content-Type`, `Content-Length`, `Last-Modified`, `ETag`) and user metadata (`x-amz-meta-*`) |
| Version ID | Set by S3 when versioning is on. Each overwrite gets a new version ID. Without versioning it is `null` |
| Tags | Up to 10 key-value tags per object, used for lifecycle filters, cost and access control |

**Folders are fake.** S3 has a flat namespace. The console shows `images/2026/` as a folder only because the key contains `/`. In the API it is just a prefix, and `aws s3 ls --prefix images/` filters by it.

### Size limits and multipart upload

- A single object can be up to **50 TB** (raised from 5 TB in December 2025, in all storage classes; a lot of course material still says 5 TB).
- A single `PUT` request can upload at most **5 GB**.
- Anything bigger must use **multipart upload**. AWS recommends it for objects above about 100 MB anyway.

Multipart upload in short:

1. `CreateMultipartUpload` returns an upload ID.
2. Upload parts in parallel (`UploadPart`). Each part is 5 MiB to 5 GiB (the last part can be smaller), up to 10,000 parts.
3. `CompleteMultipartUpload` joins the parts into one object.

If a part fails you only retry that part. Unfinished uploads still cost money for the parts already stored, so add a lifecycle rule that aborts incomplete multipart uploads (shown later). The high-level `aws s3 cp` command does multipart automatically for large files.

## Storage classes

The storage class is set per object, not per bucket. The cheaper the storage, the more you pay (in money or time) to read it back.

| Class | AZs | Min storage duration | Retrieval time | Use case |
|---|---|---|---|---|
| S3 Standard | 3 or more | None | Milliseconds | Hot data, websites, app content, analytics |
| S3 Intelligent-Tiering | 3 or more | None | Milliseconds (frequent, infrequent, archive instant tiers); optional archive tiers take minutes to hours | Unknown or changing access patterns |
| S3 Standard-IA | 3 or more | 30 days | Milliseconds | Backups and data read about once a month |
| S3 One Zone-IA | 1 | 30 days | Milliseconds | Re-creatable data, secondary backup copies |
| S3 Express One Zone | 1 | None (billed by the hour) | Single-digit milliseconds | Very low latency workloads like ML training, uses directory buckets |
| S3 Glacier Instant Retrieval | 3 or more | 90 days | Milliseconds | Archive data read about once a quarter (medical images, old media) |
| S3 Glacier Flexible Retrieval | 3 or more | 90 days | Expedited 1 to 5 min, Standard 3 to 5 hours, Bulk 5 to 12 hours | Backups and archives that can wait for a restore |
| S3 Glacier Deep Archive | 3 or more | 180 days | Standard within 12 hours, Bulk within 48 hours | Compliance data kept for 7 to 10 years, tape replacement |

Notes:

- IA and Glacier Instant Retrieval charge a per-GB **retrieval fee** and have a minimum billable object size of 128 KB.
- Deleting an object before its minimum duration still charges you for the full minimum period.
- Glacier Flexible Retrieval and Deep Archive objects must be **restored** (`RestoreObject`) before you can `GET` them. The restore creates a temporary copy.
- Intelligent-Tiering charges a small monitoring fee per object and moves objects between tiers by itself. Objects smaller than 128 KB are not auto-tiered.
- One Zone classes lose data if that AZ is destroyed, so only use them for data you can rebuild.

```bash
# Upload straight into a cheaper class
aws s3 cp backup.tar.gz s3://parth-notes-demo-1234/backups/ --storage-class STANDARD_IA
```

## Versioning

Versioning keeps every version of every object in the bucket, so an overwrite or delete can be undone.

A bucket is always in one of three states:

| State | What happens |
|---|---|
| Unversioned (default) | Overwrite replaces the object. Delete removes it for good |
| Enabled | Every PUT creates a new version with its own version ID. Old versions are kept |
| Suspended | New writes get version ID `null`, but existing versions stay. You cannot go back to "unversioned" once versioning was enabled, only suspend it |

### Delete markers

When versioning is enabled, a normal `DELETE` (without a version ID) does **not** delete data. S3 adds a **delete marker** as the newest version, and a plain `GET` then returns 404. To "undelete", remove the delete marker. To really delete, call `DELETE` with a specific `versionId`.

```bash
aws s3api put-bucket-versioning --bucket parth-notes-demo-1234 \
  --versioning-configuration Status=Enabled

aws s3api list-object-versions --bucket parth-notes-demo-1234 --prefix notes/
```

Every version is billed as a full object, so versioning should almost always be paired with a lifecycle rule that expires noncurrent versions.

### MFA delete

MFA delete adds a second check: permanently deleting a version or changing the versioning state needs an MFA code. Only the **root user** can enable it, and only through the CLI or API (not the console). It is useful for very sensitive buckets, but S3 Object Lock is now the more common way to protect data from deletion.

## Lifecycle policies

Lifecycle rules let S3 move or delete objects automatically based on age. There are two kinds of actions:

- **Transition**: move objects to a cheaper storage class after N days.
- **Expiration**: delete objects (or noncurrent versions) after N days.

A rule can be filtered by prefix, by object tags or by object size. Example rule for a `logs/` prefix:

```json
{
  "Rules": [
    {
      "ID": "logs-archive-then-delete",
      "Status": "Enabled",
      "Filter": { "Prefix": "logs/" },
      "Transitions": [
        { "Days": 30, "StorageClass": "STANDARD_IA" },
        { "Days": 90, "StorageClass": "GLACIER" }
      ],
      "Expiration": { "Days": 365 },
      "NoncurrentVersionExpiration": { "NoncurrentDays": 30 },
      "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 7 }
    }
  ]
}
```

What this does: log files go to Standard-IA after 30 days, to Glacier Flexible Retrieval (`GLACIER` in the API) after 90 days, and are deleted after a year. Old versions are removed 30 days after being replaced, and half-finished multipart uploads are cleaned up after 7 days.

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket parth-notes-demo-1234 \
  --lifecycle-configuration file://lifecycle.json
```

Things to watch: Standard to Standard-IA needs the object to be at least 30 days old, and transitions follow a "waterfall" (you can only move down to colder classes, not back up with a lifecycle rule).

## Encryption

### At rest

| Option | Who manages the key | Notes |
|---|---|---|
| SSE-S3 | S3 (AES-256) | **Default for all new objects since 5 January 2023.** No extra cost, nothing to configure |
| SSE-KMS | AWS KMS key (AWS managed `aws/s3` or your own customer managed key) | Key usage is logged in CloudTrail, access controlled by key policy. KMS request charges apply |
| DSSE-KMS | AWS KMS | Dual-layer server-side encryption: two layers of encryption, for compliance rules that require it |
| SSE-C | The customer, sent with each request | S3 encrypts with your key but does not store it. Lose the key, lose the data. HTTPS required |
| Client-side | The customer | Data is encrypted before upload (for example with the AWS Encryption SDK). S3 only sees ciphertext |

**S3 Bucket Keys:** with SSE-KMS every object operation would normally call KMS. A bucket key is a short-lived bucket-level key generated from the KMS key, so S3 calls KMS far less often. This cuts KMS request cost a lot (AWS says up to 99%). Turn it on with `BucketKeyEnabled = true`.

### In transit

S3 endpoints support HTTPS (TLS). Plain HTTP is still accepted unless you block it, so the usual practice is a bucket policy that denies any request where `aws:SecureTransport` is `false` (example in the next section).

### Terraform

This is the same pattern as in my demo (see [../../terraform-s3-demo/main.tf](../../terraform-s3-demo/main.tf)):

```hcl
resource "aws_s3_bucket" "demo" {
  bucket = "parth-notes-demo-1234"
}

resource "aws_s3_bucket_versioning" "demo" {
  bucket = aws_s3_bucket.demo.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "demo" {
  bucket = aws_s3_bucket.demo.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"   # SSE-S3. Use "aws:kms" plus kms_master_key_id for SSE-KMS
    }
  }
}
```

In AWS provider v4 and later, versioning, encryption, lifecycle and policy are separate resources, not blocks inside `aws_s3_bucket`.

## Bucket policies and access control

There are a few layers that decide who can access a bucket:

1. **IAM policies** attached to users and roles (identity-based).
2. **Bucket policies**: JSON resource-based policies attached to the bucket.
3. **Block Public Access** settings at the account and bucket level.
4. **ACLs**: the old per-object permission system, now disabled by default.

An explicit `Deny` anywhere wins over any `Allow`.

### Example 1: enforce TLS only

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::parth-notes-demo-1234",
        "arn:aws:s3:::parth-notes-demo-1234/*"
      ],
      "Condition": {
        "Bool": { "aws:SecureTransport": "false" }
      }
    }
  ]
}
```

Both ARNs are needed: the bucket ARN covers bucket-level actions like `ListBucket`, and `/*` covers object-level actions like `GetObject`.

### Example 2: allow one IAM role to read and write

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAppRoleList",
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::111122223333:role/app-server-role" },
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::parth-notes-demo-1234"
    },
    {
      "Sid": "AllowAppRoleObjects",
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::111122223333:role/app-server-role" },
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::parth-notes-demo-1234/*"
    }
  ]
}
```

```bash
aws s3api put-bucket-policy --bucket parth-notes-demo-1234 --policy file://policy.json
```

### Block Public Access

Four switches, all **on by default for new buckets since April 2023**:

| Setting | Effect |
|---|---|
| `BlockPublicAcls` | Reject PUT requests that include a public ACL |
| `IgnorePublicAcls` | Ignore any public ACLs that already exist |
| `BlockPublicPolicy` | Reject bucket policies that grant public access |
| `RestrictPublicBuckets` | Limit access to buckets with public policies to AWS services and the owner account |

My Terraform demo sets all four to `true` with `aws_s3_bucket_public_access_block`. You should only turn these off on purpose, for example for a public static website, and even then CloudFront with Origin Access Control is the better design.

### ACLs and Object Ownership

ACLs are the legacy way to grant access per object. Since April 2023 new buckets use the **Object Ownership** setting `BucketOwnerEnforced`, which means:

- ACLs are disabled and ignored.
- The bucket owner automatically owns every object, even ones uploaded by other accounts.
- All access is controlled with policies only.

AWS recommends keeping ACLs disabled except in rare cases.

## Common use cases

- **Static website hosting** (HTML, CSS, JS), usually behind CloudFront.
- **Backups and disaster recovery**, with versioning and Cross-Region Replication.
- **Data lake**: raw and processed data queried with Athena, Glue, EMR or Redshift Spectrum.
- **Log storage**: CloudTrail, ALB, VPC Flow Logs and CloudFront logs all write to S3.
- **Application assets**: user uploads, images and videos, often with pre-signed URLs for temporary access.
- **Terraform remote state**: the state file lives in a versioned, encrypted S3 bucket (Terraform 1.10+ can lock with S3 itself using `use_lockfile`, instead of a DynamoDB table).
- **Archive and compliance**: Glacier classes plus Object Lock for write-once-read-many (WORM) storage.
- **Artifact storage** for CI/CD pipelines (build outputs, Lambda zip files).

---

## Key takeaways

1. S3 is object storage: a flat namespace of keys inside buckets, accessed over HTTPS, with strong read-after-write consistency.
2. Bucket names are globally unique, but every bucket lives in a single region.
3. Pick the storage class per object by access pattern, and remember minimum durations and retrieval fees on the colder classes.
4. Versioning plus lifecycle rules protect against mistakes without letting old versions pile up forever.
5. All new objects are encrypted with SSE-S3 by default; use SSE-KMS (with bucket keys) when you need key control and audit logs.
6. Block Public Access and disabled ACLs are the defaults. Control access with IAM and bucket policies, and enforce TLS with `aws:SecureTransport`.
7. In Terraform each bucket feature (versioning, encryption, public access block) is its own resource, as seen in `terraform-s3-demo`.

## References

- [What is Amazon S3?](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html)
- [General purpose bucket naming rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html)
- [Uploading and copying objects using multipart upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- [Understanding and managing Amazon S3 storage classes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html)
- [Retaining multiple versions of objects with S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
- [Managing the lifecycle of objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [Protecting data with encryption](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingEncryption.html)
- [Bucket policies for Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html)
- [Blocking public access to your Amazon S3 storage](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html)
- [Controlling ownership of objects and disabling ACLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/about-object-ownership.html)
