#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE="${1:-}"
NS="${NAMESPACE:-observability}"
case "$MODULE" in
  prometheus) RELEASE=monitoring; CHART=prometheus-community/kube-prometheus-stack; REPO=prometheus-community; REPO_URL=https://prometheus-community.github.io/helm-charts; VERSION_VAR=PROMETHEUS_CHART_VERSION ;;
  loki) RELEASE=loki; CHART=grafana/loki; REPO=grafana; REPO_URL=https://grafana.github.io/helm-charts; VERSION_VAR=LOKI_CHART_VERSION ;;
  fluentd) RELEASE=fluentd; CHART=fluent/fluentd; REPO=fluent; REPO_URL=https://fluent.github.io/helm-charts; VERSION_VAR=FLUENTD_CHART_VERSION ;;
  *) echo "사용법: bash scripts/install-module.sh {prometheus|loki|fluentd}" >&2; exit 2 ;;
esac
for c in helm kubectl; do command -v "$c" >/dev/null || { echo "$c 설치 필요" >&2; exit 1; }; done
if [[ "$NS" != observability ]]; then echo '현재 Loki 서비스 DNS는 observability로 고정되어 있습니다. 변경하려면 설정의 URL도 수정하세요.' >&2; exit 1; fi
[[ ! -f "$ROOT/config/versions.env" ]] || source "$ROOT/config/versions.env"
VERSION="${!VERSION_VAR:-}"
helm repo add "$REPO" "$REPO_URL" --force-update
helm repo update "$REPO"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
args=(upgrade --install "$RELEASE" "$CHART" -n "$NS" --wait --timeout 10m)
[[ -z "$VERSION" ]] || args+=(--version "$VERSION")
while IFS= read -r -d '' f; do args+=(-f "$f"); done < <(find "$ROOT/$MODULE/values" -maxdepth 1 -type f -name '[0-9][0-9]-*.yaml' ! -name '99-private.yaml' -print0 | sort -z)
if [[ "$MODULE" == loki ]]; then
  PRIVATE="$ROOT/loki/values/99-private.yaml"
  [[ -f "$PRIVATE" ]] || { echo "먼저 $PRIVATE 파일을 생성하세요" >&2; exit 1; }
  if grep -Eq 'YOUR_|REPLACE_WITH_' "$PRIVATE"; then echo 'Loki 비밀 설정의 예시 값을 실제 값으로 변경하세요' >&2; exit 1; fi
  args+=(-f "$PRIVATE")
fi
if [[ "$MODULE" == fluentd ]]; then
  command -v python3 >/dev/null || { echo 'python3 설치 필요' >&2; exit 1; }
  python3 "$ROOT/scripts/build-fluentd-values.py" "$ROOT/.generated/fluentd-pipeline.yaml"
  args+=(-f "$ROOT/.generated/fluentd-pipeline.yaml")
fi
printf '설치 대상: %s (%s)\n' "$RELEASE" "$CHART"
helm "${args[@]}"
