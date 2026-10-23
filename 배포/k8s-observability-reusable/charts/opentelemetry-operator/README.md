# OpenTelemetry Operator wrapper

클러스터에 한 번 설치하는 자동 계측 제어 모듈. Collector를 **별도로 배포하지 않음**. Operator 이미지 설정의 `collectorImage`는 Operator의 기본 관리 이미지 옵션이지 Collector Deployment를 만드는 설정이 아님.

```bash
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm dependency build ./charts/opentelemetry-operator
helm lint ./charts/opentelemetry-operator
helm upgrade --install otel-operator ./charts/opentelemetry-operator -n observability --create-namespace
kubectl get crd instrumentations.opentelemetry.io
kubectl get pods -n observability
```

Webhook은 자체 서명 TLS 인증서를 사용. 클러스터에서 cert-manager를 사용한다면 `certManager.enabled=true`, `autoGenerateCert.enabled=false`로 변경. Operator Chart 0.126.0은 배포 환경의 Helm 버전/쿠버네티스 요구사항을 사전 확인. Operator가 관리하는 CRD는 Helm 업그레이드만으로 자동 갱신되지 않을 수 있음.
