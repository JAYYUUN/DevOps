#!/usr/bin/env bash
set -euo pipefail
kubectl get pods -n observability
kubectl get pvc -n observability
kubectl get svc -n observability | grep -E 'grafana|loki'
helm list -n observability
