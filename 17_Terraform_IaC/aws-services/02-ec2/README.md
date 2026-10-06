# 02. EC2 - Compute

**Name:** Parth Dagia
**Roll No:** 24BCS10414

EC2 (Elastic Compute Cloud) gives me virtual servers, called instances, that I can start in minutes and pay for only while I use them. To launch one I pick an AMI (the OS image), an instance type (CPU/memory size), a key pair (for SSH), one or more security groups (firewall), and storage (usually EBS). In these notes I cover each of those pieces, how public and private IPs work, the instance lifecycle and what I get billed for in each state, and a short look at the purchasing options.

## Contents

- [What is EC2?](#what-is-ec2)
- [AMI](#ami)
- [Instance types](#instance-types)
- [Key pairs](#key-pairs)
- [Security Groups](#security-groups)
- [EBS](#ebs)
- [Public vs private IP](#public-vs-private-ip)
- [Instance lifecycle](#instance-lifecycle)
- [Common use cases](#common-use-cases)
- [Key takeaways](#key-takeaways)
- [References](#references)

## What is EC2?

EC2 is AWS's Infrastructure as a Service (IaaS) offering. AWS manages the physical hardware and the hypervisor (the Nitro System on current generations); I manage everything from the OS upward: patching, software, data and firewall rules.

Things that make up an instance:

| Component | What it is |
|-----------|-----------|
| AMI | Template with the OS and preinstalled software |
| Instance type | Hardware profile (vCPU, memory, network, storage) |
| Key pair | SSH/RDP credentials |
| Security group | Stateful virtual firewall |
| EBS volume / instance store | Disk storage |
| Subnet / VPC | Network placement (one AZ) |
| IAM instance profile | Role the instance uses to call AWS APIs |
| User data | Script run at first boot (cloud-init) |

An instance always lives in **one Availability Zone**, since its subnet belongs to one AZ.

### Purchasing options (brief)

| Option | How it works | Good for |
|--------|-------------|----------|
| On-Demand | Pay per second (Linux, 60 s minimum), no commitment | Short-term, unpredictable, testing |
| Savings Plans | Commit to a $/hour spend for 1 or 3 years for a discount | Steady usage, flexible across types/regions (Compute SP) |
| Reserved Instances | Commit to a specific instance config for 1 or 3 years | Steady usage on a known type (older model, SP usually preferred now) |
| Spot | Use spare capacity at a large discount, AWS can reclaim with a 2-minute notice | Fault-tolerant batch, CI, big data |
| Dedicated Hosts / Instances | Physical isolation | Licensing (BYOL) or compliance needs |

## AMI

An AMI (Amazon Machine Image) is the template used to launch an instance. It contains:

- A root volume snapshot (OS + installed software)
- Launch permissions (who can use it: private, shared with accounts, or public)
- Block device mapping (which volumes to attach at launch)

Sources of AMIs:

| Source | Example |
|--------|---------|
| AWS provided | Amazon Linux 2023, Ubuntu, Windows Server |
| AWS Marketplace | Vendor images, sometimes with software charges |
| Community | Public AMIs shared by others (be careful) |
| My own | Created from a configured instance or with EC2 Image Builder / Packer |

Key points:

- AMIs are **regional**. To use one in another region I copy it (`aws ec2 copy-image`).
- AMI IDs differ per region, so I should not hardcode them. Use SSM public parameters or a Terraform `data` source.
- An AMI is built for one architecture: `x86_64` or `arm64`. It must match the instance type.

```bash
# latest Amazon Linux 2023 AMI for arm64 in the current region
aws ssm get-parameter \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 \
  --query Parameter.Value --output text

# make my own AMI from a running instance
aws ec2 create-image --instance-id i-0abc123 --name "parth-web-v1"
```

## Instance types

An instance type sets the vCPU, memory, network bandwidth and sometimes local storage.

### Families

| Family | Category | Typical use |
|--------|----------|-------------|
| `t` (t3, t4g) | General purpose, burstable | Low-traffic web apps, dev/test; uses CPU credits |
| `m` (m7i, m7g, m8g) | General purpose, balanced | App servers, mid-size DBs, most default workloads |
| `c` (c7i, c7g, c8g) | Compute optimized | Batch processing, high-performance web, gaming, encoding |
| `r` (r7i, r7g, r8g) | Memory optimized | In-memory caches, large relational DBs, analytics |
| `i` (i4i, i4g) | Storage optimized | High IOPS local NVMe, NoSQL, data warehouses |
| `g` (g5, g6) | Accelerated (GPU) | Graphics, video, ML inference |
| `p` (p4d, p5) | Accelerated (GPU) | ML training, HPC |

### Decoding a name: `m7g.large`

```text
m   7   g   .   large
|   |   |       |
|   |   |       +-- size (nano, micro, small, medium, large, xlarge, 2xlarge, ... metal)
|   |   +---------- attribute: g = AWS Graviton (Arm) processor
|   +-------------- generation: 7th generation
+------------------ family: m = general purpose
```

Other attribute letters I've seen:

| Letter | Meaning |
|--------|---------|
| `g` | AWS Graviton (Arm) |
| `i` | Intel |
| `a` | AMD |
| `d` | Local NVMe instance store |
| `n` | Enhanced networking bandwidth |
| `e` | Extra memory or storage |
| `flex` | Flex variant (e.g. `m7i-flex`), cheaper for workloads that don't need full CPU all the time |

Each step up in size roughly doubles vCPU and memory (e.g. `large` = 2 vCPU, `xlarge` = 4 vCPU for most `m` types).

### Graviton

Graviton is AWS's own Arm-based processor (Graviton2, 3, 4). Graviton types usually give better price-performance than comparable x86 types, so for Linux workloads (containers, Java, Python, Node, Go) they are often the default choice now. The catch: I need `arm64` AMIs and container images, and some x86-only binaries or Windows will not run on them.

## Key pairs

A key pair is used to log in to an instance: SSH for Linux, or to decrypt the admin password for Windows.

- AWS stores only the **public key**. The private key is downloaded once at creation; if I lose it, AWS cannot give it back.
- Supported types: **RSA** and **ED25519** (ED25519 is not supported for Windows instances).
- The public key is placed in `~/.ssh/authorized_keys` of the default user (e.g. `ec2-user` on Amazon Linux, `ubuntu` on Ubuntu) at first boot.

```bash
aws ec2 create-key-pair --key-name parth-key --key-type ed25519 \
  --query KeyMaterial --output text > parth-key.pem
chmod 400 parth-key.pem
ssh -i parth-key.pem ec2-user@<public-ip>
```

Alternatives that avoid managing keys and opening port 22:

- **EC2 Instance Connect**: pushes a short-lived key for one session.
- **Systems Manager Session Manager**: shell access through the SSM agent, no inbound ports, access controlled by IAM and logged.

## Security Groups

A security group (SG) is a virtual firewall attached to an instance's network interface (ENI).

- **Stateful:** if inbound traffic is allowed, the reply is automatically allowed out (and vice versa). I don't need a matching outbound rule for responses.
- **Allow rules only:** there is no "deny" rule. Anything not allowed is blocked.
- Default for a new SG: **no inbound**, **all outbound** allowed.
- A source can be a CIDR, a prefix list, or **another security group** (very useful: "allow app SG to reach DB SG on 5432").
- Multiple SGs on one instance are combined (union of all rules).
- Changes apply immediately to existing instances.

For comparison, Network ACLs work at subnet level, are **stateless**, and support both allow and deny rules.

### Example rules for a web server

| Direction | Protocol | Port | Source / Destination | Why |
|-----------|----------|------|----------------------|-----|
| Inbound | TCP | 443 | `0.0.0.0/0`, `::/0` | HTTPS from anyone |
| Inbound | TCP | 80 | `0.0.0.0/0` | HTTP, redirect to HTTPS |
| Inbound | TCP | 22 | `203.0.113.10/32` | SSH only from my IP |
| Outbound | All | All | `0.0.0.0/0` | Default, allow updates etc. |

And the DB tier:

| Direction | Protocol | Port | Source | Why |
|-----------|----------|------|--------|-----|
| Inbound | TCP | 5432 | `sg-web` (web SG ID) | Only web servers can reach Postgres |

```bash
aws ec2 create-security-group --group-name web-sg \
  --description "web tier" --vpc-id vpc-0abc123
aws ec2 authorize-security-group-ingress --group-id sg-0web123 \
  --protocol tcp --port 443 --cidr 0.0.0.0/0
```

## EBS

EBS (Elastic Block Store) is network-attached block storage for EC2. It persists independently of the instance's life (if configured to).

### Volume types

| Type | Media | Notes | Typical use |
|------|-------|-------|-------------|
| `gp3` | SSD | General purpose; baseline 3,000 IOPS and 125 MiB/s, IOPS and throughput can be raised independently of size | Default for boot and most workloads |
| `gp2` | SSD | Older; IOPS tied to size (3 IOPS per GiB, burst) | Legacy, migrate to gp3 |
| `io2` (Block Express) | SSD | Provisioned IOPS, highest durability, sub-millisecond latency, supports Multi-Attach | Critical databases |
| `st1` | HDD | Throughput optimized, cannot be a boot volume | Big sequential reads: logs, data processing |
| `sc1` | HDD | Cold HDD, lowest cost, cannot be a boot volume | Infrequently accessed data |

### Important rules

- An EBS volume is **bound to one Availability Zone**. It can only attach to instances in that same AZ.
- To move data to another AZ or region: take a **snapshot**, then create a volume from it in the new AZ (or copy the snapshot to another region).
- Most volume types attach to one instance at a time (io1/io2 support Multi-Attach in limited cases).
- Root volumes have **DeleteOnTermination = true** by default; extra volumes default to false.
- Encryption with KMS is supported; I can turn on "encryption by default" per region.
- Volumes can be resized and changed type online (Elastic Volumes).

### Snapshots

- Point-in-time backups stored in S3 (managed by AWS, I don't see the bucket).
- **Incremental:** after the first, only changed blocks are stored.
- Regional; can be copied across regions and shared with other accounts.
- Automate with **Amazon Data Lifecycle Manager** or **AWS Backup**.
- Snapshot Archive tier and Recycle Bin exist for cheaper long-term storage and accidental deletion protection.

```bash
aws ec2 create-snapshot --volume-id vol-0abc123 --description "before upgrade"
aws ec2 create-volume --snapshot-id snap-0abc123 \
  --availability-zone ap-south-1b --volume-type gp3
```

### Instance store

Some types (with `d` in the name, or `i` family) have **instance store**: physically attached NVMe disks. Very fast, but **ephemeral**: data is lost when the instance stops, hibernates or terminates, or if the underlying host fails. Use it for caches, scratch space, buffers.

## Public vs private IP

| | Private IP | Public IPv4 | Elastic IP |
|---|---|---|---|
| Reachable from | Inside the VPC (and peered/VPN networks) | Internet | Internet |
| Assigned | Always, from the subnet CIDR | Auto-assigned if subnet setting or launch option says so | Allocated to my account, then associated |
| On stop/start | Stays the same | **Changes** (released on stop) | Stays the same |
| On terminate | Released | Released | Stays in my account until I release it |

Notes:

- The instance OS only sees its private IP. The public IP is mapped by the Internet Gateway (1:1 NAT).
- For internet access a public subnet needs a route to an Internet Gateway and the instance needs a public IP. Private subnets use a NAT Gateway for outbound only.
- **Elastic IP:** a static public IPv4. Useful when something must not change (allowlisting), but usually a load balancer or DNS is a better design.
- **IPv4 charge:** since **1 February 2024** AWS charges for **all public IPv4 addresses**, including auto-assigned public IPs and Elastic IPs, whether attached or idle (USD 0.005 per IP per hour). Before that, only idle Elastic IPs were charged. This is a good reason to avoid public IPs on instances that don't need them and to look at IPv6.
- IPv6 addresses are globally unique and have no such charge; reachability is controlled by routes and SGs.

```bash
aws ec2 allocate-address --domain vpc
aws ec2 associate-address --instance-id i-0abc123 --allocation-id eipalloc-0abc123
```

## Instance lifecycle

### States

| State | What's happening | Instance usage billed? |
|-------|------------------|------------------------|
| `pending` | Being launched or started, booting | No |
| `running` | Up and usable | **Yes** |
| `stopping` | Shutting down to stop | No (but **yes** if stopping to hibernate) |
| `stopped` | Shut down, can be started again | No compute charge; **EBS volumes and Elastic IPs still billed** |
| `shutting-down` | Being terminated | No |
| `terminated` | Gone permanently (visible in console for a short while) | No |

Reserved Instances and Savings Plans are commitments, so those charges apply for the term regardless of state.

### State diagram

```text
                 launch
                   |
                   v
              +---------+
              | pending |<------------------------+
              +---------+                         |
                   |                              | start
                   v                              |
              +---------+   stop / hibernate  +----------+   +---------+
   reboot --> | running |-------------------->| stopping |-->| stopped |
  (stays in   +---------+                     +----------+   +---------+
   running)        |                                              |
                   | terminate                       terminate    |
                   v                                              |
           +---------------+                                      |
           | shutting-down |<-------------------------------------+
           +---------------+
                   |
                   v
             +------------+
             | terminated |
             +------------+
```

### Stop vs terminate vs reboot vs hibernate

| Action | EBS root volume | Instance store data | RAM | Public IPv4 | Private IP |
|--------|-----------------|---------------------|-----|-------------|-----------|
| Reboot | Kept | Kept | Lost | Kept | Kept |
| Stop | Kept | **Lost** | Lost | Released (EIP kept) | Kept |
| Hibernate | Kept | **Lost** | **Saved to EBS root** | Released (EIP kept) | Kept |
| Terminate | Deleted if DeleteOnTermination = true (default for root) | **Lost** | Lost | Released | Released |

- **Stop** is only possible for EBS-backed instances. On start the instance usually moves to a different physical host.
- **Hibernate** writes RAM contents to the encrypted EBS root volume; on start, processes resume where they were. It must be enabled at launch, the root volume must be encrypted and large enough to hold RAM, and it works only on supported instance types and AMIs.
- **Termination protection** (`DisableApiTermination`) prevents accidental terminate from the API/console.
- Spot instances can be interrupted by AWS (terminate, stop or hibernate depending on configuration).

```bash
aws ec2 stop-instances --instance-ids i-0abc123
aws ec2 stop-instances --instance-ids i-0abc123 --hibernate
aws ec2 start-instances --instance-ids i-0abc123
aws ec2 terminate-instances --instance-ids i-0abc123
```

### Terraform example

A small web server tying it all together: AMI lookup, Graviton type, SG, gp3 root volume:

```hcl
data "aws_ssm_parameter" "al2023_arm" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

resource "aws_security_group" "web" {
  name   = "parth-web-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "web" {
  ami                    = data.aws_ssm_parameter.al2023_arm.value
  instance_type          = "t4g.micro"
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.web.id]
  key_name               = "parth-key"

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = true
  }

  tags = { Name = "parth-web" }
}
```

## Common use cases

| Use case | Typical setup |
|----------|---------------|
| Web / API servers | `m` or `t` types behind an Application Load Balancer, in an Auto Scaling group |
| Self-managed databases | `r` types with `io2` or `gp3` EBS volumes |
| Batch jobs, CI runners | `c` types on Spot |
| ML training / inference | `p` types for training, `g` (or Inferentia `inf`) for inference |
| Caches / NoSQL with local disks | `i` types with instance store |
| Bastion host / jump box | Small `t4g` instance (or replace with Session Manager) |
| Dev/test environments | `t` types, stopped outside working hours |
| Legacy apps that need full OS control | Any type, lift-and-shift from on-prem |

## Key takeaways

1. An instance = AMI + instance type + key pair + security groups + storage, placed in one subnet in one AZ.
2. Instance type names decode as family, generation, attributes and size; Graviton (`g`) types usually give the best price-performance if my software runs on Arm.
3. Security groups are stateful and allow-only; reference other SGs instead of IP ranges between tiers.
4. EBS volumes are AZ-bound and persist; snapshots are incremental, regional and the way to move or back up data. Instance store is fast but ephemeral.
5. Public IPv4 changes on stop/start unless I use an Elastic IP, and every public IPv4 address has been billed hourly since February 2024.
6. Compute is billed only in `running` (and while stopping to hibernate), but EBS and Elastic IPs keep costing money while stopped.
7. Stop keeps EBS data but loses instance store and RAM; terminate removes the root volume by default.

## References

- [What is Amazon EC2?](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/concepts.html)
- [Amazon Machine Images (AMIs)](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AMIs.html)
- [Amazon EC2 instance types](https://docs.aws.amazon.com/ec2/latest/instancetypes/instance-types.html)
- [Amazon EC2 key pairs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html)
- [Security groups for your VPC](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html)
- [Amazon EBS volume types](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html)
- [Amazon EBS snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html)
- [Elastic IP addresses](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html)
- [Amazon EC2 instance state changes](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)
- [Hibernate your Amazon EC2 instance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Hibernate.html)
