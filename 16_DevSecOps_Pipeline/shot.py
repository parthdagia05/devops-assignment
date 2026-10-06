# Turns local terminal logs and `gh run view --job <id> --log` output into terminal-style screenshots.
import html
import os
import re
import subprocess

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ANSI = re.compile(r"\x1b\[[0-9;]*m|\^\[\[[0-9;]*m")
TS = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?")
LOCAL_NOISE = re.compile(r"^\[main\]\s+INFO|^\s*[│┌└]\s*$|semgrep login|false-negatives|send us feedback|^#\d+ (DONE|\[auth\]|\[internal\])"
                         r"|^(Run metrics|\t\tUndefined|\t\tLow|\t\tMedium|\t\tHigh|\tTotal issues|Files skipped)")
NOISE = re.compile(r"##\[(group|endgroup)\]|^(shell|env|with):|^  \S+: |^\s*$|pythonLocation|_ROOT_DIR|LD_LIBRARY"
                   r"|^[0-9a-f]{12}: (Pulling|Waiting|Verifying|Download|Pull complete)")


def clean(raw, steps, keep=None):
    """Keep only the given steps; drop timestamps, colour codes and the echoed script lines."""
    out, last, step = [], None, None
    for line in open(raw, encoding="utf-8", errors="replace"):
        parts = line.rstrip("\n").split("\t", 2)
        if len(parts) == 3:
            step, text = parts[1], parts[2]
        else:  # continuation line of a multi-line log entry
            text = parts[-1]
        if step not in steps:
            continue
        echoed = "\x1b[36;1m" in text or "^[[36;1m" in text
        text = TS.sub("", ANSI.sub("", text))
        if echoed or NOISE.search(text) or (keep and not keep(step, text)):
            continue
        if step != last:
            out.append(f"▶ {step}")
            last = step
        out.append("  " + text)
    return out


def shot(out, title, lines):
    def fmt(x):
        cls = "s" if x.startswith("▶") else "e" if re.search(r"FAILED|Error|exit code [1-9]|\bfailed\b", x) else \
              "p" if re.search(r"PASSED|passed|PASS\s*$|SUCCESS|healthy|successfully|\"ok\"|No issues|0 findings|No known vuln|no leaks", x) \
              else "w" if re.search(r"FAIL|Forbidden|Read-only file system|leaks found|CRITICAL|HIGH|Blocking|Issue: ", x) else ""
        return f'<span class="{cls}">{html.escape(x)}</span>\n' if cls else html.escape(x) + "\n"
    body = "".join(fmt(x) for x in lines)
    w = min(1400, max(760, int(max(len(x) for x in lines) * 8.45) + 50))
    h = len(lines) * 19 + 80
    page = f"""<html><body style="margin:0;background:#1e1e1e"><div style="font:14px Menlo,monospace;color:#ddd">
<div style="background:#2d2d2d;padding:8px 12px;color:#aaa;text-align:center;position:relative">
<span style="position:absolute;left:12px;top:6px;color:#ff5f56">●</span><span style="position:absolute;left:30px;top:6px;color:#ffbd2e">●</span><span style="position:absolute;left:48px;top:6px;color:#27c93f">●</span>{html.escape(title)}</div>
<pre style="margin:0;padding:12px 18px;line-height:19px;white-space:pre">{body}</pre></div>
<style>.s{{color:#79c0ff;font-weight:bold}}.p{{color:#7ee787}}.e{{color:#ff7b72}}.w{{color:#ffa657}}</style></body></html>"""
    p = os.path.join(os.environ.get("SP", "/tmp"), "_shot.html")
    open(p, "w").write(page)
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}",
                    f"--screenshot={os.path.abspath(out)}", "file://" + p], capture_output=True)
    print(out, w, h)


def terminal(out, title, logs, maxlines=None):
    lines = []
    for f in logs:
        text = ANSI.sub("", open(f).read())
        lines += [x for x in text.rstrip("\n").split("\n") if x.strip() and not LOCAL_NOISE.search(x)]
    shot(out, title, lines[:maxlines] if maxlines else lines)


if __name__ == "__main__":
    L, S = "logs/", "screenshots/"
    # Local runs on my Mac: (screenshot, title, log files, max lines)
    local = [
        ("20-local-build-test", "parth@mac: 1-2. build (flake8, compile) + unit tests", ["02-build-test"], None),
        ("21-local-sast", "parth@mac: 3. SAST - bandit, semgrep, trivy config", ["03-sast"], None),
        ("22-local-sca", "parth@mac: 4. SCA - pip-audit + SBOM", ["04-sca"], None),
        ("23-local-secret-scan", "parth@mac: 5. secret scan - gitleaks (git history)", ["05-secret-scan"], None),
        ("24-local-docker-build", "parth@mac: 6. docker build + smoke test", ["06-docker-build"], None),
        ("25-local-image-scan", "parth@mac: 7. trivy image scan", ["07-image-scan"], None),
        ("26-local-security-gate", "parth@mac: 8. security gate - PASSED", ["08-security-gate"], None),
        ("27-local-k8s-deploy", "parth@mac: 10. deploy to kind cluster", ["09-k8s-deploy"], None),
        ("28-local-k8s-verify", "parth@mac: verify app + security controls in Kubernetes", ["10-k8s-verify"], None),
        ("29-gate-before-pip-fix", "parth@mac: first image scan - pip CVEs in the image", ["01-gate-before-pip-fix"], None),
        ("30-fail-sca", "parth@mac: demo A - vulnerable dependencies (pip-audit)", ["11-fail-sca"], None),
        ("31-fail-sca-gate", "parth@mac: demo A - security gate FAILED", ["12-fail-sca-gate"], 40),
        ("32-fail-sast-code", "parth@mac: demo B - insecure code", ["13-fail-sast-code"], None),
        ("33-fail-sast-scan", "parth@mac: demo B - bandit + semgrep findings", ["14-fail-sast-scan"], 75),
        ("34-fail-sast-gate", "parth@mac: demo B - security gate FAILED", ["15-fail-sast-gate"], None),
        ("35-fail-secret-scan", "parth@mac: demo C - leaked token found in git history", ["16-fail-secret-scan"], None),
        ("36-fail-secret-gate", "parth@mac: demo C - security gate FAILED", ["17-fail-secret-gate"], None),
    ]
    for png, title, logs, maxlines in local:
        terminal(S + png + ".png", title, [L + x + ".log" for x in logs], maxlines)
