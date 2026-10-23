# Fluentd Wrapper Chart

Kubernetes 노드의 컨테이너 로그를 수집하고 Loki로 전송하는 재사용 가능한 Helm 모듈입니다. 공식 `fluentd` Chart를 의존성으로 사용하며, **DaemonSet**으로 배포됩니다.

## 구성 및 설정

```text
charts/fluentd/
├── Chart.yaml                  # fluentd 0.5.3 의존성
├── values.yaml                 # 기본 설정(자동 적용)
├── values/
│   ├── 00-common.yaml         # DaemonSet / 볼륨 / 권한 설정
│   ├── 01-resources.yaml      # CPU / 메모리
│   ├── 02-plugins.yaml        # Fluentd 플러그인
│   └── 03-healthcheck.yaml    # Liveness / Readiness Probe
├── config/
│   ├── 01_sources.conf        # 컨테이너 로그 및 메트릭 수집
│   ├── 02_filters.conf        # Kubernetes 메타데이터
│   ├── 03_dispatch.conf       # namespace / pod / container 필드
│   └── 04_outputs.conf        # Loki 전송 및 버퍼
└── templates/
    └── configmap.yaml         # config/*.conf를 ConfigMap으로 생성
```

기본 설정은 `DaemonSet`, `/var/log` 마운트, ServiceAccount/RBAC 생성, Fluentd 플러그인 3개(`fluent-plugin-grafana-loki`, `fluent-plugin-prometheus`, `fluent-plugin-kubernetes_metadata_filter`)를 사용합니다. 리소스 요청은 CPU `100m` / 메모리 `256Mi`, 제한은 CPU `500m` / 메모리 `512Mi`입니다. 헬스체크는 `/metrics` 엔드포인트를 사용합니다.

## 로그 처리 흐름

```text
/var/log/containers/*.log
    → 01_sources.conf (tail, read_from_head false)
    → 02_filters.conf (Kubernetes 메타데이터)
    → 03_dispatch.conf (필드 가공)
    → 04_outputs.conf (Loki 전송)
    → loki-gateway.observability.svc.cluster.local
```

`templates/configmap.yaml`은 Helm `.Files.Glob "config/*.conf"`로 설정 파일을 읽고 `fluentd-wrapper-files` ConfigMap을 생성합니다. 루트 `values.yaml`의 `fluentd.extraFilesConfigMapNameOverride`가 이 ConfigMap을 공식 Chart의 설정 파일 경로에 연결하도록 구성되어 있습니다. 실제 연결과 Fluentd의 `@include` 동작은 배포 전 렌더링 결과에서 확인하세요.

`values.yaml`은 자동 적용됩니다. `values/*.yaml`은 자동 병합되지 않습니다. 공통 설정 변경 시 루트 `values.yaml`을 수정하거나 `-f`로 해당 파일을 지정하세요. 반면 `config/*.conf`는 ConfigMap 템플릿에서 자동으로 읽습니다.

## 배포 방법

먼저 Loki가 배포되어 있고 `loki-gateway` 주소로 접근할 수 있어야 합니다. 프로젝트 최상위 디렉터리에서 실행합니다.

```bash
helm dependency build ./charts/fluentd
helm lint ./charts/fluentd
helm template fluentd ./charts/fluentd -n observability > /tmp/fluentd-rendered.yaml
helm upgrade --install fluentd ./charts/fluentd -n observability --create-namespace --wait --timeout 10m
```

추가 values 오버라이드 예시:

```bash
helm upgrade --install fluentd ./charts/fluentd -n observability \
  -f ./charts/fluentd/values/01-resources.yaml
```

## 배포 확인

```bash
helm list -n observability
kubectl get daemonset -n observability
kubectl get pods -n observability
kubectl get configmap fluentd-wrapper-files -n observability -o yaml
kubectl logs -n observability -l app.kubernetes.io/name=fluentd --tail=100
```

`/tmp/fluentd-rendered.yaml`에서 ConfigMap, DaemonSet의 볼륨 마운트, 설정 파일 경로를 확인하세요. `.conf` 수정 후에는 Helm 업그레이드 또는 Argo CD Sync가 필요합니다. **ConfigMap만 바뀌었다고 Fluentd 프로세스가 즉시 재시작되는 것은 아닙니다.** 필요한 경우 롤아웃을 수행하세요.


