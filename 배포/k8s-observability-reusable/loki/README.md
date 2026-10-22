# Loki 재사용 모듈

`grafana/loki` Helm 차트를 이용해 로그 저장·조회용 Loki를 독립 설치하는 모듈입니다. 현재 설정은 **SingleBinary 1개**, **TSDB v13**, **NHN Cloud S3 호환 Object Storage**를 사용합니다. 로그 청크와 인덱스는 S3에 저장하고, **WAL 및 로컬 작업 데이터는 PVC**에 보관합니다.

> 명령어는 저장소 최상위 디렉터리에서 실행합니다. 기본 Namespace는 `observability`, Helm 릴리스는 `loki`입니다.

## 1. 파일 구성

Loki는 로그 저장·검색을 담당하며, Fluentd 같은 수집기가 보낸 로그를 받아 처리합니다. 서버 동작, 스토리지, 캐시, 제한 설정을 별도 values로 나누어 운영 목적에 따라 필요한 부분만 수정하도록 구성했습니다.

| 파일 | 역할 |
|---|---|
| `values/00-common.yaml` | SingleBinary, 복제 수, TSDB 스키마, 영구 볼륨 |
| `values/01-storage.yaml` | S3 스토리지 타입과 버킷 이름 |
| `values/02-cache.yaml` | chunks/results 캐시 활성화 여부 |
| `values/03-limits.yaml` | Loki limits 설정 |
| `values/99-private.yaml.example` | S3 엔드포인트·리전·Access/Secret Key 입력 예시 |
| `values/99-private.yaml` | 실제 인증정보(사용자가 생성, Git 제외) |

## 2. 설치 준비

Loki가 Object Storage에 로그를 저장하려면 S3 호환 엔드포인트와 접근 권한이 필요합니다. Helm 저장소와 Namespace를 준비한 다음, NHN Cloud에서 발급한 인증정보와 사용할 버킷을 설정합니다. 인증키는 Git에 올리지 않도록 예시 파일을 복사해 별도로 보관합니다.

```bash
kubectl config current-context
kubectl get nodes
helm version
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update grafana
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
```

NHN Cloud 콘솔에서 S3 호환 Object Storage의 **엔드포인트, 리전, Access Key, Secret Key**를 확인하고 로그를 저장할 버킷을 준비합니다. 버킷이 `loki-test`가 아니라면 `values/01-storage.yaml`의 `chunks`, `ruler`, `admin` 값을 변경합니다.

```bash
cp loki/values/99-private.yaml.example loki/values/99-private.yaml
chmod 600 loki/values/99-private.yaml
vi loki/values/99-private.yaml
```

입력 예시(실제 값으로 교체):

```yaml
loki:
  storage:
    s3:
      endpoint: https://YOUR_OBJECT_STORAGE_ENDPOINT
      region: YOUR_REGION
      accessKeyId: YOUR_ACCESS_KEY
      secretAccessKey: YOUR_SECRET_KEY
```

`99-private.yaml`은 `.gitignore`로 제외되어 있으며 Git에 올리지 않습니다.

### 2.1 Loki 로컬 PVC와 StorageClass 준비

S3는 Loki의 로그 청크와 인덱스를 보관하지만, Loki 프로세스는 쓰기 안정성을 위한 WAL(Write-Ahead Log)과 로컬 작업 공간도 사용합니다. 따라서 이 모듈은 테스트 중 재시작으로 인한 데이터 손실 위험을 줄이기 위해 `singleBinary.persistence.enabled: true`를 유지하며 **10Gi PVC**를 요청합니다. PVC는 S3 저장소를 대체하는 것이 아니라 별도의 로컬 저장 공간입니다.

이 모듈은 여러 Kubernetes 클러스터에서 재사용하도록 `values/00-common.yaml`의 `singleBinary.persistence.storageClass`를 **빈 문자열(`""`)**로 제공합니다. 빈 문자열은 StorageClass를 자동 생성하는 설정이 아니며, 기본 StorageClass가 있는 클러스터에서는 그 기본값을 사용하게 됩니다. **기본 StorageClass가 없는 환경에서는 설치 전에 실제 StorageClass 이름을 입력해야 합니다.**

`singleBinary.initContainers`에는 Loki가 PVC에 쓸 수 있도록 소유권을 설정하는 초기화 컨테이너가 이미 포함되어 있습니다. 이 설정은 수정할 필요가 없으며, 환경에 맞는 StorageClass와 S3 인증정보만 입력하면 됩니다.

먼저 설치 대상 클러스터에서 사용 가능한 StorageClass와 PV를 확인합니다.

```bash
kubectl get storageclass
kubectl get pv -o wide
```

출력에서 `(default)` 표시가 없는 경우 기본 StorageClass가 없는 것입니다. `values/00-common.yaml` 파일의 아래 항목에 **해당 클러스터에서 확인한 이름**을 입력합니다. 다음의 `YOUR_STORAGE_CLASS_NAME`은 설명용 자리표시자이며 실제 이름으로 바꿔야 합니다.

```yaml
singleBinary:
  replicas: 1
  persistence:
    enabled: true
    storageClass: "YOUR_STORAGE_CLASS_NAME"
    size: 10Gi
```

예를 들어 현재 테스트 클러스터에서는 `kubectl get storageclass` 결과가 `block-static-v2-sc`였으므로 **그 클러스터에서만** `storageClass: "block-static-v2-sc"`로 입력할 수 있습니다. 다른 클러스터에서는 그 환경에 존재하는 StorageClass 이름을 사용해야 합니다. 기본 StorageClass가 이미 있고 이를 사용할 계획이라면 빈 문자열을 유지할 수 있습니다.

**주의:** StorageClass를 지정해도 PVC가 반드시 `Bound`가 되는 것은 아닙니다. 정적 프로비저닝 방식이면 호환되는 PV가 사전에 있어야 할 수 있으며, 동적 프로비저닝 방식이어도 클라우드 볼륨 생성 권한·용량 등의 문제가 있을 수 있습니다. `Retain` 정책만으로 정적 프로비저닝 여부를 단정할 수는 없습니다.

설치 후 PVC 상태와 이벤트를 확인합니다.

```bash
kubectl get pvc -n observability
kubectl describe pvc storage-loki-0 -n observability
kubectl describe pod loki-0 -n observability
```

PVC가 `Pending`이라면 이벤트 메시지를 기준으로 StorageClass, PV 용량(10Gi 이상), 접근 모드, 프로비저너 동작을 점검합니다. 기존 PV가 `Released` 상태이고 `Retain` 정책이라면 이전 데이터와 `claimRef`를 검토하지 않은 채 재사용하면 안 됩니다. `persistence.enabled: false`로 변경하면 PVC가 없어지지만 WAL의 내구성이 약해지므로 이 모듈의 기본값으로 사용하지 않습니다.

## 3. 설치 및 업데이트

`loki` Helm 릴리스는 로그 저장 서버와 Gateway 등 차트가 생성하는 리소스를 관리합니다. values를 순서대로 병합하되, 마지막에 비밀 설정을 전달해 Object Storage 접속 정보를 적용합니다. 같은 명령을 다시 실행하면 Loki 릴리스만 업데이트됩니다.

```bash
bash scripts/install-module.sh loki
```

설치가 `pending-install`에 머물면 `storage-loki-0` PVC의 `Bound` 여부를 우선 확인합니다. Helm이 아직 실행 중이면 종료 또는 타임아웃을 기다리고, 실패한 설치를 재시도할 때는 PVC/PV 상태를 먼저 점검합니다. `helm uninstall`과 PVC 삭제는 데이터 손실 위험이 있으므로 원인을 확인한 뒤 수행합니다.

Helm 직접 실행:

```bash
helm upgrade --install loki grafana/loki \
  -n observability --wait --timeout 10m \
  -f loki/values/00-common.yaml \
  -f loki/values/01-storage.yaml \
  -f loki/values/02-cache.yaml \
  -f loki/values/03-limits.yaml \
  -f loki/values/99-private.yaml
```

## 4. 상태 및 API 확인

Pod 상태는 서버가 실행 중인지 보여주고, Loki API 조회는 로그 검색 기능에 접근할 수 있는지 확인합니다. `query_range`는 지정한 기간의 로그를 검색하는 API이며, `{namespace="observability"}`는 해당 Namespace 라벨을 가진 로그를 찾는 LogQL 표현식입니다.

```bash
helm status loki -n observability
kubectl get pods -n observability
kubectl get svc -n observability | grep loki
kubectl port-forward -n observability svc/loki-gateway 3100:80
```

다른 터미널에서 Loki API에 질의합니다.

```bash
curl -sG 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={namespace="observability"}' \
  --data-urlencode 'since=10m' \
  --data-urlencode 'limit=5'
```

로그를 보내는 Fluentd가 설치되어 있고 해당 Namespace에 로그가 발생한 경우 결과를 조회할 수 있습니다. Grafana에서는 Explore에서 Loki 데이터 소스를 선택해 동일한 LogQL을 사용할 수 있습니다.

## 5. 설정 확장

Loki의 설정은 Fluentd `.conf`와 달리 Helm values의 YAML 항목으로 전달합니다. 보존 기간이나 수집 제한 같은 옵션은 해당 차트가 지원하는 키를 확인한 뒤 새 values 파일로 분리할 수 있습니다. 추가한 파일은 숫자 순서에 따라 기존 설정과 병합됩니다.

Loki는 Fluentd의 `.conf` 대신 **Helm values의 `loki.*` 설정**을 사용합니다. 필요하면 `values/04-retention.yaml`처럼 새 YAML을 추가할 수 있으며 `install-module.sh`가 번호 순으로 읽습니다. 보존 기간, limits, 스토리지 변경은 사용하는 Loki 차트 버전의 values 구조에 맞춰 작성합니다.

| 변경 사항 | 수정 파일 |
|---|---|
| 버킷 이름 | `values/01-storage.yaml` |
| S3 인증정보 | `values/99-private.yaml` |
| SingleBinary/PVC 크기·StorageClass | `values/00-common.yaml` |
| 캐시 | `values/02-cache.yaml` |
| Limits | `values/03-limits.yaml` |

차트 버전 고정은 루트의 `config/versions.env`에서 `LOKI_CHART_VERSION`을 사용합니다.
