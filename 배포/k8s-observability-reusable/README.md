# Kubernetes Observability 재사용 모듈

Kubernetes에서 필요한 관측 도구를 **차트별로 독립 설치·수정·업데이트**할 수 있도록 구성한 Helm 설정 모음입니다. 전체 스택을 한 번에 설치하는 프로젝트가 아니라, **Prometheus Stack / Loki / Fluentd를 선택적으로 재사용하는 모듈 저장소**입니다.

## 1. 모듈 구성

**Observability(관측성)**는 시스템의 상태를 메트릭과 로그로 파악하는 운영 방식입니다. 이 저장소는 세 도구를 하나의 배포 단위로 묶지 않고, 필요한 기능만 선택해서 재사용하도록 구성했습니다. 예를 들어 메트릭 모니터링만 필요하면 Prometheus 모듈만 설치할 수 있습니다.

| 모듈 | 역할 | Helm 차트 | 릴리스 이름 |
|---|---|---|---|
| Prometheus Stack | 메트릭 수집, Grafana, Alertmanager | `prometheus-community/kube-prometheus-stack` | `monitoring` |
| Loki | 로그 저장·검색, NHN Cloud S3 호환 Object Storage | `grafana/loki` | `loki` |
| Fluentd | 노드별 CRI 컨테이너 로그 수집 및 Loki 전송 | `fluent/fluentd` | `fluentd` |

```text
Worker Node ─ Fluentd ─ Loki Gateway ─ Loki ─ Object Storage
                                           │
                                      Grafana Explore
Node/Pod Metrics ─ Prometheus ─────────────┘
```

## 2. 폴더 구조와 설정 역할

각 모듈의 `values/`는 Helm 차트에 전달하는 설정이며, 숫자 접두사는 적용 순서를 나타냅니다. 공통 설정과 기능별 설정을 분리해 수정 범위를 줄이고, 차트별 README에서 해당 모듈의 상세 절차를 안내합니다.

```text
k8s-observability-reusable/
├── README.md
├── .gitignore
├── git/
│   └── README.md                       # Git 설치, clone, 서버 전송, 업데이트 가이드
├── config/
│   └── versions.env.example            # 차트 버전 지정 예시
├── prometheus/
│   ├── README.md                       # Prometheus 모듈 사용 가이드
│   └── values/
│       ├── 00-common.yaml              # 공통 설정
│       ├── 01-prometheus.yaml          # Prometheus 활성화
│       ├── 02-grafana.yaml             # Grafana, Loki 데이터 소스
│       └── 03-alertmanager.yaml        # Alertmanager 활성화
├── loki/
│   ├── README.md                       # Loki 모듈 사용 가이드
│   └── values/
│       ├── 00-common.yaml              # SingleBinary, TSDB 스키마
│       ├── 01-storage.yaml             # S3 버킷 및 저장 방식
│       ├── 02-cache.yaml               # 캐시 활성화 여부
│       ├── 03-limits.yaml              # Loki 제한 설정
│       └── 99-private.yaml.example     # Object Storage 비밀 설정 예시
├── fluentd/
│   ├── README.md                       # Fluentd 모듈 사용 가이드
│   ├── values/
│   │   ├── 00-common.yaml              # DaemonSet, 마운트, RBAC
│   │   ├── 01-resources.yaml           # CPU/메모리
│   │   ├── 02-plugins.yaml             # Fluentd 플러그인
│   │   └── 03-healthcheck.yaml         # /metrics 프로브
│   └── config/
│       ├── 01_sources.conf             # CRI 로그 및 메트릭 입력
│       ├── 02_filters.conf             # Kubernetes 메타데이터
│       ├── 03_dispatch.conf            # 로그 필드 추출
│       └── 04_outputs.conf             # Loki 전송/버퍼
└── scripts/
    ├── README.md                       # 스크립트별 실행 가이드
    ├── install-module.sh               # 지정 모듈만 설치/업데이트
    ├── build-fluentd-values.py         # .conf → fileConfigs YAML 생성
    ├── verify.sh                       # 배포 상태 확인
    └── export-live.sh                  # 설치된 Helm 값 추출
```

GitHub 저장소를 Bastion 서버로 가져오는 방법은 [`git/README.md`](git/README.md)에서 설명합니다. Git 설치, `~/git` 작업 디렉터리 생성, 전체 clone, 특정 폴더만 받기, 변경사항 갱신, 폐쇄망 SCP 전송을 단계별로 확인할 수 있습니다.

각 모듈의 상세 설치·수정 방법은 [`prometheus/README.md`](prometheus/README.md), [`loki/README.md`](loki/README.md), [`fluentd/README.md`](fluentd/README.md), [`scripts/README.md`](scripts/README.md)에서 확인합니다. 루트 README는 전체 개요와 공통 실행 방법을 다룹니다.

각 `values/` 파일은 Helm의 `-f` 옵션으로 **파일명 순서대로 병합**합니다. 동일한 키가 중복되면 뒤에 적용한 파일이 우선합니다. `fluentd/config/*.conf`는 Python 스크립트가 임시 `fileConfigs` values로 생성한 후 **마지막에 적용**합니다.

## GitHub에서 서버로 모듈 가져오기

GitHub는 재사용 모듈의 원본을 보관하고, Bastion 서버는 이 파일을 가져와 Helm 설치 명령을 실행하는 작업 환경입니다. 서버에 `~/git` 디렉터리를 만든 뒤 저장소를 `git clone`하면 파일을 별도로 복사할 필요가 없고, 이후 `git pull`로 수정사항을 받아올 수 있습니다.

```bash
mkdir -p ~/git
cd ~/git
git clone https://github.com/JAYYUUN/DevOps.git
cd DevOps/k8s-observability-reusable
```

Git 설치부터 Private 저장소 인증, 특정 폴더만 내려받는 방법, GitHub 접속이 불가능한 서버에서 SCP로 옮기는 방법까지는 **[git/README.md — Git 환경 설정 및 서버 전송 가이드](git/README.md)**를 참고하세요. 위 경로는 GitHub 저장소에 해당 폴더를 최상위에 업로드한 경우의 예시입니다.

## 설치 전 필수 설정: Loki StorageClass와 PVC

이 저장소의 Loki는 **S3와 PVC를 함께 사용**합니다. NHN Cloud Object Storage(S3)는 로그 청크와 인덱스를 저장하고, Loki의 **10Gi PVC는 WAL 및 로컬 작업 데이터**를 유지합니다. 따라서 S3를 설정했더라도 PVC를 비활성화하지 않습니다.

재사용 가능한 구성을 위해 `loki/values/00-common.yaml`의 `singleBinary.persistence.storageClass`는 특정 클러스터 이름으로 고정하지 않고 **빈 문자열(`""`)**로 제공됩니다. 설치 대상 클러스터에 기본 StorageClass가 없다면 설치 전에 반드시 실제 StorageClass 이름으로 변경해야 합니다.

**① 클러스터 StorageClass와 PV 확인**

```bash
kubectl get storageclass
kubectl get pv -o wide
```

**② `loki/values/00-common.yaml` 수정**

```yaml
singleBinary:
  replicas: 1
  persistence:
    enabled: true
    storageClass: ""  # 설치 환경에 맞게 입력. 기본 StorageClass가 있으면 빈 값 유지 가능
    size: 10Gi
```

예를 들어 기본 StorageClass가 없는 환경에서 조회한 이름이 `block-static-v2-sc`라면, **해당 환경에서만** `storageClass: block-static-v2-sc`로 변경합니다. 이는 예시이며 기본 설정에 고정하지 않습니다. 정적 프로비저닝 방식이면 사용할 수 있는 PV도 미리 준비해야 할 수 있습니다.

**③ Loki 설치 후 PVC 바인딩 확인**

```bash
bash scripts/install-module.sh loki
kubectl get pvc,pods -n observability
kubectl describe pvc storage-loki-0 -n observability
```

PVC가 `Pending`이면 StorageClass 이름, 기본 StorageClass 지정 여부, PV 존재 여부 및 PVC 이벤트를 확인하세요. **[Loki 상세 설정 및 장애 점검 가이드](loki/README.md)**에 추가 설명이 있습니다.

## 3. 설치 전 준비: 실제 명령어

### 3.1 kubectl / Helm / Python 확인

`kubectl`은 Kubernetes 클러스터에 명령을 전달하고, `helm`은 Kubernetes 애플리케이션을 차트 단위로 설치·업데이트합니다. `python3`는 Fluentd의 분리된 `.conf`를 Helm 설정으로 변환할 때 사용합니다. 아래 명령으로 도구 설치 여부뿐 아니라 현재 연결된 클러스터도 확인합니다.

설치 명령은 Kubernetes API에 접근 가능한 **Bastion 또는 관리 서버**에서 실행합니다.

```bash
kubectl version --client
helm version
python3 --version
kubectl config current-context
kubectl get nodes -o wide
```

Ubuntu에서 Helm이 없는 경우 Helm 공식 설치 스크립트를 이용할 수 있습니다(스크립트 실행 전 내용을 확인하세요).

```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
less get_helm.sh
chmod 700 get_helm.sh
./get_helm.sh
```

`kubectl`이 없으면 Kubernetes 공식 문서의 [Linux 설치 안내](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)에 따라 클러스터 버전에 맞춰 설치하세요. Python이 없다면 Ubuntu에서 `sudo apt-get update && sudo apt-get install -y python3`로 설치할 수 있습니다.

**폐쇄망:** 위 다운로드는 인터넷 접근이 가능한 환경에서만 가능합니다. 폐쇄망에서는 사전에 준비한 Helm/kubectl 바이너리, Helm 차트 패키지, 컨테이너 이미지, Fluentd 플러그인이 포함된 이미지를 내부 경로로 제공해야 합니다. 이 저장소의 기본 설치 스크립트는 Helm 저장소에 접근합니다.

### 3.2 모듈 파일 배치 및 Namespace 확인

Namespace는 Kubernetes 리소스를 논리적으로 구분하는 공간입니다. 세 모듈의 기본 설치 대상인 `observability`를 미리 생성하면 Pod와 Service를 같은 공간에서 관리할 수 있습니다. `--dry-run=client -o yaml | kubectl apply -f -`는 이미 Namespace가 있어도 적용할 수 있는 방식입니다.

```bash
unzip k8s-observability-reusable.zip
cd k8s-observability-reusable
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
kubectl get ns observability
```

기본 Namespace는 `observability`입니다. 다른 Namespace를 쓰려면 Loki Gateway 서비스 DNS를 포함한 설정도 변경해야 합니다.

### 3.3 Helm 차트 등록

Helm 저장소는 차트의 배포 위치를 알려주는 목록입니다. `helm repo add`로 저장소를 등록하고 `helm repo update`로 최신 차트 목록을 가져옵니다. 마지막 `helm search repo`는 설치하려는 차트가 조회되는지 확인하는 명령입니다.

각 모듈을 수동으로 설치할 때 필요한 저장소를 등록합니다.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add fluent https://fluent.github.io/helm-charts
helm repo update
helm search repo prometheus-community/kube-prometheus-stack
helm search repo grafana/loki
helm search repo fluent/fluentd
```

설치 스크립트도 선택한 모듈의 저장소를 자동 등록합니다.

### 3.4 Loki Object Storage 정보 입력

Loki는 수집한 로그를 장기 저장하기 위해 S3 호환 Object Storage를 사용합니다. 엔드포인트와 인증키는 접속 정보이고, 버킷은 로그 데이터를 저장할 대상입니다. 공개 저장소에 인증키가 포함되지 않도록 일반 설정과 비밀 설정을 별도 파일로 관리합니다.

Loki를 설치할 때만 필요한 단계입니다. NHN Cloud Object Storage에서 **S3 호환 엔드포인트, 리전, Access Key, Secret Key, 버킷 이름**을 확인하고 버킷이 생성되어 있는지 확인합니다.

```bash
cp loki/values/99-private.yaml.example loki/values/99-private.yaml
chmod 600 loki/values/99-private.yaml
vi loki/values/99-private.yaml
```

예시 파일의 `endpoint`, `region`, `accessKeyId`, `secretAccessKey`를 실제 값으로 교체합니다. 버킷 이름은 `loki/values/01-storage.yaml`의 `chunks`, `ruler`, `admin`에서 변경합니다. **`99-private.yaml`은 Git에 업로드하지 않습니다.**

### 3.5 차트 버전 고정(선택)

차트 버전은 Helm이 설치할 Kubernetes 리소스 템플릿의 버전을 의미합니다. 버전을 고정하면 같은 모듈을 다른 클러스터에 설치할 때 차트 변경으로 인한 차이를 줄일 수 있습니다. 지정하지 않으면 저장소에서 선택되는 차트 버전이 사용됩니다.

```bash
cp config/versions.env.example config/versions.env
vi config/versions.env
```

`PROMETHEUS_CHART_VERSION`, `LOKI_CHART_VERSION`, `FLUENTD_CHART_VERSION`에 사용하려는 차트 버전을 넣습니다. 비워두면 Helm 저장소에서 사용 가능한 버전을 사용합니다.

## 4. 모듈별 설치 및 업데이트

`helm upgrade --install`은 릴리스가 없으면 설치하고, 있으면 기존 릴리스를 업데이트합니다. 이 저장소의 설치 스크립트는 요청한 모듈 하나에만 이 명령을 실행하므로, 다른 모듈을 불필요하게 재배포하지 않습니다. 각 모듈은 아래의 상세 README를 참고해 독립적으로 관리할 수 있습니다.

**세 모듈을 한꺼번에 설치하지 않습니다.** 필요한 모듈만 선택합니다. 처음 구성한다면 메트릭은 Prometheus, 로그 저장은 Loki, 로그 전송은 Fluentd 순서로 설치하면 됩니다.

### 4.1 Prometheus Stack

Prometheus Stack은 메트릭 수집·조회용 Prometheus와 시각화용 Grafana, 알림용 Alertmanager를 함께 배포합니다. `01-prometheus.yaml` 등 기능별 values를 병합하므로 설정 변경 시 해당 파일만 수정하면 됩니다. Grafana에 등록된 Loki 데이터 소스는 Loki 모듈이 설치된 뒤 로그 조회에 사용합니다.

```bash
bash scripts/install-module.sh prometheus
kubectl get pods -n observability
kubectl get svc -n observability | grep grafana
```

스크립트 없이 직접 설치하려면:

```bash
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  -n observability --wait --timeout 10m \
  -f prometheus/values/00-common.yaml \
  -f prometheus/values/01-prometheus.yaml \
  -f prometheus/values/02-grafana.yaml \
  -f prometheus/values/03-alertmanager.yaml
```

### 4.2 Loki

Loki는 Fluentd가 전송한 로그를 저장하고 LogQL로 검색할 수 있게 해주는 로그 백엔드입니다. 이 모듈은 SingleBinary 방식이며 Object Storage 인증정보를 별도 파일에서 읽습니다. **S3는 로그 청크·인덱스 저장소이고, PVC(10Gi)는 Loki WAL 및 로컬 작업 공간**입니다. 설치 전 비밀 설정과 버킷 이름뿐 아니라 StorageClass와 PV 준비 상태도 확인해야 합니다.

먼저 `99-private.yaml`을 작성한 후 실행합니다.

이 모듈의 `loki/values/00-common.yaml`에는 `singleBinary.persistence.storageClass: ""`로 **빈 값**을 넣어 두었습니다. 설치 대상 클러스터에서 `kubectl get storageclass`로 사용 가능한 이름을 확인하고, **기본 StorageClass가 없는 경우 반드시 실제 이름을 입력한 다음 설치**하세요. 기본 StorageClass가 있는 클러스터에서는 빈 값을 유지할 수 있습니다. StorageClass가 정적 프로비저닝 방식이면 PVC에 맞는 PV를 별도로 준비해야 할 수 있습니다. 상세 절차는 [`loki/README.md`](loki/README.md#21-loki-로컬-pvc와-storageclass-준비)를 참고합니다.

```bash
kubectl get storageclass
kubectl get pv -o wide
kubectl get pvc -n observability
```

설정 파일에서 수정할 부분:

```yaml
singleBinary:
  persistence:
    enabled: true
    storageClass: ""  # 기본 StorageClass가 없으면 실제 StorageClass 이름 입력
    size: 10Gi
```

```bash
bash scripts/install-module.sh loki
kubectl get pods -n observability
kubectl get svc -n observability | grep loki
```

직접 설치:

```bash
helm upgrade --install loki grafana/loki \
  -n observability --wait --timeout 10m \
  -f loki/values/00-common.yaml \
  -f loki/values/01-storage.yaml \
  -f loki/values/02-cache.yaml \
  -f loki/values/03-limits.yaml \
  -f loki/values/99-private.yaml
```

### 4.3 Fluentd

Fluentd는 각 노드에서 컨테이너 로그를 읽고 Kubernetes 메타데이터를 추가한 뒤 Loki로 전송합니다. Fluentd의 파이프라인은 `.conf` 파일로 관리하지만 Helm 차트는 `fileConfigs` 값을 받으므로 변환 과정이 필요합니다. 스크립트 설치 시 이 변환을 자동 수행합니다.

Fluentd는 `.conf`를 Helm 차트의 `fileConfigs`에 포함해야 하므로 **먼저 변환 스크립트를 실행**합니다. `install-module.sh`는 이 과정을 자동 처리합니다.

```bash
bash scripts/install-module.sh fluentd
kubectl rollout status daemonset/fluentd -n observability --timeout=180s
```

직접 설치:

```bash
python3 scripts/build-fluentd-values.py .generated/fluentd-pipeline.yaml
helm upgrade --install fluentd fluent/fluentd \
  -n observability --wait --timeout 10m \
  -f fluentd/values/00-common.yaml \
  -f fluentd/values/01-resources.yaml \
  -f fluentd/values/02-plugins.yaml \
  -f fluentd/values/03-healthcheck.yaml \
  -f .generated/fluentd-pipeline.yaml
```

## 5. Prometheus/Loki 추가 설정 파일 관리

모든 모듈에 설정 파일을 추가할 수 있지만, 도구마다 설정 방식이 다릅니다. Prometheus의 수집 대상과 알림 규칙은 별도 Kubernetes 리소스로 관리할 수 있고, Loki 서버 동작 설정은 주로 Helm values로 관리합니다. 따라서 Fluentd처럼 모든 설정을 `.conf`로 분리하지는 않습니다.

**Prometheus와 Loki에도 설정 파일을 추가할 수 있습니다.** 다만 Fluentd와 달리 일반 `.conf` 파일을 단순 연결하는 방식은 아닙니다.

- **Prometheus Stack**: Prometheus의 수집 대상은 `ServiceMonitor`, `PodMonitor`, `Probe`, `ScrapeConfig` 같은 Kubernetes CRD 리소스로 추가할 수 있습니다. 알림 규칙은 `PrometheusRule` 리소스를 사용합니다. Helm values에 `additionalScrapeConfigs`를 설정하는 방법도 있지만 차트 및 Operator 지원 형식에 맞춰야 합니다.
- **Loki**: Loki의 주요 설정은 `loki/values/*.yaml`에서 Helm 차트가 지원하는 `loki.*` 값으로 관리합니다. 별도 설정을 추가할 때는 해당 차트 버전의 values 스키마를 확인하고 `04-*.yaml`처럼 추가합니다.

Prometheus CRD를 별도 관리하려면 `prometheus/manifests/` 폴더를 추가해 다음처럼 적용할 수 있습니다. 이 예시는 **파일을 둘 위치와 적용 방법**을 보여주며, 실제 CRD 매니페스트는 수집 대상에 맞게 작성해야 합니다.

```bash
kubectl apply -n observability -f prometheus/manifests/
```

예를 들어 Loki limits를 바꾸려면 `loki/values/03-limits.yaml`을 수정하고 **Loki 모듈만** 다시 설치합니다.

```bash
bash scripts/install-module.sh loki
```

## 6. Grafana / Loki 확인

Grafana는 메트릭과 로그를 시각적으로 조회하는 화면이고, Loki Gateway는 로그 검색 API에 접근하는 진입점입니다. `kubectl port-forward`는 Kubernetes Service의 포트를 관리 서버로 전달하며, SSH 터널은 작업 PC에서 Bastion의 포워딩 포트에 안전하게 접근하도록 연결합니다.

Grafana 포트포워딩(Bastion):

```bash
kubectl port-forward -n observability svc/monitoring-grafana 3000:80
```

작업 PC가 Bastion으로 SSH 접속 가능한 경우, 별도 터미널에서 기존 SSH 접속 포트를 사용해 로컬 터널을 생성합니다.

```bash
ssh -p <SSH_PORT> -L 3000:127.0.0.1:3000 ubuntu@<BASTION_IP>
```

브라우저에서 `http://localhost:3000` 접속 후 **Explore → Loki**에서 아래 쿼리를 실행합니다.

```logql
{namespace="observability"}
```

Loki API를 직접 확인하려면 Bastion에서:

```bash
kubectl port-forward -n observability svc/loki-gateway 3100:80
```

다른 터미널에서:

```bash
curl -sG 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={namespace="observability"}' \
  --data-urlencode 'since=10m' \
  --data-urlencode 'limit=5'
```

## 7. 변경·업데이트 방법

설정 수정은 해당 모듈의 파일에서 수행하고, 동일한 설치 명령을 다시 실행해 변경사항을 반영합니다. Prometheus의 별도 CRD 매니페스트는 Helm values와 달리 `kubectl apply`로 적용해야 합니다. 변경 후에는 해당 릴리스와 Pod 상태를 확인합니다.

| 변경 목적 | 수정 위치 | 재배포 |
|---|---|---|
| Grafana 데이터 소스 | `prometheus/values/02-grafana.yaml` | `bash scripts/install-module.sh prometheus` |
| Prometheus 수집 대상 | `prometheus/manifests/` (추가 시) | `kubectl apply -f` |
| Loki 버킷/스토리지 | `loki/values/01-storage.yaml`, `99-private.yaml` | `bash scripts/install-module.sh loki` |
| Loki 캐시/제한 | `loki/values/02-cache.yaml`, `03-limits.yaml` | `bash scripts/install-module.sh loki` |
| Fluentd 리소스/프로브 | `fluentd/values/` | `bash scripts/install-module.sh fluentd` |
| Fluentd 수집/필터/전송 | `fluentd/config/*.conf` | `bash scripts/install-module.sh fluentd` |

Fluentd의 `read_from_head false`는 기존 로그를 소급 수집하지 않습니다. 메모리 버퍼는 재시작 시 미전송 로그가 유실될 수 있습니다. Loki SingleBinary는 단일 인스턴스 구성입니다.

## 8. GitHub 업로드

GitHub에서는 각 폴더의 README가 자동으로 표시되므로 필요한 모듈만 찾아 사용하기 쉽습니다. 공개 가능한 설정과 설명서는 버전 관리하되, 실제 인증정보와 내보낸 운영 설정은 제외합니다. 아래 명령은 기존 Git 저장소에 이 모듈 폴더를 추가한 경우에 사용합니다.

기존 Git 저장소 안에 이 폴더를 복사한 뒤:

```bash
git add k8s-observability-reusable/
git commit -m "feat: add reusable Kubernetes observability modules"
git push
```

`loki/values/99-private.yaml`과 `exports/`, `.generated/`는 `.gitignore`로 제외합니다. 인증정보를 커밋하지 마세요.
