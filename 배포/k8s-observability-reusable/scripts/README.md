# 설치 및 운영 스크립트 가이드

이 디렉터리에는 **Helm 차트별 독립 설치·업데이트**와 설정 변환, 상태 조회, 현재 Helm 설정 추출을 위한 스크립트가 있습니다. 명령어는 저장소 최상위 디렉터리에서 실행합니다.

## 1. 스크립트 구성

스크립트는 각 Helm 차트의 반복 설치 명령을 간단하게 실행하도록 만든 보조 도구입니다. 실제 설정은 모듈의 values와 `.conf`에 보관하고, 스크립트는 파일을 모아 Helm에 전달하는 역할만 담당합니다.

| 파일 | 역할 | 실행 예시 |
|---|---|---|
| `install-module.sh` | 지정한 Helm 모듈만 설치·업데이트 | `bash scripts/install-module.sh loki` |
| `build-fluentd-values.py` | `.conf`를 Helm `fileConfigs` YAML로 결합 | `python3 scripts/build-fluentd-values.py .generated/fluentd-pipeline.yaml` |
| `verify.sh` | 전체 Namespace의 Helm 릴리스, Pod, Fluentd DaemonSet 확인 | `bash scripts/verify.sh` |
| `export-live.sh` | 설치된 세 릴리스의 사용자 지정 values와 릴리스 목록 추출 | `bash scripts/export-live.sh` |

## 2. 사전 준비

설치 스크립트는 현재 kubeconfig가 가리키는 클러스터에 리소스를 생성합니다. 따라서 실행 전에 Kubernetes 연결 대상과 Helm 설치 여부를 확인해야 합니다. Fluentd 모듈은 Python으로 설정을 결합하므로 Python 3도 필요합니다.

```bash
kubectl config current-context
kubectl get nodes
helm version
python3 --version
```

`install-module.sh`는 대상 차트의 Helm 저장소를 등록·갱신하고 `observability` Namespace를 생성합니다. Loki 설치에는 `loki/values/99-private.yaml`이 필요합니다.

차트 버전을 고정하려면:

```bash
cp config/versions.env.example config/versions.env
vi config/versions.env
```

해당 파일의 `PROMETHEUS_CHART_VERSION`, `LOKI_CHART_VERSION`, `FLUENTD_CHART_VERSION`을 설정합니다. 비워두면 Helm 저장소에서 선택되는 버전을 사용합니다.

## 3. 모듈별 실행

`install-module.sh`는 인자로 전달한 모듈 하나만 선택해 설치 또는 업데이트합니다. 내부적으로 Helm 저장소 등록, Namespace 생성, values 파일 수집, `helm upgrade --install` 순서로 처리합니다. 세 모듈을 자동으로 모두 설치하는 스크립트는 아닙니다.

```bash
# Prometheus Stack만 설치 또는 업데이트
bash scripts/install-module.sh prometheus

# Loki만 설치 또는 업데이트
bash scripts/install-module.sh loki

# Fluentd만 설치 또는 업데이트
bash scripts/install-module.sh fluentd
```

각 모듈의 `values/[0-9][0-9]-*.yaml`을 **파일명 순서대로 `-f` 옵션에 추가**합니다. 뒤에 지정한 파일이 동일 키를 덮어씁니다. Loki는 `99-private.yaml`을 마지막에 추가하고, Fluentd는 생성된 `.generated/fluentd-pipeline.yaml`을 마지막에 추가합니다.

## 4. Fluentd 설정 결합만 실행

Fluentd Helm 차트는 `fileConfigs` 키 아래에 설정 파일 내용을 받아야 합니다. 이 스크립트는 `config/*.conf`를 읽어 임시 values YAML을 생성하며, 실제 Kubernetes 배포는 수행하지 않습니다. 결과 파일을 확인한 후 직접 Helm 명령에 `-f`로 추가할 수도 있습니다.

```bash
python3 scripts/build-fluentd-values.py .generated/fluentd-pipeline.yaml
cat .generated/fluentd-pipeline.yaml
```

이 스크립트는 Python 표준 라이브러리만 사용합니다. `.conf` 파일을 Helm의 `fileConfigs` 블록 문자열로 만들어 주며, Kubernetes에 직접 적용하지는 않습니다.

## 5. 상태 확인

설치 후에는 Helm 릴리스와 Kubernetes Pod가 정상적으로 생성되었는지 확인합니다. 제공된 `verify.sh`는 Fluentd DaemonSet까지 확인하므로 세 모듈이 모두 있는 환경을 전제로 합니다. 특정 모듈만 설치했다면 해당 릴리스의 `helm status`를 직접 조회하면 됩니다.

```bash
bash scripts/verify.sh
```

현재 `verify.sh`는 **세 모듈이 함께 설치된 경우**를 기준으로 Fluentd DaemonSet의 rollout 상태도 조회합니다. Prometheus 또는 Loki만 설치한 경우에는 해당 모듈에 맞춰 다음 명령어를 직접 사용하세요.

```bash
helm status monitoring -n observability
helm status loki -n observability
helm status fluentd -n observability
kubectl get pods -n observability -o wide
```

## 6. 현재 설치 설정 내보내기

`helm get values`는 현재 릴리스에 적용된 사용자 지정 Helm 값을 추출하는 명령입니다. 백업하거나 다른 클러스터에 설정을 재사용할 때 유용하며, 기본값 전체가 아니라 사용자가 지정한 override를 가져옵니다. 내보낸 결과에는 인증정보가 포함될 수 있으므로 저장 위치와 접근 권한을 관리해야 합니다.

```bash
bash scripts/export-live.sh
```

`exports/YYYYMMDD-HHMMSS/`에 `monitoring.values.yaml`, `loki.values.yaml`, `fluentd.values.yaml`, `releases.json`을 생성합니다. 이 스크립트는 **세 릴리스가 모두 존재할 때** 실행하는 용도이며, 개별 모듈만 설치한 경우에는 다음처럼 내보낼 수 있습니다.

```bash
helm get values loki -n observability -o yaml > loki-live-values.yaml
```

내보낸 파일에는 인증정보가 포함될 수 있으므로 Git에 업로드하지 마세요.

## 7. 운영 참고

이 스크립트는 모듈별 재사용을 위해 기본 Namespace와 차트 저장소 경로를 정해 둔 형태입니다. 다른 클러스터 환경에 맞춰 사용할 때는 Namespace, Loki 서비스 주소, 이미지 접근 경로 등을 함께 고려해야 합니다.

- 기본 Namespace는 `observability`이며, 스크립트는 다른 Namespace로 변경하는 것을 제한합니다. 변경하려면 Loki Gateway URL 등 설정도 함께 변경해야 합니다.
- 설치 스크립트는 Helm 저장소에 접근합니다. 폐쇄망에서는 차트와 이미지, Fluentd 플러그인 배포 경로를 별도로 준비해야 합니다.
- 설치 스크립트는 전체 스택을 일괄 배포하지 않습니다. 각 모듈은 독립 실행합니다.
