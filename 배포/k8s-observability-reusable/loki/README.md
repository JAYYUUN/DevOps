# Loki 재사용 모듈

`grafana/loki` Helm 차트를 이용해 로그 저장·조회용 Loki를 독립 설치하는 모듈입니다. 현재 설정은 **SingleBinary 1개**, **TSDB v13**, **NHN Cloud S3 호환 Object Storage**를 사용합니다.

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

## 3. 설치 및 업데이트

`loki` Helm 릴리스는 로그 저장 서버와 Gateway 등 차트가 생성하는 리소스를 관리합니다. values를 순서대로 병합하되, 마지막에 비밀 설정을 전달해 Object Storage 접속 정보를 적용합니다. 같은 명령을 다시 실행하면 Loki 릴리스만 업데이트됩니다.

```bash
bash scripts/install-module.sh loki
```

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
| SingleBinary/영구 볼륨 | `values/00-common.yaml` |
| 캐시 | `values/02-cache.yaml` |
| Limits | `values/03-limits.yaml` |

차트 버전 고정은 루트의 `config/versions.env`에서 `LOKI_CHART_VERSION`을 사용합니다.
