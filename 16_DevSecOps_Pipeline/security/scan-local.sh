#!/bin/bash
# Runs the same scanners as the pipeline on this machine and then the security gate.
# Needs: Docker, and a venv with bandit, semgrep and pip-audit (see README).
set -u
cd "$(dirname "$0")/.."
TRIVY="aquasec/trivy:0.75.0"
GITLEAKS="zricethezav/gitleaks:v8.30.1"
IMAGE="${IMAGE:-notes-api:local}"
mkdir -p reports

echo "▶ SAST: bandit"
bandit -c security/bandit.yaml -r app -f json -o reports/bandit.json -q --exit-zero
bandit -c security/bandit.yaml -r app -q --exit-zero

echo "▶ SAST: semgrep"
semgrep scan --config security/semgrep.yml --config p/python --config p/flask --config p/secrets \
  --metrics=off --quiet --json -o reports/semgrep.json app
semgrep scan --config security/semgrep.yml --config p/python --config p/flask --config p/secrets \
  --metrics=off --quiet app

echo "▶ SAST: trivy config (Dockerfile + Kubernetes manifests)"
docker run --rm -v "$PWD":/src -w /src -v "$HOME/.cache/trivy":/root/.cache/ $TRIVY \
  config --quiet --format json -o reports/trivy-iac.json .
docker run --rm -v "$PWD":/src -w /src -v "$HOME/.cache/trivy":/root/.cache/ $TRIVY config --quiet .

echo "▶ SCA: pip-audit"
pip-audit -r requirements.txt -f json -o reports/pip-audit.json --progress-spinner off || true
pip-audit -r requirements.txt --progress-spinner off || true

echo "▶ Secret scan: gitleaks (full git history of this folder)"
# mount the git root (the history lives there) and limit the scan to this folder
ROOT="$(git rev-parse --show-toplevel)"
DIR="$(git rev-parse --show-prefix)"; DIR="${DIR%/}"; DIR="${DIR:-.}"
docker run --rm -v "$ROOT":/repo -w /repo $GITLEAKS git --config "$DIR/.gitleaks.toml" --redact \
  --log-opts="-- $DIR" --report-format json --report-path "$DIR/reports/gitleaks.json" --exit-code 0 -v .

echo "▶ Image scan: trivy image $IMAGE"
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD":/src -w /src \
  -v "$HOME/.cache/trivy":/root/.cache/ $TRIVY image --quiet --format json -o reports/trivy-image.json "$IMAGE"
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD":/src -w /src \
  -v "$HOME/.cache/trivy":/root/.cache/ $TRIVY image --quiet "$IMAGE"

echo "▶ Security gate"
python3 security/gate.py reports security/policy.json
