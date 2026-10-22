#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${NAMESPACE:-observability}"
DEST="$ROOT/exports/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DEST"; chmod 700 "$DEST"
for r in monitoring loki fluentd; do helm get values "$r" -n "$NS" -o yaml > "$DEST/$r.values.yaml"; done
helm list -n "$NS" -o json > "$DEST/releases.json"
chmod 600 "$DEST"/*
echo "저장 위치: $DEST (민감정보 포함 가능, Git 업로드 금지)"
