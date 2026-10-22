#!/usr/bin/env bash
set -euo pipefail
NS="${NAMESPACE:-observability}"
helm list -n "$NS"
kubectl get pods -n "$NS" -o wide
kubectl rollout status daemonset/fluentd -n "$NS" --timeout=180s
kubectl get svc -n "$NS" | grep -E 'grafana|loki-gateway' || true
printf '\nGrafana Explore에서 {namespace="observability"} 쿼리로 실제 로그 수집을 검증하세요.\n'
