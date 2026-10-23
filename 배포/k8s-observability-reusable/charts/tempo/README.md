# Tempo Wrapper Chart

Kubernetes 애플리케이션의 **분산 트레이스(Trace)를 수신·저장하고 Grafana에서 조회**하기 위한 재사용 가능한 Helm 모듈입니다. Grafana Community 공식 `tempo` Chart **2.3.0**을 의존성으로 사용하며, 현재 구성은 **Single Binary 1개 + 로컬 스토리지(PVC)** 기반의 테스트·소규모 환경용입니다. HA 구성은 아닙니다.

## 구성 및 설정

```text
charts/tempo/
├── Chart.yaml        # Grafana Community tempo 2.3.0 의존성
├── values.yaml       # OTLP 수신, 보존기간, 스토리지 및 리소스 설정
└── README.md
```

`values.yaml`에는 OTLP gRPC `4317`, OTLP HTTP `4318` 수신, Trace 보존기간 `24h`, 로컬 저장 경로 `/var/tempo/traces`, WAL 경로 `/var/tempo/wal`이 정의되어 있습니다. `persistence.enabled: true`, PVC 요청 크기는 `10Gi`이며 CPU 요청 `100m`, 메모리 요청 `256Mi`, 제한 `1 CPU / 1Gi`입니다. 실제 리소스 생성 위치와 Service 포트는 의존 Chart 렌더링 결과를 기준으로 확인해야 합니다.

## 배포 전 준비

클러스터의 기본 StorageClass 또는 사용할 StorageClass와 PVC 프로비저너를 확인합니다. Instrumentation에서 지정하는 `http://tempo.observability.svc.cluster.local:4318` 주소는 **실제 Tempo Service 이름과 OTLP HTTP 포트가 일치해야** 동작합니다. Grafana에서 조회하려면 Tempo 데이터소스 연결도 필요합니다.

## 배포 방법

프로젝트 최상위 디렉터리에서 실행합니다.

```bash
helm dependency build ./charts/tempo
helm lint ./charts/tempo
helm template tempo ./charts/tempo -n observability > /tmp/tempo-rendered.yaml
helm upgrade --install tempo ./charts/tempo \
  -n observability --create-namespace --wait --timeout 10m
```

## 배포 확인

```bash
helm list -n observability
kubectl get pods -n observability
kubectl get svc -n observability
kubectl get pvc -n observability
kubectl get svc tempo -n observability -o yaml
```

실제 생성된 Service에서 OTLP HTTP `4318` 및 Grafana 조회용 HTTP `3200` 포트가 노출되는지 확인하세요. Grafana Tempo 데이터소스 URL 예시는 `http://tempo.observability.svc.cluster.local:3200`이며 실제 Service 이름에 맞춰 변경해야 합니다. Tempo는 기본 인증 계층이 없으므로 외부에 직접 공개하지 마세요.

## 운영 시 확인사항

현재 로컬 PVC 구성은 단일 인스턴스 장애에 취약합니다. 운영 환경에서는 **NHN Cloud S3 호환 Object Storage**, 보존기간, 인증정보 보호, 네트워크 정책, TLS 및 고가용성 구성을 별도로 검토해야 합니다. 이 Chart만 설치해도 애플리케이션 Trace가 자동 생성되지는 않으며, Operator와 Instrumentation을 함께 적용해야 합니다.
