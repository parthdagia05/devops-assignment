# Turns the terminal logs in logs/ into terminal-style PNG screenshots (headless Chrome).
import html
import os
import re
import subprocess

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def fmt(x):
    cls = "c" if x.startswith("$ ") else \
          "e" if re.search(r"Error|exit code [1-9]|will be destroyed|^\s+- |Destroying|Destruction complete|does not exist|NoSuchBucket|NotFound|terminated", x) else \
          "p" if re.search(r"Success|successfully|complete!|Creation complete|will be created|^\s+\+ |no changes|Enabled|AES256|Hello from|exit code 0|No changes|available|running|Enabled\"|true$", x) else \
          "w" if re.search(r"updated in-place|^\s+~ |^\.\.\.", x) else \
          "w" if x.startswith("...") else ""
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


def pick(log, head=None, tail=None, skip=0):
    """Whole log, or its first `head` and last `tail` lines with a '...' marker between."""
    lines = open(log).read().rstrip("\n").split("\n")[skip:]
    if head is None and tail is None:
        return lines
    keep = lines[:head or 0] + (["... (cut) ..."] if (head or 0) + (tail or 0) < len(lines) else [])
    return keep + (lines[-tail:] if tail else [])


def rng(log, a, b=None):
    """Lines a..b (1-based, inclusive) of a log."""
    lines = open(log).read().rstrip("\n").split("\n")
    return lines[a - 1:b]


if __name__ == "__main__":
    L, S = "logs/", "screenshots/"
    cut = ["... (cut) ..."]
    jobs = [  # (png, title, lines)
        ("01-init", "terraform init", rng(L + "01-init.log", 1)),
        ("02-fmt-validate", "terraform fmt -check + validate", rng(L + "02-fmt-validate.log", 1)),
        ("03-plan", "terraform plan -out=tfplan",
         rng(L + "03-plan.log", 1, 12) + cut + rng(L + "03-plan.log", 409, 439) + cut + rng(L + "03-plan.log", 506)),
        ("04-apply", "terraform apply tfplan", rng(L + "04-apply.log", 1)),
        ("05-output", "terraform output", rng(L + "05-output.log", 1)),
        ("06-state", "terraform state list + state show aws_instance.web", pick(L + "06-state.log", 50, 0)),
        ("07-verify", "verify VPC, subnet, routes, SG rules, EC2, S3 through the AWS API", rng(L + "07-verify.log", 1)),
        ("08-second-plan", "second plan: idempotency check", rng(L + "08-second-plan.log", 1)),
        ("09-change-plan", "plan with -var instance_type=t3.small", rng(L + "09-change-plan.log", 1)),
        ("10-graph", "terraform graph: dependency edges", rng(L + "10-graph.log", 1)),
        ("11-destroy", "terraform destroy",
         rng(L + "11-destroy.log", 1, 2) + cut + rng(L + "11-destroy.log", 596)),
        ("12-after-destroy", "after destroy: state empty, resources gone", rng(L + "12-after-destroy.log", 1)),
    ]
    for png, title, lines in jobs:
        shot(S + png + ".png", "parth@mac: 18_Cloud_Terraform_Project/terraform: " + title, lines)
