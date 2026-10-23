# Kubernetes Observability — Reusable Helm Modules

Prometheus, Grafana, Alertmanager, Loki, Fluentd 및 Tempo·OpenTelemetry 계측 구성을 Kubernetes에 배포하기 위한 **재사용 가능한 Wrapper Helm Chart 모음**입니다. 각 모듈은 공식 Helm Chart를 의존성으로 사용하며, Helm CLI 또는 Argo CD로 독립적으로 배포할 수 있습니다.

| 모듈 | 역할 | Helm Release |
|---|---|---|
| Prometheus (`kube-prometheus-stack`) | 메트릭 수집·조회, Grafana 대시보드, Alertmanager | `monitoring` |
| Loki | 로그 저장·조회, S3 호환 Object Storage 사용 | `loki` |
| Fluentd | Kubernetes 컨테이너 로그 수집·가공 및 Loki 전송 | `fluentd` |
| Tempo | 분산 Trace 수신·저장 | `tempo` |
| OpenTelemetry Operator | 자동 계측 Webhook 및 Agent 주입 | `otel-operator` |
| Instrumentation | 네임스페이스·언어별 Tempo 전송 및 계측 정책 | `otel-java` 등 |

## 1. 디렉터리 구조

```text
k8s-observability-reusable/
├── charts/
│   ├── prometheus/
│   │   ├── Chart.yaml                 # 공식 kube-prometheus-stack 의존성
│   │   ├── values.yaml               # 기본 적용 설정
│   │   ├── values/                   # 기능별 values (선택적 오버라이드)
│   │   └── README.md
│   ├── loki/
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   ├── values/
│   │   │   ├── 00-common.yaml
│   │   │   ├── 01-storage.yaml
│   │   │   ├── 02-cache.yaml
│   │   │   ├── 03-limits.yaml
│   │   │   └── 99-private.yaml.example
│   │   └── README.md
│   ├── fluentd/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values/                   # 공통·리소스·플러그인·헬스체크
│       ├── config/
│       │   ├── 01_sources.conf       # 로그 및 메트릭 수집
│       │   ├── 02_filters.conf       # Kubernetes 메타데이터
│       │   ├── 03_dispatch.conf      # 로그 필드 가공
│       │   └── 04_outputs.conf       # Loki 전송
│       ├── templates/
│       │   └── configmap.yaml        # config/*.conf → ConfigMap
│       └── README.md
│   ├── tempo/                       # OTLP 수신·Trace 저장
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── README.md
│   ├── opentelemetry-operator/      # 자동 계측 컨트롤러·Webhook
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── README.md
│   └── instrumentation/            # 언어별 Instrumentation CR
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values/                   # java/python/nodejs/dotnet
│       ├── templates/instrumentation.yaml
│       └── README.md
├── gitops/argocd/                   # 모듈별 Argo CD Application 예시
├── scripts/                         # 선택적 점검·설정 추출 스크립트
└── README.md
```

### 설정 적용 방식

- `Chart.yaml`: 공식 Helm Chart의 이름, 저장소, 버전을 정의합니다.
- `charts/<모듈>/values.yaml`: **Helm이 자동으로 읽는 기본 설정**입니다. 의존 Chart에 전달할 설정은 의존성 이름 아래에 작성합니다.
- `charts/<모듈>/values/*.yaml`: 기능별 설정 파일입니다. **자동 병합되지 않으며**, `-f` 또는 Argo CD `helm.valueFiles`로 지정해야 합니다. 현재 기본 `values.yaml`에는 해당 설정이 통합되어 있습니다. 기능별 파일만 수정해도 기본 파일에 자동 반영되지는 않습니다.
- `charts/instrumentation/templates/instrumentation.yaml`: 공통 values와 언어별 오버라이드로 네임스페이스별 Instrumentation CR을 생성합니다. **Operator 설치와 CRD 생성 이후** 적용해야 합니다.
- `charts/fluentd/config/*.conf`: Fluentd 설정 원본입니다. `templates/configmap.yaml`이 `.Files.Glob`으로 파일을 읽어 ConfigMap을 생성합니다. Fluentd Chart의 `extraFilesConfigMapNameOverride` 설정을 통해 이 ConfigMap을 사용하도록 구성되어 있습니다. **실제 마운트와 include 동작은 배포 전 렌더링 결과에서 확인하세요.**

## 2. 사전 준비

- Kubernetes 클러스터 접근 권한 및 정상적인 `kubectl` 컨텍스트
- Helm 3
- Helm Chart 저장소에 대한 네트워크 접근
- Loki용 S3 호환 Object Storage의 endpoint, region, 접근 키 및 버킷
- Loki 영구 볼륨용 StorageClass 또는 클러스터의 기본 StorageClass

```bash
helm version
kubectl config current-context
kubectl get nodes
kubectl get storageclass
helm list -n observability
```

> 기존 Release가 있다면 **업그레이드 전 Chart 버전과 변경될 리소스**를 확인하세요. Wrapper의 의존 Chart 버전은 `charts/*/Chart.yaml`에 지정되어 있습니다.

## 3. Loki 스토리지 및 인증정보

`charts/loki/values.yaml`의 다음 항목을 배포 환경에 맞게 확인하세요.

```yaml
loki:
  singleBinary:
    persistence:
      enabled: true
      storageClass: ""    # 기본 StorageClass 사용; 필요하면 실제 이름 입력
      size: 10Gi
```

`storageClass`가 빈 문자열이면 별도의 StorageClass를 명시하지 않는 설정입니다. 기본 StorageClass가 없다면 클러스터에서 제공하는 StorageClass 이름을 지정하세요.

로컬 Helm CLI에서 사용할 S3 인증정보 파일을 준비합니다.

```bash
cp charts/loki/values/99-private.yaml.example charts/loki/values/99-private.yaml
chmod 600 charts/loki/values/99-private.yaml
vi charts/loki/values/99-private.yaml
```

예시 파일의 endpoint, region, accessKeyId, secretAccessKey를 실제 환경 값으로 변경하세요. **인증정보 파일과 이를 포함한 렌더링 YAML을 Git에 올리지 마세요.**

## 4. Helm CLI 배포

아래 명령은 **프로젝트 루트(`k8s-observability-reusable/`)**에서 실행합니다.

### 4.1 의존 Chart 준비

```bash
helm dependency build ./charts/prometheus
helm dependency build ./charts/loki
helm dependency build ./charts/fluentd
helm dependency build ./charts/tempo
helm dependency build ./charts/opentelemetry-operator
```

### 4.2 Chart 검사 및 배포 YAML 확인

```bash
helm lint ./charts/prometheus
helm lint ./charts/loki -f ./charts/loki/values/99-private.yaml
helm lint ./charts/fluentd
helm lint ./charts/tempo
helm lint ./charts/opentelemetry-operator
helm lint ./charts/instrumentation -f ./charts/instrumentation/values/java.yaml

helm template monitoring ./charts/prometheus -n observability > /tmp/prometheus.yaml
helm template loki ./charts/loki -n observability \
  -f ./charts/loki/values/99-private.yaml > /tmp/loki.yaml
helm template fluentd ./charts/fluentd -n observability > /tmp/fluentd.yaml
```

`helm template`은 Kubernetes에 설치하지 않고 최종 YAML만 생성합니다. `/tmp/loki.yaml`에는 인증정보가 포함될 수 있으므로 접근을 제한하고 확인 후 삭제하세요.

### 4.3 설치 또는 업데이트

```bash
# 1. 메트릭·대시보드
helm upgrade --install monitoring ./charts/prometheus \
  -n observability --create-namespace --wait --timeout 10m

# 2. 로그 저장소
helm upgrade --install loki ./charts/loki \
  -n observability \
  -f ./charts/loki/values/99-private.yaml \
  --wait --timeout 10m

# 3. 로그 수집기
helm upgrade --install fluentd ./charts/fluentd \
  -n observability --wait --timeout 10m
```

### 4.4 분산 추적(Tracing) 모듈 설치

Trace 수집은 **Tempo → OpenTelemetry Operator → 애플리케이션 네임스페이스별 Instrumentation → Deployment 주입 어노테이션** 순서로 구성합니다. Operator는 Agent를 주입하고, Agent가 Tempo로 직접 OTLP 전송합니다. 별도 Collector는 포함하지 않습니다.

```bash
helm upgrade --install tempo ./charts/tempo \
  -n observability --create-namespace --wait --timeout 10m
helm upgrade --install otel-operator ./charts/opentelemetry-operator \
  -n observability --wait --timeout 10m
kubectl get crd instrumentations.opentelemetry.io
helm upgrade --install otel-java ./charts/instrumentation \
  -n payment --create-namespace \
  -f ./charts/instrumentation/values/java.yaml
```

Java 애플리케이션의 `spec.template.metadata.annotations`에 `instrumentation.opentelemetry.io/inject-java: "java-instrumentation"`을 지정하고 Pod를 재생성해야 주입됩니다. Python/Node.js/.NET은 각 언어별 values와 주입 어노테이션을 사용합니다. 공통 전송 주소·프로토콜·샘플링은 `charts/instrumentation/values.yaml`에서 관리하며, **수동 계측은 애플리케이션 코드에 추가**하고 자동 계측 SDK/Context를 공유합니다.

현재 Tempo는 **로컬 PVC 10Gi, 보존기간 24h의 단일 인스턴스 테스트 구성**입니다. 운영용 S3 호환 Object Storage 및 HA는 별도 설정이 필요합니다. 또한 Tempo Service의 OTLP `4318` 포트와 Operator Webhook TLS/CRD, 언어별 Agent 호환성을 실제 배포 전에 확인하세요.

### 4.5 배포 확인

```bash
helm list -n observability
kubectl get pods -n observability
kubectl get svc -n observability
kubectl get pvc -n observability
kubectl get daemonset -n observability
```

추가 점검 스크립트는 선택 사항입니다.

```bash
bash scripts/verify.sh
```

## 5. 설정 변경 및 모듈 재사용

**기본 설정 변경:** `charts/<모듈>/values.yaml`을 수정한 뒤 해당 모듈을 다시 배포합니다.

**기능별 values 파일 적용:** 아래처럼 `-f`로 지정하면 기본 `values.yaml` 위에 해당 설정을 병합합니다.

```bash
helm template fluentd ./charts/fluentd -n observability \
  -f ./charts/fluentd/values/01-resources.yaml
```

여러 파일은 `-f`를 반복해 지정합니다. `values/*.yaml`을 자동으로 읽지는 않습니다. 파일이 여러 개일 때 같은 키는 나중에 지정한 값이 우선합니다.

**Fluentd 설정 변경:** `charts/fluentd/config/`의 `.conf`를 수정하거나 추가합니다. Helm이 ConfigMap에 포함하지만, ConfigMap 변경만으로 Pod 재시작이 보장되지는 않습니다. 설정 적용 여부를 확인하고 필요하면 실제 DaemonSet 이름을 확인한 후 재시작하세요.

**환경별 재사용:** 같은 Chart를 사용하되 환경별 오버라이드 파일과 Release/Namespace를 구분해 설치할 수 있습니다. Loki 주소, StorageClass, S3 인증정보 등 환경 종속 값은 대상 클러스터에 맞게 설정해야 합니다.

## 6. Argo CD 배포

`gitops/argocd/`에 Prometheus, Loki, Fluentd Application 예시가 있습니다.

1. Chart와 설정을 Git 저장소에 업로드합니다.
2. 각 Application의 `spec.source.repoURL`, `targetRevision`, `path`를 실제 저장소에 맞게 수정합니다.
3. Argo CD repo-server가 의존 Helm Chart 저장소에 접근할 수 있는지 확인합니다.
4. Loki S3 인증정보는 Git에 평문으로 커밋하지 않고 **별도의 Secret 관리·주입 방식**을 준비합니다. 제공된 Loki Application 예시만으로는 로컬 `99-private.yaml`이 적용되지 않습니다.
5. Application을 등록하고 렌더링 결과 및 Sync 상태를 확인합니다.

```bash
kubectl apply -f gitops/argocd/prometheus.yaml
kubectl apply -f gitops/argocd/fluentd.yaml
# Loki는 인증정보 주입 구성을 완료한 뒤 Application 등록 및 동기화
```

Argo CD는 Helm Chart를 렌더링해 Kubernetes에 적용합니다. **동일한 리소스를 Helm CLI와 Argo CD가 동시에 관리하지 마세요.**

## 7. 운영 시 확인사항

- **Tracing:** Tempo OTLP 수신 Service, Operator Webhook/CRD, 네임스페이스별 Instrumentation, Agent 주입 상태를 확인합니다.
- **Chart 버전:** `charts/*/Chart.yaml`의 Dependency 버전과 대상 클러스터의 설치 버전을 비교합니다.
- **Loki 저장소:** StorageClass, PVC 용량, S3 버킷·endpoint·인증정보를 확인합니다.
- **Fluentd:** 렌더링된 DaemonSet의 ConfigMap 마운트, `@include` 설정, 플러그인 및 `/metrics` 프로브를 확인합니다.
- **연결 주소:** Fluentd와 Grafana의 Loki URL은 `loki-gateway.observability.svc.cluster.local`을 사용하도록 설정되어 있습니다. Namespace 또는 Service 이름이 다르면 수정해야 합니다.
- **보안:** Loki 개인 values 파일 및 렌더링 결과를 공유하거나 커밋하지 않습니다.

모듈별 상세 설정은 [Prometheus](charts/prometheus/README.md), [Loki](charts/loki/README.md), [Fluentd](charts/fluentd/README.md), [Tempo](charts/tempo/README.md), [OpenTelemetry Operator](charts/opentelemetry-operator/README.md), [Instrumentation](charts/instrumentation/README.md)를 참고하세요.
