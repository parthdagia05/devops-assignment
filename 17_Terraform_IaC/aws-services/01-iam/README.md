# 01. IAM - Governance

**Name:** Parth Dagia
**Roll No:** 24BCS10414

IAM (Identity and Access Management) is the AWS service that decides who can do what on which resources. Every API call to AWS, whether it comes from the console, the CLI, Terraform or an application, is checked against IAM before it runs. In these notes I go through the building blocks (users, groups, roles, policies), how AWS actually evaluates a request, the extra guardrails (permission boundaries and SCPs), and the best practices I want to follow when I write Terraform for the rest of this course.

## Contents

- [What is IAM?](#what-is-iam)
- [Users](#users)
- [Groups](#groups)
- [Roles](#roles)
- [Policies](#policies)
- [Permissions](#permissions)
- [Least privilege](#least-privilege)
- [IAM best practices](#iam-best-practices)
- [Common use cases](#common-use-cases)
- [Key takeaways](#key-takeaways)
- [References](#references)

## What is IAM?

IAM is a global service (not tied to a region) and it is free to use. It answers two questions for every request:

1. **Authentication:** who is making this request? (a user, a role session, the root user)
2. **Authorization:** is this principal allowed to perform this action on this resource right now?

Main terms I need to keep straight:

| Term | Meaning |
|------|---------|
| Principal | The entity making the request (IAM user, role session, AWS service, federated user) |
| Identity | A user, group or role that policies can be attached to |
| Policy | A JSON document that allows or denies actions |
| Action | An API operation, e.g. `s3:GetObject`, `ec2:RunInstances` |
| Resource | The thing being acted on, identified by an ARN |
| ARN | Amazon Resource Name, e.g. `arn:aws:s3:::my-bucket/*` |

The **root user** is the email address used to create the account. It has full access that cannot be restricted by IAM policies (only by SCPs in an organization). I should only use it for a few account-level tasks, lock it with MFA, and never create access keys for it.

## Users

An IAM user is a long-term identity inside one account. It represents a person or (in older setups) an application.

A user can have:

- A **console password** (for signing in to the AWS Management Console)
- Up to two **access keys** (access key ID + secret, for CLI/SDK)
- **MFA devices** (virtual authenticator app, FIDO2 security key, hardware TOTP)
- Policies attached directly or inherited through groups

```bash
# create a user and give it CLI access keys
aws iam create-user --user-name parth-dev
aws iam create-access-key --user-name parth-dev
```

My note: AWS now recommends using **IAM Identity Center** (formerly AWS SSO) for human users instead of IAM users with long-lived keys. Identity Center gives temporary credentials and works across multiple accounts. IAM users still make sense for small personal/lab accounts like the one I use for this course, or for rare cases that truly need long-term keys.

## Groups

A group is just a collection of users. Permissions attached to a group apply to every user in it.

- A user can be in multiple groups (up to 10).
- Groups cannot contain other groups (no nesting).
- A group is **not a principal**: you cannot reference a group in a resource-based policy or assume a group.

Typical layout I would use:

| Group | Attached policy |
|-------|-----------------|
| `Admins` | `AdministratorAccess` |
| `Developers` | `PowerUserAccess` or custom policy |
| `ReadOnly` | `ReadOnlyAccess` |
| `Billing` | `job-function/Billing` |

```bash
aws iam create-group --group-name Developers
aws iam attach-group-policy --group-name Developers \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
aws iam add-user-to-group --group-name Developers --user-name parth-dev
```

Managing permissions at group level means when someone changes team I just move them between groups instead of editing policies.

## Roles

A role is an identity with permissions but **no long-term credentials**. Someone (or something) assumes the role and gets temporary credentials from AWS STS (Security Token Service) that expire after a set duration (default 1 hour).

Every role has two policies that do different jobs:

| Part | Question it answers |
|------|---------------------|
| **Trust policy** | Who is allowed to assume this role? |
| **Permissions policy** | What can the role do once assumed? |

Who can assume a role:

- AWS services (EC2 via an instance profile, Lambda, ECS tasks)
- Users or roles in the same account or another account (cross-account access)
- Federated identities (SAML, OIDC, e.g. GitHub Actions via OIDC)
- IAM Identity Center users (permission sets are implemented as roles)

Example trust policy that lets EC2 assume the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

```bash
# assume a role from the CLI and get temporary credentials back
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/ReadOnlyAuditor \
  --role-session-name parth-session
```

Roles are the main thing I should be using. Any time I find myself pasting access keys into an app or a CI pipeline, the answer is usually a role.

## Policies

A policy is a JSON document that defines permissions. AWS evaluates policies when a principal makes a request.

### Identity-based vs resource-based

| | Identity-based | Resource-based |
|---|---|---|
| Attached to | User, group or role | A resource (S3 bucket, SQS queue, KMS key, Lambda function) |
| Has `Principal` element? | No (the principal is whoever it is attached to) | Yes, says who gets access |
| Cross-account | Needs a role or resource policy on the other side | Can grant access to another account directly |
| Example | Policy on a role allowing `s3:GetObject` | S3 bucket policy allowing another account to read |

A role's trust policy is actually a resource-based policy on the role itself.

### Managed vs inline

| Type | Description | When I'd use it |
|------|-------------|-----------------|
| AWS managed | Created and maintained by AWS (e.g. `ReadOnlyAccess`) | Quick start, broad job functions |
| Customer managed | Created by me, reusable, versioned (up to 5 versions) | Most real cases, custom least-privilege policies |
| Inline | Embedded directly in one identity, deleted with it | Strict 1:1 relationship that should never be reused |

AWS recommends customer managed over inline in most cases because they are reusable and easier to audit.

### JSON structure

A policy has a `Version` and one or more `Statement` blocks. Each statement uses these elements:

| Element | Required | Purpose |
|---------|----------|---------|
| `Sid` | No | Statement ID, just a label |
| `Effect` | Yes | `Allow` or `Deny` |
| `Action` / `NotAction` | Yes | Which API calls, wildcards allowed (`s3:Get*`) |
| `Resource` / `NotResource` | Yes for identity policies | Which ARNs the statement applies to |
| `Condition` | No | Extra checks, e.g. source IP, MFA present, tags, region |
| `Principal` | Only in resource-based policies | Who the statement applies to |

`Version` should always be `"2012-10-17"` (the current policy language version, not a date I pick).

### Real example policy

This is a customer managed policy I'd attach to a role used by an app that reads and writes objects in one bucket prefix. It also denies any request that is not over HTTPS.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListOnlyAppPrefix",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::parth-app-data",
      "Condition": {
        "StringLike": { "s3:prefix": ["uploads/*"] }
      }
    },
    {
      "Sid": "ReadWriteAppObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::parth-app-data/uploads/*"
    },
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::parth-app-data",
        "arn:aws:s3:::parth-app-data/*"
      ],
      "Condition": {
        "Bool": { "aws:SecureTransport": "false" }
      }
    }
  ]
}
```

Things to notice: `ListBucket` applies to the bucket ARN, while `GetObject`/`PutObject` apply to object ARNs (`/*`). Getting this wrong is a very common mistake.

### Policy evaluation logic

When a request comes in, AWS collects every policy that applies and evaluates them together. The simplified order:

1. **Default: implicit deny.** Everything starts denied.
2. **Explicit deny wins.** If any applicable policy has a `Deny` that matches, the request is denied. Nothing can override this.
3. **Explicit allow.** If there is no explicit deny and some policy has a matching `Allow`, the request is allowed (provided every guardrail type in play, like SCPs and boundaries, also allows it).
4. **Otherwise implicit deny.** No matching allow means denied.

```text
Explicit Deny   >   Explicit Allow   >   Implicit Deny (default)
```

Extra rules I wrote down:

- SCPs, permission boundaries and session policies never grant anything. They only set a maximum. The action must be allowed by them **and** by an identity-based or resource-based policy.
- Within the same account, an allow in **either** the identity-based policy or the resource-based policy is enough.
- For cross-account access, both sides must allow: the identity policy in account A and the resource policy in account B.

I can test this with the IAM policy simulator:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/app-role \
  --action-names s3:GetObject \
  --resource-arns arn:aws:s3:::parth-app-data/uploads/a.txt
```

## Permissions

The effective permissions of a principal are the overlap of several policy types:

| Policy type | Applies to | Grants? | Limits? |
|-------------|-----------|---------|---------|
| Identity-based | User, group, role | Yes | Yes (via deny) |
| Resource-based | Resource | Yes | Yes (via deny) |
| Permission boundary | User or role | No | Yes, sets max |
| SCP (Organizations) | Accounts / OUs | No | Yes, sets max |
| RCP (Organizations) | Resources in accounts / OUs | No | Yes, sets max |
| Session policy | One assumed role / federation session | No | Yes, sets max |

### Permission boundaries

A permission boundary is a managed policy attached to a user or role that sets the **maximum** permissions it can ever have. Effective permissions = identity policy allows AND boundary allows.

Main use: safely delegating IAM. For example, I let developers create roles for their Lambda functions, but force every role they create to carry a boundary, so they can never create a role more powerful than they are.

```bash
aws iam put-role-permissions-boundary \
  --role-name dev-lambda-role \
  --permissions-boundary arn:aws:iam::123456789012:policy/DevBoundary
```

### SCPs (Service Control Policies)

SCPs are part of AWS Organizations. They are attached to the organization root, an OU or an account, and they cap what any principal in those accounts can do, including the account's root user. They do not apply to the management account.

Common SCP examples:

- Deny leaving the organization
- Deny use of regions outside an approved list
- Deny disabling CloudTrail or GuardDuty

Again, an SCP only filters. An account under an SCP that allows `s3:*` still needs IAM policies that grant S3 access.

## Least privilege

Least privilege means giving a principal only the permissions it needs to do its job, and nothing more. In practice:

- Start with nothing, add actions as needed, rather than starting with `*` and trying to remove things later.
- Scope `Resource` to specific ARNs instead of `"*"` wherever the action supports it.
- Use `Condition` keys to narrow further (`aws:SourceIp`, `aws:MultiFactorAuthPresent`, `aws:RequestedRegion`, `aws:ResourceTag/...`).
- Use **IAM Access Analyzer** to generate a policy from actual CloudTrail activity and to find unused access (unused roles, keys, permissions).
- Review "last accessed" information to drop services a role never touches.

Bad vs better:

| Bad | Better |
|-----|--------|
| `"Action": "s3:*", "Resource": "*"` | `"Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::bucket/reports/*"` |
| One shared admin user for the team | Separate identities via Identity Center, admin only for those who need it |
| Long-lived access keys in CI | OIDC federation to a role with a narrow policy |

## IAM best practices

My checklist, mostly from the AWS IAM best practices page:

1. **Lock down the root user:** enable MFA, no access keys, use it only for root-only tasks.
2. **Use federation / IAM Identity Center for humans** so they get temporary credentials.
3. **Use roles for workloads** (EC2 instance profiles, Lambda execution roles, ECS task roles) instead of access keys.
4. **Require MFA** for human users, especially privileged ones.
5. **Rotate or remove access keys** where long-term keys exist; delete unused credentials.
6. **Apply least privilege** and refine with Access Analyzer policy generation.
7. **Prefer customer managed policies** over inline policies.
8. **Use conditions** to add guardrails (MFA, IP ranges, regions, tags).
9. **Use permission boundaries** when delegating IAM administration.
10. **Use SCPs / RCPs** in multi-account setups for org-wide guardrails.
11. **Validate policies** with Access Analyzer policy checks before deploying.
12. **Audit with CloudTrail** and the IAM credential report.

```bash
# quick audit: credential report for every user in the account
aws iam generate-credential-report
aws iam get-credential-report --query Content --output text | base64 --decode
```

### Terraform example

How I'd create a role for an EC2 instance that can read one bucket, with an instance profile so the instance can use it:

```hcl
data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "parth-app-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
}

data "aws_iam_policy_document" "s3_read" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::parth-app-data/*"]
  }
}

resource "aws_iam_policy" "s3_read" {
  name   = "parth-app-s3-read"
  policy = data.aws_iam_policy_document.s3_read.json
}

resource "aws_iam_role_policy_attachment" "app_s3" {
  role       = aws_iam_role.app.name
  policy_arn = aws_iam_policy.s3_read.arn
}

resource "aws_iam_instance_profile" "app" {
  name = "parth-app-profile"
  role = aws_iam_role.app.name
}
```

Using `aws_iam_policy_document` instead of raw JSON strings lets Terraform validate the structure and avoids formatting issues.

## Common use cases

| Scenario | IAM feature |
|----------|-------------|
| App on EC2 needs to read S3 | Role + instance profile |
| Lambda writes to DynamoDB | Lambda execution role |
| GitHub Actions deploys with Terraform | OIDC identity provider + role with trust on the repo |
| Auditor from another account needs read-only access | Cross-account role with `ReadOnlyAccess` |
| Team members log in to several accounts | IAM Identity Center with permission sets |
| Developers create their own roles safely | Permission boundaries |
| Block all regions except `ap-south-1` and `us-east-1` | SCP with `aws:RequestedRegion` condition |
| Share an S3 bucket with a partner account | Bucket policy (resource-based) |
| Require MFA before deleting resources | Condition `aws:MultiFactorAuthPresent` |

## Key takeaways

1. IAM controls authentication and authorization for every AWS API call, is global, and costs nothing.
2. Users and groups are for long-term identities; roles give temporary credentials and should be the default for workloads (and, through Identity Center, for people).
3. Policies are JSON with `Effect`, `Action`, `Resource` and optional `Condition`; identity-based policies attach to identities, resource-based policies attach to resources and name a `Principal`.
4. Evaluation order is explicit deny, then explicit allow, then implicit deny; one matching deny anywhere ends the request.
5. Permission boundaries, SCPs and session policies only set a ceiling; they never grant access by themselves.
6. Least privilege means specific actions on specific ARNs with conditions, refined over time with Access Analyzer.
7. Protect the root user with MFA and never create access keys for it.

## References

- [What is IAM?](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html)
- [Security best practices in IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [IAM roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles.html)
- [Managed policies and inline policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-vs-inline.html)
- [IAM JSON policy elements reference](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements.html)
- [Policy evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html)
- [Permissions boundaries for IAM entities](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html)
- [Service control policies (SCPs)](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)
- [What is IAM Access Analyzer?](https://docs.aws.amazon.com/IAM/latest/UserGuide/what-is-access-analyzer.html)
