# Loki Wrapper Chart

Kubernetes 로그를 저장하고 Grafana에서 조회하기 위한 재사용 가능한 Helm 모듈입니다. 공식 `loki` Chart를 의존성으로 사용하며, 현재 설정은 **SingleBinary 1개 Replica + S3 호환 Object Storage** 구성입니다.

## 구성 및 설정

```text
charts/loki/
├── Chart.yaml                       # loki 6.55.0 의존성
├── values.yaml                      # 기본 설정(자동 적용)
└── values/
    ├── 00-common.yaml              # 배포 모드 및 공통 설정
    ├── 01-storage.yaml             # Object Storage / PVC 관련 설정
    ├── 02-cache.yaml               # 캐시 설정
    ├── 03-limits.yaml              # Loki 제한 설정
    └── 99-private.yaml.example     # Object Storage 인증정보 예시
```

현재 기본값은 `deploymentMode: SingleBinary`, `singleBinary.replicas: 1`, `read/write/backend.replicas: 0`, `minio.enabled: false`, `chunksCache/resultsCache.enabled: false`입니다. TSDB schema v13 및 S3 저장소를 사용하며 버킷명은 `loki-test`로 설정되어 있습니다. PVC는 `10Gi`이고 **`storageClass`는 현재 빈 문자열(`''`)**입니다. 사용할 StorageClass가 있다면 클러스터에 맞게 지정해야 합니다.

`values.yaml`은 자동 적용됩니다. `values/*.yaml`은 자동 병합되지 않으므로 해당 파일만 수정할 경우 기본 설정에 반영되지 않습니다. 변경 사항을 `values.yaml`에 반영하거나 `-f`로 지정하세요.

## 배포 전 준비

Object Storage 인증정보 파일을 준비합니다.

```bash
cp ./charts/loki/values/99-private.yaml.example ./charts/loki/values/99-private.yaml
chmod 600 ./charts/loki/values/99-private.yaml
```

`99-private.yaml`에 실제 endpoint, region, accessKeyId, secretAccessKey를 입력합니다. 이 파일은 **Git에 커밋하지 마세요.** 또한 클러스터에서 사용할 StorageClass와 `loki-test` 버킷의 존재 및 접근 권한을 확인하세요.

## 배포 방법

프로젝트 최상위 디렉터리에서 실행합니다.

```bash
helm dependency build ./charts/loki
helm lint ./charts/loki -f ./charts/loki/values/99-private.yaml
helm template loki ./charts/loki -n observability \
  -f ./charts/loki/values/99-private.yaml > /tmp/loki-rendered.yaml
helm upgrade --install loki ./charts/loki -n observability --create-namespace \
  -f ./charts/loki/values/99-private.yaml --wait --timeout 10m
```

`/tmp/loki-rendered.yaml`에는 인증정보가 포함될 수 있으므로 공유하지 말고 안전하게 삭제하세요.

## 배포 확인

```bash
helm list -n observability
kubectl get pods -n observability
kubectl get pvc -n observability
kubectl get svc -n observability
```

PVC가 `Pending`이라면 StorageClass, 프로비저너 및 용량을 확인하세요. Fluentd가 사용하는 Loki 주소는 `http://loki-gateway.observability.svc.cluster.local`이므로 Gateway Service가 실제로 생성되는지도 확인해야 합니다.
