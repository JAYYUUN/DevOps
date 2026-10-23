# Tempo Wrapper Chart

Kubernetes 애플리케이션의 **분산 트레이스(Trace)를 수신·저장하고 Grafana에서 조회**하기 위한 재사용 가능한 Helm 모듈입니다. Grafana Community 공식 `tempo` Chart **2.3.0**을 의존성으로 사용하며, 현재 구성은 **Single Binary 1개 + S3 Object Storage + WAL용 PVC** 기반입니다. HA 구성은 아닙니다.

## 구성 및 설정

```text
charts/tempo/
├── Chart.yaml        # Grafana Community tempo 2.3.0 의존성
├── values.yaml       # OTLP 수신, 보존기간, S3 및 PVC 설정
├── values/
│   └── 99-private.yaml.example  # S3 인증정보 예시
└── README.md
```

`values.yaml`에는 OTLP gRPC `4317`, OTLP HTTP `4318` 수신, Trace 보존기간 `24h`, S3 저장소 및 WAL 경로 `/var/tempo/wal`이 정의되어 있습니다. `persistence.enabled: true`, PVC 요청 크기는 `10Gi`이며 CPU 요청 `100m`, 메모리 요청 `256Mi`, 제한 `1 CPU / 1Gi`입니다.

### S3 및 PVC 저장 구조

| 저장소 | 용도 | 설정 |
|---|---|---|
| S3 Object Storage | 완성된 Trace 데이터 저장 및 조회 | `storage.trace.s3` |
| PVC | S3 저장 전 WAL 데이터 기록 및 장애 복구 | `persistence` |
| WAL | Trace 처리 중 데이터를 기록하는 Write-Ahead Log | `/var/tempo/wal` |

S3에 저장된 Trace는 Tempo Pod가 재생성되어도 유지됩니다. PVC는 S3에 저장되기 전 WAL 데이터를 보존하는 데 사용합니다.

### 배포 전 입력할 설정값

`charts/tempo/values.yaml`에서 다음 항목을 환경에 맞게 설정합니다.

| 설정값 | 입력 내용 |
|---|---|
| `bucket` | 미리 생성한 S3 버킷 이름 |
| `endpoint` | NHN Cloud Object Storage의 S3 호환 엔드포인트 |
| `region` | Object Storage 리전 |
| `access_key` | S3 접근 Access Key |
| `secret_key` | S3 접근 Secret Key |
| `storageClassName` | 클러스터에서 사용할 StorageClass 이름 |
| `size` | WAL용 PVC 용량 (기본 `10Gi`) |
| `retention` | Trace 보존기간 (기본 `24h`) |

S3 버킷은 사전에 생성해야 하며, Access Key와 Secret Key는 GitHub에 업로드하지 않도록 별도 비밀 설정 파일로 관리합니다.

## 배포 전 준비

클러스터의 기본 StorageClass 또는 사용할 StorageClass와 PVC 프로비저너를 확인합니다. NHN Cloud Object Storage에서 Tempo용 S3 버킷을 생성하고 엔드포인트, 리전 및 인증정보를 준비합니다.

`charts/tempo/values/99-private.yaml.example`을 복사해 실제 인증정보를 입력합니다.

```bash
cp ./charts/tempo/values/99-private.yaml.example ./charts/tempo/values/99-private.yaml
chmod 600 ./charts/tempo/values/99-private.yaml
```

`99-private.yaml`은 `.gitignore`에 등록하여 Git에 업로드하지 않습니다.

Instrumentation에서 지정하는 `http://tempo.observability.svc.cluster.local:4318` 주소는 **실제 Tempo Service 이름과 OTLP HTTP 포트가 일치해야** 동작합니다. Grafana에서 조회하려면 Tempo 데이터소스 연결도 필요합니다.

## 배포 방법

프로젝트 최상위 디렉터리에서 실행합니다.

```bash
helm dependency build ./charts/tempo

helm lint ./charts/tempo \
  -f ./charts/tempo/values/99-private.yaml

helm template tempo ./charts/tempo -n observability \
  -f ./charts/tempo/values/99-private.yaml > /tmp/tempo-rendered.yaml

helm upgrade --install tempo ./charts/tempo \
  -n observability --create-namespace \
  -f ./charts/tempo/values/99-private.yaml \
  --wait --timeout 10m
```

`helm template` 결과에는 S3 인증정보가 포함될 수 있으므로 해당 파일을 외부에 공유하지 마세요.

## 배포 확인

```bash
helm list -n observability
kubectl get pods -n observability
kubectl get svc -n observability
kubectl get pvc -n observability
kubectl get svc tempo -n observability -o yaml
```

실제 생성된 Service에서 OTLP HTTP `4318` 및 Grafana 조회용 HTTP `3200` 포트가 노출되는지 확인하세요.

Grafana Tempo 데이터소스 URL 예시는 `http://tempo.observability.svc.cluster.local:3200`이며 실제 Service 이름에 맞춰 변경해야 합니다. Tempo는 기본 인증 계층이 없으므로 외부에 직접 공개하지 마세요.

## 운영 시 확인사항

현재 구성은 **S3에 Trace를 저장하고 PVC에 WAL을 보관하는 단일 인스턴스 구성**입니다. S3를 사용하더라도 Tempo 자체의 고가용성이 보장되는 것은 아닙니다.

운영 환경에서는 보존기간, S3 접근 권한, 인증정보 보호, 네트워크 정책, TLS 및 고가용성 구성을 검토해야 합니다.

이 Chart만 설치해도 애플리케이션 Trace가 자동 생성되지는 않으며, Operator와 Instrumentation을 함께 적용해야 합니다.
