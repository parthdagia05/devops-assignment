"""Security gate: reads every scanner report and fails if any tool is over its policy limit.

Usage: python security/gate.py [reports_dir] [policy.json]
A missing or unreadable report also fails the gate - no evidence means no release.
"""
import json
import os
import sys
from collections import Counter

REPORTS = sys.argv[1] if len(sys.argv) > 1 else "reports"
POLICY = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "policy.json")


def bandit(data):
    return [(r["issue_severity"], f'{r["test_id"]} {r["filename"]}:{r["line_number"]} {r["issue_text"]}')
            for r in data["results"]]


def semgrep(data):
    return [(r["extra"]["severity"], f'{r["check_id"].split(".")[-1]} {r["path"]}:{r["start"]["line"]}')
            for r in data["results"]]


def trivy_iac(data):
    return [(m["Severity"], f'{m["ID"]} {res["Target"]}: {m["Title"]}')
            for res in data.get("Results", []) for m in res.get("Misconfigurations") or []]


def pip_audit(data):
    # pip-audit can list the same package twice; count each (package, advisory) once
    found = {f'{d["name"]}=={d["version"]} {v["id"]} (fix: {", ".join(v["fix_versions"]) or "none"})'
             for d in data["dependencies"] for v in d.get("vulns", [])}
    return [("ANY", text) for text in sorted(found)]


def gitleaks(data):
    return [("ANY", f'{f["RuleID"]} {f["File"]}:{f["StartLine"]}') for f in data or []]


def trivy_image(data):
    return [(v["Severity"], f'{v["VulnerabilityID"]} {v["PkgName"]} {v["InstalledVersion"]}'
             f' -> {v.get("FixedVersion", "?")}')
            for res in data.get("Results", []) for v in res.get("Vulnerabilities") or []]


# stage, policy key, report file, parser
CHECKS = [
    ("SAST", "bandit", "bandit.json", bandit),
    ("SAST", "semgrep", "semgrep.json", semgrep),
    ("SAST", "trivy-iac", "trivy-iac.json", trivy_iac),
    ("SCA", "pip-audit", "pip-audit.json", pip_audit),
    ("Secret scan", "gitleaks", "gitleaks.json", gitleaks),
    ("Image scan", "trivy-image", "trivy-image.json", trivy_image),
]


def main():
    policy = json.load(open(POLICY))
    rows, details, failed = [], [], False
    for stage, tool, report, parse in CHECKS:
        limits = policy[tool]
        try:
            findings = parse(json.load(open(os.path.join(REPORTS, report))))
        except (OSError, ValueError, KeyError) as e:
            rows.append((stage, tool, "report missing", "-", "FAIL"))
            details.append(f"{tool}: cannot read {report}: {e}")
            failed = True
            continue
        counts = Counter(sev.upper() for sev, _ in findings)
        if "ANY" in limits:
            counts = Counter(ANY=len(findings))
        over = [s for s, n in counts.items() if n > limits.get(s, 0)]
        found = ", ".join(f"{s}={counts.get(s, 0)}" for s in limits)
        allowed = ", ".join(f"{s}<={n}" for s, n in limits.items())
        status = "FAIL" if over else "PASS"
        failed |= bool(over)
        rows.append((stage, tool, found, allowed, status))
        details += [f"{tool}: [{sev}] {text}" for sev, text in findings[:15]]

    width = [max(len(r[i]) for r in rows + [("Stage", "Tool", "Found", "Allowed", "Result")]) for i in range(5)]

    def line(r):
        return "  ".join(c.ljust(w) for c, w in zip(r, width))

    print(line(("Stage", "Tool", "Found", "Allowed", "Result")))
    print("  ".join("-" * w for w in width))
    for r in rows:
        print(line(r))
    if details:
        print("\nFindings:")
        print("\n".join("  " + d for d in details))
    verdict = "FAILED - image will NOT be pushed or deployed" if failed else "PASSED - image may be pushed and deployed"
    print(f"\nSecurity gate {verdict}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"## Security gate: {'❌ FAILED' if failed else '✅ PASSED'}\n\n")
            f.write("| Stage | Tool | Found | Allowed | Result |\n|---|---|---|---|---|\n")
            for r in rows:
                f.write("| " + " | ".join(r[:4]) + f" | {'✅' if r[4] == 'PASS' else '❌'} {r[4]} |\n")
            if details:
                f.write("\n<details><summary>Findings</summary>\n\n```\n" + "\n".join(details) + "\n```\n</details>\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
