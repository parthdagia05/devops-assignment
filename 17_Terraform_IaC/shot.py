# Turns the terminal logs in logs/ into terminal-style PNG screenshots (headless Chrome).
import html
import os
import re
import subprocess

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def fmt(x):
    cls = "c" if x.startswith("$ ") else \
          "e" if re.search(r"Error|exit code [1-9]|will be destroyed|^\s+- |Destroying|Destruction complete|404$", x) else \
          "p" if re.search(r"Success|successfully|complete!|Creation complete|will be created|^\s+\+ |no changes|Enabled|AES256|Hello from|exit code 0", x) else \
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


if __name__ == "__main__":
    L, S = "logs/", "screenshots/"
    jobs = [  # (png, title, [(log, head, tail), ...])
        ("01-init", "terraform init", [("01-init", None, None)]),
        ("02-fmt-validate", "terraform fmt + validate", [("02-fmt", None, None), ("03-validate", None, None)]),
        ("03-plan", "terraform plan -out=s3.tfplan", [("04-plan", 40, 30)]),
        ("04-apply", "terraform apply s3.tfplan", [("05-apply", None, None)]),
        ("05-show", "terraform show", [("06-show", 45, 8)]),
        ("06-output", "terraform output", [("07-output", None, None)]),
        ("07-verify", "verify bucket: state, object, versioning, encryption, tags, public access block", [("08-verify", None, None)]),
        ("08-destroy", "terraform destroy", [("09-destroy", 10, 23, 2)]),
        ("09-after-destroy", "after destroy: state empty, bucket gone", [("10-after-destroy", None, None)]),
    ]
    for png, title, parts in jobs:
        lines = []
        for log, *cut in parts:
            lines += pick(L + log + ".log", *cut)
        shot(S + png + ".png", "parth@mac: terraform-s3-demo: " + title, lines)
