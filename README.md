# DevOps Assignment 1

**Name:** Parth Dagia
**Roll No:** 24BCS10414

This is my homework for the DevOps course. Each topic has its own folder, and every folder has a `README.md` with the commands I ran, the output from my terminal, screenshots and what I understood from it.

## Section A: Submission links

| # | Topic | README |
|---|---|---|
| 1 | Linux Fundamentals | [01_Linux_Fundamental/README.md](01_Linux_Fundamental/README.md) |
| 2 | Shell Scripting | [02_shell_scripting/README.md](02_shell_scripting/README.md) |
| 3 | Networking | [03_networking/README.md](03_networking/README.md) |
| 4 | Git and GitHub | [04_git/README.md](04_git/README.md) |
| 5 | Docker Fundamentals | [05_Docker_Fundamental/README.md](05_Docker_Fundamental/README.md) |
| 6 | Dockerfiles and Images (multi stage build) | [06_DockerFiles_Images/README.md](06_DockerFiles_Images/README.md) |
| 7 | Docker Networking and Volumes | [07_Docker_Networking/README.md](07_Docker_Networking/README.md) |
| 8 | Kubernetes Fundamentals | [08_Kubernetes_Fundamentals/README.md](08_Kubernetes_Fundamentals/README.md) |
| 9 | Kubernetes Pods, ReplicaSets and Deployments | [09_K8s_Pods_ReplicaSets_Deployments/README.md](09_K8s_Pods_ReplicaSets_Deployments/README.md) |
| 10 | Kubernetes Networking and Services | [10_K8s_Networking_Services/README.md](10_K8s_Networking_Services/README.md) |
| 11 | Kubernetes Ingress, ConfigMaps and Secrets | [11_K8s_Ingress_ConfigMaps_Secrets/README.md](11_K8s_Ingress_ConfigMaps_Secrets/README.md) |
| 12 | Session 12: ConfigMaps, Secrets, Ingress, Ingress vs Controller and Troubleshooting | [12_K8s_ConfigMaps_Secrets_Ingress_Troubleshooting/README.md](12_K8s_ConfigMaps_Secrets_Ingress_Troubleshooting/README.md) |
| 13 | Session 13: Kubernetes Storage, HPA and Probes | [13_K8s_Storage_HPA_Probes/README.md](13_K8s_Storage_HPA_Probes/README.md) |
| 14 | Session 15: Helm | [14_Helm/README.md](14_Helm/README.md) |
| 15 | Session 16: CI/CD and GitHub Actions | [15_CICD_GitHub_Actions/README.md](15_CICD_GitHub_Actions/README.md) (repo: <https://github.com/parthdagia05/session16-cicd-github-actions>) |
| 16 | Session 17: Complete CI/CD and DevSecOps | [16_DevSecOps_Pipeline/README.md](16_DevSecOps_Pipeline/README.md) (workflow: [.github/workflows/session17-devsecops.yml](.github/workflows/session17-devsecops.yml)) |
| 17 | Session 18: Terraform and Infrastructure as Code (+ AWS IAM, EC2, S3, VPC, DynamoDB/RDS notes) | [17_Terraform_IaC/README.md](17_Terraform_IaC/README.md) |
| 18 | Session 19: Cloud & Terraform in Action (VPC, subnet, security group, EC2, S3) | [18_Cloud_Terraform_Project/README.md](18_Cloud_Terraform_Project/README.md) |
| 19 | Session 20: Monitoring, Observability and GitOps (Prometheus, Grafana, Alertmanager, Loki, Jaeger, Argo CD) | [19_Monitoring_Observability_GitOps/README.md](19_Monitoring_Observability_GitOps/README.md) |

## My setup

- MacBook Air (Apple Silicon) with Docker Desktop
- Linux tasks: inside an `ubuntu:24.04` container
- Kubernetes: a local 2 node cluster (1 control plane + 1 worker) made with [kind](https://kind.sigs.k8s.io/), config in [08_Kubernetes_Fundamentals/kind-cluster.yaml](08_Kubernetes_Fundamentals/kind-cluster.yaml)
- Class repository used for the labs: <https://github.com/Nency-Ravaliya/devops-heros>
