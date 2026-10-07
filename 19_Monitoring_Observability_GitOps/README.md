# Session 20: Monitoring, Observability & GitOps

**Name:** Parth Dagia
**Roll No:** 24BCS10414

Everything in this session ran on my local 2-node kind cluster (`devops-lab`, Kubernetes v1.37). I installed a full monitoring and observability stack (Prometheus, Alertmanager, Grafana, node-exporter, kube-state-metrics, Loki, Alloy, Jaeger), deployed a small two-service demo app that produces **metrics, logs and traces**, and then broke it on purpose (CPU/memory stress, an outage) to see the alerts fire and resolve. For GitOps I set up **Argo CD** with an in-cluster **Gitea** server as the Git source of truth and ran the full workflow: bootstrap, change through Git, drift and self-heal, prune, and rollback with `git revert`.

Every command's output is saved in [logs/](logs). The terminal screenshots are rendered from those logs with [shot.py](shot.py). The `ui-*.png` screenshots are real screenshots of the web UIs, taken through `kubectl port-forward`.

## Deliverables

| Deliverable | Where |
|---|---|
| Monitoring demo | [Task 1](#task-1-monitoring), manifests in [01-monitoring/](01-monitoring), logs 01–07 |
| Observability documentation | [Task 2](#task-2-observability), manifests in [02-observability/](02-observability), logs 08, 09, 15 |
| GitOps demo | [Task 3](#task-3-gitops), manifests in [03-gitops/](03-gitops), logs 10–14 |
| Screenshots | [screenshots/](screenshots): 15 terminal + 19 UI screenshots ([gallery](#screenshots)) |
| Architecture diagram | [diagram/architecture.png](diagram/architecture.png) ([svg](diagram/architecture.svg)) |
| README.md | this file |

## Architecture

![architecture](diagram/architecture.png)

| Component | Version | Role |
|---|---|---|
| kube-prometheus-stack (Helm chart 92.0.0) | Prometheus v3.15.0, Alertmanager v0.34.1, Grafana 13.2.3, node-exporter v1.12.1, kube-state-metrics v2.20.0 | metrics, alerts, dashboards |
| Loki (chart 7.3.0) | 3.6.11, single binary | log storage + LogQL |
| Grafana Alloy (chart 1.13.0) | v1.20.0, DaemonSet | ships every pod's logs to Loki |
| Jaeger | 2.11.0 all-in-one | trace storage + UI (OTLP receiver) |
| podinfo | 6.9.1 / 6.9.2 | the demo app (has `/metrics`, `/healthz`, `/readyz`, JSON logs, OpenTelemetry) |
| Argo CD (chart 10.9.6) | v3.5.3 | GitOps controller |
| Gitea | 1.24.6 | in-cluster Git server, stands in for GitHub |

## Folder layout

```text
19_Monitoring_Observability_GitOps/
├── 01-monitoring/
│   ├── kube-prometheus-stack-values.yaml  # Prometheus/Alertmanager/Grafana config, alert routing, Loki+Jaeger datasources
│   ├── demo-app.yaml                      # frontend + backend (podinfo), loadgen, alert-logger webhook receiver
│   ├── servicemonitor.yaml                # tells Prometheus to scrape the demo app
│   ├── alert-rules.yaml                   # PrometheusRule: 6 alerts + 2 recording rules
│   ├── make_dashboard.py                  # generates the dashboard below
│   └── grafana-dashboard.yaml             # "Demo App - Monitoring" dashboard as a ConfigMap
├── 02-observability/
│   ├── loki-values.yaml                   # Loki single-binary, filesystem storage
│   ├── alloy-values.yaml                  # Alloy DaemonSet config (Kubernetes discovery -> Loki)
│   └── jaeger.yaml                        # Jaeger v2 Deployment + Service
├── 03-gitops/
│   ├── platform/gitea.yaml                # the Git server
│   ├── platform/argocd-values.yaml        # Argo CD install values
│   ├── bootstrap/root-app.yaml            # the one manifest applied by hand (app of apps)
│   ├── gitops-repo/                       # final contents of the Git repo Argo CD watches
│   └── gitops-repo-history.txt            # git log --stat of that repo
├── diagram/                               # architecture diagram
├── logs/                                  # 15 command logs
├── screenshots/                           # terminal + UI screenshots
└── shot.py                                # renders logs/*.log -> screenshots/*.png
```

---

## Task 1: Monitoring

### What monitoring is

Monitoring means collecting known signals from a system all the time, so you can **see** whether it's healthy and get **told** when it isn't. It answers questions you already know to ask: *is the service up? is CPU too high? are we returning errors?*

| Concept | What it is | In my demo |
|---|---|---|
| **Metrics** | Numbers sampled over time, with labels (`http_requests_total{status="500"}`). Cheap to store and fast to query and graph. | Prometheus scrapes `/metrics` from every pod every 15s, plus node-exporter (node CPU/mem/disk), kubelet/cAdvisor (container CPU/mem) and kube-state-metrics (Kubernetes object state). |
| **Logs** | Timestamped text records of individual events. They tell you *what exactly happened*. | podinfo writes JSON logs to stdout; Alloy ships them to Loki; I query them with LogQL in Grafana. |
| **Alerts** | Rules evaluated against metrics. When a rule stays true for a `for:` duration it fires, and Alertmanager groups it, de-duplicates it and routes it to a receiver (Slack, PagerDuty, email, webhook…). | 6 rules in [alert-rules.yaml](01-monitoring/alert-rules.yaml); Alertmanager sends `team="demo"` alerts to a webhook receiver whose logs I read. |
| **CPU utilisation** | CPU time used per second, compared with what's available. For a container the useful number is **usage ÷ limit**, because at 100% of its limit the container is throttled. | `rate(container_cpu_usage_seconds_total[1m]) / kube_pod_container_resource_limits{resource="cpu"}`; alert above 80% for 1m. |
| **Memory utilisation** | Working-set bytes (what the kernel can't reclaim) compared with the limit. Past the limit the container is **OOMKilled**. | `container_memory_working_set_bytes / kube_pod_container_resource_limits{resource="memory"}`; alert above 80% for 1m. |
| **Application health** | Is the app alive and able to serve? Kubernetes checks this with **liveness** probes (restart if dead) and **readiness** probes (remove from Service endpoints if not ready). Prometheus checks it with the `up` metric (could it scrape the target?). | `/healthz` = liveness, `/readyz` = readiness; `PodinfoDown` fires when no backend target is up; `PodinfoPodNotReady` uses kube-state-metrics. |

The four **golden signals** (Google SRE book) are latency, traffic, errors and saturation. The dashboard has a panel for each: request rate, 5xx ratio, p50/p95 latency, and CPU/memory against limits.

### The demo app

[demo-app.yaml](01-monitoring/demo-app.yaml), namespace `demo`:

- **frontend** (2× podinfo): every `POST /echo` calls the backend, so one request crosses two services.
- **backend** (2× podinfo): adds a random 0–300 ms delay, so latency graphs aren't flat.
- **loadgen**: a curl loop, about 4 req/s to the frontend, with a `/status/500` every 10th round and a 1 s `/delay/1` every 15th, so there are errors and slow requests to look at.
- **alert-logger**: an HTTP echo server; Alertmanager posts alerts to it and it prints each body to its log.

Both podinfo deployments have liveness/readiness probes and CPU/memory **requests and limits**. The limits are what make the "% of limit" metrics and alerts meaningful.

How Prometheus finds the app without editing any Prometheus config: the Prometheus Operator watches `ServiceMonitor` objects. [servicemonitor.yaml](01-monitoring/servicemonitor.yaml) selects every Service labelled `app.kubernetes.io/part-of: podinfo`, and the operator turns that into scrape config. All 4 pods show `UP` in [ui-02](screenshots/ui-02-prometheus-targets.png).

### Alert rules

[alert-rules.yaml](01-monitoring/alert-rules.yaml) (a `PrometheusRule`):

| Alert | Expression (short) | for | Severity |
|---|---|---|---|
| `PodinfoDown` | `sum by (service)(up) == 0` or `absent(up{service="backend"})` | 30s | critical |
| `PodinfoPodNotReady` | `kube_pod_status_ready{condition="false"} > 0` | 30s | warning |
| `PodinfoHighErrorRate` | 5xx ÷ all requests > 5% | 1m | warning |
| `PodinfoHighLatencyP95` | `histogram_quantile(0.95, …) > 1s` | 2m | warning |
| `PodinfoHighCPU` | CPU usage ÷ CPU limit > 80% | 1m | warning |
| `PodinfoHighMemory` | working set ÷ memory limit > 80% | 1m | warning |

There are also two **recording rules** (`podinfo:http_requests:rate1m`, `podinfo:http_errors:ratio1m`). They precompute the expensive queries every 15s; the dashboard and the error-rate alert both use them.

`absent()` matters in `PodinfoDown`: when the backend is scaled to 0 there are **no** `up` series for it at all, so `up == 0` would never match. `absent()` returns 1 exactly when the series disappears.

Alertmanager routing (in [kube-prometheus-stack-values.yaml](01-monitoring/kube-prometheus-stack-values.yaml)): alerts with `team="demo"` go to the `webhook-logger` receiver, grouped by `alertname, namespace`, `group_wait: 10s`, `send_resolved: true`. Everything else goes to a `null` receiver.

### Demo 1: CPU and memory alerts ([05](logs/05-alert-firing.log), [06](logs/06-alert-resolved.log))

I patched the backend to start podinfo with `--stress-cpu=1 --stress-memory=95` (burn one full core, hold 95 MB) while its limits are 200m CPU / 128Mi memory:

```text
$ kubectl top pods -n demo -l app=backend
backend-6b4ff5f57f-49cg9   200m   108Mi        # pinned at the CPU limit (throttled)
backend-6b4ff5f57f-mvzd5   200m   109Mi

CPU ÷ limit:     0.998, 0.999
memory ÷ limit:  0.864, 0.850
```

The alert lifecycle was exactly **inactive → pending → firing**:

| Time after patch | `PodinfoHighCPU` / `PodinfoHighMemory` | Why |
|---|---|---|
| 0 s | inactive | rule false |
| ~40 s | **pending** | rule true, but not yet for the full `for: 1m` |
| ~100 s | **firing** | true for 1m, so sent to Alertmanager |

Alertmanager delivered them to the webhook (each line below is one alert inside a POST body):

```text
POST from Alertmanager  status=firing   PodinfoHighMemory  backend-6b4ff5f57f-mvzd5  "memory at 85.31% of its limit"
POST from Alertmanager  status=firing   PodinfoHighCPU     backend-6b4ff5f57f-mvzd5  "CPU at 86.43% of its limit"
...
```

Then I re-applied the original manifest. About 2 minutes later all rules were `inactive`, Alertmanager held 0 alerts, and the webhook received a `status=resolved` message for each one.

> **A flap I didn't expect.** One `PodinfoHighCPU` alert resolved *before* I removed the stress. Querying the history showed why: the throttled CPU ratio was `1.0, 1.0, 0.791, 1.001, …`. One 15s evaluation dipped under 0.8, the rule went false, and Alertmanager sent "resolved". For real alerts you'd add hysteresis (`keep_firing_for: 2m`) or alert on a longer `rate()` window so one noisy sample can't resolve a page.

### Demo 2: application health and an outage ([07](logs/07-health-outage.log))

`kubectl scale deploy backend --replicas=0`:

- The backend Service had no endpoints, and the frontend logged `backend call failed … connection refused`.
- `absent(up{service="backend"}) => 1` → **`PodinfoDown` fired** (critical) after 30s, delivered to the webhook; after scaling back to 2 it **resolved**.
- The frontend's own `/healthz` stayed `200`, which is correct: the frontend process was fine, so Kubernetes had no reason to restart it.

The interesting part: **the frontend still answered `HTTP 200`** to `POST /echo` while the backend was down (podinfo puts the error in the response body). So the 5xx error-ratio metric didn't move and `PodinfoHighErrorRate` never fired. Only the **logs** and **traces** showed the failure, which is the argument for Task 2.

### Grafana dashboard

[make_dashboard.py](01-monitoring/make_dashboard.py) builds the "Demo App – Monitoring" dashboard and writes it into a ConfigMap labelled `grafana_dashboard: "1"`; the Grafana sidecar loads it automatically, so the dashboard is code too. Rows: **application health** (targets up, ready pods, restarts, firing alerts), **golden signals** (req/s, 5xx ratio, p50/p95), **resources** (pod CPU % of limit, pod memory, node CPU/memory), **logs** (live Loki panel).

| Normal (45 min view: stress at ~05:08, outage at ~05:18) | During the stress test |
|---|---|
| ![dashboard](screenshots/ui-01-grafana-dashboard.png) | ![stress](screenshots/ui-03-grafana-stress.png) |

In the 45-minute view you can see the CPU spike to 100% of the limit and memory jump to ~110 MiB during the stress test, then the backend request rate and latency drop to zero during the outage.

---

## Task 2: Observability

### Monitoring vs observability

**Monitoring** tells you *that* something is wrong, using checks you decided on in advance. **Observability** is a property of the system: how well you can work out *why* it's wrong, including failures you never predicted, from the telemetry it produces. A system is observable when you can answer new questions without shipping new code.

The outage above is a small example. The monitoring I had set up in advance (5xx ratio) said everything was fine. The logs and traces showed what was actually broken.

### The three pillars

| Pillar | What it is | Good at | Weak at | Example from my run |
|---|---|---|---|---|
| **Metrics** | Numeric time series: name + labels + value, sampled at intervals. Aggregated, so cheap to keep for a long time. | Trends, dashboards, alerting, capacity planning; "how much / how often". | Detail. A counter tells you there were 37 errors, not which request or why. High-cardinality labels (user IDs) blow up storage. | `podinfo:http_requests:rate1m{service="frontend"} => 2.55` req/s |
| **Logs** | Timestamped records of discrete events, ideally structured (JSON) so fields are queryable. | The exact details of one event: error messages, stack traces, inputs. | Volume and cost; hard to follow one request across many services; you only find what you thought to log. | `{"level":"error","msg":"backend call failed","error":"… connection refused","trace_id":"…"}` |
| **Traces** | The path of **one request** through the system. A trace is a tree of **spans**; each span is one operation with a start, duration, service, attributes and status. Context (trace ID) is passed between services in HTTP headers (W3C `traceparent`). | Latency breakdowns ("where did the 280 ms go?"), finding which hop failed, service dependency maps. | Needs instrumentation in code; usually **sampled** in production, so not every request is kept. | `frontend POST /echo → HTTP POST → backend POST /echo`, 9 spans, 2 services |

The pillars are most useful **connected**. In this setup every podinfo log line carries the `trace_id` of its request, and the Loki datasource has a *derived field* that turns that ID into a link to the trace in Jaeger. So you can go metric spike → logs from that minute → the exact trace.

### Why observability is needed

- **Distributed systems fail in new ways.** One user request in a microservice app touches many services, queues and databases. "The site is slow" could be any of them, and the cause is often something nobody wrote a check for.
- **Containers are short-lived.** Pods get rescheduled and their IPs and names change; you can't SSH into the box later. The telemetry has to be collected centrally as it happens.
- **Faster recovery (MTTR).** Going straight from an alert to the failing span or error log is much faster than guessing.
- **Health isn't binary.** In my outage the frontend was "healthy" by every probe while every `/echo` request was silently failing.
- **Performance and cost.** Traces show which hop adds latency; metrics show which pods are over- or under-provisioned (see the 87.7% memory-of-requests figure in [ui-19](screenshots/ui-19-grafana-k8s-namespace.png)).
- **SLOs.** Service-level objectives (e.g. 99.9% of requests under 300 ms) are computed from metrics and drive alerting and error budgets.

### Common tools

| Area | Open source | Managed / commercial |
|---|---|---|
| Metrics | **Prometheus** (used here), Thanos / Cortex / Mimir (long-term, multi-cluster), VictoriaMetrics | Amazon CloudWatch, Google Cloud Monitoring, Azure Monitor, Datadog, New Relic |
| Logs | **Loki** + **Alloy**/Promtail (used here), ELK/EFK (Elasticsearch + Logstash/Fluentd/Fluent Bit + Kibana), OpenSearch | CloudWatch Logs, Splunk, Datadog Logs |
| Traces | **Jaeger** (used here), Grafana Tempo, Zipkin | AWS X-Ray, Datadog APM, Honeycomb, Dynatrace |
| Instrumentation standard | **OpenTelemetry** (SDKs + Collector; vendor-neutral, covers all three pillars; podinfo uses its Go SDK here) | – |
| Visualisation | **Grafana** (used here), Kibana | vendor UIs |
| Alerting | **Alertmanager** (used here), Grafana Alerting | PagerDuty, Opsgenie |

### Kubernetes observability ([15](logs/15-k8s-observability.log))

Kubernetes has observability at several layers; this run touched each one:

| Layer | Built into Kubernetes | Added by the stack |
|---|---|---|
| Cluster control plane | `kubectl get --raw '/readyz?verbose'` (API server health checks) | API server metrics, `Kubernetes / API server` dashboard |
| Nodes | `kubectl top nodes` (metrics-server) | **node-exporter**: CPU, memory, disk, network per node |
| Containers | `kubectl top pods --containers`; kubelet's **cAdvisor** exposes `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes` | Prometheus scrapes the kubelet; 16 built-in "Kubernetes / Compute Resources / …" dashboards |
| Object state | `kubectl get/describe`, `kubectl get events` (e.g. `Readiness probe failed`, `Killing`, `ScalingReplicaSet`) | **kube-state-metrics** turns object state into metrics: `kube_pod_status_ready`, `kube_deployment_status_replicas_unavailable`, `kube_pod_container_resource_limits` |
| App health | liveness / readiness / startup **probes** | `up` per scrape target, `PodinfoDown` alert |
| Logs | `kubectl logs` (only the current and previous container, lost when the pod is deleted) | **Alloy DaemonSet** on every node (control plane too, via a toleration) tails `/var/log/pods` and adds `namespace/pod/container/app` labels from the API; **Loki** keeps them after the pod is gone |
| Traces | – | OpenTelemetry SDK in the app → **Jaeger** |

A few things Kubernetes-specific I noticed:

- **Labels are the join key.** The same `namespace`/`pod`/`app` labels appear on metrics (from the ServiceMonitor), on log streams (from Alloy's relabel rules) and in events, which is what lets Grafana correlate them.
- **The Prometheus Operator pattern** (`ServiceMonitor`, `PrometheusRule`) puts monitoring config in the same Git repo and namespace as the app instead of a central Prometheus config file.
- **kind caveat:** etcd, the scheduler and the controller manager bind their metrics ports to `127.0.0.1` inside the node container, so Prometheus can't reach them. I disabled those scrape jobs and their default rules in the values file instead of living with permanent "target down" alerts.

![k8s namespace dashboard](screenshots/ui-19-grafana-k8s-namespace.png)

### Logs demo: LogQL ([08](logs/08-logs-loki.log))

Loki only indexes **labels**, not the log text, which keeps it cheap. You select streams by label and then filter or parse:

```logql
{namespace="demo", app="frontend"} |= "backend call failed"           # text filter
{namespace="demo", app="frontend"} | json | level="error"              # parse JSON, filter on a field
  | line_format "{{.ts}} {{.msg}} -> {{.error}}"                         # reshape the line
sum by (app, level) (count_over_time({namespace="demo"} | json [1m]))  # logs -> metrics
topk(3, sum by (uri) (count_over_time({app="frontend"} | json | msg="request started" [5m])))
```

During the outage the third query showed `app=frontend, level=error => 86` lines/minute, while the metrics-based error ratio stayed at its normal ~3.7%.

| Error logs during the outage | Log lines per app/level over time |
|---|---|
| ![loki errors](screenshots/ui-07-loki-error-logs.png) | ![logql metrics](screenshots/ui-08-loki-logql-metrics.png) |

In the right-hand graph, `frontend/error` (orange) appears at ~05:18 exactly when `backend/debug` (green) drops to zero.

### Traces demo: Jaeger ([09](logs/09-traces-jaeger.log))

Both podinfo deployments run with `--otel-service-name` and `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger.observability.svc:4317`, so every request creates spans, and the frontend's HTTP client passes the trace context to the backend.

**Log → trace:** I took the `trace_id` from a frontend log line and opened it:

```text
trace 265f4290c6fdd27202e47d0528fda90b: 9 spans, services: ['backend', 'frontend']
frontend  POST /echo     +   0.00ms     52.40ms  200
  frontend  echoHandler    +   0.04ms     52.36ms
    frontend  HTTP POST      +   0.13ms     52.21ms  202
      backend   POST /echo     +   0.48ms     51.70ms  202     <- almost all of the 52 ms is here (backend's random delay)
        backend   echoHandler    +  52.07ms      0.07ms
```

**A failed request during the outage**: the client got `200`, but the trace shows the problem directly:

```text
trace 5bd1242eef3ee20db540375b335be6c2: 5 spans, services: ['frontend']   <- backend never appears
frontend  POST /echo     +   0.00ms      2.07ms  200
  frontend  echoHandler    +   0.14ms      1.90ms
    frontend  HTTP POST      +   0.28ms      1.61ms    ERROR
frontend  http.connect   +   1.72ms      0.14ms    ERROR
```

| Healthy trace (Jaeger) | Failed trace (Jaeger) |
|---|---|
| ![trace](screenshots/ui-11-jaeger-trace.png) | ![failed trace](screenshots/ui-10-jaeger-failed-trace.png) |

| Trace search | Same trace inside Grafana (Jaeger datasource) |
|---|---|
| ![search](screenshots/ui-09-jaeger-search.png) | ![grafana trace](screenshots/ui-12-grafana-trace-view.png) |

---

## Task 3: GitOps

### What GitOps is

GitOps is a way of running infrastructure and deployments where **a Git repository holds the desired state of the system as declarative files, and an automated agent running in the cluster keeps the real system matching that repository**. Every change to the system is a Git commit, and nobody runs `kubectl apply` by hand against production.

The four principles (from OpenGitOps, CNCF):

1. **Declarative**: the desired state is described, not scripted.
2. **Versioned and immutable**: that description lives in Git, so every version is kept and can't be silently altered.
3. **Pulled automatically**: software agents pull the desired state from Git (instead of a CI job pushing into the cluster).
4. **Continuously reconciled**: the agents keep comparing actual with desired state and correct any difference.

### Git as the source of truth

The Git repo is the only place where the desired state is defined. In this demo that repo is [`parth/gitops-demo`](03-gitops/gitops-repo) on Gitea. What that gives you:

- **Audit trail**: `git log` shows who changed what, when and why ([history](03-gitops/gitops-repo-history.txt)). Argo CD records which commit each sync deployed (`argocd app history`).
- **Review**: changes go through pull requests and code review like application code.
- **Rollback = `git revert`**: no special rollback tooling; the previous state is a commit.
- **Disaster recovery**: if the cluster is lost, point a new Argo CD at the same repo and everything is recreated.
- **Security**: CI doesn't need cluster credentials; only the in-cluster agent can change the cluster, and developers only need Git access.

### Declarative configuration

**Imperative** = commands that describe *how* (`kubectl scale --replicas=3`, `kubectl set image …`). The end state depends on what was run before, in what order.
**Declarative** = a file that describes *what* (`replicas: 3`, `image: podinfo:6.9.2`). The tool works out how to get there, and running it twice gives the same result.

The repo is plain Kubernetes YAML, organised with **Kustomize**:

```text
gitops-repo/
├── apps/                       # Argo CD Application objects (also declarative, also in Git)
│   ├── podinfo-dev.yaml        #   source: podinfo/overlays/dev  -> namespace gitops-dev
│   └── podinfo-prod.yaml       #   source: podinfo/overlays/prod -> namespace gitops-prod
└── podinfo/
    ├── base/                   # Deployment + Service shared by both environments
    └── overlays/
        ├── dev/                # 1 replica, dev message/colour (configMapGenerator)
        └── prod/               # 2 replicas, prod message/colour
```

`configMapGenerator` adds a hash of the data to the ConfigMap's name (`podinfo-config-m4hbbttbbb`). Changing the message changes the name, which changes the Deployment's pod template, which triggers a rolling update. Without the hash, editing a ConfigMap doesn't restart the pods that use it.

### Continuous reconciliation

Argo CD runs a control loop, the same pattern as the Kubernetes controllers themselves:

```text
        ┌──────────────────────────────────────────────────────────┐
        ▼                                                          │
  1. fetch Git (every 60s, or right away on a webhook)             │
  2. render manifests (Kustomize/Helm/plain YAML) = DESIRED state  │
  3. read the objects from the cluster          = LIVE state       │
  4. diff → Synced / OutOfSync                                     │
  5. if automated: apply the difference                            │
       prune: true    → delete objects that were removed from Git  │
       selfHeal: true → undo changes made directly in the cluster  │
        └──────────────────────────────────────────────────────────┘
```

**Sync status** (does live match Git? `Synced` / `OutOfSync`) and **health status** (are the resources working? `Healthy` / `Progressing` / `Degraded`) are separate. In my drift test the app was briefly `OutOfSync` + `Progressing` at the same time.

### GitOps workflow

```text
developer ── edit YAML ── commit ── PR + review ── merge to main
                                                       │
                                     webhook (or poll) ▼
                         Argo CD fetches main, diffs, applies
                                                       │
                                                       ▼
                      cluster matches Git again; drift is reverted automatically
```

**Push model vs pull model.** In a classic CI/CD pipeline (Session 16/17), the CI job runs `kubectl apply`/`helm upgrade` and so needs cluster credentials, and nothing notices if someone changes the cluster afterwards. In GitOps (pull), CI only builds and tests the image and then commits the new tag to the config repo; the agent inside the cluster pulls. A common setup keeps two repos: the **app repo** (code, CI builds the image) and the **config repo** (manifests, watched by Argo CD).

### Kubernetes + GitOps

Kubernetes suits GitOps because its API is already declarative (you submit desired state, controllers reconcile it), so a GitOps tool is just one more controller one level up. The two main tools are both CNCF graduated projects:

| | Argo CD (used here) | Flux CD |
|---|---|---|
| Model | `Application` CRD → repo + path + destination | `GitRepository` + `Kustomization`/`HelmRelease` CRDs |
| UI | rich web UI (resource tree, diff, history) | CLI-first; UIs are add-ons |
| Multi-cluster | one Argo CD can manage many clusters | usually one Flux per cluster |
| Templating | Kustomize, Helm, Jsonnet, plain YAML | Kustomize, Helm |
| Patterns | app of apps, `ApplicationSet` (generate apps per cluster/env/dir) | Kustomization dependencies |

The **app-of-apps** pattern used here: the only object I applied by hand is [root-app.yaml](03-gitops/bootstrap/root-app.yaml), which points at `apps/` in Git. The `podinfo-dev` and `podinfo-prod` Applications are themselves files in Git, so adding an environment is also just a commit.

### GitOps demo

#### Setup ([10](logs/10-gitops-setup.log))

Argo CD installed with Helm ([argocd-values.yaml](03-gitops/platform/argocd-values.yaml): reconcile every 60s, read-only anonymous UI, metrics + ServiceMonitors so Prometheus also monitors Argo CD). Gitea ([gitea.yaml](03-gitops/platform/gitea.yaml)) runs in the cluster with a PVC and SQLite. I created the repo through Gitea's API, added a **push webhook** to `http://argocd-server.argocd.svc/api/webhook`, and pushed the first commit.

I used an in-cluster Git server instead of GitHub so the demo is self-contained and the cluster doesn't need internet access to my account. The workflow is identical with GitHub: change `repoURL`, and add the webhook in the repo settings.

#### Step 1: bootstrap ([11](logs/11-gitops-bootstrap.log))

```text
$ kubectl get ns gitops-dev gitops-prod
Error from server (NotFound): namespaces "gitops-dev" not found ...
$ kubectl apply -f 03-gitops/bootstrap/root-app.yaml        # the only manual apply
application.argoproj.io/root created

# ~50s later
$ argocd app list
NAME                 NAMESPACE    STATUS  HEALTH   SYNCPOLICY  PATH
argocd/podinfo-dev   gitops-dev   Synced  Healthy  Auto-Prune  podinfo/overlays/dev
argocd/podinfo-prod  gitops-prod  Synced  Healthy  Auto-Prune  podinfo/overlays/prod
argocd/root          argocd       Synced  Healthy  Auto-Prune  apps
```

Argo CD created both namespaces (`CreateNamespace=true`), the Deployments, Services, ConfigMaps and the prod PodDisruptionBudget.

| Applications | app of apps | podinfo-prod resource tree |
|---|---|---|
| ![apps](screenshots/ui-13-argocd-apps.png) | ![root](screenshots/ui-15-argocd-app-of-apps.png) | ![tree](screenshots/ui-14-argocd-prod-tree.png) |

#### Step 2: change prod through Git ([12](logs/12-gitops-change-via-git.log))

```diff
+images:
+  - { name: ghcr.io/stefanprodan/podinfo, newTag: 6.9.2 }
 replicas:
-  - { name: podinfo, count: 2 }
+  - { name: podinfo, count: 3 }
-      - PODINFO_UI_MESSAGE=hello from PROD (deployed by Argo CD)
+      - PODINFO_UI_MESSAGE=hello from PROD v2 (changed in Git)
```

| Time (UTC) | Event |
|---|---|
| 23:59:40 | `git push` (f0e6175) |
| 23:59:43 | argocd-server log: `refreshing app from webhook` |
| 23:59:44 | sync finished, rolling update started (app `Progressing`) |
| ~00:00:20 | 3/3 pods on `podinfo:6.9.2`, app `Synced` + `Healthy`, response says `"version": "6.9.2", "message": "hello from PROD v2 (changed in Git)"` |

About **4 seconds from push to deploy**, without running `kubectl`. Argo CD also **pruned** the old ConfigMap (`podinfo-config-m4hbbttbbb … Pruned`) because the new hash replaced it. The commit in Gitea: [ui-17](screenshots/ui-17-gitea-commit-diff.png).

#### Step 3: drift and self-heal ([13](logs/13-gitops-drift-selfheal.log))

Someone "fixes" prod by hand:

```text
05:30:28 $ kubectl scale deploy podinfo -n gitops-prod --replicas=1
         $ kubectl set image deploy/podinfo -n gitops-prod podinfo=ghcr.io/stefanprodan/podinfo:6.9.0
         $ kubectl delete svc podinfo -n gitops-prod
05:30:30 podinfo-prod   OutOfSync   Progressing
05:30:50 deployment.apps/podinfo   3/3   ghcr.io/stefanprodan/podinfo:6.9.2    <- back to what Git says
         service/podinfo   ClusterIP   10.96.12.45   AGE 19s                  <- recreated
         podinfo-prod   Synced   Healthy
```

All three manual changes were reverted within seconds (controller log: `Initiated automated sync to 'f0e6175…'`). This is what `selfHeal: true` does: the cluster can't drift away from Git, so the correct way to change prod is to change Git.

#### Step 4: prune ([14](logs/14-gitops-prune-rollback.log))

`git rm podinfo/overlays/prod/pdb.yaml` + remove it from `kustomization.yaml`, commit, push → `kubectl get pdb -n gitops-prod` → `No resources found`. Controller log: `kind=PodDisruptionBudget name=podinfo … status: 'Pruned'`. Without `prune: true`, Argo CD would only flag it as OutOfSync and leave it running.

#### Step 5: rollback with `git revert` ([14](logs/14-gitops-prune-rollback.log))

```text
$ git revert --no-edit f0e6175
d848e39 Revert "prod: 3 replicas, podinfo 6.9.1 -> 6.9.2, new message"
$ git push
$ kubectl get deploy podinfo -n gitops-prod -o wide
podinfo   2/2   ...   ghcr.io/stefanprodan/podinfo:6.9.1
"version": "6.9.1",  "message": "hello from PROD (deployed by Argo CD)"

$ argocd app history podinfo-prod
ID  DATE                           REVISION
0   2026-10-06 23:58:08 +0000 UTC  main (9d3e5a4)   initial
1   2026-10-06 23:59:44 +0000 UTC  main (f0e6175)   v2
2   2026-10-07 00:01:05 +0000 UTC  main (fadda8c)   drop PDB
3   2026-10-07 00:01:16 +0000 UTC  main (d848e39)   revert v2
```

The revert only undid the v2 commit, so the PDB removal from step 4 stayed. The rollback is itself a commit, so it shows up in the history like any other change. (Argo CD's UI also has a "Rollback" button, but with auto-sync on it would be overwritten by Git on the next sync; reverting in Git is the GitOps way.)

| Git history (Gitea) | Argo CD sync history |
|---|---|
| ![commits](screenshots/ui-16-gitea-commits.png) | ![history](screenshots/ui-18-argocd-history.png) |

I made one more commit afterwards (`9cbe7fc`, README only) so the repo's README no longer mentions the removed PDB.

---

## Commands I ran

```bash
# --- monitoring + observability stack ---
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add argo https://argoproj.github.io/argo-helm
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack --version 92.0.0 \
  -n monitoring --create-namespace -f 01-monitoring/kube-prometheus-stack-values.yaml
kubectl create ns observability
kubectl apply -f 02-observability/jaeger.yaml
helm upgrade --install loki  grafana/loki  --version 7.3.0  -n observability -f 02-observability/loki-values.yaml
helm upgrade --install alloy grafana/alloy --version 1.13.0 -n observability -f 02-observability/alloy-values.yaml

# --- demo app, scraping, alerts, dashboard ---
kubectl apply -f 01-monitoring/demo-app.yaml -f 01-monitoring/servicemonitor.yaml -f 01-monitoring/alert-rules.yaml
python3 01-monitoring/make_dashboard.py && kubectl apply -f 01-monitoring/grafana-dashboard.yaml

# --- UIs ---
kubectl -n monitoring    port-forward svc/monitoring-kube-prometheus-prometheus   9090:9090
kubectl -n monitoring    port-forward svc/monitoring-kube-prometheus-alertmanager 9093:9093
kubectl -n monitoring    port-forward svc/monitoring-grafana 3000:80        # admin / admin123 (lab-only password)
kubectl -n observability port-forward svc/jaeger 16686:16686
kubectl -n observability port-forward svc/loki 3100:3100
kubectl -n argocd        port-forward svc/argocd-server 8080:80
kubectl -n gitea         port-forward svc/gitea 3001:3000

# --- monitoring demos ---
kubectl patch deploy backend -n demo --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/command/-","value":"--stress-cpu=1"},{"op":"add","path":"/spec/template/spec/containers/0/command/-","value":"--stress-memory=95"}]'
kubectl apply -f 01-monitoring/demo-app.yaml           # remove the stress
kubectl scale deploy backend -n demo --replicas=0      # outage
kubectl scale deploy backend -n demo --replicas=2      # recover

# --- GitOps ---
kubectl apply -f 03-gitops/platform/gitea.yaml
helm upgrade --install argocd argo/argo-cd --version 10.9.6 -n argocd --create-namespace -f 03-gitops/platform/argocd-values.yaml
kubectl exec -n gitea deploy/gitea -- gitea admin user create --username parth --admin ...
# create repo + webhook through the Gitea API, then:
git push -u origin main
kubectl apply -f 03-gitops/bootstrap/root-app.yaml
# edit -> commit -> push; kubectl scale/set image/delete svc (drift); git rm pdb.yaml; git revert f0e6175
```

In the logs, `pq`, `lq`, `alert_rules`, `am_alerts`, `webhooks` and `trace` are small shell/Python helpers I wrote for this session. They call the Prometheus, Loki, Alertmanager and Jaeger HTTP APIs and print the JSON as readable lines. `argocd` is the Argo CD CLI run inside the argocd-server pod (`kubectl exec … argocd --server localhost:8080`), so I didn't have to install it on the Mac.

## Results

| # | Step | Result | Log | Screenshot |
|---|---|---|---|---|
| 1 | Install stack | 3 Helm releases (monitoring, loki, alloy), 7 monitoring + 4 observability pods Running | [01](logs/01-stack-install.log) | [png](screenshots/01-stack-install.png) |
| 2 | Demo app | 6 pods Running, `/healthz` + `/readyz` → 200, `/metrics` exposed | [02](logs/02-demo-app.log) | [png](screenshots/02-demo-app.png), [targets](screenshots/ui-02-prometheus-targets.png) |
| 3 | CPU / memory / request metrics | `kubectl top` + PromQL for pod CPU % of limit, memory, node utilisation, req/s, 5xx ratio | [03](logs/03-metrics-cpu-memory.log) | [png](screenshots/03-metrics-cpu-memory.png) |
| 4 | Alert rules | 6 rules loaded, all `inactive`, 0 in Alertmanager | [04](logs/04-alert-rules.log) | [png](screenshots/04-alert-rules.png) |
| 5 | Stress test | `PodinfoHighCPU` + `PodinfoHighMemory`: pending → **firing**, webhook got them | [05](logs/05-alert-firing.log) | [png](screenshots/05-alert-firing.png), [Prometheus](screenshots/ui-04-prometheus-alerts-firing.png), [Alertmanager](screenshots/ui-05-alertmanager.png) |
| 6 | Stress removed | all `inactive`, 4 `resolved` webhooks | [06](logs/06-alert-resolved.log) | [png](screenshots/06-alert-resolved.png) |
| 7 | Outage | `PodinfoDown` (critical) fired and resolved; frontend still returned 200 | [07](logs/07-health-outage.log) | [png](screenshots/07-health-outage.png), [Prometheus](screenshots/ui-06-prometheus-podinfodown.png) |
| 8 | Logs | LogQL filter / parse / count queries; 86 error lines/min during outage | [08](logs/08-logs-loki.log) | [png](screenshots/08-logs-loki.png) |
| 9 | Traces | 9-span trace across 2 services; failed trace with ERROR spans | [09](logs/09-traces-jaeger.log) | [png](screenshots/09-traces-jaeger.png) |
| 10 | GitOps setup | Argo CD v3.5.3 + Gitea, first commit pushed | [10](logs/10-gitops-setup.log) | [png](screenshots/10-gitops-setup.png) |
| 11 | Bootstrap | 1 manual apply → 3 apps `Synced`/`Healthy` | [11](logs/11-gitops-bootstrap.log) | [png](screenshots/11-gitops-bootstrap.png) |
| 12 | Change via Git | push → webhook → synced in ~4 s; 6.9.2, 3 replicas | [12](logs/12-gitops-change-via-git.log) | [png](screenshots/12-gitops-change-via-git.png) |
| 13 | Drift | scale/set image/delete svc reverted in < 20 s | [13](logs/13-gitops-drift-selfheal.log) | [png](screenshots/13-gitops-drift-selfheal.png) |
| 14 | Prune + rollback | PDB pruned; `git revert` → back to 6.9.1 / 2 replicas | [14](logs/14-gitops-prune-rollback.log) | [png](screenshots/14-gitops-prune-rollback.png) |
| 15 | Kubernetes observability | API readyz, `top`, events, probes, kube-state-metrics queries, 16 built-in dashboards | [15](logs/15-k8s-observability.log) | [png](screenshots/15-k8s-observability.png) |

## Screenshots

**UI screenshots**

| | |
|---|---|
| ![](screenshots/ui-01-grafana-dashboard.png) Grafana: demo dashboard | ![](screenshots/ui-02-prometheus-targets.png) Prometheus: scrape targets |
| ![](screenshots/ui-03-grafana-stress.png) Grafana: during stress test | ![](screenshots/ui-04-prometheus-alerts-firing.png) Prometheus: CPU + memory alerts firing |
| ![](screenshots/ui-05-alertmanager.png) Alertmanager: grouped alerts → webhook-logger | ![](screenshots/ui-06-prometheus-podinfodown.png) Prometheus: PodinfoDown firing |
| ![](screenshots/ui-07-loki-error-logs.png) Grafana Explore: Loki error logs | ![](screenshots/ui-08-loki-logql-metrics.png) Grafana Explore: LogQL metric query |
| ![](screenshots/ui-09-jaeger-search.png) Jaeger: trace search | ![](screenshots/ui-10-jaeger-failed-trace.png) Jaeger: failed trace |
| ![](screenshots/ui-11-jaeger-trace.png) Jaeger: frontend → backend trace | ![](screenshots/ui-12-grafana-trace-view.png) Grafana: same trace |
| ![](screenshots/ui-13-argocd-apps.png) Argo CD: applications | ![](screenshots/ui-14-argocd-prod-tree.png) Argo CD: podinfo-prod tree |
| ![](screenshots/ui-15-argocd-app-of-apps.png) Argo CD: app of apps | ![](screenshots/ui-16-gitea-commits.png) Gitea: commit history |
| ![](screenshots/ui-17-gitea-commit-diff.png) Gitea: the prod change | ![](screenshots/ui-18-argocd-history.png) Argo CD: sync history |
| ![](screenshots/ui-19-grafana-k8s-namespace.png) Grafana: built-in Kubernetes namespace dashboard | |

**Terminal screenshots** (from the logs)

| | |
|---|---|
| ![](screenshots/01-stack-install.png) | ![](screenshots/02-demo-app.png) |
| ![](screenshots/03-metrics-cpu-memory.png) | ![](screenshots/04-alert-rules.png) |
| ![](screenshots/05-alert-firing.png) | ![](screenshots/06-alert-resolved.png) |
| ![](screenshots/07-health-outage.png) | ![](screenshots/08-logs-loki.png) |
| ![](screenshots/09-traces-jaeger.png) | ![](screenshots/10-gitops-setup.png) |
| ![](screenshots/11-gitops-bootstrap.png) | ![](screenshots/12-gitops-change-via-git.png) |
| ![](screenshots/13-gitops-drift-selfheal.png) | ![](screenshots/14-gitops-prune-rollback.png) |
| ![](screenshots/15-k8s-observability.png) | |

## What I learned

- **Health checks aren't the whole picture.** During the outage every probe and every metric-based alert except `PodinfoDown` said the frontend was fine, because it returned 200 with the error in the body. Logs and traces found it straight away. I'd want an alert on the `backend call failed` log rate (Loki can alert on LogQL) or on error spans.
- **`for:` and thresholds are a trade-off.** `for: 1m` stopped short spikes from paging, but a throttled CPU sitting right at the limit still flapped once at 0.79. `keep_firing_for` or a longer window would fix that.
- **`absent()`** is needed for "the thing disappeared" alerts, because a scaled-to-zero target has no series to compare against.
- **Correlation needs a shared ID.** Putting `trace_id` in every log line is what makes it possible to go from a log to a trace.
- **GitOps makes the cluster follow Git.** Self-heal reverted my manual `kubectl` changes in seconds, so the only change that sticks is a commit. That makes drift impossible, but it also means that in an emergency you have to commit the fix (or pause auto-sync deliberately).
- **Webhooks vs polling:** with only polling (60s here, 180s by default) a push takes up to a few minutes to deploy; with the Gitea webhook it took about 4 seconds.

## Cleanup

```bash
kubectl delete -f 03-gitops/bootstrap/root-app.yaml     # finalizers delete podinfo-dev/prod and their resources
helm uninstall argocd -n argocd; kubectl delete -f 03-gitops/platform/gitea.yaml
kubectl delete -f 01-monitoring/demo-app.yaml
helm uninstall alloy loki -n observability; kubectl delete -f 02-observability/jaeger.yaml
helm uninstall monitoring -n monitoring
kubectl delete crd $(kubectl get crd -o name | grep -E 'monitoring.coreos.com|argoproj.io' | cut -d/ -f2)
```

I left everything running in the cluster after taking the screenshots.
