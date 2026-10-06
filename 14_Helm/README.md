# Session 15: Helm

**Name:** Parth Dagia
**Roll No:** 24BCS10414

Everything was run on my local kind cluster (`devops-lab`: 1 control plane + 1 worker) with **Helm v4.3.0** (`brew install helm`). Class material: [session-15-helm](https://github.com/Nency-Ravaliya/devops-heros/tree/main/session-15-helm).

| Task | What | Files |
|---|---|---|
| 1 | All important Helm commands (create, install, list, status, get, upgrade, history, rollback, uninstall, repo, search) | [01-helm-commands/README.md](01-helm-commands/README.md), chart [01-helm-commands/myapp/](01-helm-commands/myapp) |
| 2 | Rollback workflow: install → upgrade → verify → upgrade → verify → rollback → verify | [02-helm-rollback/README.md](02-helm-rollback/README.md) |
| 3 | Mini project: Notes app chart (dev/prod values, bad upgrade, rollback) | [03-mini-project/README.md](03-mini-project/README.md), chart [03-mini-project/notes-chart/](03-mini-project/notes-chart) |

Raw command output is in [logs/](logs) and terminal screenshots in [screenshots/](screenshots) (rendered from those logs with [shot.py](shot.py)).

---

## What is Helm

Helm is the package manager for Kubernetes. A **chart** is a folder of templated YAML + default values. Installing a chart creates a **release**; every install/upgrade/rollback creates a new **revision**, stored as a Secret in the release's namespace. That stored history is what makes `helm history` and `helm rollback` possible.

```text
Chart (templates + values.yaml) ──helm install──▶ Release "web" rev 1
                         --set / -f values ──helm upgrade──▶ rev 2
                                           ──helm rollback 1─▶ rev 3 (= rev 1 config)
```

| Term | Meaning |
|---|---|
| Chart | Package: `Chart.yaml`, `values.yaml`, `templates/` |
| Values | Inputs to the templates. Priority: `--set` > `-f file` > chart `values.yaml` |
| Release | One installed instance of a chart (same chart can be installed many times with different names) |
| Revision | Numbered version of a release |
| Repository | HTTP server (or OCI registry) hosting packaged charts |

## Deliverables

| Deliverable | Where |
|---|---|
| Helm chart | [03-mini-project/notes-chart/](03-mini-project/notes-chart), [01-helm-commands/myapp/](01-helm-commands/myapp) |
| values.yaml | [notes-chart/values.yaml](03-mini-project/notes-chart/values.yaml), [values-prod.yaml](03-mini-project/notes-chart/values-prod.yaml) |
| Templates | [notes-chart/templates/](03-mini-project/notes-chart/templates) |
| Installation | [Task 1 §3](01-helm-commands/README.md#3-helm-install), [Mini project step 3](03-mini-project/README.md#step-3-install-development) |
| Upgrade | [Task 1 §7](01-helm-commands/README.md#7-helm-upgrade), [Task 2](02-helm-rollback/README.md), [Mini project step 4](03-mini-project/README.md#step-4-upgrade-to-production-values) |
| Rollback | [Task 2](02-helm-rollback/README.md), [Mini project step 6](03-mini-project/README.md#step-6-bad-upgrade-then-rollback) |
| Screenshots | [screenshots/](screenshots) (15 images) |

## Key learnings

1. `helm rollback` never deletes history, it creates a new revision with the old config.
2. Without `--wait`, a broken upgrade (bad image) still shows `deployed`. Use `--wait` + `--rollback-on-failure` (v4) / `--atomic` (v3) in CI.
3. `helm get values` shows only what you overrode; `--all` shows the merged result.
4. `helm template` + `helm lint` catch most mistakes before touching the cluster.
5. Helm v4 applies manifests with server-side apply by default (`APPLY_METHOD: server-side apply` in `helm get metadata`).
