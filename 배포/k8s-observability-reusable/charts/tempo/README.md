# Tempo wrapper

Grafana Community `tempo` 2.3.0 기반 단일 바이너리 Tempo 모듈. **테스트/소규모 구성**이며 HA가 아님.

```bash
helm repo add grafana-community https://grafana-community.github.io/helm-charts
helm dependency build ./charts/tempo
helm lint ./charts/tempo
helm upgrade --install tempo ./charts/tempo -n observability --create-namespace
kubectl get svc -n observability
```

OTLP HTTP `4318`, OTLP gRPC `4317` 수신. `tempo.observability.svc.cluster.local:4318` 접근이 실제 생성된 Service에서 열리는지 `kubectl get svc tempo -n observability -o yaml`로 확인. **스토리지 기본값은 로컬 PVC**. 운영은 S3/Object Storage, 보존기간, PVC/StorageClass, 네트워크 정책, 인증/TLS 및 HA 구성을 별도 검토.

Grafana 데이터소스: `http://tempo.observability.svc.cluster.local:3200` (Service 포트 확인 필수). Tempo는 기본 인증 계층이 없으므로 외부 공개 금지.
