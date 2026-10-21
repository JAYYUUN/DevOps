# Environments — 환경별 입력값

클라우드에 따라 달라지는 값만 입력합니다.

```bash
cp environments/.env.example environments/.env
```

`environments/.env`:

| 변수 | 입력할 값 | 확인 위치 |
|---|---|---|
| `S3_ENDPOINT` | S3 호환 Object Storage API URL | 클라우드 Object Storage 안내 |
| `S3_REGION` | S3 리전 식별자 | 클라우드 리전 정보 |
| `S3_BUCKET` | 생성된 로그 저장 버킷명 | Object Storage 버킷 목록 |
| `LOKI_STORAGE_CLASS` | PVC에 사용할 StorageClass 이름 | `kubectl get storageclass` |

입력 예시 형식:

```dotenv
S3_ENDPOINT=https://s3.example.com
S3_REGION=example-region
S3_BUCKET=example-loki-bucket
LOKI_STORAGE_CLASS=example-storage-class
```

위 값은 **형식 예시**이며 실제 값으로 바꿔야 합니다. 버킷은 미리 생성합니다.

## S3 인증키

접근키는 `.env`에 넣지 않고 Kubernetes Secret으로 전달합니다.

```bash
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic loki-s3-credentials -n observability \
  --from-literal=AWS_ACCESS_KEY_ID='ACCESS_KEY' \
  --from-literal=AWS_SECRET_ACCESS_KEY='SECRET_KEY'
```

이미 Secret이 있으면 생성 명령은 생략합니다. `.env`는 `.gitignore`에 포함되어 있습니다.

설정 적용 전 프로젝트 루트에서 `source scripts/load-env.sh`를 실행합니다.
