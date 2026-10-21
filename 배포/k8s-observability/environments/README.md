# environments — 클라우드/클러스터별 설정

`cp environments/.env.example environments/.env` 실행 후 `.env`에 아래 값을 입력합니다. `.env`는 Git 추적에서 제외됩니다.

| 키 | 입력 방법 | 예시 형식 |
|---|---|---|
| `S3_ENDPOINT` | 사용 중인 Object Storage의 **S3 API 엔드포인트** | `https://s3.example.internal` |
| `S3_REGION` | 해당 서비스가 요구하는 S3 region 식별자 | `region-1` |
| `S3_BUCKET` | 미리 생성한 로그 저장 버킷명 | `my-loki-bucket` |
| `LOKI_STORAGE_CLASS` | `kubectl get storageclass`로 확인한 PVC용 StorageClass 이름 | `my-storageclass` |

값은 예시일 뿐이며 클라우드마다 달라집니다. 특히 Swift API와 S3 API 엔드포인트가 다를 수 있으므로 공급자 문서에서 확인하세요. `S3_REGION`은 서비스가 요구하는 실제 문자열을 사용하세요. 버킷은 이 배포가 자동 생성하지 않습니다.

```bash
source scripts/load-env.sh
kubectl get storageclass
```

S3 인증키는 `.env`에 쓰지 않고 `loki-s3-credentials` Secret의 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`로 전달합니다. `observability` 네임스페이스에 생성해야 합니다.
