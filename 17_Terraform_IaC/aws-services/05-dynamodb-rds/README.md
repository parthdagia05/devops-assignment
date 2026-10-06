# 05. DynamoDB & RDS - Database Services

**Name:** Parth Dagia
**Roll No:** 24BCS10414

These are my notes on the two main managed database services in AWS. DynamoDB is a serverless NoSQL key-value and document database: there are no servers to size, you design around access patterns, and it scales almost without limit. RDS (Relational Database Service) runs normal SQL engines like PostgreSQL and MySQL for you, handling patching, backups and failover, while you still pick the instance size and write SQL. For each one I cover the core concepts, the security and availability features, and small aws CLI and Terraform examples. The last part compares the two and lists how I would choose between them.

## Contents

- [DynamoDB](#dynamodb)
  - [NoSQL](#nosql)
  - [Tables](#tables)
  - [Items](#items)
  - [Attributes](#attributes)
  - [Partition key](#partition-key)
  - [Sort key](#sort-key)
  - [Other DynamoDB features (brief)](#other-dynamodb-features-brief)
  - [DynamoDB examples](#dynamodb-examples)
  - [Use cases](#use-cases)
- [RDS](#rds)
  - [Relational database](#relational-database)
  - [Supported engines](#supported-engines)
  - [DB instances](#db-instances)
  - [Security](#security)
  - [Backups](#backups)
  - [Multi-AZ](#multi-az)
  - [Read replicas](#read-replicas)
  - [RDS examples](#rds-examples)
  - [Use cases](#use-cases-1)
- [DynamoDB vs RDS](#dynamodb-vs-rds)
- [Key takeaways](#key-takeaways)
- [References](#references)

---

## DynamoDB

Amazon DynamoDB is a fully managed, serverless NoSQL database. There is no instance to choose and no OS or engine version to patch. You create a table, define its key, and read/write through an API (HTTPS). Data is automatically replicated across three Availability Zones in the Region.

### NoSQL

"NoSQL" means "not only SQL": databases that do not use the classic relational model of fixed tables, joins and a schema enforced up front.

DynamoDB supports two NoSQL data models:

- **Key-value:** you look up a value by its key, like a giant hash map.
- **Document:** a value can be a nested JSON-like structure (maps and lists).

How it differs from a relational database:

| Point | Relational (SQL) | DynamoDB (NoSQL) |
|---|---|---|
| Schema | Fixed columns, defined before inserting | Only the primary key is fixed; other attributes can differ per item |
| Joins | Yes, normalise and join at query time | No joins; you denormalise and store data the way you read it |
| Query language | SQL, flexible ad-hoc queries | API calls (GetItem, Query, Scan), PartiQL also supported but still key-based |
| Scaling | Mostly vertical (bigger instance) plus read replicas | Horizontal, data split across partitions automatically |
| Design approach | Model the entities first, queries later | Model the access patterns first, then the table |

The big mindset change: in DynamoDB you must know your queries before designing the table.

### Tables

- A **table** is a collection of items, similar to a table in SQL.
- A table name is unique per account per Region.
- The only thing you must define when creating a table is the **primary key** (partition key, optionally plus sort key) and the capacity mode.
- There is no limit on how many items a table can hold.

### Items

- An **item** is one record in the table, like a row.
- Each item is identified uniquely by its primary key.
- Items in the same table can have different sets of attributes.
- **Maximum item size is 400 KB**, which includes attribute names and values. Large objects (images, files) should go to S3 with only the S3 key stored in DynamoDB.

### Attributes

An **attribute** is a single data element of an item, like a column, except it is not required on every item.

| Category | Types | Notes |
|---|---|---|
| Scalar | String (S), Number (N), Binary (B), Boolean (BOOL), Null (NULL) | One value. Numbers are sent as strings in the API but stored as numbers |
| Document | List (L), Map (M) | Nested structures, up to 32 levels deep |
| Set | String Set (SS), Number Set (NS), Binary Set (BS) | Unique values of one type, unordered, cannot be empty |

Key attributes (partition key and sort key) must be scalar of type String, Number or Binary.

### Partition key

- The **partition key** (also called the hash key) is the simple primary key.
- DynamoDB runs the partition key value through an internal hash function to decide which physical partition stores the item.
- With only a partition key, every item must have a unique partition key value.
- A good partition key has **high cardinality** and spreads traffic evenly (for example `userId`). A bad one, like `status` with only 3 values, creates "hot partitions".

### Sort key

- The **sort key** (also called the range key) is optional. Partition key + sort key together form a **composite primary key**.
- Many items can share the same partition key, but the combination of partition key and sort key must be unique.
- Items with the same partition key are stored together, sorted by sort key. This allows range queries such as `between`, `begins_with`, `>`, `<`.

Example: an `Orders` table with partition key `customerId` and sort key `orderDate`.

| customerId (PK) | orderDate (SK) | orderId | amount | status | items |
|---|---|---|---|---|---|
| C001 | 2026-01-14 | O-1001 | 1250 | DELIVERED | ["keyboard"] |
| C001 | 2026-03-02 | O-1042 | 499 | SHIPPED | ["mouse", "pad"] |
| C001 | 2026-09-21 | O-1107 | 3200 | PLACED | ["monitor"] |
| C002 | 2026-02-10 | O-1015 | 899 | DELIVERED | ["headphones"] |
| C003 | 2026-09-30 | O-1110 | 150 | CANCELLED | |

With this design, "get all orders for customer C001 in 2026" is a single efficient Query (`customerId = C001 AND begins_with(orderDate, "2026")`). Note C003 has no `items` attribute, which is fine in DynamoDB. In a real design the sort key would usually be `orderDate#orderId` so two orders on the same day do not collide.

### Other DynamoDB features (brief)

**Capacity modes**

| Mode | How it works | Good for |
|---|---|---|
| On-demand | Pay per read/write request, no capacity planning, scales automatically | New apps, spiky or unknown traffic (now the recommended default) |
| Provisioned | You set read capacity units (RCU) and write capacity units (WCU), optionally with auto scaling | Steady, predictable traffic where you want cost control |

1 RCU = one strongly consistent read per second of up to 4 KB (or two eventually consistent reads). 1 WCU = one write per second of up to 1 KB.

**Secondary indexes: GSI vs LSI**

| | Global Secondary Index (GSI) | Local Secondary Index (LSI) |
|---|---|---|
| Keys | Any partition key and optional sort key | Same partition key as the table, different sort key |
| When created | Any time | Only at table creation |
| Consistency | Eventually consistent reads only | Eventual or strong |
| Capacity | Its own capacity (provisioned mode) | Shares the table's capacity |
| Limits | Default quota of 20 per table | Up to 5 per table; 10 GB limit per partition key value |

**Query vs Scan**

- **Query:** needs the partition key value, optionally a sort key condition. Reads only matching items. Fast and cheap.
- **Scan:** reads every item in the table (or index) and then filters. Slow and expensive on big tables. Avoid in hot paths.
- Both return up to 1 MB per call and paginate with `LastEvaluatedKey`. A `FilterExpression` is applied after reading, so it does not reduce consumed capacity.

**Read consistency**

- **Eventually consistent (default):** may return slightly stale data right after a write. Costs half the capacity.
- **Strongly consistent:** returns the latest committed data. Set `ConsistentRead=true`. Not available on GSIs.

**TTL (Time to Live)**: pick a Number attribute holding an epoch timestamp in seconds. After that time DynamoDB deletes the item in the background (typically within a few days, not instantly) without consuming write capacity. Good for sessions, OTPs, temporary data.

**Streams**: DynamoDB Streams captures an ordered log of item changes (insert, modify, remove), kept for 24 hours. Commonly consumed by Lambda for triggers, audit logs or syncing to another store. View type can be KEYS_ONLY, NEW_IMAGE, OLD_IMAGE or NEW_AND_OLD_IMAGES.

**Backups**

- **Point-in-time recovery (PITR):** continuous backups; restore to any second within the recovery period (up to 35 days, configurable).
- **On-demand backups:** full backups kept until you delete them, also possible through AWS Backup.
- A restore always creates a **new table**.

**Global tables**: replicate a table across multiple Regions, with every replica accepting reads and writes (multi-active). The default is eventual consistency between Regions with last-writer-wins conflict resolution; a multi-Region strong consistency option also exists. Used for low-latency global apps and Region-level disaster recovery.

### DynamoDB examples

Create the `Orders` table (on-demand):

```bash
aws dynamodb create-table \
  --table-name Orders \
  --attribute-definitions \
      AttributeName=customerId,AttributeType=S \
      AttributeName=orderDate,AttributeType=S \
  --key-schema \
      AttributeName=customerId,KeyType=HASH \
      AttributeName=orderDate,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
```

Insert an item:

```bash
aws dynamodb put-item \
  --table-name Orders \
  --item '{
    "customerId": {"S": "C001"},
    "orderDate":  {"S": "2026-09-21"},
    "orderId":    {"S": "O-1107"},
    "amount":     {"N": "3200"},
    "status":     {"S": "PLACED"}
  }'
```

Query all 2026 orders of one customer:

```bash
aws dynamodb query \
  --table-name Orders \
  --key-condition-expression "customerId = :c AND begins_with(orderDate, :y)" \
  --expression-attribute-values '{":c": {"S": "C001"}, ":y": {"S": "2026"}}'
```

Same table in Terraform, with TTL, PITR and Streams turned on:

```hcl
resource "aws_dynamodb_table" "orders" {
  name         = "Orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customerId"
  range_key    = "orderDate"

  attribute {
    name = "customerId"
    type = "S"
  }

  attribute {
    name = "orderDate"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  tags = {
    Project = "devops-course"
  }
}
```

Only key attributes (and index keys) go in `attribute` blocks. Adding non-key attributes there is an error.

### Use cases

- User sessions, shopping carts, user profiles.
- Gaming leaderboards and player state.
- IoT and time-series style data (device id as partition key, timestamp as sort key).
- Serverless backends with API Gateway + Lambda.
- Metadata store for files kept in S3.
- Terraform state locking table (the classic S3 backend setup; newer Terraform versions can also lock using S3 itself).

---

## RDS

Amazon RDS is a managed service for running relational databases. AWS runs the database server for you: provisioning, OS and engine patching, automated backups, monitoring and failover. You still connect with a normal database client and write SQL.

### Relational database

- Data is stored in **tables** with fixed **columns** and **rows**.
- Each table has a **primary key**; tables are linked through **foreign keys**.
- Data is usually **normalised** (no duplication) and combined at query time with **joins**.
- Supports **ACID transactions** (Atomicity, Consistency, Isolation, Durability), so things like "debit one account and credit another" either fully happen or not at all.
- Queried with **SQL**, which is very flexible for ad-hoc queries, reporting and aggregation.

### Supported engines

| Engine | Notes |
|---|---|
| MySQL | Open source, very common for web apps |
| PostgreSQL | Open source, rich features (JSONB, extensions) |
| MariaDB | Community fork of MySQL |
| Oracle | Commercial; license included or bring your own license (BYOL) |
| Microsoft SQL Server | Commercial; Express, Web, Standard, Enterprise editions |
| IBM Db2 | Commercial; added to RDS in 2023 |
| Amazon Aurora (MySQL-compatible) | AWS-built engine, compatible with MySQL |
| Amazon Aurora (PostgreSQL-compatible) | AWS-built engine, compatible with PostgreSQL |

Aurora is managed through the RDS console/API but works differently: storage is a shared distributed volume replicated six ways across three AZs, it grows automatically, and you add up to 15 Aurora Replicas to the cluster. It also has a Serverless v2 option that scales capacity automatically.

### DB instances

A **DB instance** is the basic building block: an isolated database environment running one engine, with its own compute and storage.

**Instance classes** (format: `db.<family><generation>.<size>`, for example `db.t4g.micro`):

| Family | Type | Use |
|---|---|---|
| db.t (t3, t4g) | Burstable | Dev/test, small or low-traffic workloads (CPU credits) |
| db.m (m6g, m7g, m6i...) | General purpose | Balanced CPU and memory, most production apps |
| db.r (r6g, r7g, r6i...) | Memory optimised | Large datasets, heavy caching in memory, analytics-style queries |

The `g` suffix means AWS Graviton (ARM) processors, which usually give better price/performance.

**Storage types** (EBS-based):

| Type | Notes |
|---|---|
| gp3 (General Purpose SSD) | Default choice; baseline IOPS and throughput that you can raise separately from size |
| io1 (Provisioned IOPS SSD) | Older provisioned IOPS option for I/O heavy workloads |
| io2 (Provisioned IOPS SSD, Block Express) | Higher durability and lower latency than io1; for critical OLTP |

Storage autoscaling can grow allocated storage automatically up to a maximum you set. Storage can be increased but not shrunk.

**Managed by AWS vs what you still own:**

| AWS handles | You still own |
|---|---|
| Hardware, OS install and OS patching | Choosing instance class and storage |
| Database engine install and minor version patching (in maintenance window) | Schema design, indexes, query tuning |
| Automated backups and snapshots storage | Backup retention settings and testing restores |
| Multi-AZ replication and failover | Deciding to enable Multi-AZ / read replicas |
| Monitoring metrics (CloudWatch, Performance Insights) | Network setup: VPC, subnets, security groups |
| | Users, grants, application credentials |
| | Major version upgrades (you choose when) |

There is no SSH/OS access on standard RDS (RDS Custom exists for Oracle/SQL Server if you need it).

### Security

- **VPC and private subnets:** an RDS instance always runs inside a VPC. Put it in **private subnets** (no route to an Internet Gateway).
- **DB subnet group:** a named list of subnets that RDS can place the instance in. It must include subnets in at least **two AZs** (needed for Multi-AZ).
- **Security groups:** act as the firewall. Allow the DB port (5432 for PostgreSQL, 3306 for MySQL) only from the application's security group, not from `0.0.0.0/0`.
- **Not publicly accessible:** set `publicly_accessible = false` so no public IP is assigned. Access from a laptop goes through a bastion, VPN, or SSM port forwarding.
- **Encryption at rest:** uses **AWS KMS** (AWS managed key or your own customer managed key). Covers storage, automated backups, snapshots and read replicas. Must be enabled at creation; an unencrypted DB can only be encrypted by copying a snapshot with encryption and restoring it.
- **Encryption in transit:** connect over **TLS/SSL** using the RDS CA certificates. Can be forced, for example `rds.force_ssl = 1` in a PostgreSQL parameter group, or `require_secure_transport` for MySQL.
- **IAM database authentication:** (MySQL, MariaDB, PostgreSQL) the app gets a short-lived auth token (valid 15 minutes) using its IAM role instead of a stored password.
- **Secrets Manager managed master password:** with `--manage-master-user-password` RDS generates the master password, stores it in Secrets Manager and can rotate it. The password never appears in code or in Terraform state.

### Backups

- **Automated backups:** daily snapshot of the storage volume during the backup window, plus transaction logs uploaded to S3 about every 5 minutes.
- **Retention period:** **0 to 35 days**. Setting 0 disables automated backups (and also blocks read replicas). Automated backups are deleted when the instance is deleted, unless you choose to retain them.
- **Point-in-time recovery (PITR):** restore to any second within the retention period, usually up to about the last 5 minutes (`LatestRestorableTime`). A restore creates a **new DB instance** with a new endpoint.
- **Manual snapshots:** taken by you, kept until you delete them, even after the instance is deleted. Good before upgrades or risky changes. A **final snapshot** can be taken on deletion.
- **Cross-region copy:** snapshots can be copied to another Region (and shared with other accounts). Automated backups can also be replicated to another Region for DR.

### Multi-AZ

Multi-AZ is for **high availability**, not for performance.

**Multi-AZ DB instance deployment:**

- RDS creates a **standby** in a different AZ and replicates to it **synchronously**.
- The standby **cannot be read from**; it is only there for failover.
- On failure (instance, AZ, storage) or during some maintenance, RDS does an **automatic failover**: the DNS endpoint is pointed to the standby. Typically takes 1 to 2 minutes. The app just reconnects to the same endpoint.

**Multi-AZ DB cluster deployment** (MySQL and PostgreSQL):

- One writer plus **two readable standbys**, each in a different AZ.
- Uses semi-synchronous replication; a write is committed once at least one standby acknowledges it.
- Faster failover (typically under 35 seconds) and a reader endpoint for the standbys.

Important exam point: classic Multi-AZ is **NOT for read scaling**. Use read replicas for that.

### Read replicas

- Copies of the primary updated using **asynchronous** replication, so they can lag a little behind.
- Used for **read scaling**: send reporting, analytics or read-heavy traffic to the replica endpoints.
- Up to 15 read replicas per source for MySQL, MariaDB and PostgreSQL (Oracle and SQL Server also support them with their own limits).
- Can be in the same AZ, another AZ, or **another Region** (cross-region replicas help with DR and global reads).
- A replica can be **promoted** to a standalone DB instance. Promotion is manual and breaks replication; useful for DR or splitting a database.
- Each replica has its own endpoint. A replica can itself be Multi-AZ.

**Multi-AZ vs read replica:**

| | Multi-AZ (instance) | Read replica |
|---|---|---|
| Main purpose | High availability, failover | Read scaling |
| Replication | Synchronous | Asynchronous |
| Readable | No (standby only) | Yes |
| Location | Different AZ, same Region | Same AZ, cross-AZ or cross-Region |
| Failover | Automatic, same endpoint | Manual promotion, new endpoint |
| Count | One standby | Up to 15 (engine dependent) |

### RDS examples

Create a private, encrypted PostgreSQL instance with Multi-AZ:

```bash
aws rds create-db-instance \
  --db-instance-identifier app-db \
  --engine postgres \
  --db-instance-class db.t4g.micro \
  --allocated-storage 20 \
  --storage-type gp3 \
  --storage-encrypted \
  --master-username dbadmin \
  --manage-master-user-password \
  --db-subnet-group-name app-db-subnets \
  --vpc-security-group-ids sg-0123456789abcdef0 \
  --no-publicly-accessible \
  --backup-retention-period 7 \
  --multi-az
```

Create a read replica of it:

```bash
aws rds create-db-instance-read-replica \
  --db-instance-identifier app-db-replica-1 \
  --source-db-instance-identifier app-db
```

Terraform version:

```hcl
resource "aws_db_subnet_group" "app" {
  name       = "app-db-subnets"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}

resource "aws_db_instance" "app" {
  identifier     = "app-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t4g.micro"

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  username                    = "dbadmin"
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.app.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false

  multi_az                = true
  backup_retention_period = 7
  deletion_protection     = true
  skip_final_snapshot     = false
  final_snapshot_identifier = "app-db-final"
}
```

`max_allocated_storage` turns on storage autoscaling. Because of `manage_master_user_password`, no password is written in the code; the secret ARN is available as `aws_db_instance.app.master_user_secret`.

### Use cases

- Traditional web and business applications (CMS, ERP, CRM, e-commerce backends).
- Anything that needs transactions across several tables (payments, banking, inventory).
- Applications that need complex queries, joins, reporting and aggregations.
- Lift-and-shift of an existing MySQL/PostgreSQL/Oracle/SQL Server database to AWS.
- Apps built on frameworks and ORMs that expect SQL (Django, Rails, Spring, Laravel).

---

## DynamoDB vs RDS

| Point | DynamoDB | RDS |
|---|---|---|
| Type | NoSQL (key-value and document) | Relational (SQL) |
| Server management | Serverless, nothing to size | You choose instance class and storage |
| Schema | Flexible, only key is fixed | Fixed schema, migrations needed for changes |
| Query style | By key (GetItem/Query), Scan is costly | Any SQL, joins, aggregations |
| Joins | Not supported | Supported |
| Transactions | Supported (TransactWriteItems, limited to 100 items) | Full ACID across tables |
| Scaling | Horizontal, automatic, very high throughput | Vertical (bigger instance) plus read replicas |
| Availability | 3 AZs by default; global tables for multi-Region | Single-AZ unless you enable Multi-AZ |
| Connection | HTTPS API, no connection pooling issues | Persistent DB connections (watch limits; RDS Proxy helps) |
| Max item / row size | 400 KB per item | Engine dependent, much larger |
| Backups | PITR (up to 35 days) and on-demand | Automated (0 to 35 days), PITR, manual snapshots |
| Pricing model | Per request (on-demand) or per capacity unit, plus storage | Per instance hour, plus storage, IOPS and backups |
| Best for | Known access patterns at large scale | Complex relationships and ad-hoc queries |

**How I'd choose:**

1. If the data is relational and I need joins, reporting or multi-table transactions, I pick **RDS** (PostgreSQL by default).
2. If I know my access patterns up front and they are simple lookups by key, I pick **DynamoDB**.
3. For serverless apps (Lambda + API Gateway), I lean to **DynamoDB** because there are no connections to manage and it scales to zero cost-wise with on-demand.
4. For very high or unpredictable scale (millions of requests per second), **DynamoDB**.
5. If the team already knows SQL or uses an ORM, or I am migrating an existing database, **RDS**.
6. If I need the RDS model but with better availability and scaling, I look at **Aurora**.
7. Using both is normal: for example RDS for orders and billing, DynamoDB for sessions and carts.

---

## Key takeaways

1. DynamoDB is serverless NoSQL: design the table from the access patterns, not from the entities.
2. A DynamoDB primary key is either a partition key alone or a partition key + sort key (composite); items are limited to 400 KB.
3. Prefer Query over Scan, and use GSIs to support extra access patterns (LSIs only at table creation).
4. RDS gives you managed SQL engines (MySQL, PostgreSQL, MariaDB, Oracle, SQL Server, Db2, Aurora), but you still own schema, sizing, networking and credentials.
5. Secure RDS with private subnets, a DB subnet group, tight security groups, KMS encryption, TLS, and Secrets Manager or IAM auth instead of hard-coded passwords.
6. RDS automated backups keep 0 to 35 days and allow point-in-time restore to a new instance; manual snapshots stay until deleted.
7. Multi-AZ (synchronous standby) is for availability; read replicas (asynchronous) are for read scaling.
8. Both services can be fully defined in Terraform (`aws_dynamodb_table`, `aws_db_instance`), which keeps the setup repeatable.

## References

- [What is Amazon DynamoDB?](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html)
- [DynamoDB core components](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.CoreComponents.html)
- [DynamoDB read/write capacity modes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadWriteCapacityMode.html)
- [DynamoDB secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/SecondaryIndexes.html)
- [DynamoDB Time to Live (TTL)](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)
- [DynamoDB Streams](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html)
- [DynamoDB global tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html)
- [What is Amazon RDS?](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html)
- [RDS DB instance classes](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.html)
- [RDS DB instance storage](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html)
- [RDS automated backups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html)
- [RDS Multi-AZ deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html)
- [RDS read replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html)
- [IAM database authentication for RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html)
- [RDS password management with Secrets Manager](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html)
