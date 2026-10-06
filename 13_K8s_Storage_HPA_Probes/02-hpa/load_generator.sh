#!/usr/bin/env bash
# Starts the in-cluster load generator, watches the HPA, then stops the load.
# Usage: ./load_generator.sh [seconds]   (default 180)
set -euo pipefail
cd "$(dirname "$0")"
DURATION="${1:-180}"

kubectl apply -f load-generator.yaml
trap 'kubectl delete -f load-generator.yaml --ignore-not-found' EXIT

end=$((SECONDS + DURATION))
while [ $SECONDS -lt $end ]; do
  echo "----- $(date +%T)"
  kubectl get hpa hpa-demo --no-headers
  kubectl top pods -l app=hpa-demo --no-headers 2>/dev/null || true
  sleep 15
done
