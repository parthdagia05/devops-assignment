# 04. VPC - Networking

**Name:** Parth Dagia
**Roll No:** 24BCS10414

These are my notes on Amazon VPC (Virtual Private Cloud). A VPC is my own private network inside an AWS region, where I choose the IP range, cut it into subnets, and decide how traffic gets in and out using route tables, gateways, security groups and network ACLs. Almost every AWS resource that has an IP address (EC2, RDS, Lambda in a VPC, load balancers, EKS nodes) lives inside a VPC, so understanding it is needed before doing anything real with Terraform on AWS. The notes go from CIDR maths up to a full 2-AZ layout with public and private subnets.

## Contents

- [What is VPC?](#what-is-vpc)
- [CIDR](#cidr)
- [Subnets](#subnets)
- [Route tables](#route-tables)
- [Internet Gateway](#internet-gateway)
- [NAT Gateway](#nat-gateway)
- [Security Groups](#security-groups)
- [Network ACLs](#network-acls)
- [Public vs private subnet](#public-vs-private-subnet)
- [Architecture diagram](#architecture-diagram)
- [Other ways to connect](#other-ways-to-connect)
- [Key takeaways](#key-takeaways)
- [References](#references)

---

## What is VPC?

A VPC is a logically isolated virtual network in one AWS region. It is like having my own data center network, but software-defined.

- A VPC belongs to **one region** and spans **all AZs** in that region.
- Subnets inside it belong to **one AZ** each.
- Traffic between VPCs is blocked unless I connect them (peering, Transit Gateway and so on).
- Every account has a **default VPC** in each region (`172.31.0.0/16`, one public `/20` subnet per AZ). It is fine for quick tests, but for real work you create your own.

The main building blocks:

| Component | Job |
|---|---|
| VPC | The network and its IP range (CIDR) |
| Subnet | A slice of the VPC range in one AZ |
| Route table | Decides where packets leaving a subnet go |
| Internet Gateway (IGW) | Connects the VPC to the internet |
| NAT Gateway | Lets private subnets reach the internet, outbound only |
| Security Group | Stateful firewall on each network interface (instance) |
| Network ACL | Stateless firewall on each subnet |

## CIDR

### Notation

CIDR (Classless Inter-Domain Routing) writes a network as `address/prefix`. The prefix is how many bits, from the left, are fixed as the network part. The rest are host bits.

```text
10.0.0.0/16
first 16 bits fixed (10.0), last 16 bits free for hosts
```

### Counting IPs

Number of addresses = 2^(32 - prefix).

| CIDR | Host bits | Total IPs | Usable in an AWS subnet (minus 5) |
|---|---|---|---|
| /16 | 16 | 65,536 | 65,531 |
| /20 | 12 | 4,096 | 4,091 |
| /24 | 8 | 256 | 251 |
| /26 | 6 | 64 | 59 |
| /28 | 4 | 16 | 11 |

Each step of +1 on the prefix halves the size.

### AWS limits

- A VPC (IPv4) CIDR must be between **/16** (65,536 IPs, the biggest) and **/28** (16 IPs, the smallest).
- The same /16 to /28 limit applies to subnets.
- You can add secondary CIDR blocks to a VPC later, but you cannot change the primary one, so plan big enough at the start.
- IPv6 is optional: AWS can give the VPC a /56 and each subnet a /64.

### 5 reserved IPs per subnet

AWS keeps 5 addresses in every subnet. For `10.0.1.0/24`:

| Address | Reserved for |
|---|---|
| `10.0.1.0` | Network address |
| `10.0.1.1` | VPC router |
| `10.0.1.2` | Amazon DNS server (always "VPC base + 2") |
| `10.0.1.3` | Reserved for future use |
| `10.0.1.255` | Network broadcast (AWS does not support broadcast, but reserves it) |

So a /24 gives 251 usable IPs, and a /28 gives only 11.

### RFC 1918 private ranges

Use private ranges so the VPC does not clash with public internet addresses:

| Range | CIDR | Size |
|---|---|---|
| 10.0.0.0 to 10.255.255.255 | `10.0.0.0/8` | about 16.7 million |
| 172.16.0.0 to 172.31.255.255 | `172.16.0.0/12` | about 1 million |
| 192.168.0.0 to 192.168.255.255 | `192.168.0.0/16` | 65,536 |

If the VPC will ever connect to an office network or another VPC, pick ranges that **do not overlap**, because peering and VPN routing break with overlapping CIDRs.

### Worked example: splitting 10.0.0.0/16

The VPC has 65,536 addresses. If I cut it into /24 subnets, I get 2^(24-16) = **256 subnets** of 256 IPs each. A simple plan for 2 AZs:

| Subnet | AZ | CIDR | Range | Usable |
|---|---|---|---|---|
| public-a | ap-south-1a | `10.0.1.0/24` | 10.0.1.0 to 10.0.1.255 | 251 |
| public-b | ap-south-1b | `10.0.2.0/24` | 10.0.2.0 to 10.0.2.255 | 251 |
| private-a | ap-south-1a | `10.0.11.0/24` | 10.0.11.0 to 10.0.11.255 | 251 |
| private-b | ap-south-1b | `10.0.12.0/24` | 10.0.12.0 to 10.0.12.255 | 251 |

Most of the /16 is still free for later (databases, more AZs, EKS pods). If I needed bigger subnets I could cut it into /20s instead: 2^(20-16) = 16 subnets of 4,096 IPs (`10.0.0.0/20`, `10.0.16.0/20`, `10.0.32.0/20`, ...). The third octet jumps by 16 each time because 4,096 = 16 x 256.

## Subnets

- A subnet is a range of IPs inside the VPC, and it is **bound to exactly one AZ**. It can never span two AZs.
- For high availability you create the same kind of subnet in at least 2 AZs, as in the table above.
- Subnet CIDRs inside one VPC must not overlap.
- Each subnet is associated with exactly one route table and one network ACL.
- "Auto-assign public IPv4 address" is a subnet setting. In a public subnet you usually turn it on.

```bash
aws ec2 create-vpc --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=notes-vpc}]'

aws ec2 create-subnet --vpc-id vpc-0abc123 \
  --cidr-block 10.0.1.0/24 --availability-zone ap-south-1a

aws ec2 describe-subnets --filters Name=vpc-id,Values=vpc-0abc123 \
  --query 'Subnets[].[SubnetId,CidrBlock,AvailabilityZone]' --output table
```

## Route tables

A route table is a list of rules: "traffic for this destination goes to this target". The most specific (longest prefix) match wins.

- **Main route table**: created with the VPC. Any subnet that is not explicitly associated with another table uses it.
- **Custom route tables**: ones I create and associate with specific subnets. Good practice is to leave the main table private (local route only) and create custom tables for public subnets, so a new subnet is never public by accident.
- **Local route**: every route table has a route for the VPC CIDR with target `local`. It lets all subnets in the VPC talk to each other and cannot be deleted.

### Public subnet route table

| Destination | Target | Meaning |
|---|---|---|
| `10.0.0.0/16` | local | Traffic inside the VPC stays inside |
| `0.0.0.0/0` | `igw-0abc123` | Everything else goes to the internet gateway |

### Private subnet route table (one per AZ)

| Destination | Target | Meaning |
|---|---|---|
| `10.0.0.0/16` | local | Traffic inside the VPC stays inside |
| `0.0.0.0/0` | `nat-0aaa111` (NAT in the same AZ) | Outbound internet goes through the NAT gateway |

```bash
aws ec2 create-route --route-table-id rtb-0pub123 \
  --destination-cidr-block 0.0.0.0/0 --gateway-id igw-0abc123

aws ec2 associate-route-table --route-table-id rtb-0pub123 --subnet-id subnet-0pubA
```

## Internet Gateway

- An Internet Gateway (IGW) is a horizontally scaled, highly available component that connects a VPC to the internet. There is no bandwidth limit to manage and no hourly charge for the IGW itself.
- **One IGW per VPC**, attached to the VPC (not to a subnet).
- It does 1:1 NAT between an instance's private IP and its public IPv4 or Elastic IP.
- Attaching it is not enough. A subnet only uses it when its route table has `0.0.0.0/0 -> igw-...`.
- For IPv6 outbound-only traffic there is a separate **egress-only internet gateway**.

Note: since February 2024 AWS charges for every public IPv4 address (about $0.005 per hour each), including ones on running instances, so do not hand out public IPs that are not needed.

## NAT Gateway

A NAT gateway lets instances in **private** subnets start connections to the internet (for `yum update`, pulling Docker images, calling external APIs) while blocking connections started from the internet.

- It **lives in a public subnet**, because it needs the route to the IGW itself.
- A public NAT gateway needs an **Elastic IP** attached. All outbound traffic appears to come from that IP.
- A NAT gateway is zonal: it is redundant inside its AZ only. For HA, create **one NAT gateway per AZ** and point each private subnet's route table at the NAT in its own AZ. If all private subnets share one NAT and that AZ goes down, every private subnet loses internet access (and cross-AZ traffic also costs extra).
- **Cost**: NAT gateways are one of the most common surprise bills. You pay per hour for each NAT gateway plus per GB of data processed (around $0.045/hour and $0.045/GB in us-east-1). Two NATs in a lab left running for a month cost real money, so `terraform destroy` after practice.
- Cheaper ideas: use VPC gateway endpoints for S3 and DynamoDB so that traffic skips the NAT, or a single NAT for dev environments only.
- There is also a **private NAT gateway** type (no EIP) for routing between private networks with overlapping ranges.
- AWS added a **regional** availability mode for NAT gateways in November 2025: one NAT gateway expands across the AZs where you have workloads and doesn't need a public subnet. The classic zonal setup above is still what most course material and Terraform examples use.

Old way: a **NAT instance** (an EC2 instance doing NAT). It is cheaper but you manage patching, scaling and failover yourself, and you must disable source/destination check.

```bash
aws ec2 allocate-address --domain vpc
aws ec2 create-nat-gateway --subnet-id subnet-0pubA --allocation-id eipalloc-0abc123
```

## Security Groups

A security group (SG) is a **stateful** virtual firewall attached to an elastic network interface (so effectively to an instance, RDS DB, load balancer and so on).

- **Allow rules only**. You cannot write a deny rule.
- **Stateful**: if inbound traffic is allowed, the response is automatically allowed out, and the other way round.
- All rules are evaluated together; if any rule allows the traffic, it is allowed.
- A new SG has **no inbound rules** (deny all in) and an **allow all outbound** rule.
- The **source can be another security group**, not just a CIDR. This is the clean way to say "only the web tier can reach the DB on 3306".
- One instance can have several SGs (5 per interface by default), and the rules are combined.

Example web and DB tiers:

| SG | Direction | Port | Source |
|---|---|---|---|
| `web-sg` | Inbound | 443 | `0.0.0.0/0` |
| `web-sg` | Inbound | 22 | my IP only, e.g. `203.0.113.10/32` |
| `db-sg` | Inbound | 3306 | `web-sg` |

## Network ACLs

A network ACL (NACL) is a **stateless** firewall at the **subnet** boundary. It is an extra layer, most setups keep the default NACL and do the real filtering with security groups.

- Rules have numbers and are evaluated **in order, lowest number first**. The first match decides; later rules are ignored.
- Both **allow and deny** rules. Handy for blocking one bad IP range quickly.
- Each NACL ends with a `*` rule that denies everything not matched.
- The **default NACL allows all** inbound and outbound. A **custom NACL denies all** until you add rules.
- **Stateless** means return traffic is not automatically allowed. You must allow the response traffic on **ephemeral ports**. Clients pick a random high source port, so for replies you usually allow `1024-65535` (Linux uses 32768-60999, Windows 49152-65535, AWS docs suggest the wide range to cover everything).

Example NACL for a public web subnet:

| Rule # | Direction | Protocol | Port | Source/Dest | Action |
|---|---|---|---|---|---|
| 100 | Inbound | TCP | 443 | `0.0.0.0/0` | ALLOW |
| 110 | Inbound | TCP | 1024-65535 | `0.0.0.0/0` | ALLOW (replies to outbound calls) |
| * | Inbound | All | All | `0.0.0.0/0` | DENY |
| 100 | Outbound | TCP | 1024-65535 | `0.0.0.0/0` | ALLOW (replies to clients) |
| 110 | Outbound | TCP | 443 | `0.0.0.0/0` | ALLOW (instance calling HTTPS APIs) |
| * | Outbound | All | All | `0.0.0.0/0` | DENY |

### Security Group vs NACL

| | Security Group | Network ACL |
|---|---|---|
| Level | Instance (network interface) | Subnet |
| State | Stateful, return traffic allowed automatically | Stateless, return traffic needs its own rule |
| Rule types | Allow only | Allow and deny |
| Evaluation | All rules checked, any allow wins | Numbered order, first match wins |
| Default (new) | No inbound, all outbound | Default NACL: allow all. Custom NACL: deny all |
| Ephemeral ports | Not needed | Must open them (usually 1024-65535) |
| Source can be an SG | Yes | No, CIDR only |
| Applies to | Only resources the SG is attached to | Everything in the associated subnets |

Traffic coming into an instance passes the NACL first (subnet), then the SG (interface).

## Public vs private subnet

AWS has no "public" checkbox on a subnet. A subnet is **public** only because of its routing:

1. Its route table has `0.0.0.0/0` (or `::/0`) pointing to an **Internet Gateway**.
2. Instances in it have a **public IPv4 or Elastic IP** (otherwise they still cannot be reached, even with the route).

A **private** subnet has no route to the IGW. Its default route goes to a NAT gateway (outbound only) or nowhere at all (fully isolated, for example a database subnet).

| | Public subnet | Private subnet |
|---|---|---|
| Default route | IGW | NAT gateway (or none) |
| Public IP on instances | Yes | No |
| Reachable from internet | Yes, if SG/NACL allow | No |
| Typical contents | ALB, NAT gateway, bastion host | App servers, databases, EKS worker nodes |

## Architecture diagram

A standard 2-AZ VPC with one public and one private subnet per AZ:

```text
                                  Internet
                                      |
                           +---------------------+
                           |  Internet Gateway   |
                           +----------+----------+
                                      |
+-------------------------------------+-------------------------------------+
| VPC 10.0.0.0/16  (region ap-south-1)                                      |
|                                                                           |
|   AZ ap-south-1a                      AZ ap-south-1b                      |
|  +-------------------------------+     +-------------------------------+  |
|  | Public subnet 10.0.1.0/24     |     | Public subnet 10.0.2.0/24     |  |
|  |  [ALB node]  [NAT GW + EIP]   |     |  [ALB node]  [NAT GW + EIP]   |  |
|  |  RT: 0.0.0.0/0 -> IGW         |     |  RT: 0.0.0.0/0 -> IGW         |  |
|  +---------------+---------------+     +---------------+---------------+  |
|                  |                                     |                  |
|  +---------------+---------------+     +---------------+---------------+  |
|  | Private subnet 10.0.11.0/24   |     | Private subnet 10.0.12.0/24   |  |
|  |  [EC2 app]   [RDS primary]    |     |  [EC2 app]   [RDS standby]    |  |
|  |  RT: 0.0.0.0/0 -> NAT (1a)    |     |  RT: 0.0.0.0/0 -> NAT (1b)    |  |
|  +-------------------------------+     +-------------------------------+  |
|                                                                           |
|  All route tables also have: 10.0.0.0/16 -> local                         |
+---------------------------------------------------------------------------+
```

Request path: user -> IGW -> ALB in public subnet -> app instance in private subnet. Outbound path from the app: private subnet -> NAT gateway in the same AZ -> IGW -> internet.

### Terraform sketch

```hcl
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = { Name = "notes-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "ap-south-1a"
  map_public_ip_on_launch = true
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "ap-south-1a"
}

resource "aws_eip" "nat_a" {
  domain = "vpc"
}

resource "aws_nat_gateway" "a" {
  allocation_id = aws_eip.nat_a.id
  subnet_id     = aws_subnet.public_a.id   # NAT lives in the public subnet
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
}

resource "aws_route_table" "private_a" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.a.id
  }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private_a.id
}
```

The `b` side is the same with `10.0.2.0/24`, `10.0.12.0/24` and `ap-south-1b`. In real projects people often use the `terraform-aws-modules/vpc/aws` module, which builds all of this from a few inputs.

## Other ways to connect

Brief notes, not covered in depth:

- **VPC endpoints**: reach AWS services without going over the internet or through a NAT.
  - *Gateway endpoints*: only S3 and DynamoDB, added as a route table entry, free.
  - *Interface endpoints* (AWS PrivateLink): an ENI with a private IP in your subnet for most other services, charged per hour and per GB.
- **VPC peering**: a private 1:1 connection between two VPCs (same or different account or region). CIDRs must not overlap, and it is **not transitive** (A-B and B-C does not give A-C).
- **Transit Gateway**: a regional hub that many VPCs and on-premises networks attach to. Replaces a messy mesh of peering connections when you have lots of VPCs.
- **Site-to-Site VPN** and **Direct Connect**: link the VPC to an on-premises data center.

---

## Key takeaways

1. A VPC is regional and spans all AZs; each subnet sits in exactly one AZ.
2. VPC and subnet CIDRs must be between /16 and /28, and AWS reserves 5 IPs in every subnet (a /24 gives 251 usable).
3. A subnet is public only because its route table sends `0.0.0.0/0` to an Internet Gateway; everything else is private.
4. NAT gateways sit in public subnets with an Elastic IP, give private subnets outbound-only internet, should be one per AZ for HA, and cost money every hour.
5. Security groups are stateful, allow-only and attached to instances; NACLs are stateless, allow/deny, numbered and attached to subnets.
6. Plan non-overlapping CIDRs from RFC 1918 up front, because peering and VPN cannot handle overlaps.
7. Use gateway endpoints for S3 and DynamoDB to keep traffic private and cut NAT data charges.

## References

- [What is Amazon VPC?](https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html)
- [VPC CIDR blocks](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-cidr-blocks.html)
- [Subnet CIDR blocks](https://docs.aws.amazon.com/vpc/latest/userguide/subnet-sizing.html)
- [Configure route tables](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Route_Tables.html)
- [Enable internet access using an internet gateway](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Internet_Gateway.html)
- [NAT gateways](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html)
- [Security groups](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html)
- [Network ACLs](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-network-acls.html)
- [What is AWS PrivateLink?](https://docs.aws.amazon.com/vpc/latest/privatelink/what-is-privatelink.html)
- [What is VPC peering?](https://docs.aws.amazon.com/vpc/latest/peering/what-is-vpc-peering.html)
- [What is a transit gateway?](https://docs.aws.amazon.com/vpc/latest/tgw/what-is-transit-gateway.html)
