# scripts — 운영 보조 스크립트

- `source scripts/load-env.sh`: `.env`에서 S3·StorageClass 값 로드 및 필수값 검증. **source로 실행**해야 현재 셸에 환경변수가 유지됩니다.
- `./scripts/check.sh`: Pod/PVC/Service/Helm 릴리스 상태 출력.
- `./scripts/export-live-values.sh`: 현재 클러스터의 Helm 오버라이드를 `*-live-values.yaml`로 저장. 이 파일은 Git에서 제외됩니다. 비밀정보 포함 가능성을 확인하세요.

배포는 루트에서 `helmfile repos`, `helmfile template`, `helmfile sync`를 실행합니다. 스크립트 자체는 클러스터에 리소스를 설치하지 않습니다.
