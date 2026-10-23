# Smart Kubernetes Observability — Wrapper Helm Charts

기존 ZIP의 **Prometheus(kube-prometheus-stack), Loki, Fluentd** 설정을 유지하고, Python 설정 조립 및 `install-module.sh`를 제거한 Helm-native 구성입니다.

## 전체 구조

```text
Smart-wrapper-chart/
├── charts/
│   ├── prometheus/{Chart.yaml,values.yaml,values/,README.md}
│   ├── loki/{Chart.yaml,values.yaml,values/,README.md}
│   └── fluentd/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values/{00-common,01-resources,02-plugins,03-healthcheck}.yaml
│       ├── config/{01_sources,02_filters,03_dispatch,04_outputs}.conf
│       └── templates/configmap.yaml
├── gitops/argocd/{prometheus,loki,fluentd}.yaml
├── scripts/{verify,export-live}.sh
└── .gitignore
```

## 적용 원리

1. `Chart.yaml`이 공식 Chart를 Dependency로 선언합니다.
2. **루트 `values.yaml`은 Helm이 자동 적용**합니다. 기존의 숫자별 values 설정을 병합한 사본이 들어 있어 별도 스크립트나 여러 `-f`가 필요 없습니다.
3. `values/*.yaml`은 기능별로 나눈 **선택적 오버라이드/편집 단위**입니다. **자동 로드되지 않습니다.** 변경 후 루트 `values.yaml`에도 반영하거나 해당 파일을 `-f`/Argo CD `helm.valueFiles`에 지정하세요. 같은 값을 두 곳에 변경하면 관리가 어려우므로 기본 설정 변경은 동기화가 필요합니다.
4. Fluentd `templates/configmap.yaml`은 `.Files.Glob "config/*.conf"`로 설정 파일을 읽어 `fluentd-wrapper-files` ConfigMap을 만듭니다. 공식 Fluentd Chart의 `extraFilesConfigMapNameOverride`가 이 ConfigMap을 DaemonSet에 연결합니다. 공식 Chart의 기본 `fluent.conf`는 `config.d/*.conf`를 포함합니다.
5. Helm CLI는 리소스를 직접 설치하고, Argo CD는 Helm 렌더링 결과를 Kubernetes에 동기화합니다.

## 기존 설정 보존 범위

- Prometheus/Grafana/Alertmanager 사용 여부, Grafana의 Loki 데이터 소스
- Loki SingleBinary 1개, 10Gi PVC, UID 10001 권한 초기화, S3 저장소, 캐시/제한 설정
- Fluentd DaemonSet, 리소스, 플러그인, 프로브, `.conf` 네 개의 원문 및 `read_from_head false`
- Loki Object Storage 접근 정보는 ZIP에 실값이 없어서 예시만 유지

## 0. 필수 확인

```bash
helm version
kubectl config current-context
kubectl get storageclass
helm list -n observability
```

**중요:** 원본에는 설치된 Chart의 실제 버전 정보가 없었습니다. Wrapper의 `Chart.yaml` 버전은 재현 가능한 **예시 고정 버전**으로 지정했으므로 기존 설치 버전을 `helm list -n observability`로 확인한 뒤 **세 Chart.yaml의 의존성 버전을 일치시키세요.** 특히 Loki는 Chart 버전에 따라 설정 스키마가 달라질 수 있습니다. 기존 릴리스에 검증 없이 업그레이드하지 마세요.

## 1. Loki 비밀값 준비 (로컬 Helm CLI)

```bash
cp charts/loki/values/99-private.yaml.example charts/loki/values/99-private.yaml
chmod 600 charts/loki/values/99-private.yaml
vi charts/loki/values/99-private.yaml
```

원본의 `endpoint`, `region`, `accessKeyId`, `secretAccessKey`는 실값이 제공되지 않았습니다. `YOUR_`를 실제 값으로 교체하세요. Object Storage 버킷 이름은 기존 `loki-test`를 보존했습니다. Loki PVC는 기본 StorageClass를 사용하며, 없다면 `charts/loki/values.yaml`의 `loki.singleBinary.persistence.storageClass`를 수정하세요.

## 2. Helm CLI 설치

저장소 루트에서 실행합니다. **Python 필요 없음.**

```bash
helm dependency build ./charts/prometheus
helm dependency build ./charts/loki
helm dependency build ./charts/fluentd

# 먼저 렌더링으로 점검
helm template monitoring ./charts/prometheus -n observability > /tmp/prometheus.yaml
helm template loki ./charts/loki -n observability -f ./charts/loki/values/99-private.yaml > /tmp/loki.yaml
helm template fluentd ./charts/fluentd -n observability > /tmp/fluentd.yaml

# 기존 릴리스 이름을 유지: monitoring / loki / fluentd
helm upgrade --install monitoring ./charts/prometheus -n observability --create-namespace --wait --timeout 10m
helm upgrade --install loki ./charts/loki -n observability -f ./charts/loki/values/99-private.yaml --wait --timeout 10m
helm upgrade --install fluentd ./charts/fluentd -n observability --wait --timeout 10m
bash scripts/verify.sh
```

Loki 개인 values 파일은 **비밀정보**를 포함하므로 `/tmp/loki.yaml` 역시 민감합니다. 공유하거나 Git에 커밋하지 마세요. 실행 후 안전하게 삭제하세요.

## 3. values 모듈 사용

예를 들어 Fluentd 리소스만 덮어쓸 경우:

```bash
helm upgrade --install fluentd ./charts/fluentd -n observability \
  -f ./charts/fluentd/values/01-resources.yaml
```

모듈을 모두 다시 적용할 필요는 없습니다. 기본 `values.yaml`에 기존 설정 전체가 포함되어 있습니다. 추가 파일을 여러 개 지정할 경우 Helm은 지정한 순서대로 병합합니다. `-f values/*.yaml`은 여러 파일을 자동 인식하는 기능이 아닙니다.

## 4. Fluentd config 추가/수정

`charts/fluentd/config/05_custom.conf`처럼 파일을 추가하면 Wrapper의 `.Files.Glob`에 자동 포함됩니다. 별도 Python 변환은 없습니다. 다만 **ConfigMap 변경이 Pod 재시작을 자동 보장하지 않으므로**, 배포 후 Pod가 새 설정을 로드했는지 확인하고 필요하면 `kubectl rollout restart daemonset/fluentd -n observability`를 수행하세요. 실제 DaemonSet 이름은 렌더링 결과로 확인하세요.

## 5. Argo CD

`gitops/argocd/`에 모듈별 Application 예시가 있습니다. Git 저장소의 실제 업로드 경로에 맞춰 `spec.source.path`를 조정하세요. 의존성 다운로드를 위해 Argo CD repo-server가 Helm Chart 저장소에 접근 가능해야 합니다.

- Prometheus / Fluentd: 루트 `values.yaml`이 자동 적용되므로 `helm.valueFiles` 불필요
- Loki: **실제 S3 자격증명을 Git에 넣지 마세요.** 제공된 Loki Application은 자동 동기화를 비활성화했습니다. Argo CD에서 Secret 기반 주입(예: 별도 Secret 관리 방식)을 설계하고 검증한 다음 Sync하세요. 로컬 `99-private.yaml`은 Git에 없으므로 Argo CD에서 자동 사용되지 않습니다.
- Argo CD는 `helm upgrade --install`을 실행하는 것이 아니라 Chart를 렌더링해 적용합니다. 동일 리소스를 Helm CLI와 Argo CD가 동시에 관리하지 마세요.

## 6. 배포 전 주의

- **버전 호환성:** 원본에 버전 정보가 없어 Chart.yaml 버전은 실제 운영 버전과 다를 수 있습니다. Loki 6.x와 최신 Chart 간 스키마 차이에 주의하세요.
- **Fluentd ConfigMap:** 공식 Fluentd Chart의 `extraFilesConfigMapNameOverride` 지원을 기준으로 구성했습니다. 설치 버전의 `helm template` 결과에서 ConfigMap 마운트 경로(`/etc/fluent/config.d`)와 기본 `@include config.d/*.conf`를 확인하세요.
- **기존 Helm 릴리스 전환:** Chart 이름 변경으로 기존 리소스 이름/소유권이 바뀔 수 있습니다. `helm diff` 등으로 변경사항을 검토한 뒤 적용하세요.
- **Grafana/Loki 서비스 DNS:** 기존 설정 `loki-gateway.observability.svc.cluster.local` 유지. namespace 변경 시 URL도 수정해야 합니다.
- **Fluentd 플러그인:** 기존 플러그인 설치 목록을 보존했습니다. 대상 이미지/플러그인 호환성을 확인하세요.

## 파일별 안내

- [Prometheus](charts/prometheus/README.md)
- [Loki](charts/loki/README.md)
- [Fluentd](charts/fluentd/README.md)
