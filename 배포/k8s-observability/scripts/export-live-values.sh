#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
helm get values monitoring -n observability -o yaml > monitoring/monitoring-live-values.yaml
helm get values loki -n observability -o yaml > loki/loki-live-values.yaml
printf 'Saved live values as git-ignored reference files. Inspect and redact secrets before sharing.\n'
