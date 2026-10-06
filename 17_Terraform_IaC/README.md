# Session 18: Terraform & Infrastructure as Code

**Name:** Parth Dagia
**Roll No:** 24BCS10414

Terraform v1.16.4 on my Mac, with the AWS provider pointed at a LocalStack container (S3 API emulator in Docker), so I could run the whole lifecycle without an AWS bill. The same code runs on real AWS by setting one variable.

| Task | What | Files |
|---|---|---|
| 1 | Terraform S3 demo: `init`, `fmt`, `validate`, `plan`, `apply`, `show`, `output`, `destroy` | [terraform-s3-demo/README.md](terraform-s3-demo/README.md), code in [terraform-s3-demo/](terraform-s3-demo) |
| 2 | AWS services research | [aws-services/](aws-services) (5 READMEs, below) |

Raw command output is in [logs/](logs) and terminal screenshots in [screenshots/](screenshots) (rendered from those logs with [shot.py](shot.py)).

---

## What is Infrastructure as Code

Infrastructure as Code (IaC) means describing servers, networks, buckets, etc. in text files that live in git, and letting a tool create them, instead of clicking through a console. You get code review, history, repeatable environments (dev = prod) and easy teardown.

Terraform is a **declarative** IaC tool. I write *what* should exist in HCL; Terraform compares that with its **state** file and works out *how* to get there.

```text
 .tf files (desired)  ─┐
                       ├─▶ terraform plan ──▶ diff (+ create, ~ update, - destroy)
 terraform.tfstate  ───┘                          │
 (what TF created)                                ▼
                                           terraform apply ──▶ provider plugin ──▶ AWS API
                                                                                     │
                                           state updated  ◀──────────────────────────┘
```

| Term | Meaning |
|---|---|
| Provider | Plugin that talks to one API (`hashicorp/aws`, `hashicorp/random`) |
| Resource | Something Terraform creates and manages (`aws_s3_bucket`) |
| Data source | Something Terraform only reads |
| Variable / tfvars | Inputs; `terraform.tfvars` is loaded automatically |
| Output | Values exposed after apply (`terraform output`) |
| State | JSON mapping resource addresses to real IDs; source of truth for Terraform |
| Backend | Where state is stored (local file, or S3 with locking for teams) |
| Module | A folder of `.tf` files; reusable unit |

## Task 1: Terraform S3 demo

```text
terraform-s3-demo/
├── main.tf              # bucket + versioning + SSE-S3 encryption + public access block + hello.txt
├── variables.tf         # typed variables with validation rules
├── outputs.tf           # bucket name, ARN, region, versioning status, object key
├── provider.tf          # aws ~> 6.0, random ~> 3.6, LocalStack/real-AWS switch, default_tags
├── terraform.tfvars     # my values
└── README.md            # full workflow with output and explanations
```

| Step | Command | Result | Log | Screenshot |
|---|---|---|---|---|
| 1 | `terraform init` | aws v6.67.0 + random v3.9.1 installed, lock file created | [01](logs/01-init.log) | [png](screenshots/01-init.png) |
| 2 | `terraform fmt` | already formatted, no changes | [02](logs/02-fmt.log) | [png](screenshots/02-fmt-validate.png) |
| 3 | `terraform validate` | `Success! The configuration is valid.` | [03](logs/03-validate.log) | [png](screenshots/02-fmt-validate.png) |
| 4 | `terraform plan -out=s3.tfplan` | `Plan: 6 to add, 0 to change, 0 to destroy.` | [04](logs/04-plan.log) | [png](screenshots/03-plan.png) |
| 5 | `terraform apply s3.tfplan` | `Apply complete! Resources: 6 added` | [05](logs/05-apply.log) | [png](screenshots/04-apply.png) |
| 6 | `terraform show` | full state of all 6 resources | [06](logs/06-show.log) | [png](screenshots/05-show.png) |
| 7 | `terraform output` | `bucket_name = "parth-tf-demo-dev-2ca593e3"` ... | [07](logs/07-output.log) | [png](screenshots/06-output.png) |
| 8 | verify + second `plan` | object readable, versioning/encryption/tags/public block set, `No changes` | [08](logs/08-verify.log) | [png](screenshots/07-verify.png) |
| 9 | `terraform destroy` | `Destroy complete! Resources: 6 destroyed.` | [09](logs/09-destroy.log) | [png](screenshots/08-destroy.png) |
| 10 | after destroy | state empty, bucket returns 404 | [10](logs/10-after-destroy.log) | [png](screenshots/09-after-destroy.png) |

The full walkthrough is in [terraform-s3-demo/README.md](terraform-s3-demo/README.md), including a problem I hit: a perpetual tag diff caused by an old LocalStack image, which I tracked down with `TF_LOG=DEBUG`.

![apply](screenshots/04-apply.png)

## Task 2: AWS services research

| # | Service | Category | Notes |
|---|---|---|---|
| 01 | IAM | Governance | [aws-services/01-iam/README.md](aws-services/01-iam/README.md) |
| 02 | EC2 | Compute | [aws-services/02-ec2/README.md](aws-services/02-ec2/README.md) |
| 03 | S3 | Storage | [aws-services/03-s3/README.md](aws-services/03-s3/README.md) |
| 04 | VPC | Networking | [aws-services/04-vpc/README.md](aws-services/04-vpc/README.md) |
| 05 | DynamoDB & RDS | Database | [aws-services/05-dynamodb-rds/README.md](aws-services/05-dynamodb-rds/README.md) |

How they fit together in a typical web app:

```text
                 IAM (who can do what: users, roles, policies on every call below)
 ┌──────────────────────────── VPC 10.0.0.0/16 ────────────────────────────┐
 │  public subnet  ── Internet Gateway ── internet                          │
 │    load balancer, NAT Gateway                                            │
 │  private subnet                                                          │
 │    EC2 app servers (AMI + EBS, security group) ──▶ RDS (Multi-AZ)        │
 └───────────────────────────────────────┬──────────────────────────────────┘
                                         ├──▶ S3 (static files, backups, Terraform state)
                                         └──▶ DynamoDB (sessions, carts, fast key-value data)
```

## Deliverables

| Deliverable | Where |
|---|---|
| `terraform-s3-demo/` (main.tf, variables.tf, outputs.tf, provider.tf, terraform.tfvars, README.md) | [terraform-s3-demo/](terraform-s3-demo) |
| Workflow documented in README.md | [terraform-s3-demo/README.md](terraform-s3-demo/README.md) |
| `aws-services/01-iam` to `05-dynamodb-rds` | [aws-services/](aws-services) |
| Logs / screenshots | [logs/](logs) (10 files), [screenshots/](screenshots) (9 images) |

## Key learnings

1. Terraform state is what makes `plan`, `show`, `output` and `destroy` work. Lose it and Terraform forgets what it owns.
2. Separate S3 setting resources (versioning, encryption, public access block) since AWS provider v4: one resource per concern.
3. A second `plan` after `apply` showing no changes is the quick idempotency check.
4. The provider-level `default_tags` block tags every resource without repeating tags in each one.
5. LocalStack is good for practising, but it trails the real AWS API. Pin a recent image.
