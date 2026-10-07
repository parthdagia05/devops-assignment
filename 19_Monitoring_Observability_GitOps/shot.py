# Turns the terminal logs in logs/ into terminal-style PNG screenshots (headless Chrome).
# The ui-*.png screenshots were taken from the real web UIs (Grafana, Prometheus, Alertmanager,
# Jaeger, Argo CD, Gitea) through kubectl port-forward.
import html
import os
import re
import subprocess

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def fmt(x):
    cls = "c" if x.startswith("$ ") else \
          "e" if re.search(r"\bfiring\b|ERROR|\"level\":\"error\"|call failed|OutOfSync|connection refused|Terminating|deleted|Pruned|No resources found|Warning", x) else \
          "w" if re.search(r"\bpending\b|Progressing|ContainerCreating|^\.\.\.|^[-+](?![-+])", x) and not x.startswith("+++") else \
          "p" if re.search(r"Synced|Healthy|resolved|\binactive\b|Running|\bOK\b|successfully|HTTP 200|readyz check passed|\bup\b|=> 1$|created|Logged In: true", x) else ""
    return f'<span class="{cls}">{html.escape(x)}</span>\n' if cls else html.escape(x) + "\n"


def shot(out, title, lines):
    body = "".join(fmt(x) for x in lines)
    w = min(1400, max(900, int(max(len(x) for x in lines) * 8.45) + 50))
    cols = (w - 36) // 8.45  # wrapped lines take more than one row
    h = sum(max(1, -(-len(x) // int(cols))) for x in lines) * 19 + 80
    page = f"""<html><body style="margin:0;background:#1e1e1e"><div style="font:14px Menlo,monospace;color:#ddd">
<div style="background:#2d2d2d;padding:8px 12px 8px 76px;color:#aaa;text-align:center;position:relative">
<span style="position:absolute;left:12px;top:6px;color:#ff5f56">●</span><span style="position:absolute;left:30px;top:6px;color:#ffbd2e">●</span><span style="position:absolute;left:48px;top:6px;color:#27c93f">●</span>{html.escape(title)}</div>
<pre style="margin:0;padding:12px 18px;line-height:19px;white-space:pre-wrap;word-break:break-all">{body}</pre></div>
<style>.c{{color:#79c0ff;font-weight:bold}}.p{{color:#7ee787}}.e{{color:#ff7b72}}.w{{color:#ffa657}}</style></body></html>"""
    p = os.path.join(os.environ.get("SP", "/tmp"), "_shot.html")
    open(p, "w").write(page)
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}",
                    f"--screenshot={os.path.abspath(out)}", "file://" + p], capture_output=True)
    print(out, w, h)


def lines(log):
    return open(log).read().rstrip("\n").split("\n")


if __name__ == "__main__":
    jobs = [  # (log/png name, title)
        ("01-stack-install", "helm list + monitoring / observability pods"),
        ("02-demo-app", "demo app: pods, ServiceMonitor, /healthz, /readyz, /metrics"),
        ("03-metrics-cpu-memory", "kubectl top + PromQL: CPU, memory, request rate, errors"),
        ("04-alert-rules", "alert rules loaded, nothing firing"),
        ("05-alert-firing", "stress backend CPU + memory -> alerts pending -> firing -> webhook"),
        ("06-alert-resolved", "remove the stress -> alerts resolved"),
        ("07-health-outage", "application health: scale backend to 0 -> PodinfoDown"),
        ("08-logs-loki", "logs: LogQL queries against Loki"),
        ("09-traces-jaeger", "traces: log -> trace_id -> Jaeger span tree"),
        ("10-gitops-setup", "GitOps: Argo CD + Gitea, first commit pushed"),
        ("11-gitops-bootstrap", "GitOps: apply root app -> Argo CD deploys everything from Git"),
        ("12-gitops-change-via-git", "GitOps: change prod in Git -> git push -> auto sync"),
        ("13-gitops-drift-selfheal", "GitOps: manual kubectl changes -> self-heal"),
        ("14-gitops-prune-rollback", "GitOps: prune a removed file, rollback with git revert"),
        ("15-k8s-observability", "Kubernetes observability: events, probes, top, kube-state-metrics"),
    ]
    for name, title in jobs:
        shot(f"screenshots/{name}.png", "parth@mac: 19_Monitoring_Observability_GitOps: " + title, lines(f"logs/{name}.log"))
